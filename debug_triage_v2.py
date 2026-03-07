import pdfplumber
from pathlib import Path

docs = [
    "data/CBE ANNUAL REPORT 2023-24.pdf",
    "data/fta_performance_survey_final_report_2022.pdf",
    "data/tax_expenditure_ethiopia_2021_22.pdf"
]

for doc_path in docs:
    p = Path(doc_path)
    if not p.exists(): continue
    
    try:
        with pdfplumber.open(p) as pdf:
            print(f"\nDoc: {p.name}")
            for i in range(min(5, len(pdf.pages))):
                page = pdf.pages[i]
                page_area = float(page.width * page.height)
                char_count = len(page.chars)
                image_area = sum([float(i.get('width', 0) * i.get('height', 0)) for i in page.images])
                
                char_density = char_count / page_area
                image_ratio = image_area / page_area
                print(f"  Page {i}: Chars={char_count}, Density={char_density:.6f}, ImgRatio={image_ratio:.2f}")
    except Exception as e:
        print(f"Error {p.name}: {e}")
