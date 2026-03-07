# No pytest dependency — run directly from project root
# Usage: .\env\Scripts\python.exe tests/test_hierarchy.py
from src.models.chunk import LogicalDocumentUnit, ChunkType, SectionRef
from src.agents.indexer import PageIndexBuilder


def test_hierarchical_nesting():
    builder = PageIndexBuilder()

    # Level 1 Header: Introduction
    h1 = LogicalDocumentUnit(
        content="Introduction",
        chunk_type=ChunkType.HEADER,
        page_refs=[1],
        parent_section=SectionRef(title="Introduction", level=1, page_number=1)
    )
    # Body text under Introduction
    c1 = LogicalDocumentUnit(
        content="This is the introduction text.",
        chunk_type=ChunkType.TEXT,
        page_refs=[1]
    )
    # Level 2 Header: Background (child of Introduction)
    h2 = LogicalDocumentUnit(
        content="Background",
        chunk_type=ChunkType.HEADER,
        page_refs=[2],
        parent_section=SectionRef(title="Background", level=2, page_number=2)
    )
    # Body text under Background
    c2 = LogicalDocumentUnit(
        content="This is background text.",
        chunk_type=ChunkType.TEXT,
        page_refs=[2]
    )
    # Level 1 Header: Methodology (sibling of Introduction)
    h3 = LogicalDocumentUnit(
        content="Methodology",
        chunk_type=ChunkType.HEADER,
        page_refs=[3],
        parent_section=SectionRef(title="Methodology", level=1, page_number=3)
    )

    ldus = [h1, c1, h2, c2, h3]
    tree = builder.build_index("test_doc", ldus)

    # --- Assertions ---
    assert len(tree.root_nodes) == 2, (
        f"Expected 2 root nodes, got {len(tree.root_nodes)}: "
        f"{[n.title for n in tree.root_nodes]}"
    )
    assert tree.root_nodes[0].title == "Introduction"
    assert tree.root_nodes[1].title == "Methodology"

    intro_node = tree.root_nodes[0]
    assert len(intro_node.child_sections) == 1, (
        f"Expected 1 child section under Introduction, "
        f"got {len(intro_node.child_sections)}"
    )
    assert intro_node.child_sections[0].title == "Background"
    assert intro_node.child_sections[0].metadata["level"] == 2

    print("✅ PASS: Hierarchical nesting test PASSED")
    print(f"   Root sections: {[n.title for n in tree.root_nodes]}")
    print(f"   Children of Introduction: {[n.title for n in intro_node.child_sections]}")


def test_flat_single_level():
    """All headers at the same level should all be root nodes."""
    builder = PageIndexBuilder()

    headers = [
        LogicalDocumentUnit(
            content=f"Section {i}",
            chunk_type=ChunkType.HEADER,
            page_refs=[i],
            parent_section=SectionRef(title=f"Section {i}", level=1, page_number=i)
        )
        for i in range(1, 4)
    ]
    tree = builder.build_index("flat_doc", headers)

    assert len(tree.root_nodes) == 3, (
        f"Expected 3 root nodes, got {len(tree.root_nodes)}"
    )
    print("✅ PASS: Flat single-level test PASSED")
    print(f"   Root sections: {[n.title for n in tree.root_nodes]}")


def test_empty_ldus():
    """No LDUs should produce an empty tree without crashing."""
    builder = PageIndexBuilder()
    tree = builder.build_index("empty_doc", [])

    assert len(tree.root_nodes) == 0
    assert tree.total_pages == 0
    print("✅ PASS: Empty LDU test PASSED")


if __name__ == "__main__":
    print("=" * 50)
    print("Phase 3 Hierarchy Verification Tests")
    print("=" * 50)
    test_hierarchical_nesting()
    test_flat_single_level()
    test_empty_ldus()
    print("=" * 50)
    print("All tests PASSED ✅")
