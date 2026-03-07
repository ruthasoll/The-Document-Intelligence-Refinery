from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator
import hashlib

class ChunkType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    FIGURE = "figure"
    LIST = "list"
    CAPTION = "caption"
    HEADER = "header"
    OTHER = "other"

class SectionRef(BaseModel):
    title: str
    level: int
    page_number: int

class LogicalDocumentUnit(BaseModel):
    content: str
    chunk_type: ChunkType
    page_refs: List[int]
    bounding_box: Optional[Dict[str, float]] = None
    parent_section: Optional[Union[str, SectionRef]] = None
    token_count: int = 0
    content_hash: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    related_chunks: List[str] = Field(default_factory=list, description="List of content_hashes of related chunks")

    @model_validator(mode='after')
    def generate_hash(self) -> 'LogicalDocumentUnit':
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        return self

class SectionNode(BaseModel):
    title: str
    page_start: int
    page_end: int
    summary: Optional[str] = None
    key_entities: List[str] = Field(default_factory=list)
    data_types_present: List[str] = Field(default_factory=list)
    child_sections: List["SectionNode"] = Field(default_factory=list)
    chunk_ids: List[str] = Field(default_factory=list, description="Hashes of LDUs in this section")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PageIndexTree(BaseModel):
    doc_id: str
    root_nodes: List[SectionNode]
    total_pages: int
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ChunkValidationError(Exception):
    """Raised when a chunk violates semantic rules."""
    pass

class ProvenanceInfo(BaseModel):
    """Metadata for tracking origin of extracted facts (Phase 4 preparation)."""
    doc_id: str
    page_number: int
    bbox: Dict[str, float]
    content_hash: str
    strategy_used: str
    timestamp: str
