from docling.document_converter import DocumentConverter
from pathlib import Path
import os

def debug():
    converter = DocumentConverter()
    doc_path = "data/Consumer Price Index August 2025.pdf"
    result = converter.convert(doc_path)
    doc = result.document
    if doc.tables:
        tbl = doc.tables[0]
        if tbl.data.table_cells:
            cell = tbl.data.table_cells[0]
            print(f"Row/Col attributes: {[a for a in dir(cell) if 'row' in a.lower() or 'col' in a.lower()]}")
            print(f"Sample data: {cell.text[:20] if hasattr(cell, 'text') else 'N/A'}")


if __name__ == "__main__":
    debug()
