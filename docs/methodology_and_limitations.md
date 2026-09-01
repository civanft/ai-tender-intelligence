# Methodology and limitations

## Method

1. Retrieve every matching page of active published notices for Belgium, Italy, and Finland from the EU TED Search API.
2. Use broad CPV families and explicit AI/data phrases to create a candidate set.
3. Normalize repeated and multilingual fields to one procedure-level analysis row.
4. Classify candidates with a transparent, versioned combination of CPV prefixes and multilingual keywords.
5. Calculate a configurable profile-fit score from country, theme, classification evidence, deadline runway, and budget clarity.
6. Compare deterministic normalized-content hashes with the preceding complete snapshot to label records `new`, `updated`, `unchanged`, or `closed`.
7. Publish readable JSON and analysis-ready Parquet so the dashboard can run without the local SQLite file.
8. Keep every component and match as JSON evidence so a dashboard user can inspect the result.

The MVP is intentionally rule-based. That makes errors visible and creates a defensible baseline before experimenting with embeddings or supervised learning.

## Opportunity score: what it is and is not

The score is a **profile-fit ranking aid** for a hypothetical Belgium-first AI/data market-entry profile. It is not a probability, forecast, legal assessment, or statement that an organisation can win the tender.

| Component | Maximum | Interpretation |
|---|---:|---|
| Country fit | 20 | Belgium receives the highest configured priority, followed by Italy and Finland. |
| Theme fit | 30 | Higher points for the profile's preferred AI/data themes. |
| Classification evidence | 20 | Stronger explicit CPV/keyword evidence receives more points. |
| Deadline runway | 20 | More preparation time is treated as a better fit. |
| Budget clarity | 10 | A disclosed amount and currency improve basic qualification clarity. |

Weights are stored in `config/profile.json` and should be replaced when a real company profile exists.

## Important limitations

- TED coverage is not the same as all public procurement. Threshold rules, publication choices, and national portals affect coverage.
- CPV has no single dedicated AI code. Broad IT codes create false positives; incomplete or general CPV coding creates false negatives.
- Keyword matching depends on the text returned in selected TED fields and a limited multilingual dictionary. Synonyms and domain language will be missed.
- The country field represents the buyer's country. Delivery location can differ and can contain multiple NUTS codes.
- Procedure-level budget can be missing, repeated, lot-specific, non-comparable, or expressed in different currencies. This MVP performs no currency conversion.
- Multiple lot deadlines may exist. The prototype uses the earliest disclosed date as a conservative simplification.
- `ACTIVE` is a moving TED search scope. Counts will change between runs; raw snapshots and fetch metadata are retained locally.
- A `closed` label means the notice was absent from a later complete `ACTIVE` result for the same target countries. It does not prove award, cancellation, or contract completion.
- A limited or interrupted fetch never closes missing records. Only a complete result set can do so.
- TED page-number mode exposes at most 15,000 results. The pipeline fails clearly above that ceiling rather than publishing a misleading partial snapshot; iteration-mode backfill remains future work.
- GitHub Actions schedules are best-effort and may begin later than the configured time.
- Translated titles can be machine-produced or differ from the source-language detail. Users must inspect the official notice before acting.
- The prototype does not assess eligibility, consortium requirements, technical capacity, financial capacity, procurement law, or bid quality.

## Data source and terms

The source is the Publications Office of the European Union's [TED Search API](https://docs.ted.europa.eu/api/latest/search.html). Published-notice search is anonymously accessible. Query syntax follows the official [TED Search and browse help](https://ted.europa.eu/en/help/search-browse), and CPV is the EU's [Common Procurement Vocabulary](https://ted.europa.eu/en/simap/cpv). Users should also review the TED legal notice and the original procurement documents.
