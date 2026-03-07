"""
Phase 4 – Vector Store using FAISS + sentence-transformers.
Ingests LDUs as dense embeddings with rich metadata for semantic retrieval.
Persists to .refinery/vector_store/ as index + metadata sidecar.
"""
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from src.models.chunk import LogicalDocumentUnit
from src.models.query import ProvenanceChain, SearchResult

logger = logging.getLogger(__name__)


class VectorStore:
    """FAISS-backed vector store with metadata sidecar for LDU retrieval."""

    DEFAULT_MODEL = "all-MiniLM-L6-v2"
    STORE_DIR = Path(".refinery/vector_store")

    def __init__(
        self,
        embedding_model: str = DEFAULT_MODEL,
        store_dir: str | Path = STORE_DIR,
    ):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.store_dir / "faiss.index"
        self.meta_path = self.store_dir / "metadata.json"

        logger.info(f"Loading embedding model: {embedding_model}")
        self.model = SentenceTransformer(embedding_model)
        self.dim = self.model.get_sentence_embedding_dimension()

        # Metadata store: list of dicts, one per vector (positional)
        self.metadata: List[Dict[str, Any]] = []

        if self.index_path.exists() and self.meta_path.exists():
            self._load()
        else:
            self.index = faiss.IndexFlatL2(self.dim)

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest(self, ldus: List[LogicalDocumentUnit], doc_id: str) -> int:
        """
        Embed and store a list of LDUs.
        Returns number of vectors added.
        """
        texts = [ldu.content for ldu in ldus]
        if not texts:
            return 0

        logger.info(f"Embedding {len(texts)} LDUs for doc_id={doc_id}")
        embeddings = self.model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        embeddings = np.array(embeddings, dtype="float32")

        self.index.add(embeddings)

        for ldu in ldus:
            section_title = None
            if isinstance(ldu.parent_section, str):
                section_title = ldu.parent_section
            elif ldu.parent_section and hasattr(ldu.parent_section, "title"):
                # Case for SectionRef model
                section_title = getattr(ldu.parent_section, "title")

            self.metadata.append({
                "doc_id": doc_id,
                "content": ldu.content,
                "chunk_type": ldu.chunk_type.value,
                "page_refs": ldu.page_refs,
                "bbox": ldu.bounding_box or {},
                "content_hash": ldu.content_hash,
                "token_count": ldu.token_count,
                "parent_section_title": section_title,
                "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })

        self._save()
        logger.info(f"Vector store now has {self.index.ntotal} total vectors.")
        return len(texts)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_id_filter: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Semantic search returning ranked SearchResult objects with provenance.
        Optionally filter by doc_id.
        """
        if self.index.ntotal == 0:
            logger.warning("Vector store is empty. Ingest documents first.")
            return []

        query_vec = self.model.encode([query], show_progress_bar=False, normalize_embeddings=True)
        query_vec = np.array(query_vec, dtype="float32")

        # Retrieve more candidates if filtering, to ensure we have enough after filter
        fetch_k = top_k * 5 if doc_id_filter else top_k
        fetch_k = min(fetch_k, self.index.ntotal)

        distances, indices = self.index.search(query_vec, fetch_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            meta = self.metadata[idx]

            if doc_id_filter and meta["doc_id"] != doc_id_filter:
                continue

            # Convert L2 distance to a [0,1] similarity score (normalized embeddings → cosine)
            score = float(max(0.0, 1.0 - dist / 2.0))

            provenance = ProvenanceChain(
                doc_id=meta["doc_id"],
                document_name=meta["doc_id"].replace("_", " "),
                page_numbers=meta["page_refs"],
                bbox=meta["bbox"],
                content_hash=meta["content_hash"],
                strategy_used="semantic_search",
            )

            results.append(SearchResult(
                content=meta["content"],
                chunk_type=meta["chunk_type"],
                page_refs=meta["page_refs"],
                score=round(score, 4),
                provenance=provenance,
                parent_section_title=meta.get("parent_section_title"),
            ))

            if len(results) >= top_k:
                break

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self):
        faiss.write_index(self.index, str(self.index_path))
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2)
        logger.debug(f"Saved FAISS index ({self.index.ntotal} vectors) to {self.store_dir}")

    def _load(self):
        self.index = faiss.read_index(str(self.index_path))
        with open(self.meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)
        logger.info(f"Loaded FAISS index: {self.index.ntotal} vectors, {len(self.metadata)} metadata entries.")

    def clear(self):
        """Reset the store (useful for re-ingestion)."""
        self.index = faiss.IndexFlatL2(self.dim)
        self.metadata = []
        if self.index_path.exists():
            self.index_path.unlink()
        if self.meta_path.exists():
            self.meta_path.unlink()
        logger.info("Vector store cleared.")
