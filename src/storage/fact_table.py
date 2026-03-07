"""
Phase 4 – FactTable Extractor.
Detects financial/structured tables in LDUs, extracts key-value pairs,
and persists to a SQLite database at .refinery/facts.db
"""
import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import List, Optional

from src.models.chunk import ChunkType, LogicalDocumentUnit
from src.models.query import FactRecord

logger = logging.getLogger(__name__)

FINANCIAL_KEYWORDS = [
    "revenue", "profit", "loss", "assets", "liabilities", "equity",
    "expenditure", "income", "expense", "cash", "budget", "surplus",
    "deficit", "tax", "dividend", "earnings", "ebitda", "net",
]

DEFAULT_DB = Path(".refinery/facts.db")

DDL = """
CREATE TABLE IF NOT EXISTS facts (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id          TEXT NOT NULL,
    fact_key             TEXT NOT NULL,
    fact_value           TEXT NOT NULL,
    page_number          INTEGER,
    chunk_hash           TEXT,
    extraction_timestamp TEXT
);
CREATE INDEX IF NOT EXISTS idx_document_id ON facts(document_id);
CREATE INDEX IF NOT EXISTS idx_fact_key    ON facts(fact_key);
"""


class FactTableExtractor:
    """Extracts key-value facts from TABLE-type LDUs and stores them in SQLite."""

    def __init__(self, db_path: str | Path = DEFAULT_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_financial_table(self, ldu: LogicalDocumentUnit) -> bool:
        """Returns True if the LDU is a TABLE with financial keywords."""
        if ldu.chunk_type != ChunkType.TABLE:
            return False
        content_lower = ldu.content.lower()
        return any(kw in content_lower for kw in FINANCIAL_KEYWORDS)

    def extract_key_values(self, ldu: LogicalDocumentUnit) -> List[FactRecord]:
        """
        Parse a Markdown table LDU into FactRecord key-value pairs.
        Handles two formats:
          - Two-column (key | value) tables
          - Header-row tables where header cells become keys and data values are facts
        """
        records: List[FactRecord] = []
        page = ldu.page_refs[0] if ldu.page_refs else 0
        lines = [l.strip() for l in ldu.content.splitlines() if l.strip()]

        rows = [l for l in lines if l.startswith("|") and not re.match(r"\|[-| ]+\|", l)]
        if not rows:
            return records

        def parse_row(line: str) -> List[str]:
            return [c.strip() for c in line.strip("|").split("|")]

        # Identify header row
        header = parse_row(rows[0]) if rows else []
        data_rows = rows[1:] if len(rows) > 1 else []

        if len(header) == 2:
            # Two-column key | value table
            for row in data_rows:
                cells = parse_row(row)
                if len(cells) >= 2 and cells[0] and cells[1]:
                    records.append(FactRecord(
                        document_id=ldu.metadata.get("doc_id", "unknown"),
                        fact_key=self._clean(cells[0]),
                        fact_value=self._clean(cells[1]),
                        page_number=page,
                        chunk_hash=ldu.content_hash,
                    ))
        elif len(header) > 2:
            # Multi-column: first column is the row label, remaining columns are values
            for row in data_rows:
                cells = parse_row(row)
                if not cells:
                    continue
                row_label = self._clean(cells[0])
                for i, col_header in enumerate(header[1:], start=1):
                    if i < len(cells) and cells[i]:
                        key = f"{row_label} – {self._clean(col_header)}"
                        records.append(FactRecord(
                            document_id=ldu.metadata.get("doc_id", "unknown"),
                            fact_key=key,
                            fact_value=self._clean(cells[i]),
                            page_number=page,
                            chunk_hash=ldu.content_hash,
                        ))

        return records

    def save_to_sqlite(self, records: List[FactRecord]) -> int:
        """Upsert FactRecords to SQLite. Returns number of rows inserted."""
        if not records:
            return 0
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            rows = [
                (r.document_id, r.fact_key, r.fact_value,
                 r.page_number, r.chunk_hash, r.extraction_timestamp)
                for r in records
            ]
            cur.executemany(
                "INSERT INTO facts (document_id, fact_key, fact_value, page_number, chunk_hash, extraction_timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows
            )
            conn.commit()
            logger.info(f"Saved {len(records)} fact records to {self.db_path}")
            return len(records)
        finally:
            conn.close()

    def extract_and_save(self, ldus: List[LogicalDocumentUnit], doc_id: str) -> int:
        """Convenience method: extract facts from all relevant LDUs and save."""
        all_records: List[FactRecord] = []
        for ldu in ldus:
            if self.detect_financial_table(ldu):
                # Attach doc_id to metadata for extract_key_values
                ldu.metadata["doc_id"] = doc_id
                all_records.extend(self.extract_key_values(ldu))

        count = self.save_to_sqlite(all_records)
        logger.info(f"[{doc_id}] Extracted {count} facts across {len(ldus)} LDUs.")
        return count

    def query_facts(self, sql: str) -> List[dict]:
        """Execute a raw SQL SELECT against the facts DB and return list of dicts."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(sql)
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"SQL error: {e} | query: {sql}")
            return [{"error": str(e)}]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(DDL)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _clean(text: str) -> str:
        """Strip markdown formatting and excess whitespace from cell text."""
        text = re.sub(r"\*+", "", text)   # bold/italic
        text = re.sub(r"`", "", text)      # code
        return text.strip()
