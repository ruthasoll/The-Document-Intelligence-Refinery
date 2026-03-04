import time
from pathlib import Path
from src.models.profile import (
    ExtractedDocument, DocumentProfile, ExtractionCost, PageMetadata,
    TextBlock, BoundingBox
)
from .base import BaseExtractor

class VisionExtractor(BaseExtractor):
    def __init__(self, budget_cap: float = 0.50):
        self.budget_cap = budget_cap
        self.current_spend = 0.0

    def extract(self, file_path: Path, profile: DocumentProfile) -> ExtractedDocument:
        start_time = time.time()
        
        # In a production system, we would:
        # 1. Convert suspicious/complex pages to high-res images.
        # 2. Call a VLM (Gemini 1.5 Flash) with the image and a structured prompt.
        # 3. Parse the VLM's JSON response.
        
        estimated_cost = 0.05 # Mock cost per doc for Flash
        if self.current_spend + estimated_cost > self.budget_cap:
            # Fallback or error
            print(f"WARNING: Vision budget cap reached. Skipping vision extraction for {profile.doc_id}")
            return ExtractedDocument(
                doc_id=profile.doc_id,
                profile=profile,
                full_text="[VISION EXTRACTION SKIPPED: BUDGET CAP]",
                processing_time_s=time.time() - start_time,
                total_cost_usd=0.0
            )
            
        self.current_spend += estimated_cost
        
        # Standardizing output for the demonstration
        return ExtractedDocument(
            doc_id=profile.doc_id,
            profile=profile,
            pages=[
                PageMetadata(
                    page_number=1,
                    width=612, height=792,
                    char_count=0, char_density=0,
                    image_area_ratio=1.0,
                    images_count=1,
                    tables_count=0,
                    strategy_used="vision"
                )
            ],
            blocks=[
                TextBlock(
                    text="[SIMULATED VLM OUTPUT: This document appears to be a scanned image or has extremely complex layout that requires vision-based analysis.]",
                    bbox=BoundingBox(x0=50, y0=50, x1=500, y1=100, page_number=1),
                    confidence=0.95
                )
            ],
            full_text="[SIMULATED VISION TEXT]",
            processing_time_s=time.time() - start_time,
            total_cost_usd=estimated_cost
        )

    @property
    def cost_tier(self) -> ExtractionCost:
        return ExtractionCost.HIGH
