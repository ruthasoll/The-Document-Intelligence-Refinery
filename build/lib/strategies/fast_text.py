import pdfplumber
import time
from pathlib import Path
from src.models.profile import (
    ExtractedDocument, DocumentProfile, TextBlock, 
    BoundingBox, PageMetadata, ExtractionCost
)
from .base import BaseExtractor

class FastTextExtractor(BaseExtractor):
    def extract(self, file_path: Path, profile: DocumentProfile) -> ExtractedDocument:
        start_time = time.time()
        blocks = []
        pages_meta = []
        full_text_parts = []

        with pdfplumber.open(file_path) as pdf:
            # For extraction, we limit to first 10 pages for Strategy A to be "Fast"
            pages = pdf.pages[:10] 
            for page in pages:
                page_text = page.extract_text(layout=True) or ""
                full_text_parts.append(page_text)
                
                # Extract text blocks (lines)
                # pdfplumber.extract_text() with layout=True is good, 
                # but for structured blocks with BBoxes, we use page.extract_words()
                # and group them by line.
                words = page.extract_words()
                if words:
                    # Group by top coordinate (simple line detection)
                    current_line = []
                    last_top = words[0]['top']
                    
                    def commit_line(line_words):
                        if not line_words: return
                        x0 = min(w['x0'] for w in line_words)
                        y0 = min(w['top'] for w in line_words)
                        x1 = max(w['x1'] for w in line_words)
                        y1 = max(w['bottom'] for w in line_words)
                        text = " ".join(w['text'] for w in line_words)
                        blocks.append(TextBlock(
                            text=text,
                            bbox=BoundingBox(
                                x0=float(x0), y0=float(y0),
                                x1=float(x1), y1=float(y1),
                                page_number=page.page_number
                            ),
                            confidence=1.0
                        ))

                    for word in words:
                        if abs(word['top'] - last_top) < 2: # Tolerance for same line
                            current_line.append(word)
                        else:
                            commit_line(current_line)
                            current_line = [word]
                            last_top = word['top']
                    commit_line(current_line)

                # Page Metadata
                p_width = float(page.width)
                p_height = float(page.height)
                p_area = p_width * p_height
                char_count = len(page.chars)
                
                # Calculate image area properly
                img_area = 0
                for img in page.images:
                    img_area += float(img.get('width', 0) * img.get('height', 0))
                
                pages_meta.append(PageMetadata(
                    page_number=page.page_number,
                    width=p_width,
                    height=p_height,
                    char_count=char_count,
                    char_density=char_count / p_area if p_area > 0 else 0,
                    image_area_ratio=img_area / p_area if p_area > 0 else 0,
                    images_count=len(page.images),
                    tables_count=len(page.find_tables()),
                    strategy_used="fast_text"
                ))

        return ExtractedDocument(
            doc_id=profile.doc_id,
            profile=profile,
            pages=pages_meta,
            blocks=blocks,
            full_text="\n".join(full_text_parts),
            processing_time_s=time.time() - start_time,
            total_cost_usd=0.0
        )

    @property
    def cost_tier(self) -> ExtractionCost:
        return ExtractionCost.LOW
