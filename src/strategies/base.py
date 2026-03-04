from abc import ABC, abstractmethod
from src.models.profile import ExtractedDocument, DocumentProfile, ExtractionCost
from pathlib import Path

class BaseExtractor(ABC):
    """
    Abstract Base Class for extraction strategies.
    
    The Extraction Contract:
    1. Coordinate Normalization: All BoundingBoxes MUST use absolute PDF points 
       (or normalized 0-1000) consistently.
    2. Reading Order: The `blocks` list SHOULD follow the logical reading order 
       of the document.
    3. Spatial Provenance: Every extracted element MUST be linked to a BoundingBox.
    4. Schema Fidelity: Outputs MUST strictly adhere to the ExtractedDocument schema.
    """
    @abstractmethod
    def extract(self, file_path: Path, profile: DocumentProfile) -> ExtractedDocument:
        """Execute extraction and return a standardized ExtractedDocument."""
        pass

    @property
    @abstractmethod
    def cost_tier(self) -> ExtractionCost:
        """Return the cost tier for this strategy."""
        pass
