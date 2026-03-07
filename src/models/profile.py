from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator

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
    language_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    domain_hint: DomainHint = DomainHint.GENERAL
    estimated_cost: ExtractionCost = ExtractionCost.LOW
    page_count: int = Field(ge=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""

# --- Structure Extraction Layer Models ---

class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float
    page_number: int = Field(ge=1)

    @model_validator(mode='after')
    def check_bbox_sanity(self) -> 'BoundingBox':
        # Automatically normalize ranges instead of failing
        if self.x1 < self.x0:
            self.x0, self.x1 = self.x1, self.x0
        if self.y1 < self.y0:
            self.y0, self.y1 = self.y1, self.y0
        return self

class TextBlock(BaseModel):
    text: str
    bbox: BoundingBox
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_header: bool = False
    level: Optional[int] = None

class TableCell(BaseModel):
    text: str
    row_index: int = Field(ge=0)
    col_index: int = Field(ge=0)
    row_span: int = Field(default=1, ge=1)
    col_span: int = Field(default=1, ge=1)
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
    page_number: int = Field(ge=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    char_count: int = Field(ge=0)
    char_density: float = Field(ge=0)
    image_area_ratio: float = Field(ge=0.0, le=1.0)
    images_count: int = Field(ge=0)
    tables_count: int = Field(ge=0)
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    strategy_used: str

class ExtractedDocument(BaseModel):
    doc_id: str
    profile: DocumentProfile
    pages: List[PageMetadata] = Field(default_factory=list)
    blocks: List[TextBlock] = Field(default_factory=list)
    tables: List[Table] = Field(default_factory=list)
    figures: List[Figure] = Field(default_factory=list)
    full_text: str = ""
    processing_time_s: float = Field(default=0.0, ge=0.0)
    total_cost_usd: float = Field(default=0.0, ge=0.0)

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
