# Data dictionary

The SQLite database is created at `data/processed/tenders.db`.

## `tender_notices`

| Column | Type | Source / rule | Meaning |
|---|---|---|---|
| `notice_id` | TEXT, PK | `publication-number` | Stable TED publication number for this notice version. |
| `publication_date` | TEXT | `publication-date` | ISO calendar date. |
| `title` | TEXT | `notice-title` | English text when present, otherwise a deterministic language fallback. |
| `buyer_name` | TEXT | `buyer-name` | First normalized buyer name. |
| `buyer_country` | TEXT | `buyer-country` | ISO alpha-3 buyer country code; target values are BEL, ITA, FIN. |
| `sector` | TEXT | first CPV division | Broad human-readable sector derived from CPV. |
| `cpv_codes_json` | TEXT/JSON | `classification-cpv` | Deduplicated CPV codes. |
| `place_codes_json` | TEXT/JSON | `place-of-performance` | Deduplicated NUTS/country performance codes. |
| `estimated_value` | REAL | `estimated-value-proc` | Procedure estimate when disclosed; not summed across lots. |
| `currency` | TEXT | `estimated-value-cur-proc` | Currency supplied by TED. No conversion is performed. |
| `deadline_date` | TEXT | earliest `deadline-receipt-tender-date-lot` | Earliest disclosed lot tender deadline. |
| `notice_type` | TEXT | `notice-type` | TED notice type code. |
| `procedure_type` | TEXT | `procedure-type` | TED procedure type code, when present. |
| `ted_url` | TEXT | `links.html.ENG` or fallback | Public TED detail URL. |
| `description` | TEXT | procedure/lot descriptions | Compact text used as classifier evidence. |
| `primary_theme` | TEXT | classifier | Highest-evidence technology theme. |
| `matched_keywords_json` | TEXT/JSON | classifier | Keyword evidence grouped by theme. |
| `matched_cpv_json` | TEXT/JSON | classifier | CPV evidence grouped by theme. |
| `classification_score` | REAL | classifier | Evidence strength, capped at 10; not a probability. |
| `is_relevant` | INTEGER | classifier | 1 when evidence meets the versioned threshold, else 0. |
| `opportunity_score` | REAL | scorer | 0–100 profile-fit score; never a win probability. |
| `score_explanation_json` | TEXT/JSON | scorer | Points and reason for each of the five components. |
| `raw_notice_json` | TEXT/JSON | API | Original notice object returned for the selected fields. |
| `fetched_at` | TEXT | pipeline | UTC ingestion timestamp. |
| `first_seen_at` | TEXT | lifecycle tracker | First UTC time the record entered the local registry. |
| `last_seen_at` | TEXT | lifecycle tracker | Most recent UTC time the record was returned by TED. |
| `lifecycle_status` | TEXT | lifecycle tracker | `new`, `updated`, `unchanged`, or `closed` for the latest refresh. |
| `content_hash` | TEXT | lifecycle tracker | SHA-256 of normalized analytical fields; operational timestamps and raw JSON are excluded. |
| `closed_at` | TEXT, nullable | lifecycle tracker | UTC time an unseen record was marked closed after a complete `ACTIVE` refresh. |

## `fetch_runs`

Stores one row per pipeline run: query, scope, requested/received count, API match count, relevant count, timestamps, status, raw snapshot path, fetched page count, completeness flag, each lifecycle count, and publication paths. It supports reproducibility and basic monitoring.

## Published files

`data/published/tenders.json` contains a `schema_version`, publication metadata, and a `notices` array. JSON-encoded SQLite columns are exposed as native arrays/objects named `cpv_codes`, `place_codes`, `matched_keywords`, `matched_cpv`, and `score_explanation`. Raw API objects are deliberately excluded.

`data/published/tenders.parquet` contains the same analytical rows in a compact columnar format. Its structured evidence fields retain their SQLite-style `*_json` names so they remain portable scalar columns. Both files include lifecycle state and exclude raw notice payloads.
