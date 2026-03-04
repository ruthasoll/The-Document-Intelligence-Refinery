from src.agents.triage import DocumentTriageAgent
import json
from pathlib import Path

def test_triage():
    agent = DocumentTriageAgent()
    
    files = [
        "data/CBE ANNUAL REPORT 2023-24.pdf",
        "data/Audit Report - 2023.pdf",
        "data/fta_performance_survey_final_report_2022.pdf",
        "data/tax_expenditure_ethiopia_2021_22.pdf"
    ]
    
    # Ensure .refinery/profiles exists
    Path(".refinery/profiles").mkdir(parents=True, exist_ok=True)
    
    results = []
    for f in files:
        print(f"\nTriaging {f}...")
        try:
            profile = agent.profile_document(f)
            print(agent.explain_classification(profile))
            
            # Save to .refinery/profiles/
            profile_path = Path(f".refinery/profiles/{profile.doc_id}.json")
            with open(profile_path, "w") as out:
                out.write(profile.model_dump_json(indent=2))
            
            results.append(profile)
        except Exception as e:
            print(f"Error triaging {f}: {e}")

    # Basic assertions for 4 classes
    # Class A: CBE - expect NATIVE_DIGITAL
    # Class B: Audit - expect SCANNED_IMAGE
    # Class C: FTA - expect MIXED
    # Class D: Tax - expect NATIVE_DIGITAL or MIXED depending on thresholds
    
if __name__ == "__main__":
    test_triage()
