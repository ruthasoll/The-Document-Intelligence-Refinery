import os
import json
import time
from pathlib import Path
from src.agents.triage import DocumentTriageAgent
from src.agents.extractor import ExtractionRouter

def verify_extraction():
    print("=== Phase 2: Extraction Engine Verification ===")
    
    triage_agent = DocumentTriageAgent()
    router = ExtractionRouter()
    
    data_dir = Path("data")
    if not data_dir.exists():
        print("Data directory not found.")
        return
        
    pdf_files = list(data_dir.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found in data directory.")
        return
        
    print(f"Found {len(pdf_files)} documents. Starting extraction...")
    
    results = []
    
    for pdf_path in pdf_files[:5]: # Test with first 5 to keep it fast
        print(f"\nProcessing: {pdf_path.name}")
        
        # 1. Triage
        profile = triage_agent.profile_document(pdf_path)
        print(f"Triage: {profile.origin_type} | {profile.layout_complexity}")
        
        # 2. Extract
        start_time = time.time()
        try:
            doc = router.route_and_extract(pdf_path, profile)
            elapsed = time.time() - start_time
            
            print(f"Extraction strategy: {doc.pages[0].strategy_used if doc.pages else 'N/A'}")
            print(f"Blocks: {len(doc.blocks)}, Tables: {len(doc.tables)}")
            print(f"Time: {elapsed:.2f}s, Time in Doc: {doc.processing_time_s:.2f}s")
            
            # Save a snippet of the output
            out_file = Path(f".refinery/extracted_{profile.doc_id}.json")
            with open(out_file, "w") as f:
                f.write(doc.model_dump_json(indent=2))
            
            results.append({
                "file": pdf_path.name,
                "status": "SUCCESS",
                "strategy": doc.pages[0].strategy_used if doc.pages else "unknown",
                "tables": len(doc.tables)
            })
            
        except Exception as e:
            print(f"Extraction FAILED: {e}")
            results.append({
                "file": pdf_path.name,
                "status": "FAILED",
                "error": str(e)
            })

    print("\n=== Verification Summary ===")
    for res in results:
        status_icon = "[OK]" if res["status"] == "SUCCESS" else "[FAIL]"
        print(f"{status_icon} {res['file']}: {res['status']} ({res.get('strategy', 'N/A')}) - Tables: {res.get('tables', 0)}")

if __name__ == "__main__":
    verify_extraction()
