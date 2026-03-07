# tests/test_fact_table.py
# Run from project root: $env:PYTHONPATH = "."; .\env\Scripts\python.exe tests/test_fact_table.py
import os
import sqlite3
from pathlib import Path

from src.storage.fact_table import FactTableExtractor
from src.models.chunk import ChunkType, LogicalDocumentUnit

# --- Use a temp DB for tests ---
TEST_DB = Path(".refinery/test_facts.db")


def make_table_ldu(content: str, page: int = 1) -> LogicalDocumentUnit:
    return LogicalDocumentUnit(
        content=content,
        chunk_type=ChunkType.TABLE,
        page_refs=[page],
        metadata={"doc_id": "test_doc"},
    )


def test_detect_financial_table():
    fte = FactTableExtractor(db_path=TEST_DB)

    financial_ldu = make_table_ldu("| Revenue | 100M |\n| Profit | 20M |")
    non_financial_ldu = make_table_ldu("| Name | Age |\n| Alice | 30 |")
    text_ldu = LogicalDocumentUnit(
        content="This is plain text.",
        chunk_type=ChunkType.TEXT,
        page_refs=[1],
    )

    assert fte.detect_financial_table(financial_ldu) is True,  "Should detect revenue table"
    assert fte.detect_financial_table(non_financial_ldu) is False, "Should not detect non-financial"
    assert fte.detect_financial_table(text_ldu) is False, "Should not detect text LDU"
    print("✅ PASS: detect_financial_table")


def test_extract_two_column():
    fte = FactTableExtractor(db_path=TEST_DB)
    ldu = make_table_ldu(
        "| Item | Value |\n|---|---|\n| Total Revenue | 1,234 M |\n| Net Profit | 456 M |",
        page=5,
    )
    records = fte.extract_key_values(ldu)
    assert len(records) == 2, f"Expected 2 records, got {len(records)}"
    assert records[0].fact_key == "Total Revenue"
    assert records[0].fact_value == "1,234 M"
    assert records[0].page_number == 5
    print("✅ PASS: extract_two_column_table")


def test_extract_multi_column():
    fte = FactTableExtractor(db_path=TEST_DB)
    ldu = make_table_ldu(
        "| Category | 2022 | 2023 |\n|---|---|---|\n| Revenue | 100 | 120 |\n| Expenses | 80 | 90 |",
        page=7,
    )
    records = fte.extract_key_values(ldu)
    keys = [r.fact_key for r in records]
    assert "Revenue – 2022" in keys
    assert "Revenue – 2023" in keys
    assert "Expenses – 2022" in keys
    print(f"✅ PASS: extract_multi_column_table ({len(records)} records)")


def test_save_and_query():
    fte = FactTableExtractor(db_path=TEST_DB)
    ldu = make_table_ldu("| Revenue | 999 B |\n|---|---|\n| Net Profit | 111 B |")
    records = fte.extract_key_values(ldu)
    saved = fte.save_to_sqlite(records)
    assert saved == len(records), f"Saved {saved} but expected {len(records)}"

    rows = fte.query_facts("SELECT fact_key, fact_value FROM facts WHERE document_id = 'test_doc'")
    assert len(rows) >= 1
    assert "error" not in rows[0]
    print(f"✅ PASS: save_and_query ({saved} rows saved, {len(rows)} rows queried)")


def test_extract_and_save_pipeline():
    fte = FactTableExtractor(db_path=TEST_DB)
    ldus = [
        make_table_ldu("| Revenue | 500M |\n|---|---|\n| Tax | 50M |"),
        make_table_ldu("| Name | Score |\n|---|---|\n| Alice | 99 |"),  # Non-financial, skipped
    ]
    count = fte.extract_and_save(ldus, "pipeline_test_doc")
    assert count >= 1, "Should extract at least 1 fact from financial table"
    print(f"✅ PASS: extract_and_save_pipeline ({count} facts)")


if __name__ == "__main__":
    # Clean up any previous test DB
    if TEST_DB.exists():
        TEST_DB.unlink()

    print("=" * 50)
    print("Phase 4: FactTable Tests")
    print("=" * 50)
    test_detect_financial_table()
    test_extract_two_column()
    test_extract_multi_column()
    test_save_and_query()
    test_extract_and_save_pipeline()
    print("=" * 50)
    print("All FactTable tests PASSED ✅")

    # Cleanup
    if TEST_DB.exists():
        TEST_DB.unlink()
