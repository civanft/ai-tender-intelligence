# Iteration 1 report — AI Tender Intelligence

Date: 2026-09-01 (Europe/Istanbul)

## Outcome

The first working repository iteration is complete. It includes official TED API research, an anonymous live Search API proof of concept, a normalized SQLite model, a versioned CPV/keyword taxonomy, an explainable profile-fit score, a five-view Streamlit dashboard, documentation, and automated tests.

No GitHub push, external account change, or API-key request was made.

## Live proof-of-concept result

- TED query syntax validation: passed
- Search endpoint: `POST https://api.ted.europa.eu/v3/notices/search`
- Search scope: `ACTIVE`
- Target buyer countries: Belgium, Italy, Finland
- API matches reported at run time: 4,000
- Candidates retrieved for the small proof of concept: 25
- Candidates passing the local taxonomy threshold: 2
- Raw response: saved locally under `data/raw/` and excluded from Git
- Normalized database: `data/processed/tenders.db` and excluded from Git

The small relevant count is expected because the API query deliberately creates a broad candidate set while the local rule system applies a narrower, inspectable AI/data screen.

## Verification

- Python compile check: passed
- Automated tests: 9 passed
- Live TED dry-run validation: passed
- Live TED fetch and SQLite upsert: passed
- Streamlit programmatic app test: 0 exceptions
- Dashboard views detected: opportunity list, country comparison, trends, notice explanation, method

## Immediate next steps

1. Manually label a balanced country sample and define a written labelling guide.
2. Measure precision, recall, and false-positive patterns by technology theme.
3. Add historical extraction with TED iteration mode and checkpointing.
4. Improve lot-level budgets and deadlines rather than relying only on procedure-level simplifications.
5. Add reusable SQL analysis queries for institutions, sectors, budgets, and themes.
6. Record the three-minute demo after the validation results are available.
