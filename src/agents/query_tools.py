"""
Phase 4 – Query Tools.
Three LangGraph-compatible tool functions:
  1. pageindex_navigate(topic)   → top SectionNodes by keyword score
  2. semantic_search(query, top_k) → ranked SearchResults with provenance
  3. structured_query(sql)       → rows from SQLite fact table
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.storage.fact_table import FactTableExtractor
from src.agents.vector_store import VectorStore
from src.models.chunk import SectionNode
from src.models.query import ProvenanceChain, SearchResult

logger = logging.getLogger(__name__)

DEFAULT_INDEX_DIR = Path(".refinery/pageindex")
DEFAULT_DB = Path(".refinery/facts.db")


# ---------------------------------------------------------------------------
# Tool 1 – Page Index Navigation
# ---------------------------------------------------------------------------

def pageindex_navigate(
    topic: str,
    index_dir: Optional[str | Path] = None,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Keyword-based navigation over saved PageIndex JSON files.
    Returns the top-k matching SectionNodes (with doc context) sorted by relevance score.

    Args:
        topic:     Natural-language topic to search for.
        index_dir: Directory containing PageIndex JSON files.
        top_k:     Number of top sections to return.

    Returns:
        List of dicts: {doc_id, section_title, page_start, page_end, score, summary, provenance}
    """
    if index_dir is None:
        index_dir = DEFAULT_INDEX_DIR
    index_dir = Path(index_dir)
    if not index_dir.exists():
        logger.warning(f"PageIndex directory not found: {index_dir}")
        return []

    topic_lower = topic.lower()
    topic_tokens = set(topic_lower.split())
    candidates: List[Dict[str, Any]] = []

    for json_file in index_dir.glob("*.json"):
        doc_id = json_file.stem
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                tree_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load index {json_file}: {e}")
            continue

        root_nodes = tree_data.get("root_nodes", [])
        _score_nodes_recursive(root_nodes, doc_id, topic_lower, topic_tokens, candidates)

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_k]


def _score_node(node: Dict[str, Any], doc_id: str, topic_lower: str, topic_tokens: set) -> float:
    score = 0.0
    title = (node.get("title") or "").lower()
    summary = (node.get("summary") or "").lower()
    entities = " ".join(node.get("key_entities", [])).lower()

    if topic_lower in title:
        score += 10.0
    else:
        title_tokens = set(title.split())
        score += len(title_tokens & topic_tokens) * 3.0

    if topic_lower in summary:
        score += 5.0
    else:
        summary_tokens = set(summary.split())
        score += len(summary_tokens & topic_tokens) * 1.5

    score += len(set(entities.split()) & topic_tokens) * 2.0
    return round(score, 2)


def _score_nodes_recursive(nodes, doc_id, topic_lower, topic_tokens, candidates):
    for node in nodes:
        score = _score_node(node, doc_id, topic_lower, topic_tokens)
        if score > 0:
            candidates.append({
                "doc_id": doc_id,
                "section_title": node.get("title", ""),
                "page_start": node.get("page_start", 0),
                "page_end": node.get("page_end", 0),
                "score": score,
                "summary": node.get("summary"),
                "data_types_present": node.get("data_types_present", []),
                "provenance": ProvenanceChain(
                    doc_id=doc_id,
                    document_name=doc_id.replace("_", " "),
                    page_numbers=list(range(node.get("page_start", 1), node.get("page_end", 1) + 1)),
                    bbox={},
                    content_hash="",
                    strategy_used="pageindex_navigate",
                ).model_dump(),
            })
        # Recurse into children
        _score_nodes_recursive(node.get("child_sections", []), doc_id, topic_lower, topic_tokens, candidates)


# ---------------------------------------------------------------------------
# Tool 2 – Semantic Search
# ---------------------------------------------------------------------------

def semantic_search(
    query: str,
    top_k: int = 5,
    doc_id_filter: Optional[str] = None,
    vector_store: Optional[VectorStore] = None,
) -> List[Dict[str, Any]]:
    """
    Dense vector search over the FAISS index.
    Returns ranked SearchResult dicts with full ProvenanceChain.

    Args:
        query:        Natural-language query string.
        top_k:        Number of results to return.
        doc_id_filter: If provided, restrict results to this document.
        vector_store: Pre-loaded VectorStore; defaults to loading from disk.
    """
    if vector_store is None:
        vector_store = VectorStore()

    results: List[SearchResult] = vector_store.search(query, top_k=top_k, doc_id_filter=doc_id_filter)

    return [
        {
            "content": r.content,
            "chunk_type": r.chunk_type,
            "page_refs": r.page_refs,
            "score": r.score,
            "parent_section_title": r.parent_section_title,
            "provenance": r.provenance.model_dump(),
        }
        for r in results
    ]


# ---------------------------------------------------------------------------
# Tool 3 – Structured Query
# ---------------------------------------------------------------------------

def structured_query(
    sql: str,
    db_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    """
    Execute a SQL SELECT against the SQLite FactTable database.
    Returns list of row dicts.

    Args:
        sql:     A SELECT query against the 'facts' table.
        db_path: Path to the SQLite database file.

    Example SQL:
        SELECT fact_key, fact_value FROM facts
        WHERE document_id = 'CBE ANNUAL REPORT 2023-24'
        AND fact_key LIKE '%Revenue%'
    """
    if db_path is None:
        db_path = DEFAULT_DB
    extractor = FactTableExtractor(db_path=db_path)
    results = extractor.query_facts(sql)
    logger.info(f"structured_query returned {len(results)} rows for SQL: {sql[:80]}...")
    return results
