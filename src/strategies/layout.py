from docling.document_converter import DocumentConverter
import time
from pathlib import Path
from src.models.profile import (
    ExtractedDocument, DocumentProfile, TextBlock, 
    Table, TableCell, BoundingBox, PageMetadata, ExtractionCost
)
from .base import BaseExtractor

import pypdf
import os

class LayoutExtractor(BaseExtractor):
    def __init__(self):
        self.converter = DocumentConverter()

    def extract(self, file_path: Path, profile: DocumentProfile) -> ExtractedDocument:
        start_time = time.time()
        
        # Create a 10-page subset to avoid OOM but allow more context
        temp_pdf_path = f"temp_{profile.doc_id}_subset.pdf"
        try:
            reader = pypdf.PdfReader(file_path)
            writer = pypdf.PdfWriter()
            num_pages = min(10, len(reader.pages))
            for i in range(num_pages):
                writer.add_page(reader.pages[i])
            with open(temp_pdf_path, "wb") as f_out:
                writer.write(f_out)
        except Exception as e:
            print(f"Error creating PDF subset: {e}")
            temp_pdf_path = str(file_path) # Fallback to original if small or error
            
        # Docling conversion
        try:
            result = self.converter.convert(temp_pdf_path)
            doc = result.document
        finally:
            if temp_pdf_path != str(file_path) and os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
        
        blocks = []
        tables = []
        pages_meta = []
        
        # Extract text blocks with accurate BBoxes
        for item in doc.texts:
            # item.prov is typically a list of Provenance objects
            # Each prov has page_no and bbox
            bbox = None
            page_no = 1
            if item.prov:
                prov = item.prov[0]
                page_no = prov.page_no
                # Docling BBox: l, t, r, b
                b = prov.bbox
                bbox = BoundingBox(
                    x0=float(b.l), y0=float(b.t),
                    x1=float(b.r), y1=float(b.b),
                    page_number=page_no
                )
            
            blocks.append(TextBlock(
                text=item.text,
                bbox=bbox or BoundingBox(x0=0, y0=0, x1=0, y1=0, page_number=page_no),
                confidence=1.0
            ))
            
        # Extract tables
        for tbl in doc.tables:
            cells = []
            for cell in tbl.data.table_cells:
                # Map cell bbox if available
                c_bbox = None
                if cell.prov:
                    cb = cell.prov[0].bbox
                    c_bbox = BoundingBox(
                        x0=float(cb.l), y0=float(cb.t),
                        x1=float(cb.r), y1=float(cb.b),
                        page_number=cell.prov[0].page_no
                    )

                cells.append(TableCell(
                    text=cell.text,
                    row_index=cell.row_index,
                    col_index=cell.col_index,
                    row_span=cell.row_span,
                    col_span=cell.col_span,
                    bbox=c_bbox
                ))
            
            t_bbox = None
            t_page = 1
            if tbl.prov:
                tb = tbl.prov[0].bbox
                t_page = tbl.prov[0].page_no
                t_bbox = BoundingBox(
                    x0=float(tb.l), y0=float(tb.t),
                    x1=float(tb.r), y1=float(tb.b),
                    page_number=t_page
                )

            tables.append(Table(
                cells=cells,
                markdown=tbl.export_to_markdown(),
                bbox=t_bbox or BoundingBox(x0=0, y0=0, x1=0, y1=0, page_number=t_page)
            ))
            
        # Docling provides page information in result.pages
        for p in result.pages:
            pages_meta.append(PageMetadata(
                page_number=p.page_no,
                width=float(p.size.width),
                height=float(p.size.height),
                char_count=0, # Docling doesn't give raw char count easily here
                char_density=0,
                image_area_ratio=0,
                images_count=0,
                tables_count=len([t for t in doc.tables if t.prov[0].page_no == p.page_no]) if doc.tables else 0,
                strategy_used="layout_aware"
            ))

        return ExtractedDocument(
            doc_id=profile.doc_id,
            profile=profile,
            pages=pages_meta,
            blocks=blocks,
            tables=tables,
            full_text=doc.export_to_markdown(),
            processing_time_s=time.time() - start_time,
            total_cost_usd=0.01 
        )

    @property
    def cost_tier(self) -> ExtractionCost:
        return ExtractionCost.MEDIUM
