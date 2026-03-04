from .base import BaseExtractor
from src.models.profile import ExtractedDocument, DocumentProfile, ExtractionCost
from pathlib import Path

class FastTextExtractor(BaseExtractor):
    def extract(self, file_path: Path, profile: DocumentProfile) -> ExtractedDocument:
        # Placeholder for Strategy A
        return ExtractedDocument(doc_id=profile.doc_id, profile=profile)

    @property
    def cost_tier(self) -> ExtractionCost:
        return ExtractionCost.LOW

class LayoutExtractor(BaseExtractor):
    def extract(self, file_path: Path, profile: DocumentProfile) -> ExtractedDocument:
        # Placeholder for Strategy B (Docling/MinerU)
        return ExtractedDocument(doc_id=profile.doc_id, profile=profile)

    @property
    def cost_tier(self) -> ExtractionCost:
        return ExtractionCost.MEDIUM

class VisionExtractor(BaseExtractor):
    def extract(self, file_path: Path, profile: DocumentProfile) -> ExtractedDocument:
        # Placeholder for Strategy C (VLM)
        return ExtractedDocument(doc_id=profile.doc_id, profile=profile)

    @property
    def cost_tier(self) -> ExtractionCost:
        return ExtractionCost.HIGH
