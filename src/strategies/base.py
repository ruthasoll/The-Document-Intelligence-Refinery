from abc import ABC, abstractmethod
from src.models.profile import ExtractedDocument, DocumentProfile, ExtractionCost
from pathlib import Path

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: Path, profile: DocumentProfile) -> ExtractedDocument:
        pass

    @property
    @abstractmethod
    def cost_tier(self) -> ExtractionCost:
        pass
