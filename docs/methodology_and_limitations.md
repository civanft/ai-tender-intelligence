# Methodology and limitations

## Method

1. Retrieve every matching page of active published notices for all 27 EU member states from the EU TED Search API, using stable iteration mode for complete snapshots.
2. Use broad CPV families and explicit AI/data phrases to create a candidate set.
3. Normalize repeated and multilingual fields to one procedure-level analysis row.
4. Classify candidates with a transparent, versioned combination of CPV prefixes and multilingual keywords.
5. Calculate a configurable profile-fit score from country, theme, classification evidence, deadline runway, and budget clarity.
6. Compare deterministic normalized-content hashes with the preceding complete snapshot to label records `new`, `updated`, `unchanged`, or `closed`.
7. Publish readable JSON and analysis-ready Parquet so the dashboard can run without the local SQLite file.
8. Keep every component and match as JSON evidence so a dashboard user can inspect the result.

The MVP is intentionally rule-based. That makes errors visible and creates a defensible baseline before experimenting with embeddings or supervised learning.

## Opportunity score: what it is and is not

The score is a **profile-fit ranking aid** for a hypothetical EU-27 AI/data research profile with equal country priority. It is not a probability, forecast, legal assessment, or statement that an organisation can win the tender.

| Component | Maximum | Interpretation |
|---|---:|---|
| Country fit | 20 | Each of the 27 EU member states receives the same 20 points; personal preferences belong in Fit lab. |
| Theme fit | 30 | Higher points for the profile's preferred AI/data themes. |
| Classification evidence | 20 | Stronger explicit CPV/keyword evidence receives more points. |
| Deadline runway | 20 | More preparation time is treated as a better fit. |
| Budget clarity | 10 | A disclosed amount and currency improve basic qualification clarity. |

Weights are stored in `config/profile.json` and should be replaced when a real company profile exists.

## Important limitations

- TED coverage is not the same as all public procurement. Threshold rules, publication choices, and national portals affect coverage.
- CPV has no single dedicated AI code. Broad IT codes create false positives; incomplete or general CPV coding creates false negatives.
- Keyword matching depends on the text returned in selected TED fields and a limited multilingual dictionary. Synonyms and domain language will be missed.
- The country field represents the first disclosed EU buyer country in a joint-buyer notice. Delivery location can differ and can contain multiple NUTS codes. All original buyer countries remain in local raw evidence; one notice is not counted once per buyer country.
- Procedure-level budget can be missing, repeated, lot-specific, non-comparable, or expressed in different currencies. This MVP performs no currency conversion.
- Multiple lot deadlines may exist. The prototype uses the earliest disclosed date as a conservative simplification.
- `ACTIVE` is a moving TED search scope. Counts will change between runs; raw snapshots and fetch metadata are retained locally.
- A `closed` label means the notice was absent from a later complete `ACTIVE` result for the same target countries. It does not prove award, cancellation, or contract completion.
- A limited or interrupted fetch never closes missing records. Only a complete result set can do so.
- TED page-number mode exposes at most 15,000 results and is used for small capped probes. Complete snapshots use ITERATION mode, pass the opaque continuation token and check count stability and duplicate IDs. Iteration finishes only after an empty terminal page is confirmed by requesting the same cursor again. The live latest-version API can report more matches than distinct retrievable notices; both API match count and actual received count are retained separately. Timeout, repeated/missing tokens or unconfirmed terminal pages fail before lifecycle changes. Extracts stay bounded at 100,000 notices. Gzip JSON stays bounded at 95 MiB on disk and 256 MiB decompressed.
- Adding every EU country does not imply equal language recall. CPV rules are shared across countries, but the keyword dictionary still covers selected languages; native-language false negatives must be measured in new evaluation rounds.
- GitHub Actions schedules are best-effort and may begin later than the configured time.
- Automated security scanners cover known advisory databases and recognizable source patterns; they cannot prove the absence of unknown vulnerabilities or business-logic flaws.
- The public dataset remains read-only. Research desk notes and search presets are isolated in individual, non-durable Streamlit sessions and can be explicitly exported/imported as plain-text workspace files. Persistent accounts, shared annotations and cloud sync require authentication, authorization, retention and privacy controls. See `research_desk.md` for the current feature threat model.
- Translated titles can be machine-produced or differ from the source-language detail. Users must inspect the official notice before acting.
- The prototype does not assess eligibility, consortium requirements, technical capacity, financial capacity, procurement law, or bid quality.

## Data source and terms

The source is the Publications Office of the European Union's [TED Search API](https://docs.ted.europa.eu/api/latest/search.html). Published-notice search is anonymously accessible. Query syntax follows the official [TED Search and browse help](https://ted.europa.eu/en/help/search-browse), and CPV is the EU's [Common Procurement Vocabulary](https://ted.europa.eu/en/simap/cpv). Users should also review the TED legal notice and the original procurement documents.
