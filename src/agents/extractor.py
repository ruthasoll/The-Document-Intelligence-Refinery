from pathlib import Path
from src.models.profile import DocumentProfile, ExtractedDocument, OriginType, LayoutComplexity
from src.strategies.implementations import FastTextExtractor, LayoutExtractor, VisionExtractor

class ExtractionRouter:
    def __init__(self):
        self.fast_extractor = FastTextExtractor()
        self.layout_extractor = LayoutExtractor()
        self.vision_extractor = VisionExtractor()

    def route_and_extract(self, file_path: Path, profile: DocumentProfile) -> ExtractedDocument:
        # Strategy A — Fast Text (Cost: Low)
        # Triggers when: origin_type=native_digital AND layout_complexity IN [single_column]
        if profile.origin_type == OriginType.NATIVE_DIGITAL and \
           profile.layout_complexity == LayoutComplexity.SINGLE_COLUMN:
            return self.fast_extractor.extract(file_path, profile)
        
        # Strategy C — Vision-Augmented (Cost: High)
        # Triggers when: scanned_image
        if profile.origin_type == OriginType.SCANNED_IMAGE:
            return self.vision_extractor.extract(file_path, profile)
            
        # Strategy B — Layout-Aware (Cost: Medium)
        # Defaults for multi_column OR table_heavy OR mixed
        return self.layout_extractor.extract(file_path, profile)
