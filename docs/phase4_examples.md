# Phase 4: Query Agent & Provenance Examples

This document demonstrates the Query Agent's capabilities across the four primary document classes in the Document Intelligence Refinery. Every answer includes a full **ProvenanceChain** for transparency and auditability.

---

## Document Class 1: Financial Reports (Banking/CBE)
### Example 1: Navigation Query
**Q:** "Show me the sections related to financial highlights in the CBE report."
**A:** Answer to: "Show me the sections related to financial highlights in the CBE report."
Section 'Financial Highlights' (pp. 12–15, CBE_ANNUAL_REPORT_2023): Summary: Overview of fiscal performance for the current year.

**Sources:**
- CBE ANNUAL REPORT 2023 (p. 12, 13, 14, 15)

### Example 2: Structured Query
**Q:** "What was the total net profit for CBE in 2023?"
**A:** Answer to: "What was the total net profit for CBE in 2023?"
• Net Profit: 24.5 Billion ETB (p.13, CBE_ANNUAL_REPORT_2023)

**Sources:**
- CBE ANNUAL REPORT 2023 (p. 13)

### Example 3: Semantic Search
**Q:** "Explain the bank's strategy for digital transformation."
**A:** Answer to: "Explain the bank's strategy for digital transformation."
[TEXT, score=0.82] p.[45]: "The bank aims to migrate 80% of transactions to mobile platforms by 2025..."

**Sources:**
- CBE ANNUAL REPORT 2023 (p. 45)

---

## Document Class 2: NGO Transparency Documents (Humanitarian)
### Example 4: Compound Query (Multi)
**Q:** "What are the main topics and who are the primary beneficiaries mentioned?"
**A:** Answer to: "What are the main topics and who are the primary beneficiaries mentioned?"
Section 'Beneficiary Demographics' (pp. 5–8, NGO_ASSESSMENT_2024): Population breakdown.
[TEXT, score=0.78] p.[6]: "Primary beneficiaries include displaced persons in the Tigray region..."

**Sources:**
- NGO ASSESSMENT 2024 (p. 5, 6, 7, 8)

### Example 5: Audit Mode
**Q:** /audit "The project reached 50,000 households."
**A:** Verified: True
**Reason:** Claim is supported by 2 source(s). Top match score=0.91, keyword overlap=100%.
**Source:** NGO ASSESSMENT 2024 (p. 10)

### Example 6: Structured Query
**Q:** "How much was the total expenditure for the WASH program?"
**A:** Answer to: "How much was the total expenditure for the WASH program?"
• WASH Program Total: $1,250,000 (p.22, NGO_FINANCE_SHEET)

**Sources:**
- NGO FINANCE SHEET (p. 22)

---

## Document Class 3: Regulatory & Compliance
### Example 7: Navigation Query
**Q:** "Find the section on compliance auditing."
**A:** Section 'Audit Framework' (pp. 20–22, CENTRAL_BANK_REG_01).

**Sources:**
- CENTRAL BANK REG 01 (p. 20, 21, 22)

### Example 8: Semantic Search
**Q:** "What are the penalties for non-compliance with the AML directive?"
**A:** [TEXT, score=0.89] p.[105]: "Violations may lead to fines up to 5,000,000 ETB and license revocation..."

**Sources:**
- CENTRAL BANK REG 01 (p. 105)

### Example 9: Audit Mode
**Q:** /audit "Fines for AML violations are capped at 1 million ETB."
**A:** Verified: False
**Reason:** Claim could not be verified. Top similarity=0.88, but content indicates 5 million ETB limit.
**Sources:** CENTRAL BANK REG 01 (p. 105)

---

## Document Class 4: Strategic & Economic Assessments
### Example 10: Navigation Query
**Q:** "Overview of the macroeconomic assessment."
**A:** Section 'Executive Summary' (pp. 1–3, IMF_ETHIOPIA_2023).

**Sources:**
- IMF ETHIOPIA 2023 (p. 1, 2, 3)

### Example 11: Structured Query (Fact Extraction)
**Q:** "What is the projected GDP growth rate for 2024?"
**A:** • GDP Growth 2024 (Proj): 6.2% (p.5, IMF_ETHIOPIA_2023)

**Sources:**
- IMF ETHIOPIA 2023 (p. 5)

### Example 12: Semantic Search
**Q:** "Impact of inflation on agricultural sector."
**A:** [TEXT, score=0.75] p.[18]: "Rising fertilizer costs driven by currency inflation are suppressing crop yields..."

**Sources:**
- IMF ETHIOPIA 2023 (p. 18)
