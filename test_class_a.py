from src.agents.triage import DocumentTriageAgent
from src.agents.extractor import ExtractionRouter
from pathlib import Path

def main():
    router = ExtractionRouter()
    triage = DocumentTriageAgent()
    path = Path("data/CBE ANNUAL REPORT 2023-24.pdf")
    profile = triage.profile_document(path)
    print(f"Triage: {profile.origin_type.value}, {profile.layout_complexity.value}")
    
    doc, ldus, index = router.process_complete_pipeline(path, profile)
    print(f"Chunks: {len(ldus)}, Sections: {len(index.root_nodes)}")
    
    saved_path = router.chunker.save_chunks(doc.doc_id, ldus)
    print(f"Saved to: {saved_path}")
    import os
    print(f"File size: {os.path.getsize(saved_path)} bytes")
    
    if ldus:
        print(f"Chunk 0 content: {ldus[0].content[:200]}")

if __name__ == "__main__":
    main()
