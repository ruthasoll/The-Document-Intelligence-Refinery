from src.agents.triage import DocumentTriageAgent
from pathlib import Path
import json

def profile_corpus():
    agent = DocumentTriageAgent()
    data_dir = Path("data")
    
    # Selected 12 files representing 4 classes
    selected_files = [
        # Class A: Annual Reports
        "CBE ANNUAL REPORT 2023-24.pdf",
        "CBE Annual Report 2017-18.pdf",
        "CBE Annual Report 2015-16.pdf",
        
        # Class B: Audited Financial Statements (often scanned)
        "Audit Report - 2023.pdf",
        "2021_Audited_Financial_Statement_Report.pdf",
        "2018_Audited_Financial_Statement_Report.pdf",
        
        # Class C: Technical/Assessment
        "fta_performance_survey_final_report_2022.pdf",
        "20191010_Pharmaceutical-Manufacturing-Opportunites-in-Ethiopia_VF.pdf",
        "Company_Profile_2024_25.pdf",
        
        # Class D: Tax/Fiscal/Budget
        "tax_expenditure_ethiopia_2021_22.pdf",
        "2013-E.C-Assigned-regular-budget-and-expense.pdf",
        "2013-E.C-Audit-finding-information.pdf"
    ]
    
    export_dir = Path(".refinery/profiles")
    export_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"--- Profiling {len(selected_files)} documents ---")
    
    for filename in selected_files:
        path = data_dir / filename
        if not path.exists():
            print(f"Warning: {filename} not found in data/")
            continue
            
        try:
            profile = agent.profile_document(str(path))
            profile_path = export_dir / f"{profile.doc_id}.json"
            
            with open(profile_path, "w") as f:
                f.write(profile.model_dump_json(indent=2))
            
            print(f"Propiled: {filename} -> {profile.origin_type.value}, {profile.domain_hint.value}")
        except Exception as e:
            print(f"Error profiling {filename}: {e}")

if __name__ == "__main__":
    profile_corpus()
