import sys
from pathlib import Path
from src.agents.triage import DocumentTriageAgent
from src.agents.extractor import ExtractionRouter
import json

def main():
    docs = {
        "Class_A_Financial": "data/CBE ANNUAL REPORT 2023-24.pdf",
        "Class_B_Scanned": "data/Audit Report - 2023.pdf", 
        "Class_C_Technical": "data/fta_performance_survey_final_report_2022.pdf",
        "Class_D_Fiscal": "data/tax_expenditure_ethiopia_2021_22.pdf"
    }

    triage_agent = DocumentTriageAgent()
    router = ExtractionRouter()

    for class_name, path_str in docs.items():
        path = Path(path_str)
        if not path.exists():
            print(f"Skipping {class_name}: {path} not found")
            continue

        print(f"\n=== Processing {class_name} ({path.name}) ===")
        
        # 1. Triage
        profile = triage_agent.profile_document(path)
        print(f"Triage: {profile.origin_type.value}, {profile.layout_complexity.value}")

        # 2. Start-to-Finish Pipeline
        doc, ldus, index_tree = router.process_complete_pipeline(path, profile)

        if doc:
            # Save chunks explicitly
            router.chunker.save_chunks(doc.doc_id, ldus)
            print(f"Success! Chunks: {len(ldus)}, Sections: {len(index_tree.root_nodes)}")
            
            # Show a sample LDU
            if ldus:
                sample = ldus[0]
                print(f"Sample LDU ({sample.chunk_type}): {sample.content[:100]}...")
        else:
            print(f"Failed to process {class_name}")

if __name__ == "__main__":
    main()
