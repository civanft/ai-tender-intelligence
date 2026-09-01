# Security review

Review date: 2026-09-01

## Scope

The review covered the TED HTTP client, normalization and scoring pipeline, SQLite access, JSON/Parquet publication and restoration, Streamlit rendering, dependency supply chain, GitHub Actions, secrets exposure, and repository security settings.

## Findings and remediations

| Area | Risk found | Remediation |
|---|---|---|
| Dashboard links | External TED fields reached an HTML `href` and `st.link_button` without a scheme/host allowlist. | Accept only canonical HTTPS links on `ted.europa.eu`; otherwise generate a quoted official record fallback. Revalidate at render time. |
| External text | Source text could contain control or bidirectional-formatting characters and unbounded long fields. | Normalize Unicode, remove control/format/surrogate categories, limit list sizes, and cap title, buyer, description, and code lengths. |
| TED responses | A malformed response could return an invalid count, non-list collection, or more records than requested. | Validate response shape, non-negative count, and page-size boundary before processing. |
| Publication state | JSON restoration trusted schema, URLs, counts, and stored hashes; predictable temporary names could be targeted locally. | Add 95 MB/15,000-row bounds, full contract and SHA-256 validation, trusted-link checks, exclusive temporary files, fsync, and atomic replacement. Validate Parquet size and contract. |
| Local state | SQLite/raw files inherited broad process defaults. | Apply owner-only file permissions, private directories, SQLite foreign keys, `trusted_schema=OFF`, and a busy timeout. |
| SQL analysis | Static analysis flagged dynamically assembled identifier/placeholder SQL even though values were bound. | Replace the two dynamic insert statements with fully static named-parameter SQL; use `json_each(?)` for variable-length lists; add malicious-value regression coverage. |
| Streamlit server | Security defaults were implicit and viewer errors could expose internals. | Explicitly enable CORS/XSRF, strict SameSite, small upload/message limits, viewer toolbar, and hidden error details/links. |
| Python dependencies | Unbounded resolution and two current advisories affected local tooling (`pip 26.1.2`, `setuptools 80.10.2`). | Upgrade to fixed `pip 26.2.1` and `setuptools 83.0.0`; add a complete wheel-only SHA-256 lock and recurring `pip-audit`. |
| GitHub Actions | Mutable major tags were used and the complete refresh job held `contents: write`. | Pin every official action to a full commit SHA; split computation (read-only) from publication (write-only); restrict credentials persistence. |
| Continuous monitoring | Dependabot alerts/security updates and private vulnerability reporting were not active. | Add Dependabot configuration, CodeQL, Bandit, advisory audits, a security policy, CODEOWNERS, and enable repository security controls. |

## Verification gates

- `pytest`
- `python -m pip_audit --requirement requirements.txt`
- `python -m bandit -q -r src scripts app.py`
- `osv-scanner scan source --recursive --include-git-root .`
- `gitleaks git --staged --redact`
- `actionlint .github/workflows/*.yml`
- Streamlit `AppTest`
- Anonymous live TED query and complete refresh
- GitHub Actions security and refresh workflow runs

## Residual risk

No automated review can guarantee that all current or future vulnerabilities are absent. Residual risks include unknown dependency vulnerabilities, denial-of-service controls supplied by the eventual hosting platform, upstream TED data-quality changes, and future features accidentally crossing the current public/read-only boundary. Any feature involving accounts, private profiles, notes, uploads, or secrets requires a new threat model before implementation.
