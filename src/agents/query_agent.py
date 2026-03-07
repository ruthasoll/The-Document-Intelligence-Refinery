"""
Phase 4 – Query Agent (LangGraph StateGraph).

Architecture:
  START → router → [run_navigate | run_search | run_structured | run_multi] → synthesize → END

The router is a deterministic keyword classifier (no LLM required for routing),
making the agent fast, fully testable, and cost-free.

The synthesize node assembles a QueryResponse with ProvenanceChain citations.
audit_claim() reuses the agent graph to verify factual claims.
"""
import logging
import re
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.query_tools import (
    pageindex_navigate,
    semantic_search,
    structured_query,
)
from src.agents.vector_store import VectorStore
from src.models.query import AuditResult, ProvenanceChain, QueryResponse
from src.provenance import format_provenance_list, build_provenance_from_ldu, build_provenance_from_fact

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent State
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    """Shared mutable state flowing through the LangGraph nodes."""
    question: str
    route: str                        # "navigate" | "search" | "structured" | "multi"
    navigate_results: List[Dict[str, Any]]
    search_results: List[Dict[str, Any]]
    structured_results: List[Dict[str, Any]]
    final_response: Optional[QueryResponse]
    doc_id_filter: Optional[str]
    top_k: int


# ---------------------------------------------------------------------------
# Router – pure keyword classification, no LLM needed
# ---------------------------------------------------------------------------

SQL_TOKENS = re.compile(
    r"\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|LIKE|COUNT|SUM|AVG|MAX|MIN|IN|JOIN|HAVING)\b",
    re.I,
)
NAVIGATE_TOKENS = re.compile(
    r"\b(sections?|chapters?|overviews?|about|structures?|topics?|table of contents|index|outlines?)\b",
    re.I,
)
STRUCTURED_TOKENS = re.compile(
    r"\b(facts?|values?|figures?|numbers?|amounts?|totals?|revenues?|profits?|expenditures?|how much|what is the value)\b",
    re.I,
)


def _classify_query(question: str) -> str:
    if SQL_TOKENS.search(question):
        return "structured"
    nav_score = len(NAVIGATE_TOKENS.findall(question))
    struct_score = len(STRUCTURED_TOKENS.findall(question))
    if nav_score > 0 and struct_score > 0:
        return "multi"
    if nav_score > struct_score:
        return "navigate"
    if struct_score > nav_score:
        return "structured"
    return "search"   # default: dense vector search


# ---------------------------------------------------------------------------
# Node: router
# ---------------------------------------------------------------------------

def router_node(state: AgentState) -> AgentState:
    route = _classify_query(state["question"])
    logger.info(f"[router] question='{state['question'][:60]}' → route='{route}'")
    state["route"] = route
    return state


# ---------------------------------------------------------------------------
# Nodes: tool execution
# ---------------------------------------------------------------------------

def run_navigate_node(state: AgentState) -> AgentState:
    results = pageindex_navigate(state["question"], top_k=state.get("top_k", 3))
    state["navigate_results"] = results
    return state


def run_search_node(state: AgentState) -> AgentState:
    vs = VectorStore()
    results = semantic_search(
        state["question"],
        top_k=state.get("top_k", 5),
        doc_id_filter=state.get("doc_id_filter"),
        vector_store=vs,
    )
    state["search_results"] = results
    return state


def run_structured_node(state: AgentState) -> AgentState:
    # Build a safe SQL query from the question (keyword-based heuristic)
    sql = _build_sql(state["question"], state.get("doc_id_filter"))
    results = structured_query(sql)
    state["structured_results"] = results
    return state


def run_multi_node(state: AgentState) -> AgentState:
    """Run both navigate and search in sequence (LangGraph is sequential by default)."""
    state = run_navigate_node(state)
    state = run_search_node(state)
    return state


# ---------------------------------------------------------------------------
# Node: synthesizer – builds QueryResponse with ProvenanceChain
# ---------------------------------------------------------------------------

def synthesize_node(state: AgentState) -> AgentState:
    route = state.get("route", "search")
    question = state["question"]
    provenance: List[ProvenanceChain] = []
    raw: List[Dict[str, Any]] = []
    answer_parts: List[str] = []

    if route in ("navigate", "multi"):
        nav = state.get("navigate_results", [])
        raw.extend(nav)
        for r in nav:
            answer_parts.append(
                f"Section '{r['section_title']}' (pp. {r['page_start']}–{r['page_end']}, "
                f"{r['doc_id']}): {r.get('summary', '')}"
            )
            p = r.get("provenance")
            if p:
                provenance.append(ProvenanceChain(**p))

    if route in ("search", "multi"):
        search = state.get("search_results", [])
        raw.extend(search)
        for r in search:
            snippet = r["content"][:200].replace("\n", " ")
            answer_parts.append(
                f"[{r['chunk_type'].upper()}, score={r['score']:.2f}] "
                f"p.{r['page_refs']}: \"{snippet}...\""
            )
            p = r.get("provenance")
            if p:
                provenance.append(ProvenanceChain(**p))

    if route == "structured":
        struct = state.get("structured_results", [])
        raw.extend(struct)
        if struct and "error" not in struct[0]:
            for row in struct[:5]:
                key = row.get("fact_key", "")
                val = row.get("fact_value", "")
                page = row.get("page_number", "?")
                doc = row.get("document_id", "")
                answer_parts.append(f"• {key}: {val} (p.{page}, {doc})")
                provenance.append(ProvenanceChain(
                    doc_id=doc,
                    document_name=doc.replace("_", " "),
                    page_numbers=[page] if isinstance(page, int) else [],
                    bbox={},
                    content_hash=row.get("chunk_hash", ""),
                    strategy_used="structured_query",
                ))
        else:
            answer_parts.append("No matching facts found in the fact table.")

    if answer_parts:
        answer = f"Answer to: \"{question}\"\n\n" + "\n\n".join(answer_parts)
        # Add Citations block if provenance exists
        citations = format_provenance_list(provenance)
        if citations:
            answer += "\n" + citations
    else:
        answer = f"No results found for: \"{question}\""

    confidence = _estimate_confidence(route, state)

    state["final_response"] = QueryResponse(
        question=question,
        answer=answer,
        tool_used=route,
        provenance=provenance,
        raw_results=raw,
        confidence=confidence,
    )
    return state


# ---------------------------------------------------------------------------
# Routing edge – decides which tool node to call after router
# ---------------------------------------------------------------------------

def _route_edge(state: AgentState) -> str:
    return state.get("route", "search")


# ---------------------------------------------------------------------------
# Build LangGraph
# ---------------------------------------------------------------------------

def build_query_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("run_navigate", run_navigate_node)
    graph.add_node("run_search", run_search_node)
    graph.add_node("run_structured", run_structured_node)
    graph.add_node("run_multi", run_multi_node)
    graph.add_node("synthesize", synthesize_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        _route_edge,
        {
            "navigate": "run_navigate",
            "search": "run_search",
            "structured": "run_structured",
            "multi": "run_multi",
        },
    )
    graph.add_edge("run_navigate", "synthesize")
    graph.add_edge("run_search", "synthesize")
    graph.add_edge("run_structured", "synthesize")
    graph.add_edge("run_multi", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# High-level API
# ---------------------------------------------------------------------------

class QueryAgent:
    """
    High-level interface to the Phase 4 LangGraph Query Agent.
    Wraps the compiled graph with a simple query() method.
    """

    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self.graph = build_query_graph()

    def query(
        self,
        question: str,
        doc_id_filter: Optional[str] = None,
    ) -> QueryResponse:
        """
        Run the full agent pipeline for a natural-language question.
        Returns a QueryResponse with answer and ProvenanceChain citations.
        """
        initial_state: AgentState = {
            "question": question,
            "route": "",
            "navigate_results": [],
            "search_results": [],
            "structured_results": [],
            "final_response": None,
            "doc_id_filter": doc_id_filter,
            "top_k": self.top_k,
        }

        final_state = self.graph.invoke(initial_state)
        response = final_state.get("final_response")

        if response is None:
            response = QueryResponse(
                question=question,
                answer="Agent failed to produce a response.",
                tool_used="error",
                error="No final_response in state",
            )

        logger.info(
            f"[QueryAgent] tool={response.tool_used} | "
            f"provenance_count={len(response.provenance)} | "
            f"confidence={response.confidence:.2f}"
        )
        return response

    def audit_claim(
        self,
        claim: str,
        doc_id: Optional[str] = None,
    ) -> AuditResult:
        """
        Verify whether a factual claim is supported by the corpus.
        Uses semantic_search to find the most relevant chunks,
        then checks if any chunk content overlaps with the claim.

        Returns AuditResult with verified, sources, and reason.
        """
        CONFIDENCE_THRESHOLD = 0.55

        vs = VectorStore()
        results = semantic_search(claim, top_k=5, doc_id_filter=doc_id, vector_store=vs)

        if not results:
            return AuditResult(
                claim=claim,
                verified=False,
                sources=[],
                reason="No relevant documents found in the corpus for this claim.",
                confidence=0.0,
            )

        # Heuristic: claim is considered supported if top result has similarity > threshold
        # and shares meaningful keyword overlap with the claim
        top = results[0]
        top_score = top["score"]
        top_content = top["content"].lower()
        claim_tokens = set(re.findall(r"\b\w{4,}\b", claim.lower()))
        content_tokens = set(re.findall(r"\b\w{4,}\b", top_content))
        overlap = len(claim_tokens & content_tokens)
        overlap_ratio = overlap / max(len(claim_tokens), 1)

        supported = top_score >= CONFIDENCE_THRESHOLD and overlap_ratio >= 0.2
        confidence = round(min(top_score * (1 + overlap_ratio), 1.0), 3)

        sources = [
            ProvenanceChain(**r["provenance"])
            for r in results
            if r["score"] >= CONFIDENCE_THRESHOLD
        ]

        if supported:
            reason = (
                f"Claim is supported by {len(sources)} source(s). "
                f"Top match score={top_score:.2f}, keyword overlap={overlap_ratio:.0%}."
            )
        else:
            reason = (
                f"Claim could not be verified. "
                f"Top similarity={top_score:.2f} (threshold={CONFIDENCE_THRESHOLD}), "
                f"keyword overlap={overlap_ratio:.0%}."
            )

        return AuditResult(
            claim=claim,
            verified=supported,
            sources=sources,
            reason=reason,
            confidence=confidence,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_sql(question: str, doc_id: Optional[str]) -> str:
    """Generate a safe SQL query from natural language (keyword heuristic)."""
    doc_filter = f"AND document_id = '{doc_id}'" if doc_id else ""
    # Extract any key financial terms from the question to use as LIKE clause
    kw_match = re.search(
        r"\b(revenue|profit|loss|assets|liabilities|expenditure|income|tax|budget|"
        r"surplus|deficit|dividend|cash|net|total)\b",
        question,
        re.I,
    )
    if kw_match:
        kw = kw_match.group(1)
        return (
            f"SELECT fact_key, fact_value, page_number, document_id "
            f"FROM facts WHERE fact_key LIKE '%{kw}%' {doc_filter} "
            f"ORDER BY page_number LIMIT 10"
        )
    # Fallback: return most recent facts for the doc
    return (
        f"SELECT fact_key, fact_value, page_number, document_id "
        f"FROM facts {('WHERE document_id = ' + chr(39) + doc_id + chr(39)) if doc_id else ''} "
        f"ORDER BY id DESC LIMIT 10"
    )


def _estimate_confidence(route: str, state: AgentState) -> float:
    if route == "search":
        results = state.get("search_results", [])
        if results:
            return round(results[0].get("score", 0.5), 3)
    elif route == "structured":
        results = state.get("structured_results", [])
        return 0.95 if results and "error" not in results[0] else 0.1
    elif route == "navigate":
        results = state.get("navigate_results", [])
        return 0.8 if results else 0.1
    return 0.5
