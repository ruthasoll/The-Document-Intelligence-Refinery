"""
Phase 4 Pydantic models: ProvenanceChain, FactRecord, QueryResponse, SearchResult.
These are the canonical data structures for the Query Agent and Provenance Layer.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import time


class ProvenanceChain(BaseModel):
    """End-to-end citation from a retrieved chunk back to its source document location."""
    doc_id: str
    document_name: str
    page_numbers: List[int]
    bbox: Dict[str, float] = Field(default_factory=dict)
    content_hash: str
    strategy_used: str = "unknown"
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


class FactRecord(BaseModel):
    """A single key-value fact extracted from a financial/structured table LDU."""
    document_id: str
    fact_key: str
    fact_value: str
    page_number: int
    chunk_hash: str
    extraction_timestamp: str = Field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )


class SearchResult(BaseModel):
    """A single result from semantic_search: metadata, similarity score, and provenance."""
    content: str
    chunk_type: str
    page_refs: List[int]
    score: float = Field(ge=0.0, le=1.0, description="Cosine similarity score (1=best)")
    provenance: ProvenanceChain
    parent_section_title: Optional[str] = None


class QueryResponse(BaseModel):
    """The final output of the Query Agent for any query type."""
    question: str
    answer: str
    tool_used: str  # "pageindex_navigate" | "semantic_search" | "structured_query" | "multi"
    provenance: List[ProvenanceChain] = Field(default_factory=list)
    raw_results: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    error: Optional[str] = None


class AuditResult(BaseModel):
    """Result of audit_claim() — whether a claim is verifiable by the corpus."""
    claim: str
    verified: bool
    sources: List[ProvenanceChain] = Field(default_factory=list)
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
