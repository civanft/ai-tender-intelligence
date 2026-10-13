from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


MANIFEST_SCHEMA_VERSION = "1.0"
TARGET_COUNTRIES = ("BEL", "ITA", "FIN")
DECIDED_LABELS = {"relevant": True, "not_relevant": False}
ALLOWED_LABELS = {*DECIDED_LABELS, "unsure", ""}
REQUIRED_SAMPLE_COLUMNS = {
    "notice_id",
    "publication_date",
    "title",
    "buyer_name",
    "buyer_country",
    "sector",
    "cpv_codes_json",
    "description",
    "ted_url",
    "classification_score",
    "is_relevant",
    "lifecycle_status",
    "content_hash",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_human_label(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    normalized = str(value).strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "notrelevant": "not_relevant",
        "not_relevant": "not_relevant",
        "relevant": "relevant",
        "unsure": "unsure",
        "": "",
    }
    return aliases.get(normalized, normalized)


def sampling_band(classification_score: object, is_relevant: object) -> str:
    score = float(classification_score)
    prediction = bool(int(is_relevant))
    if prediction:
        return "predicted_relevant"
    if score > 0:
        return "borderline_negative"
    return "no_evidence"


def _sample_indices(
    frame: pd.DataFrame,
    count: int,
    rng: random.Random,
) -> list[int]:
    candidates = sorted(frame.index.tolist(), key=lambda index: str(frame.at[index, "notice_id"]))
    if count >= len(candidates):
        return candidates
    return rng.sample(candidates, count)


def _country_sample(
    country_frame: pd.DataFrame,
    target_count: int,
    rng: random.Random,
) -> list[int]:
    positive_target = min(20, math.ceil(target_count / 2))
    borderline_target = min(10, max(0, target_count - positive_target))
    selected: list[int] = []

    for band, requested in (
        ("predicted_relevant", positive_target),
        ("borderline_negative", borderline_target),
    ):
        band_frame = country_frame[country_frame["sampling_band"] == band]
        chosen = _sample_indices(band_frame, min(requested, len(band_frame)), rng)
        selected.extend(chosen)

    remaining_count = target_count - len(selected)
    if remaining_count > 0:
        remaining = country_frame.drop(index=selected)
        zero_frame = remaining[remaining["sampling_band"] == "no_evidence"]
        chosen = _sample_indices(zero_frame, min(remaining_count, len(zero_frame)), rng)
        selected.extend(chosen)

    remaining_count = target_count - len(selected)
    if remaining_count > 0:
        remaining = country_frame.drop(index=selected)
        selected.extend(_sample_indices(remaining, remaining_count, rng))
    return selected


def _parse_cpv_codes(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if not isinstance(value, str) or not value:
        return []
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in decoded] if isinstance(decoded, list) else []


def _compact_text(value: object, limit: int) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return " ".join(str(value).split())[:limit]


def build_labeling_manifest(
    frame: pd.DataFrame,
    *,
    round_id: str,
    sample_size: int = 120,
    random_seed: int = 2027,
    taxonomy_version: str,
    classification_threshold: float,
    source_path: Path,
    source_label: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    missing = REQUIRED_SAMPLE_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Publication is missing evaluation columns: {sorted(missing)}")
    if sample_size < len(TARGET_COUNTRIES) or sample_size > len(frame):
        raise ValueError("Sample size is outside the available publication range.")
    if not round_id or len(round_id) > 40:
        raise ValueError("Round ID must contain between 1 and 40 characters.")

    population = frame[
        frame["buyer_country"].isin(TARGET_COUNTRIES)
        & (frame["lifecycle_status"] != "closed")
    ].copy()
    if population["notice_id"].duplicated().any():
        raise ValueError("Publication contains duplicate notice identifiers.")
    if sample_size > len(population):
        raise ValueError("Sample size exceeds the active target-country population.")

    population["sampling_band"] = [
        sampling_band(score, prediction)
        for score, prediction in zip(
            population["classification_score"],
            population["is_relevant"],
            strict=True,
        )
    ]
    population["sampling_stratum"] = (
        population["buyer_country"] + "|" + population["sampling_band"]
    )

    base_count, remainder = divmod(sample_size, len(TARGET_COUNTRIES))
    country_targets = {
        country: base_count + (1 if position < remainder else 0)
        for position, country in enumerate(TARGET_COUNTRIES)
    }
    # This PRNG is intentionally deterministic for reproducible sampling; it is
    # never used for credentials, tokens, or another security-sensitive value.
    rng = random.Random(random_seed)  # nosec B311
    selected_indices: list[int] = []
    for country in TARGET_COUNTRIES:
        country_frame = population[population["buyer_country"] == country]
        target_count = country_targets[country]
        if len(country_frame) < target_count:
            raise ValueError(f"Not enough {country} notices for the requested sample.")
        selected_indices.extend(_country_sample(country_frame, target_count, rng))

    selected = population.loc[selected_indices].copy()
    if len(selected) != sample_size or selected["notice_id"].duplicated().any():
        raise ValueError("Stratified sampling did not produce the requested unique sample.")

    population_counts = population["sampling_stratum"].value_counts().to_dict()
    sample_counts = selected["sampling_stratum"].value_counts().to_dict()
    selected["population_count"] = selected["sampling_stratum"].map(population_counts)
    selected["sample_count"] = selected["sampling_stratum"].map(sample_counts)
    selected["selection_probability"] = (
        selected["sample_count"] / selected["population_count"]
    )
    selected["sample_weight"] = (
        selected["population_count"] / selected["sample_count"]
    )

    shuffled_indices = selected.index.tolist()
    random.Random(random_seed + 1).shuffle(shuffled_indices)  # nosec B311
    selected = selected.loc[shuffled_indices]

    records = []
    for position, (_, row) in enumerate(selected.iterrows(), start=1):
        records.append(
            {
                "sample_id": f"R1-{position:03d}",
                "notice_id": str(row["notice_id"]),
                "publication_date": _compact_text(row["publication_date"], 10),
                "buyer_country": str(row["buyer_country"]),
                "buyer_name": _compact_text(row["buyer_name"], 300),
                "sector": _compact_text(row["sector"], 160),
                "title": _compact_text(row["title"], 500),
                "cpv_codes": _parse_cpv_codes(row["cpv_codes_json"]),
                "description_excerpt": _compact_text(row["description"], 1_000),
                "ted_url": str(row["ted_url"]),
                "content_hash": str(row["content_hash"]),
                "predicted_is_relevant": bool(int(row["is_relevant"])),
                "classification_score": float(row["classification_score"]),
                "sampling_band": str(row["sampling_band"]),
                "sampling_stratum": str(row["sampling_stratum"]),
                "population_count": int(row["population_count"]),
                "sample_count": int(row["sample_count"]),
                "selection_probability": round(float(row["selection_probability"]), 8),
                "sample_weight": round(float(row["sample_weight"]), 8),
            }
        )

    strata = []
    for stratum, sample_count in sorted(sample_counts.items()):
        country, band = stratum.split("|", 1)
        population_count = int(population_counts[stratum])
        strata.append(
            {
                "stratum": stratum,
                "country": country,
                "band": band,
                "population_count": population_count,
                "sample_count": int(sample_count),
                "selection_probability": round(sample_count / population_count, 8),
                "sample_weight": round(population_count / sample_count, 8),
            }
        )

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "round_id": round_id,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "source": {
            "publication_path": source_label or source_path.as_posix(),
            "publication_sha256": file_sha256(source_path),
            "population_count": int(len(population)),
            "taxonomy_version": taxonomy_version,
            "classification_threshold": float(classification_threshold),
            "target_countries": list(TARGET_COUNTRIES),
            "sample_size": sample_size,
            "random_seed": random_seed,
            "sampling_method": "country-balanced stratified random sample",
        },
        "strata": strata,
        "records": records,
    }


def load_labeling_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("Unsupported labeling manifest schema version.")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("Labeling manifest does not contain records.")
    notice_ids = [record.get("notice_id") for record in records]
    if any(not notice_id for notice_id in notice_ids) or len(set(notice_ids)) != len(notice_ids):
        raise ValueError("Labeling manifest contains invalid notice identifiers.")
    return payload


def load_label_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = {"notice_id", "human_label"} - set(frame.columns)
    if missing:
        raise ValueError(f"Label file is missing columns: {sorted(missing)}")
    return frame


def load_label_file(path: Path) -> pd.DataFrame:
    """Load reviewer labels from the normal CSV export or an auditable JSON draft."""
    if path.suffix.casefold() != ".json":
        return load_label_csv(path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("labels")
    if not isinstance(records, list) or not records:
        raise ValueError("JSON label file does not contain a non-empty labels list.")
    frame = pd.DataFrame(records)
    missing = {"sample_id", "human_label"} - set(frame.columns)
    if missing:
        raise ValueError(f"JSON label file is missing columns: {sorted(missing)}")
    return frame


def _confusion_metrics(frame: pd.DataFrame, *, weighted: bool) -> dict[str, Any]:
    if frame.empty:
        return {
            "true_positive": 0.0 if weighted else 0,
            "false_positive": 0.0 if weighted else 0,
            "false_negative": 0.0 if weighted else 0,
            "true_negative": 0.0 if weighted else 0,
            "precision": None,
            "recall": None,
            "f1": None,
            "accuracy": None,
        }
    weights = frame["sample_weight"] if weighted else pd.Series(1, index=frame.index)
    prediction = frame["predicted_is_relevant"].astype(bool)
    truth = frame["human_is_relevant"].astype(bool)
    tp = float(weights[prediction & truth].sum())
    fp = float(weights[prediction & ~truth].sum())
    fn = float(weights[~prediction & truth].sum())
    tn = float(weights[~prediction & ~truth].sum())
    if not weighted:
        tp, fp, fn, tn = int(tp), int(fp), int(fn), int(tn)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    accuracy = (tp + tn) / (tp + fp + fn + tn) if tp + fp + fn + tn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return {
        "true_positive": round(tp, 6) if weighted else tp,
        "false_positive": round(fp, 6) if weighted else fp,
        "false_negative": round(fn, 6) if weighted else fn,
        "true_negative": round(tn, 6) if weighted else tn,
        "precision": round(precision, 6) if precision is not None else None,
        "recall": round(recall, 6) if recall is not None else None,
        "f1": round(f1, 6) if f1 is not None else None,
        "accuracy": round(accuracy, 6) if accuracy is not None else None,
    }


def evaluate_manual_labels(
    manifest: dict[str, Any], labels: pd.DataFrame
) -> dict[str, Any]:
    manifest_frame = pd.DataFrame(manifest["records"])
    if "notice_id" not in labels.columns:
        if "sample_id" not in labels.columns:
            raise ValueError("Label file must contain notice_id or sample_id.")
        if labels["sample_id"].duplicated().any():
            raise ValueError("Label file contains duplicate sample identifiers.")
        unknown_sample_ids = set(labels["sample_id"]) - set(manifest_frame["sample_id"])
        if unknown_sample_ids:
            raise ValueError("Label file contains sample identifiers outside this round.")
        labels = labels.merge(
            manifest_frame[["sample_id", "notice_id"]],
            on="sample_id",
            how="left",
            validate="one_to_one",
        )
    if labels["notice_id"].duplicated().any():
        raise ValueError("Label file contains duplicate notice identifiers.")
    unknown_ids = set(labels["notice_id"]) - set(manifest_frame["notice_id"])
    if unknown_ids:
        raise ValueError("Label file contains notice identifiers outside this round.")

    label_frame = labels[["notice_id", "human_label"]].copy()
    label_frame["human_label"] = label_frame["human_label"].map(normalize_human_label)
    invalid = sorted(set(label_frame["human_label"]) - ALLOWED_LABELS)
    if invalid:
        raise ValueError(f"Label file contains unsupported labels: {invalid}")
    merged = manifest_frame.merge(label_frame, on="notice_id", how="left")
    merged["human_label"] = merged["human_label"].fillna("")
    merged["human_is_relevant"] = merged["human_label"].map(DECIDED_LABELS)
    decided = merged[merged["human_label"].isin(DECIDED_LABELS)].copy()

    total = len(merged)
    submitted = int((merged["human_label"] != "").sum())
    unsure = int((merged["human_label"] == "unsure").sum())
    decided_count = len(decided)
    countries = {}
    for country in TARGET_COUNTRIES:
        subset = decided[decided["buyer_country"] == country]
        countries[country] = {
            "decided_count": int(len(subset)),
            "unweighted": _confusion_metrics(subset, weighted=False),
            "weighted": _confusion_metrics(subset, weighted=True),
        }

    thresholds = sorted(
        {
            2.0,
            float(manifest["source"]["classification_threshold"]),
            3.0,
            3.5,
            4.0,
        }
    )
    threshold_curve = []
    for threshold in thresholds:
        threshold_frame = decided.copy()
        threshold_frame["predicted_is_relevant"] = (
            threshold_frame["classification_score"] >= threshold
        )
        threshold_curve.append(
            {
                "threshold": threshold,
                "weighted": _confusion_metrics(threshold_frame, weighted=True),
                "unweighted": _confusion_metrics(threshold_frame, weighted=False),
            }
        )

    return {
        "schema_version": "1.0",
        "round_id": manifest["round_id"],
        "status": "final" if decided_count == total else "preliminary",
        "coverage": {
            "sample_count": total,
            "submitted_count": submitted,
            "decided_count": decided_count,
            "unsure_count": unsure,
            "blank_count": total - submitted,
            "decided_rate": round(decided_count / total, 6) if total else 0.0,
        },
        "current_threshold": float(manifest["source"]["classification_threshold"]),
        "unweighted": _confusion_metrics(decided, weighted=False),
        "weighted": _confusion_metrics(decided, weighted=True),
        "countries": countries,
        "threshold_curve": threshold_curve,
        "scope_note": (
            "Recall is estimated within the retrieved TED candidate set, not across "
            "all TED notices. Stratification weights estimate this publication snapshot."
        ),
    }
