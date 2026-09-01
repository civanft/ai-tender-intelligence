# Three-minute demo script

## 0:00–0:30 — Problem

"European public procurement data is open, but finding genuinely relevant AI and data opportunities across countries is difficult. This prototype turns TED notices into an explainable shortlist for Belgium, Italy, and Finland."

## 0:30–1:00 — Data pipeline

Show the architecture diagram. Explain anonymous paginated TED access, normalization, the CPV/keyword classifier, SQLite lifecycle state, JSON/Parquet publication, and Streamlit. Mention that GitHub Actions refreshes the public snapshot daily after tests pass.

## 1:00–1:45 — Dashboard

Filter to relevant notices, choose a lifecycle status and country, and compare opportunity counts and disclosed EUR budgets. Explain that `closed` means absent from a complete later active snapshot, not proof of award or cancellation. Open the monthly trend tab and state that an API snapshot is not a complete market forecast.

## 1:45–2:30 — Explainability

Open one notice. Show matched keywords, CPV evidence, and the five opportunity-score components. Say explicitly: "This is a configurable profile-fit score, not a probability of winning."

## 2:30–3:00 — Reflection

Show the limitations page and name one false positive or false negative. Close with the next step: manually label a validation set, measure precision/recall, and compare the rule baseline with a lightweight text model.
