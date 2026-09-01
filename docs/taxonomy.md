# AI/data taxonomy v0.1

The executable taxonomy is `config/taxonomy.json`. This document explains the design choices.

## Two-stage design

The API query is intentionally broad. It retrieves candidates from computing/software/IT CPV families (`302*`, `48*`, `72*`) plus explicit AI/data phrases. A second local classifier then demands stronger, inspectable evidence.

This separation matters: using `72*` alone as a final label would incorrectly describe many ordinary software-support contracts as AI/data opportunities.

## Themes

| Theme | Strong examples | Selected CPV evidence |
|---|---|---|
| AI & machine learning | artificial intelligence, machine learning, LLM, computer vision | No dedicated AI CPV; keyword evidence is required. |
| Analytics & business intelligence | data analytics, predictive analytics, dashboards | `4846*`, `48482*`, `72316*` |
| Data engineering & platforms | data platform, ETL, warehouse, lake, integration | `7231*`, `7232*`, `72322*`, `7221261*` |
| Data infrastructure & cloud | cloud/data infrastructure, HPC, servers | `3021*`, `4882*`, `72514*`, `7272*` |
| Database & data services | database, migration, conversion, open data | `486*`, `723*` and selected `7231*` services |

## Language coverage

Version 0.1 includes selected English, Italian, French, Dutch, and Finnish terms. This reflects the three target countries but is not complete linguistic coverage. Evidence is matched case-insensitively after Unicode normalization.

## Classification rule

- Every matched keyword contributes its configured weight once.
- Every matched CPV prefix contributes its configured weight once per theme.
- Theme evidence is capped at 10 for display.
- The theme with the highest evidence becomes the primary theme.
- A candidate is marked relevant at the configured threshold of 2.5.
- All matches are retained for inspection; the value is an evidence score, not a statistical confidence.

## Planned validation

In weeks 3–4, manually label a balanced sample across Belgium, Italy, and Finland. Report precision/recall and errors by theme, then adjust the versioned taxonomy rather than tuning against a few attractive examples.
