# Security policy

## Supported version

Security fixes are applied to the latest commit on `main`.

## Reporting a vulnerability

Please do not disclose a suspected vulnerability in a public issue. Use the repository's **Security → Advisories → Report a vulnerability** form so details remain private until a fix is available:

https://github.com/civanft/ai-tender-intelligence/security/advisories/new

Include the affected component, reproduction steps, potential impact, and any suggested mitigation. Reports will be acknowledged on a best-effort basis within seven days.

## Security scope

This project processes public TED procurement records and uses no TED API secret. Raw API responses and the local SQLite database are Git-ignored. Published JSON and Parquet files intentionally contain public analytical fields but exclude raw notice payloads.
