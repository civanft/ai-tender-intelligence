from __future__ import annotations

import re
from typing import Any, Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .normalize import clean_public_text


TED_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
COUNTRY_PATTERN = re.compile(r"^[A-Z]{3}$")
MAX_PAGE_SIZE = 250
MAX_PAGE_NUMBER_RESULTS = 15_000

DEFAULT_FIELDS = [
    "publication-number",
    "publication-date",
    "notice-title",
    "buyer-name",
    "buyer-country",
    "classification-cpv",
    "main-classification-proc",
    "additional-classification-lot",
    "deadline-receipt-tender-date-lot",
    "estimated-value-proc",
    "estimated-value-cur-proc",
    "place-of-performance",
    "notice-type",
    "procedure-type",
    "description-proc",
    "description-lot",
    "links",
]


class TedApiError(RuntimeError):
    """A readable error raised for TED network or response failures."""


def _safe_log_text(value: Any) -> str:
    return " ".join(clean_public_text(value, max_chars=500).split())


def _validated_countries(countries: Iterable[str]) -> list[str]:
    values = sorted({country.upper().strip() for country in countries})
    if not values:
        raise ValueError("At least one buyer country is required.")
    invalid = [country for country in values if not COUNTRY_PATTERN.fullmatch(country)]
    if invalid:
        raise ValueError(f"Invalid ISO alpha-3 country code(s): {', '.join(invalid)}")
    return values


def build_candidate_query(
    countries: Iterable[str], taxonomy: dict[str, Any]
) -> str:
    """Build a TED expert query for a broad candidate set.

    The local classifier applies the narrower final relevance rule.
    """
    country_terms = " ".join(_validated_countries(countries))
    cpv_terms = " OR ".join(
        f"{prefix}*" for prefix in taxonomy["candidate_query_cpv_prefixes"]
    )
    phrases = []
    for phrase in taxonomy["candidate_query_phrases"]:
        if '"' in phrase:
            raise ValueError("Candidate query phrases cannot contain double quotes.")
        phrases.append(f'"{phrase}"')
    phrase_terms = " OR ".join(phrases)
    return (
        f"buyer-country IN ({country_terms}) AND "
        f"(classification-cpv = ({cpv_terms}) OR FT = ({phrase_terms})) "
        "SORT BY publication-date DESC"
    )


class TedClient:
    def __init__(
        self,
        base_url: str = TED_SEARCH_URL,
        timeout_seconds: int = 30,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.session = session or self._build_session()

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"POST"}),
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "ai-tender-intelligence/0.1 (educational portfolio project)",
            }
        )
        return session

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.session.post(
                self.base_url, json=payload, timeout=self.timeout_seconds
            )
        except requests.RequestException as exc:
            raise TedApiError(
                f"Could not reach the TED Search API: {_safe_log_text(exc)}"
            ) from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise TedApiError(
                f"TED returned HTTP {response.status_code} with a non-JSON response."
            ) from exc

        if not isinstance(body, dict):
            raise TedApiError("TED returned an unexpected JSON response shape.")
        if not response.ok:
            message = body.get("message") or body.get("error") or "Unknown TED API error"
            message = _safe_log_text(message)
            raise TedApiError(f"TED returned HTTP {response.status_code}: {message}")
        return body

    def search(
        self,
        query: str,
        *,
        limit: int = 50,
        page: int = 1,
        scope: str = "ACTIVE",
        check_query_syntax: bool = False,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        if not 0 <= limit <= MAX_PAGE_SIZE:
            raise ValueError(f"TED page limit must be between 0 and {MAX_PAGE_SIZE}.")
        if page < 1:
            raise ValueError("TED page number must be at least 1.")
        if scope not in {"LATEST", "ACTIVE", "ALL"}:
            raise ValueError("scope must be LATEST, ACTIVE, or ALL.")

        payload = {
            "query": query,
            "fields": fields or DEFAULT_FIELDS,
            "page": page,
            "limit": limit,
            "scope": scope,
            "checkQuerySyntax": check_query_syntax,
            "paginationMode": "PAGE_NUMBER",
            "onlyLatestVersions": True,
        }
        body = self._post(payload)
        notices = body.get("notices", [])
        if not isinstance(notices, list):
            raise TedApiError("TED returned an invalid notices collection.")
        if len(notices) > limit:
            raise TedApiError("TED returned more notices than requested.")
        total = body.get("totalNoticeCount", 0)
        if total is None and check_query_syntax:
            total = 0
        if isinstance(total, bool):
            raise TedApiError("TED returned an invalid total notice count.")
        try:
            parsed_total = int(total)
        except (TypeError, ValueError) as exc:
            raise TedApiError("TED returned an invalid total notice count.") from exc
        if parsed_total < 0:
            raise TedApiError("TED returned an invalid total notice count.")
        body["totalNoticeCount"] = parsed_total
        return body

    def search_all(
        self,
        query: str,
        *,
        page_size: int = MAX_PAGE_SIZE,
        max_notices: int | None = None,
        scope: str = "ACTIVE",
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return one combined result assembled from TED page-number responses."""
        if not 1 <= page_size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
        if max_notices is not None and max_notices < 1:
            raise ValueError("max_notices must be positive when provided.")

        first = self.search(
            query, limit=page_size, page=1, scope=scope, fields=fields
        )
        total = int(first.get("totalNoticeCount") or 0)
        target = total if max_notices is None else min(total, max_notices)
        if target > MAX_PAGE_NUMBER_RESULTS:
            raise TedApiError(
                "TED page-number mode can retrieve at most 15,000 notices; "
                "use a narrower query or iteration mode."
            )

        notices = list(first.get("notices", []))[:target]
        fetched_pages = 1
        page = 2
        while len(notices) < target:
            response = self.search(
                query, limit=page_size, page=page, scope=scope, fields=fields
            )
            page_notices = list(response.get("notices", []))
            fetched_pages += 1
            if not page_notices:
                break
            notices.extend(page_notices)
            page += 1

        notices = notices[:target]
        combined = dict(first)
        combined.update(
            {
                "notices": notices,
                "totalNoticeCount": total,
                "fetchedPageCount": fetched_pages,
                "isComplete": len(notices) >= total,
            }
        )
        return combined

    def validate_query(
        self, query: str, *, scope: str = "ACTIVE", fields: list[str] | None = None
    ) -> dict[str, Any]:
        """Ask TED to parse the query without executing it."""
        return self.search(
            query,
            limit=1,
            scope=scope,
            check_query_syntax=True,
            fields=fields,
        )
