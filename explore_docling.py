from docling.document_converter import DocumentConverter
import time
import sys
import pypdf
import os

files = [
    "data/CBE ANNUAL REPORT 2023-24.pdf",
    "data/Audit Report - 2023.pdf",
    "data/fta_performance_survey_final_report_2022.pdf",
    "data/tax_expenditure_ethiopia_2021_22.pdf"
]

converter = DocumentConverter()

with open("docling_analysis_results.txt", "w", encoding="utf-8") as out_file:
    for file in files:
        out_file.write(f"\n=============================================\n")
        out_file.write(f"Analyzing with Docling: {file}\n")
        out_file.write(f"=============================================\n")
        try:
            # Create a 5-page subset to avoid OOM
            temp_pdf_path = f"temp_subset_for_docling.pdf"
            reader = pypdf.PdfReader(file)
            writer = pypdf.PdfWriter()
            num_pages = len(reader.pages)
            for i in range(min(5, num_pages)):
                writer.add_page(reader.pages[i])
            with open(temp_pdf_path, "wb") as f_out:
                writer.write(f_out)
            
            start_time = time.time()
            result = converter.convert(temp_pdf_path)
            doc = result.document
            processing_time = time.time() - start_time
            
            num_tables = len(doc.tables) if hasattr(doc, 'tables') else 0
            num_texts = len(doc.texts) if hasattr(doc, 'texts') else 0
            num_pictures = len(doc.pictures) if hasattr(doc, 'pictures') else 0
            
            out_file.write(f"Processing time (first 5 pages): {processing_time:.2f} seconds\n")
            out_file.write(f"Extracted Text Blocks: {num_texts}\n")
            out_file.write(f"Extracted Tables: {num_tables}\n")
            out_file.write(f"Extracted Pictures/Figures: {num_pictures}\n")
            
            if num_tables > 0:
                out_file.write(f"\n  First Table Snippet:\n")
                first_table = doc.tables[0]
                if hasattr(first_table, 'export_to_markdown'):
                    out_file.write(f"    {first_table.export_to_markdown()[:500]}...\n")
                    
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
                
        except Exception as e:
            out_file.write(f"Error reading {file}: {e}\n")
