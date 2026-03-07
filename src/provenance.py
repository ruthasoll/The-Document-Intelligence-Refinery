"""
Phase 4 – Provenance Helpers.
Centralized logic for building and formatting ProvenanceChain objects
from LDUs, SectionNodes, and FactRecords.
"""
from typing import Any, Dict, List, Optional, Union
from src.models.chunk import LogicalDocumentUnit, SectionNode
from src.models.query import ProvenanceChain, FactRecord

def build_provenance_from_ldu(ldu: LogicalDocumentUnit, doc_id: str, strategy: str = "semantic_search") -> ProvenanceChain:
    """Creates a ProvenanceChain from a LogicalDocumentUnit."""
    return ProvenanceChain(
        doc_id=doc_id,
        document_name=doc_id.replace("_", " "),
        page_numbers=ldu.page_refs,
        bbox=ldu.bounding_box or {},
        content_hash=ldu.content_hash,
        strategy_used=strategy
    )

def build_provenance_from_fact(fact: Union[FactRecord, Dict[str, Any]], strategy: str = "structured_query") -> ProvenanceChain:
    """Creates a ProvenanceChain from a FactRecord or a raw SQLite row dict."""
    if isinstance(fact, dict):
        doc_id = fact.get("document_id", "unknown")
        page = fact.get("page_number")
        return ProvenanceChain(
            doc_id=doc_id,
            document_name=doc_id.replace("_", " "),
            page_numbers=[page] if isinstance(page, int) else [],
            bbox={},
            content_hash=fact.get("chunk_hash", ""),
            strategy_used=strategy
        )
    
    return ProvenanceChain(
        doc_id=fact.document_id,
        document_name=fact.document_id.replace("_", " "),
        page_numbers=[fact.page_number],
        bbox={},
        content_hash=fact.chunk_hash,
        strategy_used=strategy
    )

def format_provenance_short(prov: ProvenanceChain) -> str:
    """Returns a short string representation of provenance: Doc Name (p. X, Y)"""
    pages = ", ".join(map(str, prov.page_numbers))
    return f"{prov.document_name} (p. {pages})"

def format_provenance_list(provenance_list: List[ProvenanceChain]) -> str:
    """Formats a list of provenance items into a readable citations block."""
    if not provenance_list:
        return ""
    
    unique_citations = {}
    for p in provenance_list:
        key = (p.doc_id, tuple(sorted(p.page_numbers)))
        if key not in unique_citations:
            unique_citations[key] = format_provenance_short(p)
            
    return "\nSources:\n- " + "\n- ".join(unique_citations.values())
