# tests/test_query_agent.py
# Run from project root: $env:PYTHONPATH = "."; .\env\Scripts\python.exe tests/test_query_agent.py
import shutil
import sys
from pathlib import Path

# Fix encoding for Windows redirection
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.agents.vector_store import VectorStore
from src.agents.query_agent import QueryAgent, _classify_query
from src.agents.query_tools import pageindex_navigate, semantic_search, structured_query
from src.models.chunk import ChunkType, LogicalDocumentUnit, SectionRef

# --- Isolated test directories ---
TEST_VS_DIR = Path(".refinery/test_vector_store")


def _make_ldus():
    """Create a small set of test LDUs covering different chunk types."""
    return [
        LogicalDocumentUnit(
            content="Total Revenue for fiscal year 2023 was 2.4 billion birr.",
            chunk_type=ChunkType.TEXT,
            page_refs=[12],
            parent_section=SectionRef(title="Financial Highlights", level=1, page_number=12),
            metadata={"doc_id": "CBE_TEST"},
        ),
        LogicalDocumentUnit(
            content="| Item | 2023 |\n|---|---|\n| Revenue | 2.4B |\n| Profit | 0.5B |",
            chunk_type=ChunkType.TABLE,
            page_refs=[13],
            parent_section=SectionRef(title="Income Statement", level=2, page_number=13),
            metadata={"doc_id": "CBE_TEST"},
        ),
        LogicalDocumentUnit(
            content="The audit opinion concludes that the financial statements are presented fairly.",
            chunk_type=ChunkType.TEXT,
            page_refs=[2],
            parent_section=SectionRef(title="Audit Opinion", level=1, page_number=2),
            metadata={"doc_id": "AUDIT_TEST"},
        ),
    ]


# ---------------------------------------------------------------------------
# Router Tests
# ---------------------------------------------------------------------------

def test_router_classification():
    assert _classify_query("SELECT * FROM facts WHERE document_id = 'x'") == "structured"
    assert _classify_query("What sections does this document have?") == "navigate"
    assert _classify_query("What was the total revenue in 2023?") == "structured"
    assert _classify_query("Explain the main findings of the assessment") == "search"
    print("OK: router_classification")


# ---------------------------------------------------------------------------
# Vector Store Tests
# ---------------------------------------------------------------------------

def test_vector_store_ingest_and_search():
    if TEST_VS_DIR.exists():
        shutil.rmtree(TEST_VS_DIR)

    vs = VectorStore(store_dir=TEST_VS_DIR)
    ldus = _make_ldus()
    count = vs.ingest(ldus, "CBE_TEST")
    assert count == 3, f"Expected 3 vectors, got {count}"
    assert vs.index.ntotal == 3

    # Search for something related to revenue
    results = vs.search("annual revenue fiscal year", top_k=2)
    assert len(results) >= 1
    assert results[0].score > 0.0
    assert results[0].provenance.doc_id == "CBE_TEST"
    print(f"OK: vector_store_ingest_and_search (top score={results[0].score:.3f})")


def test_semantic_search_tool():
    vs = VectorStore(store_dir=TEST_VS_DIR)
    # Re-ingest just in case the first test didn't flush correctly or directory was cleared
    # But it should already be there. Let's just use what's there.
    results = semantic_search("audit opinion financial statements", top_k=3, vector_store=vs)
    if not results:
         print(f"DEBUG: semantic_search returned 0 results. Index total: {vs.index.ntotal}")
    assert len(results) >= 1, "Should return at least one result"
    top = results[0]
    assert "content" in top
    assert "provenance" in top
    assert top["provenance"]["doc_id"] == "CBE_TEST" # Because they were all ingested as CBE_TEST in the first test
    print(f"OK: semantic_search_tool (top chunk: '{top['content'][:60]}...')")


def test_doc_id_filter():
    vs = VectorStore(store_dir=TEST_VS_DIR)
    results = semantic_search("revenue financial", top_k=5, doc_id_filter="CBE_TEST", vector_store=vs)
    assert len(results) > 0, "Should have results for CBE_TEST"
    for r in results:
        assert r["provenance"]["doc_id"] == "CBE_TEST"
    print(f"OK: doc_id_filter ({len(results)} results, all from CBE_TEST)")


# ---------------------------------------------------------------------------
# Global Patching Helper
# ---------------------------------------------------------------------------

def patch_vs():
    import src.agents.query_tools as qt
    import src.agents.query_agent as qa
    
    class MockVS(VectorStore):
        def __init__(self, **kwargs):
            # Enforce use of TEST_VS_DIR
            kwargs.pop('store_dir', None)
            super().__init__(store_dir=TEST_VS_DIR, **kwargs)

    original_vs_qt = qt.VectorStore
    original_vs_qa = qa.VectorStore
    
    qt.VectorStore = MockVS
    qa.VectorStore = MockVS
    return original_vs_qt, original_vs_qa

def unpatch_vs(original_vs_qt, original_vs_qa):
    import src.agents.query_tools as qt
    import src.agents.query_agent as qa
    qt.VectorStore = original_vs_qt
    qa.VectorStore = original_vs_qa


# ---------------------------------------------------------------------------
# Full Agent Cycle Test
# ---------------------------------------------------------------------------

def test_agent_query_response_shape():
    orig_qt, orig_qa = patch_vs()
    try:
        agent = QueryAgent(top_k=3)
        response = agent.query("What was the total revenue reported?")
        assert response.question == "What was the total revenue reported?"
        assert response.answer
        assert response.tool_used in ("search", "structured", "navigate", "multi")
        assert isinstance(response.provenance, list)
        print(f"OK: agent_query_response_shape (tool={response.tool_used}, "
              f"provenance_count={len(response.provenance)})")
    finally:
        unpatch_vs(orig_qt, orig_qa)


# ---------------------------------------------------------------------------
# Audit Claim Test
# ---------------------------------------------------------------------------

def test_audit_claim():
    orig_qt, orig_qa = patch_vs()
    try:
        agent = QueryAgent()
        result = agent.audit_claim("Revenue was 2.4 billion birr in 2023")
        assert hasattr(result, "verified")
        assert hasattr(result, "reason")
        assert hasattr(result, "sources")
        assert isinstance(result.confidence, float)
        # It should be verified because of our test data
        assert result.verified is True, f"Claim should be verified. Reason: {result.reason}"
        print(f"OK: audit_claim (verified={result.verified}, "
              f"confidence={result.confidence:.2f}, reason='{result.reason[:60]}')")
    finally:
        unpatch_vs(orig_qt, orig_qa)


if __name__ == "__main__":
    import traceback
    print("=" * 55)
    print("Phase 4: Query Agent Tests")
    print("=" * 55)
    
    tests = [
        ("Router Classification", test_router_classification),
        ("Vector Store Ingest & Search", test_vector_store_ingest_and_search),
        ("Semantic Search Tool", test_semantic_search_tool),
        ("Doc ID Filter", test_doc_id_filter),
        ("Agent Query Response Shape", test_agent_query_response_shape),
        ("Audit Claim", test_audit_claim),
    ]
    
    passed = 0
    for name, func in tests:
        try:
            print(f"Running {name}...")
            func()
            passed += 1
        except Exception:
            print(f"FAIL: {name}")
            traceback.print_exc()
            
    print("=" * 55)
    if passed == len(tests):
        print("All Query Agent tests PASSED OK")
    else:
        print(f"{passed}/{len(tests)} tests passed.")

    # Cleanup
    if TEST_VS_DIR.exists():
        try:
            shutil.rmtree(TEST_VS_DIR)
        except:
             pass
