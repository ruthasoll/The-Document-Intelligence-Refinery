from pydantic import ValidationError
from src.models.profile import BoundingBox, PageMetadata, ExtractedDocument, DocumentProfile, OriginType, LayoutComplexity
from src.strategies.fast_text import FastTextExtractor

def test_bbox_validation():
    # Valid BBox
    bbox = BoundingBox(x0=0, y0=0, x1=100, y1=100, page_number=1)
    assert bbox.x1 > bbox.x0

    # Inverted x-range: Phase 2.5 Normalization Patch swaps x0/x1 silently
    bbox_inv_x = BoundingBox(x0=100, y0=0, x1=50, y1=100, page_number=1)
    assert bbox_inv_x.x0 == 50 and bbox_inv_x.x1 == 100, (
        f"Expected x0=50, x1=100 after normalization, got x0={bbox_inv_x.x0}, x1={bbox_inv_x.x1}"
    )

    # Inverted y-range: normalized silently
    bbox_inv_y = BoundingBox(x0=0, y0=100, x1=100, y1=50, page_number=1)
    assert bbox_inv_y.y0 == 50 and bbox_inv_y.y1 == 100, (
        f"Expected y0=50, y1=100 after normalization, got y0={bbox_inv_y.y0}, y1={bbox_inv_y.y1}"
    )

def test_pagemetadata_constraints():
    # Invalid image ratio
    try:
        PageMetadata(
            page_number=1, width=100, height=100, char_count=0, 
            char_density=0, image_area_ratio=1.5, images_count=0, 
            tables_count=0, strategy_used="test"
        )
        assert False, "Should have raised ValidationError for invalid image ratio"
    except ValidationError:
        pass

def test_fast_text_signals():
    extractor = FastTextExtractor()
    
    # Test garbage signal
    garbage_text = "!@#$%^&*()"
    score = extractor._calculate_signals(garbage_text, [], len(garbage_text), 10000)
    # Alnum ratio will be 0, weight is 0.4. density signal will be around 0.85. structural 1.0.
    # Total roughly: (0.85*0.3) + (0*0.4) + (1.0*0.3) = 0.255 + 0.3 = 0.555
    assert score < 0.7 

    # Test clean text
    clean_text = "This is a clean sentence with high alphanumeric content."
    score = extractor._calculate_signals(clean_text, [10, 20, 30, 40, 50, 60], len(clean_text), 10000)
    assert score > 0.8

if __name__ == "__main__":
    # Simple manual run if pytest not handy
    try:
        test_bbox_validation()
        print("BBox Validation Passed")
        test_pagemetadata_constraints()
        print("PageMetadata Constraints Passed")
        test_fast_text_signals()
        print("FastText Signals Passed")
    except Exception as e:
        print(f"Tests FAILED: {e}")
