import pdfplumber

files = [
    "data/CBE ANNUAL REPORT 2023-24.pdf",
    "data/Audit Report - 2023.pdf",
    "data/fta_performance_survey_final_report_2022.pdf",
    "data/tax_expenditure_ethiopia_2021_22.pdf"
]

with open("pdf_table_analysis.txt", "w", encoding="utf-8") as out_file:
    for file in files:
        out_file.write(f"\n=============================================\n")
        out_file.write(f"Analyzing Tables in: {file}\n")
        out_file.write(f"=============================================\n")
        try:
            with pdfplumber.open(file) as pdf:
                # Sample up to first 20 pages
                for i in range(min(20, len(pdf.pages))):
                    page = pdf.pages[i]
                    tables = page.find_tables()
                    if tables:
                        out_file.write(f"  Page {i+1}: Found {len(tables)} tables.\n")
                        for idx, table in enumerate(tables):
                            out_file.write(f"    Table {idx+1} bbox: {table.bbox}\n")
        except Exception as e:
            out_file.write(f"Error reading {file}: {e}\n")
