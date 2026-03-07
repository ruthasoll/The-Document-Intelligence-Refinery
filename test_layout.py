from src.strategies.layout import LayoutExtractor
from src.models.profile import DocumentProfile, OriginType, LayoutComplexity
from pathlib import Path

def test():
    extractor = LayoutExtractor()
    doc_path = Path("data/fta_performance_survey_final_report_2022.pdf")
    profile = DocumentProfile(
        doc_id="test_fta",
        file_name="fta_performance_survey_final_report_2022.pdf",
        origin_type=OriginType.NATIVE_DIGITAL,
        layout_complexity=LayoutComplexity.MIXED,
        page_count=20
    )
    
    print(f"Testing LayoutExtractor on {doc_path.name}")
    try:
        doc = extractor.extract(doc_path, profile)
        print(f"Blocks: {len(doc.blocks)}")
        print(f"Tables: {len(doc.tables)}")
        print(f"Figures: {len(doc.figures)}")
        if doc.blocks:
            print(f"First block: {doc.blocks[0].text[:100]} (Header: {doc.blocks[0].is_header})")
    except Exception as e:
        print(f"Extraction failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
