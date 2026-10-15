# Research desk: methods, privacy and operating limits

## Purpose

Tender Meridian combines public-notice exploration with a repeatable research
workflow: save, compare, check evidence, plan dates and export a working brief.
The current blue/slate research surfaces, Public Sans, Source Serif 4 and
IBM Plex Mono remain the visual foundation. New controls use native Streamlit
semantics, visible focus and mobile stacking. No paid service or LLM key is needed.

## Watchlist and saved searches

Each Streamlit session owns a `research_workspace` dictionary. It contains only
notice IDs, a stage, a note, manually recorded checks and filter presets. Stages
are Watching, Researching, Ready for review and Archived. None is an automated
bid/no-bid recommendation. Checkmarks are user assertions, not verified facts.

The workspace holds up to 100 notices and 20 searches. Watchlist cards are
paginated in groups of ten. Saved notices are resolved against the current
snapshot, independently of sidebar filters. Missing notice IDs keep their notes
and can be exported or removed. No invented notice content is restored from an
import. Search presets intersect their selections with currently available values.

Sessions are not durable accounts. A disconnect or server restart can clear
research. Explicit JSON download/import supports a later visit. Files include
personal notes in plain text; users should keep them privately. Import merges
with the current session and matching IDs/names take the uploaded values.

## Fit lab

This is a separate, current-date scenario; it never overwrites pipeline scores.
The pool contains screened, non-closed notices whose disclosed deadline has not
passed. Unknown deadlines remain in the pool with zero runway points. Sidebar
filters do not constrain this pool, which is explicitly stated in the UI.

Weights default to 20 market / 30 theme / 20 evidence / 20 runway / 10 disclosure.
The five chosen weights are normalized to a total of 100. Each contribution is
visible. The calculation uses:

- Market/theme: 1 for a preferred match, otherwise 0.
- Classification: clipped rule-evidence score / 10.
- Preparation time: clipped days remaining / 45; missing/expired dates get 0.
- Budget: 1 if a positive procedure estimate and currency are disclosed, else 0.

All-zero, negative, non-finite or out-of-range weights are rejected. This is
profile alignment only, not affordability, legal eligibility or win probability.
Snapshot profile scores shown elsewhere retain their original assessment date.

## Evidence neighbours

Similarity is 45 for equal theme, 25 for at least one shared five-digit CPV
family, 15 for equal buyer country and 15 for equal disclosed buyer name. The
notice itself, closed notices and expired disclosed dates are excluded. A match
below 25 is omitted. Every returned recommendation states its matching reasons.
Unknown dates are allowed but must be checked. This method uses no embeddings,
language generation, undisclosed documents or learned prediction model.

## Buyer intelligence

Buyers are grouped by exact disclosed name plus country. The directory uses the
current filters; selecting a buyer opens its complete visible snapshot profile,
including closed records. Counts are snapshot counts, not procurement history
coverage or forecasts. Aliases are not resolved. An estimate sum may repeat a
procedure across notices and is not deduplicated awarded spend. Non-EUR values
are not converted or added to the EUR total. Missing sums remain unknown.

## Deadline radar and brief exports

Radar uses the current filtered view and today's UTC date. Its horizons are
7/14/30/60/90 days. Closed and expired notices are excluded; missing dates have
an explicitly separate view. New/updated refer to the latest ingestion, not
newly opened tenders or field-level revision diffs. Old extracts show a warning.

Calendar exports contain up to 100 dated, non-closed, unexpired records sorted
by deadline. Events are all-day planning reminders. TED's normalized date cannot
establish the exact submission time, time zone or different lot deadlines.
Calendar content is escaped and folded to RFC 5545's 75-octet line length.

Standalone HTML briefs and public CSV exports contain up to 100 notices and
exclude private notes, checkmarks, internal database fields and raw TED responses.
HTML escapes all external text and uses trusted TED links. CSV and all new table
downloads neutralize formula-leading source strings. Briefs identify source,
preparation date and research gaps. A downloaded brief is a static snapshot.

## Threat model

- No personal state enters SQLite, published JSON/Parquet, GitHub or a cache.
- No workspace file is persisted to disk by the app or interpreted as code.
- Import accepts UTF-8 JSON only, capped at 500 KB, with a versioned allowlist.
- Unknown fields, invalid IDs, stages, checks, sizes and non-finite JSON numbers
  are rejected. Merge is validated before replacing the current workspace.
- Saving notes enforces the same total export-size limit, including Unicode.
- Plain-text workspace files are not encrypted; the UI explains their contents.
- Streamlit's upload, CORS and XSRF protections remain active. The existing
  reverse-proxy 1 MB request limit covers the permitted workspace upload.

An authenticated, durable multi-user workspace, background email alerts and
collaboration require a separate authorization/retention design before launch.

## Verification

`tests/test_research.py` tests current-date exclusion, score contribution math,
workspace round trips and rejection, Unicode calendar folding and injection,
HTML escaping, private-field exclusion and buyer grouping. Synthetic-database
AppTest coverage checks session isolation, note/check persistence, comparisons,
empty views, saved-search restoration and filtered-out dossier routing. Real
browser QA checks the new destinations and mobile document overflow.
