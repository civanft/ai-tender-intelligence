from __future__ import annotations

from datetime import date
from typing import Any


def _deadline_component(deadline_value: str | None, assessed_on: date) -> tuple[float, str]:
    if not deadline_value:
        return 5.0, "No deadline was normalized; a small neutral allowance is used."
    try:
        deadline = date.fromisoformat(deadline_value)
    except ValueError:
        return 0.0, "The normalized deadline could not be parsed."
    days = (deadline - assessed_on).days
    if days < 0:
        return 0.0, f"The deadline passed {-days} day(s) ago."
    if days < 7:
        return 3.0, f"Only {days} day(s) remain."
    if days < 21:
        return 8.0, f"{days} days remain, allowing limited preparation time."
    if days < 45:
        return 15.0, f"{days} days remain, allowing moderate preparation time."
    return 20.0, f"{days} days remain, allowing longer preparation time."


def score_opportunity(
    record: dict[str, Any],
    classification: dict[str, Any],
    profile: dict[str, Any],
    *,
    assessed_on: date | None = None,
) -> dict[str, Any]:
    assessed_on = assessed_on or date.today()
    country = record.get("buyer_country")
    country_points = float(profile["country_points"].get(country, 0))
    country_reason = (
        f"{country} receives {country_points:g} points in the configured market profile."
        if country
        else "Buyer country is missing."
    )

    theme = classification["primary_theme"]
    theme_points = float(profile["theme_points"].get(theme, 0))
    theme_reason = f"'{theme}' receives {theme_points:g} configured profile points."

    evidence_points = min(20.0, float(classification["classification_score"]) * 2)
    evidence_reason = (
        f"Rule evidence score {classification['classification_score']:g}/10 "
        "is converted to a maximum of 20 profile-fit points."
    )

    deadline_points, deadline_reason = _deadline_component(
        record.get("deadline_date"), assessed_on
    )

    amount = record.get("estimated_value")
    currency = record.get("currency")
    if amount and amount > 0 and currency:
        budget_points = 10.0
        budget_reason = "An estimated procedure value and currency are disclosed."
    elif amount and amount > 0:
        budget_points = 5.0
        budget_reason = "An estimated value is disclosed, but the currency is missing."
    else:
        budget_points = 0.0
        budget_reason = "No normalized procedure-level budget is disclosed."

    components = {
        "country_fit": {"points": country_points, "max": 20, "reason": country_reason},
        "theme_fit": {"points": theme_points, "max": 30, "reason": theme_reason},
        "classification_evidence": {
            "points": evidence_points,
            "max": 20,
            "reason": evidence_reason,
        },
        "deadline_runway": {
            "points": deadline_points,
            "max": 20,
            "reason": deadline_reason,
        },
        "budget_clarity": {
            "points": budget_points,
            "max": 10,
            "reason": budget_reason,
        },
    }
    total = round(sum(component["points"] for component in components.values()), 2)
    return {
        "total": total,
        "profile_name": profile["profile_name"],
        "assessed_on": assessed_on.isoformat(),
        "components": components,
        "disclaimer": "Profile fit only; this is not a probability of winning.",
    }
