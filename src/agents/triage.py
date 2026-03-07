import pdfplumber
import yaml
from pathlib import Path
from typing import Dict, Any, List
from src.models.profile import (
    DocumentProfile, OriginType, LayoutComplexity, 
    DomainHint, ExtractionCost
)

class DocumentTriageAgent:
    def __init__(self, rules_path: str = "rubric/extraction_rules.yaml"):
        self.rules_path = Path(rules_path)
        with open(self.rules_path, 'r') as f:
            self.rules = yaml.safe_load(f).get('triage_rules', {})

    def profile_document(self, file_path: str) -> DocumentProfile:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found at {file_path}")

        metrics = self._gather_metrics(path)
        
        origin_type = self._detect_origin(metrics)
        layout_complexity = self._detect_layout(metrics)
        domain_hint = self._detect_domain(metrics['text_sample'])
        
        # Heuristic cost estimation
        estimated_cost = self._estimate_cost(origin_type, layout_complexity)
        
        reasoning = (
            f"Detected {origin_type.value} due to char_density={metrics['avg_char_density']:.6f} "
            f"and image_ratio={metrics['avg_image_ratio']:.6f}. "
            f"Layout is {layout_complexity.value} based on {metrics['total_tables']} tables detected."
        )

        return DocumentProfile(
            doc_id=path.stem,
            file_name=path.name,
            origin_type=origin_type,
            layout_complexity=layout_complexity,
            domain_hint=domain_hint,
            estimated_cost=estimated_cost,
            page_count=metrics['page_count'],
            metadata=metrics,
            reasoning=reasoning
        )

    def _gather_metrics(self, file_path: Path) -> Dict[str, Any]:
        total_chars = 0
        total_image_area = 0
        total_page_area = 0
        total_tables = 0
        text_samples = []
        
        with pdfplumber.open(file_path) as pdf:
            pages = pdf.pages
            page_count = len(pages)
            # Sample up to 20 pages for triage efficiency, skipping the cover if many pages
            start_page = 1 if page_count > 2 else 0
            sample_pages = pages[start_page : start_page + 20]
            
            for page in sample_pages:
                page_area = float(page.width * page.height)
                total_page_area += page_area
                
                chars = page.chars
                total_chars += len(chars)
                
                images = page.images
                total_image_area += sum([float(i.get('width', 0) * i.get('height', 0)) for i in images])
                
                tables = page.find_tables()
                total_tables += len(tables)
                
                text = page.extract_text()
                if text:
                    text_samples.append(text[:500])

        avg_char_density = total_chars / total_page_area if total_page_area > 0 else 0
        avg_image_ratio = total_image_area / total_page_area if total_page_area > 0 else 0
        
        return {
            "page_count": page_count,
            "sampled_count": len(sample_pages),
            "avg_char_density": avg_char_density,
            "avg_image_ratio": avg_image_ratio,
            "total_tables": total_tables,
            "text_sample": " ".join(text_samples).lower()
        }

    def _detect_origin(self, metrics: Dict[str, Any]) -> OriginType:
        rules = self.rules.get('origin_type', {})
        scanned = rules.get('scanned_threshold', {})
        mixed = rules.get('mixed_threshold', {})
        
        if metrics['avg_char_density'] < scanned.get('max_char_density', 0.0001) and \
           metrics['avg_image_ratio'] > scanned.get('min_image_ratio', 0.8) and \
           metrics['page_count'] < 5: # Only classify as scanned if very few characters AND low page count (proxy for cover/image only)
            return OriginType.SCANNED_IMAGE
        
        # If any page has significant characters, it's not "scanned_image" in the sense of needing VLM for everything
        if metrics['avg_char_density'] < 0.00005: # Extremely low density
            return OriginType.SCANNED_IMAGE
            
        return OriginType.NATIVE_DIGITAL

    def _detect_layout(self, metrics: Dict[str, Any]) -> LayoutComplexity:
        rules = self.rules.get('layout_complexity', {})
        # Scale tables_per_page by sampled count, but also check absolute find.
        # If we found any table in the sample, it's at least 'mixed'.
        total_tables = metrics.get('total_tables', 0)
        tables_per_page = total_tables / max(1, metrics['sampled_count'])
        
        if total_tables > 5 or tables_per_page > rules.get('table_heavy_min_tables_per_page', 0.5):
            return LayoutComplexity.TABLE_HEAVY
            
        if total_tables > 0:
            return LayoutComplexity.MIXED
            
        return LayoutComplexity.SINGLE_COLUMN

    def _detect_domain(self, text_sample: str) -> DomainHint:
        keywords = self.rules.get('domain_keywords', {})
        
        scores = {domain: 0 for domain in DomainHint}
        
        for domain, kw_list in keywords.items():
            for kw in kw_list:
                if kw in text_sample:
                    # Map yaml key to enum if possible
                    try:
                        enum_val = DomainHint(domain)
                        scores[enum_val] += 1
                    except ValueError:
                        pass
        
        best_domain = max(scores, key=scores.get)
        if scores[best_domain] == 0:
            return DomainHint.GENERAL
        return best_domain

    def _estimate_cost(self, origin: OriginType, layout: LayoutComplexity) -> ExtractionCost:
        if origin == OriginType.SCANNED_IMAGE:
            return ExtractionCost.HIGH
        if layout in [LayoutComplexity.TABLE_HEAVY, LayoutComplexity.MULTI_COLUMN]:
            return ExtractionCost.MEDIUM
        return ExtractionCost.LOW

    def explain_classification(self, profile: DocumentProfile) -> str:
        return (
            f"--- Triage Report for {profile.file_name} ---\n"
            f"Origin: {profile.origin_type.value}\n"
            f"Layout: {profile.layout_complexity.value}\n"
            f"Domain: {profile.domain_hint.value}\n"
            f"Cost Tier: {profile.estimated_cost.value}\n"
            f"Reasoning: {profile.reasoning}\n"
        )
