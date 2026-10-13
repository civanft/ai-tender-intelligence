# Manual labeling and classifier evaluation

## Goal

The first evaluation round tests whether the transparent CPV/keyword classifier
identifies genuinely relevant AI and data opportunities inside the retrieved TED
candidate set. It measures classification quality; it does not validate the
profile-fit score and does not estimate win probability.

## Unit and label definition

Label one published notice row. Choose exactly one value:

- **Relevant** — a material part of the procurement scope concerns AI/ML,
  analytics/BI, data engineering or integration, data platforms, database/data
  services, or infrastructure specifically intended to store, process, govern,
  or serve data.
- **Not relevant** — the scope is generic IT, end-user hardware, ordinary
  networking/telecom, general application work, or another purchase where
  AI/data language is absent or merely incidental.
- **Unsure** — the supplied title, excerpt, CPV codes, and official TED page do
  not support a defensible binary decision. Add a short reason and return to it
  in adjudication.

For a mixed or multi-lot notice, use **Relevant** when at least one material lot
is an in-scope opportunity rather than an incidental mention. Read the official
TED notice when the excerpt is insufficient. Record confidence as High, Medium,
or Low. Do not look at the classifier output before making the human decision.

## Round 1 sample

`scripts/create_labeling_sample.py` creates a deterministic 120-row sample from
active Belgium, Italy, and Finland candidates. It balances 40 rows per country,
oversamples predicted-positive and near-threshold cases, and adds random
zero-evidence negatives. Prediction fields and inverse-probability weights are
kept in `data/evaluation/round_1_manifest.json`, not in the labeling sheet.

This design is efficient for finding both false positives and false negatives,
but raw sample percentages do not represent the publication population. The
evaluation therefore reports both unweighted diagnostic metrics and weighted
snapshot estimates.

Create or reproduce the manifest:

```bash
python scripts/create_labeling_sample.py --overwrite
```

## Labeling protocol

1. Work through the randomized workbook from top to bottom.
2. Read title, buyer, sector, CPV codes, and description excerpt.
3. Open the official TED URL for unclear cases.
4. Select the human label and confidence; add a concise decision reason.
5. Use `Unsure` rather than guessing.
6. After the first pass, adjudicate unsure/low-confidence rows without viewing
   model predictions.
7. Export the completed `Labels` sheet as UTF-8 CSV without renaming
   `notice_id` or `human_label`.

For a stronger study, a second reviewer should independently label at least
20–30 overlapping rows. Agreement and disagreements can then be reported before
final adjudication.

## AI-assisted first pass

Round 1 includes an explicitly identified AI-assisted draft in
`data/evaluation/round_1_ai_assisted_draft.json`. It contains a proposed label,
confidence level, concise reason, and a human-review flag for every sampled
notice. The workbook copies these proposals into `Labels` and collects the 25
medium/low-confidence cases in `Review Queue`, with a short Turkish explanation
of the decision boundary.

This draft is not independent human ground truth. Its metrics are therefore
reported as preliminary and must not be presented as the final classifier
evaluation. A reviewer can accept the proposal or choose a replacement label in
the yellow `final_decision` column. Four records without enough published scope
remain `Unsure` until adjudication.

## Precision and recall

Run the evaluator after exporting the label sheet:

```bash
python scripts/evaluate_classifier.py \
  --labels data/evaluation/round_1_labels.csv \
  --output data/evaluation/round_1_report.json
```

The evaluator also accepts the auditable JSON draft:

```bash
python scripts/evaluate_classifier.py \
  --labels data/evaluation/round_1_ai_assisted_draft.json \
  --output data/evaluation/round_1_ai_assisted_report.json
```

The report includes coverage, weighted and unweighted confusion matrices,
precision, recall, F1, accuracy, country slices, and a small threshold comparison
for 2.0–4.0. A report is `final` only when all sample rows have a binary decision;
otherwise it is explicitly `preliminary`.

## Interpretation boundary

Precision answers: among notices the rules classified as relevant, how many were
human-relevant? Recall answers: among human-relevant notices in the retrieved
candidate population, how many were classified as relevant? It does **not**
measure recall across all TED notices because the broad TED candidate query is a
separate retrieval stage. Confidence intervals, inter-rater agreement, retrieval
recall, and taxonomy changes belong in later rounds.
