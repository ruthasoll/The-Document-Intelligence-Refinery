from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class OriginType(str, Enum):
    NATIVE_DIGITAL = "native_digital"
    SCANNED_IMAGE = "scanned_image"
    MIXED = "mixed"
    FORM_FILLABLE = "form_fillable"

class LayoutComplexity(str, Enum):
    SINGLE_COLUMN = "single_column"
    MULTI_COLUMN = "multi_column"
    TABLE_HEAVY = "table_heavy"
    FIGURE_HEAVY = "figure_heavy"
    MIXED = "mixed"

class DomainHint(str, Enum):
    FINANCIAL = "financial"
    LEGAL = "legal"
    TECHNICAL = "technical"
    GOVERNMENT = "government"
    GENERAL = "general"

class ExtractionCost(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class DocumentProfile(BaseModel):
    doc_id: str
    file_name: str
    origin_type: OriginType
    layout_complexity: LayoutComplexity
    language: str = "en"
    language_confidence: float = 1.0
    domain_hint: DomainHint = DomainHint.GENERAL
    estimated_cost: ExtractionCost = ExtractionCost.LOW
    page_count: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""

# --- Structure Extraction Layer Models ---

class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float
    page_number: int

class TextBlock(BaseModel):
    text: str
    bbox: BoundingBox
    confidence: float = 1.0

class TableCell(BaseModel):
    text: str
    row_index: int
    col_index: int
    row_span: int = 1
    col_span: int = 1
    is_header: bool = False
    bbox: Optional[BoundingBox] = None

class Table(BaseModel):
    caption: Optional[str] = None
    cells: List[TableCell]
    markdown: str
    bbox: BoundingBox

class Figure(BaseModel):
    caption: Optional[str] = None
    image_path: Optional[str] = None
    bbox: BoundingBox

class PageMetadata(BaseModel):
    page_number: int
    width: float
    height: float
    char_count: int
    char_density: float
    image_area_ratio: float
    images_count: int
    tables_count: int
    extraction_confidence: float = 1.0
    strategy_used: str

class ExtractedDocument(BaseModel):
    doc_id: str
    profile: DocumentProfile
    pages: List[PageMetadata] = Field(default_factory=list)
    blocks: List[TextBlock] = Field(default_factory=list)
    tables: List[Table] = Field(default_factory=list)
    figures: List[Figure] = Field(default_factory=list)
    full_text: str = ""
    processing_time_s: float = 0.0
    total_cost_usd: float = 0.0

# --- Semantic Chunking Models ---

class LDU(BaseModel):
    """Logical Document Unit"""
    chunk_id: str
    content: str
    chunk_type: str  # text, table, figure_caption
    page_refs: List[int]
    bounding_boxes: List[BoundingBox]
    parent_section: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    token_count: int
    content_hash: str

# --- PageIndex Models ---

class SectionNode(BaseModel):
    title: str
    page_start: int
    page_end: int
    summary: Optional[str] = None
    data_types: List[str] = Field(default_factory=list) # e.g. ["table", "figure"]
    entities: List[str] = Field(default_factory=list)
    children: List["SectionNode"] = Field(default_factory=list)

class PageIndex(BaseModel):
    doc_id: str
    root: SectionNode

# --- Provenance Models ---

class Citation(BaseModel):
    doc_id: str
    page_number: int
    bbox: BoundingBox
    content_hash: str

class ProvenanceChain(BaseModel):
    answer: str
    citations: List[Citation]
