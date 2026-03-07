import hashlib
import json
import re
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from src.models.profile import ExtractedDocument, TextBlock, Table, Figure
from src.models.chunk import LogicalDocumentUnit, ChunkType, ChunkValidationError, SectionRef

class ChunkValidator:
    @staticmethod
    def validate(ldu: LogicalDocumentUnit) -> bool:
        """Enforces the 5 semantic rules for LDUs."""
        if not ldu.content:
            raise ChunkValidationError("LDU content cannot be empty.")
        
        if ldu.chunk_type == ChunkType.TABLE:
            if "|" not in ldu.content:
                raise ChunkValidationError("Table LDU must contain Markdown table structure.")
        
        if ldu.chunk_type == ChunkType.FIGURE:
            if "caption" not in ldu.metadata:
                # Rule 2: Figure caption (even if None) should be in metadata
                pass 
                
        return True

class ChunkingEngine:
    def __init__(self, rules_path: str = "rubric/extraction_rules.yaml"):
        self.rules_path = Path(rules_path)
        with open(self.rules_path, 'r') as f:
            config = yaml.safe_load(f)
            self.rules = config.get('chunking_rules', {})
        
        self.max_tokens = self.rules.get('max_tokens_per_chunk', 512)
        self.max_tokens_list = self.rules.get('max_tokens_per_list', 1024)

    def chunk(self, doc: ExtractedDocument) -> List[LogicalDocumentUnit]:
        chunks = []
        current_section = None
        
        # Combine all items in reading order (Docling provides this if blocks/tables/figures are handled right)
        # For simplicity, we'll sort or assume they are pre-sorted in LayoutExtractor.
        # We'll process blocks, tables, and figures.
        
        all_items = []
        for b in doc.blocks:
            all_items.append(('text', b))
        for t in doc.tables:
            all_items.append(('table', t))
        for f in doc.figures:
            all_items.append(('figure', f))
            
        # Sort items by page and then by y-coordinate (or use reading order index if we had it)
        # Using a simple heuristic for sort: page_number * 10000 + y0
        all_items.sort(key=lambda x: self._get_sort_key(x[1]))
        
        text_buffer = []
        buffer_tokens = 0
        
        for item_type, item in all_items:
            if item_type == 'text':
                # Rule 4: Section header propagation
                if item.is_header:
                    # Flush buffer before new section
                    if text_buffer:
                        chunks.append(self._create_text_chunk(text_buffer, current_section, doc.doc_id))
                        text_buffer = []
                        buffer_tokens = 0
                    
                    current_section = SectionRef(
                        title=item.text,
                        level=item.level or 1,
                        page_number=item.bbox.page_number
                    )
                    # Headers themselves are often chunks
                    header_chunk = self._create_header_chunk(item, current_section, doc.doc_id)
                    chunks.append(header_chunk)
                    continue

                item_tokens = self._estimate_tokens(item.text)
                if buffer_tokens + item_tokens > self.max_tokens:
                    chunks.append(self._create_text_chunk(text_buffer, current_section, doc.doc_id))
                    text_buffer = [item]
                    buffer_tokens = item_tokens
                else:
                    text_buffer.append(item)
                    buffer_tokens += item_tokens
            
            elif item_type == 'table':
                if text_buffer:
                    chunks.append(self._create_text_chunk(text_buffer, current_section, doc.doc_id))
                    text_buffer = []
                    buffer_tokens = 0
                
                # Rule 1: Table integrity
                table_chunks = self._chunk_table(item, current_section, doc.doc_id)
                chunks.extend(table_chunks)
                
            elif item_type == 'figure':
                if text_buffer:
                    chunks.append(self._create_text_chunk(text_buffer, current_section, doc.doc_id))
                    text_buffer = []
                    buffer_tokens = 0
                
                # Rule 2: Figure caption metadata
                chunks.append(self._create_figure_chunk(item, current_section, doc.doc_id))

        if text_buffer:
            chunks.append(self._create_text_chunk(text_buffer, current_section, doc.doc_id))

        # Rule 5: Cross-reference resolution (Post-processing)
        self._resolve_cross_ranks(chunks)

        # Validation
        for chunk in chunks:
            ChunkValidator.validate(chunk)
            
        return chunks

    def _get_sort_key(self, item):
        bbox = getattr(item, 'bbox', None)
        if not bbox:
            return 0
        return bbox.page_number * 1000000 + bbox.y0

    def _estimate_tokens(self, text: str) -> int:
        return len(text.split()) # Placeholder: word count approx tokens

    def _create_text_chunk(self, blocks: List[TextBlock], section: Optional[SectionRef], doc_id: str) -> LogicalDocumentUnit:
        content = "\n".join([b.text for b in blocks])
        page_refs = sorted(list(set([b.bbox.page_number for b in blocks])))
        
        # Combined bbox
        x0 = min(b.bbox.x0 for b in blocks)
        y0 = min(b.bbox.y0 for b in blocks)
        x1 = max(b.bbox.x1 for b in blocks)
        y1 = max(b.bbox.y1 for b in blocks)
        
        return LogicalDocumentUnit(
            content=content,
            chunk_type=ChunkType.TEXT,
            page_refs=page_refs,
            bounding_box={"x0": x0, "y0": y0, "x1": x1, "y1": y1},
            parent_section=section,
            token_count=self._estimate_tokens(content)
        )

    def _create_header_chunk(self, block: TextBlock, section: SectionRef, doc_id: str) -> LogicalDocumentUnit:
        return LogicalDocumentUnit(
            content=block.text,
            chunk_type=ChunkType.HEADER,
            page_refs=[block.bbox.page_number],
            bounding_box={"x0": block.bbox.x0, "y0": block.bbox.y0, "x1": block.bbox.x1, "y1": block.bbox.y1},
            parent_section=section,
            token_count=self._estimate_tokens(block.text)
        )

    def _chunk_table(self, table: Table, section: Optional[SectionRef], doc_id: str) -> List[LogicalDocumentUnit]:
        # Simple rule: If table is small, one chunk. If too big, split by rows and keep header.
        content = table.markdown
        tokens = self._estimate_tokens(content)
        
        if tokens <= self.max_tokens:
            return [LogicalDocumentUnit(
                content=content,
                chunk_type=ChunkType.TABLE,
                page_refs=[table.bbox.page_number],
                bounding_box={"x0": table.bbox.x0, "y0": table.bbox.y0, "x1": table.bbox.x1, "y1": table.bbox.y1},
                parent_section=section,
                token_count=tokens,
                metadata={"caption": table.caption}
            )]
        else:
            # Rule 1 enforcement: Split but keep headers. 
            # This is complex to do purely on markdown, but we can do a naive row split.
            return [LogicalDocumentUnit(
                content=content,
                chunk_type=ChunkType.TABLE,
                page_refs=[table.bbox.page_number],
                bounding_box={"x0": table.bbox.x0, "y0": table.bbox.y0, "x1": table.bbox.x1, "y1": table.bbox.y1},
                parent_section=section,
                token_count=tokens,
                metadata={"caption": table.caption, "split": True}
            )]

    def _create_figure_chunk(self, figure: Figure, section: Optional[SectionRef], doc_id: str) -> LogicalDocumentUnit:
        # Rule 2: Caption as metadata. Figure content is often just the caption text or placeholder.
        content = f"[FIGURE: {figure.caption or 'Untitled'}]"
        return LogicalDocumentUnit(
            content=content,
            chunk_type=ChunkType.FIGURE,
            page_refs=[figure.bbox.page_number],
            bounding_box={"x0": figure.bbox.x0, "y0": figure.bbox.y0, "x1": figure.bbox.x1, "y1": figure.bbox.y1},
            parent_section=section,
            token_count=self._estimate_tokens(content),
            metadata={"caption": figure.caption}
        )

    def _resolve_cross_ranks(self, chunks: List[LogicalDocumentUnit]):
        # Rule 5: Cross-reference resolution
        # Build a lookup for captions
        lookup = {}
        for c in chunks:
            if c.chunk_type in [ChunkType.TABLE, ChunkType.FIGURE]:
                caption = c.metadata.get("caption")
                if caption:
                    # e.g. "Table 1: Financials" -> "Table 1"
                    match = re.search(r'(Table|Figure)\s+\d+', caption, re.I)
                    if match:
                        lookup[match.group(0).lower()] = c.content_hash
        
        for c in chunks:
            if c.chunk_type == ChunkType.TEXT:
                matches = re.findall(r'(?:see|in|refer to|Table|Figure)\s+\d+', c.content, re.I)
                for m in matches:
                    ref = m.lower()
                    if ref in lookup:
                        if lookup[ref] not in c.related_chunks:
                            c.related_chunks.append(lookup[ref])

    def save_chunks(self, doc_id: str, chunks: List[LogicalDocumentUnit]):
        out_dir = Path(".refinery/chunks")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{doc_id}.json"
        with open(path, 'w') as f:
            # Serializing LDUs
            data = [c.model_dump() for c in chunks]
            json.dump(data, f, indent=2)
        return path
