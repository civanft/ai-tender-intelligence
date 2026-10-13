from pathlib import Path

import pandas as pd
import pytest

from tender_intelligence.evaluation import (
    build_labeling_manifest,
    evaluate_manual_labels,
    load_label_file,
)


def sample_frame() -> pd.DataFrame:
    rows = []
    for country in ("BEL", "ITA", "FIN"):
        for index in range(12):
            if index < 4:
                score, relevant = 4.0, 1
            elif index < 6:
                score, relevant = 2.0, 0
            else:
                score, relevant = 0.0, 0
            notice_id = f"{country}-{index:03d}"
            rows.append(
                {
                    "notice_id": notice_id,
                    "publication_date": "2026-09-01",
                    "title": f"Notice {notice_id}",
                    "buyer_name": f"Buyer {country}",
                    "buyer_country": country,
                    "sector": "IT services",
                    "cpv_codes_json": '["72316000"]',
                    "description": "Data services and platform work.",
                    "ted_url": f"https://ted.europa.eu/en/notice/-/detail/{notice_id}",
                    "classification_score": score,
                    "is_relevant": relevant,
                    "lifecycle_status": "unchanged",
                    "content_hash": "a" * 64,
                }
            )
    return pd.DataFrame(rows)


def test_labeling_sample_is_deterministic_balanced_and_weighted(tmp_path: Path):
    source_path = tmp_path / "publication.bin"
    source_path.write_bytes(b"publication")
    frame = sample_frame()

    kwargs = {
        "round_id": "test-round",
        "sample_size": 24,
        "random_seed": 2027,
        "taxonomy_version": "0.1.0",
        "classification_threshold": 2.5,
        "source_path": source_path,
        "created_at": "2026-09-02T00:00:00+00:00",
    }
    first = build_labeling_manifest(frame, **kwargs)
    second = build_labeling_manifest(frame, **kwargs)

    assert first == second
    records = pd.DataFrame(first["records"])
    assert len(records) == 24
    assert records["notice_id"].is_unique
    assert records["buyer_country"].value_counts().to_dict() == {
        "BEL": 8,
        "ITA": 8,
        "FIN": 8,
    }
    for stratum in first["strata"]:
        assert stratum["sample_count"] * stratum["sample_weight"] == pytest.approx(
            stratum["population_count"], rel=1e-7
        )


def test_evaluation_calculates_expected_confusion_metrics():
    manifest = {
        "schema_version": "1.0",
        "round_id": "round-test",
        "source": {"classification_threshold": 2.5},
        "records": [
            {
                "notice_id": "1",
                "buyer_country": "BEL",
                "predicted_is_relevant": True,
                "classification_score": 4.0,
                "sample_weight": 2.0,
            },
            {
                "notice_id": "2",
                "buyer_country": "BEL",
                "predicted_is_relevant": True,
                "classification_score": 3.0,
                "sample_weight": 1.0,
            },
            {
                "notice_id": "3",
                "buyer_country": "ITA",
                "predicted_is_relevant": False,
                "classification_score": 2.0,
                "sample_weight": 3.0,
            },
            {
                "notice_id": "4",
                "buyer_country": "FIN",
                "predicted_is_relevant": False,
                "classification_score": 0.0,
                "sample_weight": 4.0,
            },
        ],
    }
    labels = pd.DataFrame(
        {
            "notice_id": ["1", "2", "3", "4"],
            "human_label": ["Relevant", "Not relevant", "Relevant", "Not relevant"],
        }
    )

    report = evaluate_manual_labels(manifest, labels)

    assert report["status"] == "final"
    assert report["unweighted"] == {
        "true_positive": 1,
        "false_positive": 1,
        "false_negative": 1,
        "true_negative": 1,
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
        "accuracy": 0.5,
    }
    assert report["weighted"]["precision"] == pytest.approx(2 / 3, rel=1e-6)
    assert report["weighted"]["recall"] == pytest.approx(2 / 5, rel=1e-6)
    assert report["weighted"]["accuracy"] == pytest.approx(0.6, rel=1e-6)


def test_evaluation_rejects_unknown_or_duplicate_labels():
    manifest = {
        "schema_version": "1.0",
        "round_id": "round-test",
        "source": {"classification_threshold": 2.5},
        "records": [
            {
                "notice_id": "1",
                "buyer_country": "BEL",
                "predicted_is_relevant": True,
                "classification_score": 4.0,
                "sample_weight": 1.0,
            }
        ],
    }
    with pytest.raises(ValueError, match="outside this round"):
        evaluate_manual_labels(
            manifest,
            pd.DataFrame({"notice_id": ["2"], "human_label": ["Relevant"]}),
        )


def test_json_draft_labels_can_be_loaded(tmp_path: Path):
    label_path = tmp_path / "labels.json"
    label_path.write_text(
        '{"labels":[{"sample_id":"R1-001","human_label":"Relevant"}]}',
        encoding="utf-8",
    )

    labels = load_label_file(label_path)

    assert labels.to_dict("records") == [
        {"sample_id": "R1-001", "human_label": "Relevant"}
    ]


def test_evaluation_accepts_sample_ids_for_ai_assisted_drafts():
    manifest = {
        "schema_version": "1.0",
        "round_id": "round-test",
        "source": {"classification_threshold": 2.5},
        "records": [
            {
                "sample_id": "R1-001",
                "notice_id": "1",
                "buyer_country": "BEL",
                "predicted_is_relevant": True,
                "classification_score": 4.0,
                "sample_weight": 1.0,
            }
        ],
    }
    labels = pd.DataFrame(
        {"sample_id": ["R1-001"], "human_label": ["Relevant"]}
    )

    report = evaluate_manual_labels(manifest, labels)

    assert report["status"] == "final"
    assert report["unweighted"]["true_positive"] == 1
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_manual_labels(
            manifest,
            pd.DataFrame(
                {"notice_id": ["1", "1"], "human_label": ["Relevant", "Relevant"]}
            ),
        )
