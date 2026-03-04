# The Document Intelligence Refinery

Production-grade, multi-stage agentic pipeline that ingests a heterogeneous corpus of documents and emits structured, queryable knowledge.

## Project Structure
- `src/models/`: Pydantic schemas for the entire pipeline.
- `src/agents/`: Specialized agents (Triage, Extractor, Chunker, etc.).
- `src/strategies/`: Document extraction strategies (FastText, Layout, Vision).
- `rubric/`: Extraction rules and configuration thresholds.
- `.refinery/`: Generated document profiles and extraction ledger.

## Setup
1. Create and activate a virtual environment:
   ```bash
   python -m venv env
   .\env\Scripts\activate  # Windows
   ```
2. Install dependencies:
   ```bash
   pip install .
   ```

## Phase 1: Triage Agent
The Triage Agent classifies documents by:
- **Origin Type**: Native Digital vs. Scanned Image vs. Mixed.
- **Layout Complexity**: Single Column vs. Multi-Column vs. Table-Heavy.
- **Domain Hint**: Financial, Legal, Technical, Government, General.

Run triage verification:
```bash
$env:PYTHONPATH="."
python tests/test_triage.py
```

## Phase 2: Extraction Engine (Upcoming)
Implements the multi-strategy extraction layer with automated escalation.