import yaml
import json
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from src.models.profile import (
    DocumentProfile, ExtractedDocument, OriginType, 
    LayoutComplexity, ExtractionCost
)
from src.strategies.fast_text import FastTextExtractor
from src.strategies.layout import LayoutExtractor
from src.strategies.vision import VisionExtractor

from src.agents.chunker import ChunkingEngine
from src.agents.indexer import PageIndexBuilder
from src.agents.vector_store import VectorStore
from src.storage.fact_table import FactTableExtractor

class ExtractionRouter:
    def __init__(self, rules_path: str = "rubric/extraction_rules.yaml"):
        self.rules_path = Path(rules_path)
        with open(self.rules_path, 'r') as f:
            config = yaml.safe_load(f)
            self.rules = config.get('extraction_rules', {})
        
        self.extractors = {
            "fast_text": FastTextExtractor(),
            "layout_aware": LayoutExtractor(),
            "vision": VisionExtractor(budget_cap=self.rules.get('vision', {}).get('budget_cap_usd_per_doc', 0.50))
        }
        self.chunker = ChunkingEngine(rules_path=rules_path)
        self.indexer = PageIndexBuilder(rules_path=rules_path)
        
        self.ledger_path = Path(".refinery/extraction_ledger.jsonl")
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def route_and_extract(self, file_path: Path, profile: DocumentProfile) -> ExtractedDocument:
        # Initial strategy selection based on profile
        strategy_name = self._select_initial_strategy(profile)
        
        document = None
        attempted_strategies = []
        
        while strategy_name:
            attempted_strategies.append(strategy_name)
            extractor = self.extractors.get(strategy_name)
            if not extractor:
                print(f"Error: Extractor {strategy_name} not found.")
                break
            
            print(f"Attempting extraction with: {strategy_name}")
            try:
                document = extractor.extract(file_path, profile)
            except Exception as e:
                print(f"Extraction failed with {strategy_name}: {e}")
                # Emergency escalation
                next_strategy = self._escalate(strategy_name)
                if next_strategy and next_strategy not in attempted_strategies:
                    strategy_name = next_strategy
                    continue
                break
            
            # Calculate confidence
            confidence = self._calculate_confidence(document, strategy_name)
            # We don't have a confidence field in DocumentProfile in the model, 
            # so we'll add it to the ExtractedDocument's processing metadata if needed
            # or just use it for escalation.
            
            # Log the attempt
            self._log_ledger(strategy_name, confidence, document)
            
            # Check for escalation
            min_conf = self.rules.get('escalation', {}).get('min_confidence', 0.7)
            if confidence < min_conf:
                next_strategy = self._escalate(strategy_name)
                if next_strategy and next_strategy not in attempted_strategies:
                    print(f"Confidence {confidence:.2f} too low (threshold {min_conf}). Escalating to {next_strategy}...")
                    strategy_name = next_strategy
                    continue
            
            break
            
        return document

    def _select_initial_strategy(self, profile: DocumentProfile) -> str:
        # Rules-based initial selection
        if profile.origin_type == OriginType.SCANNED_IMAGE:
            return "vision"
        
        if profile.layout_complexity == LayoutComplexity.SINGLE_COLUMN:
            if profile.origin_type == OriginType.NATIVE_DIGITAL:
                return "fast_text"
            else:
                return "layout_aware"
        
        if profile.layout_complexity in [LayoutComplexity.MULTI_COLUMN, LayoutComplexity.TABLE_HEAVY]:
            return "layout_aware"
            
        return "layout_aware" # Default

    def _calculate_confidence(self, doc: ExtractedDocument, strategy: str) -> float:
        weights = self.rules.get('escalation', {}).get('weights', {})
        
        if not doc.pages:
            return 0.0
            
        page_scores = []
        for p in doc.pages:
            # Base score from page metrics
            score = (
                weights.get('char_density', 0.4) * min(p.char_density * 1000, 1.0) +
                weights.get('image_ratio', -0.3) * p.image_area_ratio +
                weights.get('font_consistency', 0.3) * (1.0 if p.char_count > 0 else 0)
            )
            
            # Strategy-specific adjustments
            if strategy == "fast_text":
                if p.tables_count > 0: score -= 0.3 # Stronger penalty for tables in FastText
                if p.char_count < 100: score *= 0.5
            
            if strategy == "layout_aware":
                # LayoutAware / Docling is very robust for native docs
                score += 0.5 # Increased baseline boost
                if p.tables_count > 0: score += 0.2 # Tables are a strength for LayoutAware
                if p.char_count > 500: score += 0.1 # High char count in native is good sign
                
            page_scores.append(max(0, min(1.0, score)))
            
        # Doc-level structural checks
        total_score = sum(page_scores) / len(page_scores)
        
        if strategy == "layout_aware":
            if len(doc.blocks) > 5:
                total_score = max(total_score, 0.9) # High confidence if we found blocks
            if doc.tables:
                total_score = max(total_score, 0.95) # Very high if tables recovered
            
        if not doc.full_text or len(doc.full_text.strip()) < 50:
            total_score *= 0.2 # Severe penalty for empty output
            
        return total_score


    def _escalate(self, current_strategy: str) -> str:
        progression = ["fast_text", "layout_aware", "vision"]
        try:
            idx = progression.index(current_strategy)
            if idx + 1 < len(progression):
                return progression[idx + 1]
        except ValueError:
            pass
        return None

    def _log_ledger(self, strategy: str, confidence: float, doc: ExtractedDocument, chunk_metrics: Optional[Dict[str, Any]] = None):
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "doc_id": doc.doc_id,
            "strategy": strategy,
            "confidence": round(confidence, 4),
            "processing_time_s": round(doc.processing_time_s, 2),
            "cost_usd": doc.total_cost_usd,
            "pages": len(doc.pages)
        }
        if chunk_metrics:
            entry.update(chunk_metrics)
            
        with open(self.ledger_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def process_complete_pipeline(self, file_path: Path, profile: DocumentProfile):
        """Runs Stage 2 (Extraction) -> Stage 3 (Chunking) -> Stage 4 (Indexing) -> Phase 4 Ingestion."""
        # 1. Extraction
        doc = self.route_and_extract(file_path, profile)
        if not doc:
            return None, None, None
            
        # 2. Chunking
        print(f"Starting Semantic Chunking for {doc.doc_id}...")
        ldus = self.chunker.chunk(doc)
        
        # 3. Indexing
        print(f"Building PageIndex for {doc.doc_id}...")
        index_tree = self.indexer.build_index(doc.doc_id, ldus)
        self.indexer.save_index(index_tree)

        # 4. Phase 4 – Vector Store Ingestion
        try:
            print(f"Ingesting {len(ldus)} LDUs into vector store for {doc.doc_id}...")
            vs = VectorStore()
            vs.ingest(ldus, doc.doc_id)
        except Exception as e:
            print(f"[WARNING] Vector store ingestion failed for {doc.doc_id}: {e}")

        # 5. Phase 4 – Fact Extraction → SQLite
        try:
            print(f"Extracting facts from tables for {doc.doc_id}...")
            fte = FactTableExtractor()
            fte.extract_and_save(ldus, doc.doc_id)
        except Exception as e:
            print(f"[WARNING] Fact extraction failed for {doc.doc_id}: {e}")
        
        # Log chunking metrics to ledger
        metrics = {
            "chunks_created": len(ldus),
            "avg_token_count": round(sum(c.token_count for c in ldus) / len(ldus), 2) if ldus else 0,
            "sections_found": len(index_tree.root_nodes)
        }
        self._log_ledger(doc.pages[0].strategy_used if doc.pages else "unknown", 1.0, doc, metrics)
        
        return doc, ldus, index_tree
