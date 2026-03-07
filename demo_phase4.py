"""
Phase 4 Demonstration – End-to-End Query Agent.
This script demonstrates the full pipeline:
1. Ingesting sample LDUs into the Vector Store and Fact Table.
2. Querying the Query Agent for different types of information.
3. Performing a fact audit.
"""
import sys
import os
from pathlib import Path

# Fix path to include src
sys.path.append(os.getcwd())

from src.agents.query_agent import QueryAgent
from src.agents.vector_store import VectorStore
from src.storage.fact_table import FactTableExtractor
from src.models.chunk import LogicalDocumentUnit, ChunkType, SectionRef

def run_demo():
    print("=== Document Intelligence Refinery: Phase 4 Demo ===\n")
    
    # 1. Setup Data
    vs_dir = Path(".refinery/demo_vector_store")
    db_path = Path(".refinery/demo_facts.db")
    
    # Cleanup previous demo run
    if vs_dir.exists():
        import shutil
        shutil.rmtree(vs_dir)
    if db_path.exists():
        db_path.unlink()

    vs = VectorStore(store_dir=vs_dir)
    fact_ext = FactTableExtractor(db_path=db_path)
    
    # Sample Data
    ldus = [
        LogicalDocumentUnit(
            content="Historical Profit in 2022 was 1.8 billion birr. Current Profit in 2023 increased to 2.4 billion birr.",
            chunk_type=ChunkType.TEXT,
            page_refs=[5],
            content_hash="h1",
            metadata={"doc_id": "CBE_REPORT"}
        ),
        LogicalDocumentUnit(
            content="| Key Performance | 2023 |\n|---|---|\n| Revenue | 2.4B |\n| Operating Profit | 0.8B |",
            chunk_type=ChunkType.TABLE,
            page_refs=[6],
            content_hash="h2",
            metadata={"doc_id": "CBE_REPORT"}
        )
    ]
    
    print("[1] Ingesting sample data into Vector Store and Fact Table...")
    vs.ingest(ldus, "CBE_REPORT")
    fact_ext.extract_and_save(ldus, "CBE_REPORT")
    
    # 2. Querying
    agent = QueryAgent()
    
    # Patch agent to use demo paths in its internal tool calls
    import src.agents.query_tools as qt
    import src.agents.query_agent as qa
    qt.DEFAULT_DB = db_path
    
    # We'll use the pre-loaded VS by passing it to semantic_search internally 
    # OR we can patch the class as we did in tests
    class DemoVS(VectorStore):
        def __init__(self, **kwargs):
            super().__init__(store_dir=vs_dir)
    qt.VectorStore = DemoVS
    qa.VectorStore = DemoVS

    print("\n[2] Semantic Search Query:")
    q1 = "What was the profit in 2023?"
    res1 = agent.query(q1)
    print(f"Question: {q1}")
    print(f"Tool used: {res1.tool_used}")
    print(f"Answer:\n{res1.answer}")

    print("\n[3] Structured SQL Query:")
    q2 = "SELECT fact_key, fact_value FROM facts WHERE fact_key LIKE '%Revenue%'"
    res2 = agent.query(q2)
    print(f"Question: {q2}")
    print(f"Tool used: {res2.tool_used}")
    print(f"Answer:\n{res2.answer}")

    print("\n[4] Fact Audit:")
    claim = "Profit in 2023 was 2.4 billion birr"
    audit = agent.audit_claim(claim)
    print(f"Claim: {claim}")
    print(f"Verified: {audit.verified}")
    print(f"Confidence: {audit.confidence}")
    print(f"Reason: {audit.reason}")
    if audit.sources:
        print(f"Source: {audit.sources[0].document_name} p.{audit.sources[0].page_numbers}")

    print("\nDemo Completed successfully.")

if __name__ == "__main__":
    run_demo()
