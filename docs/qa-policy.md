# Translation and scholarly QA protocol (v0.1)

The project favors source-linked evidence over model confidence.

## Gate rules

- G1/G2/G3/G4/G5/G10/G11 need manual bilingual editorial review or documented independent expert review. No model score is a verified PASS.
- G6/G7/G8/G9 provide partial mechanical evidence. Numeric, DOI and citation mismatches are high-priority flags, not definitive findings.
- Preserve Chinese-specific jurisdiction, distinguish from Vietnam; do not silently substitute local laws or update source assertions.
- For papers retain denominators, adjusted/unadjusted results, effect sizes, 95% CI, p-values, cohort descriptions, limitations, figure/table references.
- Compare source and translation at paragraph, chapter and cross-chapter level. Validate technical formatting and licenses before publication.
- A second model or back translation may reveal defects but is not independent scientific confirmation.
- In a future release gate, store reviewer, previous text, correction, severity, exact source span, evidence and sign-off.

## Known limits

- DOCX, EPUB formatting, figures and rich scientific tables are flattened.
- PDF reading order, columns, scanned pages and glyph extraction may be incorrect.
- Numeric regex may flag valid locale formatting or miss wrong semantic attachment.
- Metadata coverage varies; an indexed record is not verified primary evidence.
- This version does not generate a signed editor-approved publishing package.

No mass paid translation without permission, paywall bypass, patient data disclosure, silent overwrites or unreviewed publication.
