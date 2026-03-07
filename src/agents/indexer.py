import json
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.models.chunk import LogicalDocumentUnit, SectionNode, PageIndexTree, ChunkType
from src.models.profile import ExtractedDocument

class PageIndexBuilder:
    def __init__(self, rules_path: str = "rubric/extraction_rules.yaml"):
        self.rules_path = Path(rules_path)
        with open(self.rules_path, 'r') as f:
            config = yaml.safe_load(f)
            self.rules = config.get('page_index_rules', {})
        
        self.summary_model = self.rules.get('summary_model', 'gemini-1.5-flash')

    def build_index(self, doc_id: str, ldus: List[LogicalDocumentUnit]) -> PageIndexTree:
        # Create a lookup for enrichment
        chunk_lookup = {c.content_hash: c.content for c in ldus}
        
        # 1. Identify sections from LDUs and preserve levels
        flat_nodes = []
        
        for ldu in ldus:
            if ldu.chunk_type == ChunkType.HEADER:
                ref = ldu.parent_section
                if ref:
                    title = ref.title if hasattr(ref, 'title') else str(ref)
                    level = ref.level if hasattr(ref, 'level') else 1
                    
                    node = SectionNode(
                        title=title,
                        page_start=ldu.page_refs[0],
                        page_end=ldu.page_refs[0],
                        data_types_present=set(),
                        chunk_ids=[ldu.content_hash],
                        metadata={"level": level}
                    )
                    flat_nodes.append(node)
            elif flat_nodes:
                # Add content to the most recent section
                current_node = flat_nodes[-1]
                current_node.chunk_ids.append(ldu.content_hash)
                current_node.page_end = max(current_node.page_end, ldu.page_refs[-1])
                chunk_type_val = ldu.chunk_type.value
                if chunk_type_val not in current_node.data_types_present:
                    current_node.data_types_present.append(chunk_type_val)


        # 2. Build Hierarchy
        root_nodes = []
        stack = [] # (level, node)
        
        for node in flat_nodes:
            level = node.metadata.get("level", 1)
            
            # Pop stack until we find a parent (level < current level)
            while stack and stack[-1][0] >= level:
                stack.pop()
            
            if not stack:
                root_nodes.append(node)
            else:
                stack[-1][1].child_sections.append(node)
            
            stack.append((level, node))

        # 3. Generate Summaries (Simulated LLM call)
        self._enrich_tree(root_nodes, chunk_lookup)

        return PageIndexTree(
            doc_id=doc_id,
            root_nodes=root_nodes,
            total_pages=max([n.page_end for n in flat_nodes]) if flat_nodes else 0
        )

    def _enrich_tree(self, nodes: List[SectionNode], chunk_lookup: Dict[str, str]):
        for node in nodes:
            # Recursive enrichment
            # Get first few chunks of text for summary
            sample_content = [chunk_lookup.get(cid, "")[:200] for cid in node.chunk_ids[:2]]
            section_text = " ".join([node.title] + sample_content)
            
            node.summary = self.generate_section_summary(node.title, section_text)
            node.key_entities = self._extract_entities(section_text)
            
            if node.child_sections:
                self._enrich_tree(node.child_sections, chunk_lookup)



    def generate_section_summary(self, title: str, text: str) -> str:
        """Simulates a cheap LLM call for section summary."""
        # In a real FDE deployment, this would be an API call to Gemini Flash
        # For this challenge, we'll generate a programmatic summary or use a mock.
        return f"This section discusses {title} in detail, covering its implications and data."

    def _extract_entities(self, text: str) -> List[str]:
        # Simple regex for capitalized words / entities
        import re
        entities = re.findall(r'\b[A-Z][a-z]{3,}\b', text)
        return list(set(entities))[:5]

    def traverse(self, query: str, tree: PageIndexTree) -> List[SectionNode]:
        """Simple keyword-based traversal for top-N relevant sections."""
        query = query.lower()
        results = []
        for node in tree.root_nodes:
            score = 0
            if query in node.title.lower(): score += 10
            if node.summary and query in node.summary.lower(): score += 5
            for entity in node.key_entities:
                if query in entity.lower(): score += 3
            
            if score > 0:
                results.append((score, node))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:3]]

    def save_index(self, tree: PageIndexTree):
        out_dir = Path(".refinery/pageindex")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{tree.doc_id}.json"
        with open(path, 'w') as f:
            f.write(tree.model_dump_json(indent=2))
        return path
