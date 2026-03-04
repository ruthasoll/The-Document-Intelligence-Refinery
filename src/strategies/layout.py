from docling.document_converter import DocumentConverter
import time
from pathlib import Path
from src.models.profile import (
    ExtractedDocument, DocumentProfile, TextBlock, 
    Table, TableCell, BoundingBox, PageMetadata, ExtractionCost, Figure
)
from .base import BaseExtractor

import pypdf
import os

class LayoutExtractor(BaseExtractor):
    def __init__(self):
        self.converter = DocumentConverter()

    def extract(self, file_path: Path, profile: DocumentProfile) -> ExtractedDocument:
        start_time = time.time()
        
        # Create a subset to avoid OOM but allow more context
        temp_pdf_path = f"temp_{profile.doc_id}_subset.pdf"
        try:
            reader = pypdf.PdfReader(file_path)
            writer = pypdf.PdfWriter()
            num_pages = min(15, len(reader.pages)) # Increased slightly for better layout context
            for i in range(num_pages):
                writer.add_page(reader.pages[i])
            with open(temp_pdf_path, "wb") as f_out:
                writer.write(f_out)
        except Exception as e:
            temp_pdf_path = str(file_path)
            
        try:
            result = self.converter.convert(temp_pdf_path)
            doc = result.document
        finally:
            if temp_pdf_path != str(file_path) and os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
        
        blocks = []
        tables = []
        figures = []
        pages_meta = []
        
        # Docling 2.x: Use iterate_items() to walk through the document in reading order
        # or fallback to specific lists if not available.
        try:
            items = list(doc.iterate_items())
        except AttributeError:
            items = doc.texts + doc.tables + doc.pictures

        for item, level in items if isinstance(items[0], tuple) else [(i, 0) for i in items]:
            bbox = None
            page_no = 1
            if hasattr(item, 'prov') and item.prov:
                prov = item.prov[0]
                page_no = prov.page_no
                b = prov.bbox
                bbox = BoundingBox(
                    x0=float(b.l), y0=float(b.t),
                    x1=float(b.r), y1=float(b.b),
                    page_number=page_no
                )

            # Route based on type
            # In Docling, item can be TextItem, TableItem, PictureItem
            from docling_core.types.doc.document import TextItem, TableItem, PictureItem
            
            if isinstance(item, TextItem):
                blocks.append(TextBlock(
                    text=item.text,
                    bbox=bbox or BoundingBox(x0=0, y0=0, x1=0, y1=0, page_number=page_no),
                    confidence=1.0
                ))
            elif isinstance(item, PictureItem):
                figures.append(Figure(
                    caption=getattr(item, 'caption', None),
                    bbox=bbox or BoundingBox(x0=0, y0=0, x1=0, y1=0, page_number=page_no)
                ))
            # Tables are handled in a separate structured pass for cell-level detail, 
            # but we keep their position in 'blocks' if we want absolute reading order
            # or just rely on the 'tables' list.

        # Separate pass for structured elements
        for tbl in doc.tables:
            cells = []
            for cell in tbl.data.table_cells:
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
                t_page = tbl.prov[0].page_no
                tb = tbl.prov[0].bbox
                t_bbox = BoundingBox(x0=float(tb.l), y0=float(tb.t), x1=float(tb.r), y1=float(tb.b), page_number=t_page)

            tables.append(Table(
                cells=cells,
                markdown=tbl.export_to_markdown(),
                bbox=t_bbox or BoundingBox(x0=0, y0=0, x1=0, y1=0, page_number=t_page)
            ))

        for pic in doc.pictures:
            p_bbox = None
            p_page = 1
            if pic.prov:
                p_page = pic.prov[0].page_no
                pb = pic.prov[0].bbox
                p_bbox = BoundingBox(x0=float(pb.l), y0=float(pb.t), x1=float(pb.r), y1=float(pb.b), page_number=p_page)
            
            figures.append(Figure(
                caption=pic.caption if hasattr(pic, 'caption') else None,
                bbox=p_bbox or BoundingBox(x0=0, y0=0, x1=0, y1=0, page_number=p_page)
            ))
            
        for p in result.pages:
            pages_meta.append(PageMetadata(
                page_number=p.page_no,
                width=float(p.size.width),
                height=float(p.size.height),
                char_count=0,
                char_density=0,
                image_area_ratio=0,
                images_count=len([pic for pic in doc.pictures if pic.prov[0].page_no == p.page_no]) if doc.pictures else 0,
                tables_count=len([t for t in doc.tables if t.prov[0].page_no == p.page_no]) if doc.tables else 0,
                extraction_confidence=1.0, # Strategy-level confidence
                strategy_used="layout_aware"
            ))

        return ExtractedDocument(
            doc_id=profile.doc_id,
            profile=profile,
            pages=pages_meta,
            blocks=blocks,
            tables=tables,
            figures=figures,
            full_text=doc.export_to_markdown(),
            processing_time_s=time.time() - start_time,
            total_cost_usd=0.01 
        )

    @property
    def cost_tier(self) -> ExtractionCost:
        return ExtractionCost.MEDIUM
