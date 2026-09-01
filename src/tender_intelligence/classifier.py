from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def _contains(text: str, term: str) -> bool:
    pattern = rf"(?<!\w){re.escape(normalize_text(term))}(?!\w)"
    return re.search(pattern, text) is not None


def classify_notice(
    record: dict[str, Any], taxonomy: dict[str, Any]
) -> dict[str, Any]:
    text = normalize_text(
        " ".join(
            part for part in (record.get("title"), record.get("description")) if part
        )
    )
    cpv_codes = sorted(set(record.get("cpv_codes", [])))

    theme_scores: dict[str, float] = {}
    keyword_evidence: dict[str, list[dict[str, Any]]] = {}
    cpv_evidence: dict[str, list[dict[str, Any]]] = {}

    for theme, rules in taxonomy["themes"].items():
        matched_keywords = []
        keyword_points = 0.0
        for term, weight in rules.get("keywords", {}).items():
            if _contains(text, term):
                matched_keywords.append({"term": term, "weight": float(weight)})
                keyword_points += float(weight)

        matched_cpv = []
        cpv_points = 0.0
        seen_prefixes: set[str] = set()
        prefix_rules = rules.get("cpv_prefixes", {})
        for code in cpv_codes:
            matches = [prefix for prefix in prefix_rules if code.startswith(prefix)]
            if not matches:
                continue
            prefix = max(matches, key=len)
            if prefix in seen_prefixes:
                continue
            seen_prefixes.add(prefix)
            rule = prefix_rules[prefix]
            weight = float(rule["weight"])
            matched_cpv.append(
                {
                    "code": code,
                    "prefix": prefix,
                    "label": rule["label"],
                    "weight": weight,
                }
            )
            cpv_points += weight

        score = round(min(10.0, keyword_points + cpv_points), 2)
        theme_scores[theme] = score
        if matched_keywords:
            keyword_evidence[theme] = matched_keywords
        if matched_cpv:
            cpv_evidence[theme] = matched_cpv

    primary_theme, top_score = max(
        theme_scores.items(), key=lambda item: (item[1], item[0])
    )
    if top_score == 0:
        primary_theme = "Other digital"

    return {
        "primary_theme": primary_theme,
        "classification_score": top_score,
        "is_relevant": top_score >= float(taxonomy["classification_threshold"]),
        "theme_scores": theme_scores,
        "matched_keywords": keyword_evidence,
        "matched_cpv": cpv_evidence,
    }
