from __future__ import annotations

import re
from typing import Any, Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .normalize import clean_public_text, is_valid_notice_id
from .countries import EU_COUNTRY_CODES


TED_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
COUNTRY_PATTERN = re.compile(r"^[A-Z]{3}$")
MAX_PAGE_SIZE = 250
MAX_PAGE_NUMBER_RESULTS = 15_000
MAX_FETCH_NOTICES = 100_000

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
    invalid = [country for country in values if not COUNTRY_PATTERN.fullmatch(country) or country not in EU_COUNTRY_CODES]
    if invalid:
        raise ValueError(f"Invalid ISO alpha-3 EU member-state code(s): {', '.join(invalid)}")
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
                "User-Agent": "tender-meridian/0.1 (educational portfolio project)",
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
        pagination_mode: str = "PAGE_NUMBER",
        iteration_token: str | None = None,
    ) -> dict[str, Any]:
        if not 0 <= limit <= MAX_PAGE_SIZE:
            raise ValueError(f"TED page limit must be between 0 and {MAX_PAGE_SIZE}.")
        if page < 1:
            raise ValueError("TED page number must be at least 1.")
        if scope not in {"LATEST", "ACTIVE", "ALL"}:
            raise ValueError("scope must be LATEST, ACTIVE, or ALL.")
        if pagination_mode not in {"PAGE_NUMBER", "ITERATION"}:
            raise ValueError("Unsupported TED pagination mode.")
        if iteration_token is not None and (pagination_mode != "ITERATION" or not isinstance(iteration_token, str) or not iteration_token):
            raise ValueError("Iteration tokens require ITERATION mode.")

        payload = {
            "query": query,
            "fields": fields or DEFAULT_FIELDS,
            "page": page,
            "limit": limit,
            "scope": scope,
            "checkQuerySyntax": check_query_syntax,
            "paginationMode": pagination_mode,
            "onlyLatestVersions": True,
        }
        if iteration_token is not None:
            payload["iterationNextToken"] = iteration_token
        body = self._post(payload)
        if "notices" not in body or "totalNoticeCount" not in body:
            raise TedApiError("TED response is missing mandatory search fields.")
        if body.get("timedOut"):
            raise TedApiError("TED search timed out. No complete snapshot can be published.")
        notices = body.get("notices", [])
        if not isinstance(notices, list):
            raise TedApiError("TED returned an invalid notices collection.")
        if len(notices) > limit:
            raise TedApiError("TED returned more notices than requested.")
        if any(not isinstance(notice, dict) or not is_valid_notice_id(notice.get("publication-number")) for notice in notices):
            raise TedApiError("TED returned an invalid publication number or notice shape.")
        total = body.get("totalNoticeCount", 0)
        if total is None and check_query_syntax:
            total = 0
        if isinstance(total, bool):
            raise TedApiError("TED returned an invalid total notice count.")
        try:
            parsed_total = int(total)
        except (TypeError, ValueError) as exc:
            raise TedApiError("TED returned an invalid total notice count.") from exc
        if parsed_total < len(notices) or isinstance(total, float):
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
        """Use stable iteration for complete snapshots; page numbers for small caps.

        Count estimates are not the iteration stopping condition: a live TED
        latest-version iteration can exhaust before its reported match count.
        Confirm terminal emptiness with the same cursor before marking complete.
        Reject timed-out, duplicate, drifting or truncated results instead of
        closing notices against an incomplete snapshot.
        """
        if not 1 <= page_size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
        if max_notices is not None and max_notices < 1:
            raise ValueError("max_notices must be positive when provided.")

        mode = "ITERATION" if max_notices is None or max_notices > MAX_PAGE_NUMBER_RESULTS else "PAGE_NUMBER"
        first = self.search(query, limit=page_size, page=1, scope=scope, fields=fields, pagination_mode=mode)
        total = int(first.get("totalNoticeCount") or 0)
        target = total if max_notices is None else min(total, max_notices)
        if target > MAX_FETCH_NOTICES:
            raise TedApiError("TED result exceeds the bounded 100,000-notice extraction limit. Narrow the scope.")

        notices = list(first.get("notices", []))[:target]
        fetched_pages = 1
        page = 2
        token = first.get("iterationNextToken")
        seen_tokens: set[str] = set()
        iteration_finished = mode == "ITERATION" and total == 0
        if mode == "ITERATION" and total > 0 and not notices:
            raise TedApiError("TED returned an empty initial iteration with a positive match count.")
        seen_ids = {notice["publication-number"] for notice in notices}
        if len(seen_ids) != len(notices) or None in seen_ids:
            raise TedApiError("TED returned missing or duplicate publication numbers.")
        while (mode == "ITERATION" and not iteration_finished and (max_notices is None or len(notices) < max_notices)) or (mode == "PAGE_NUMBER" and len(notices) < target):
            if mode == "ITERATION":
                if not isinstance(token, str) or not token or token in seen_tokens:
                    raise TedApiError("TED iteration token is missing or repeated before the snapshot is complete.")
                seen_tokens.add(token)
                request_token = token
                response = self.search(query, limit=page_size, scope=scope, fields=fields, pagination_mode=mode, iteration_token=token)
                token = response.get("iterationNextToken")
            else:
                response = self.search(query, limit=page_size, page=page, scope=scope, fields=fields)
            if response["totalNoticeCount"] != total:
                raise TedApiError("TED result count changed during retrieval; rerun the snapshot.")
            page_notices = list(response.get("notices", []))
            fetched_pages += 1
            if not page_notices:
                if mode != "ITERATION" or not notices:
                    raise TedApiError("TED returned an empty page before the snapshot was complete.")
                confirmation = self.search(query, limit=page_size, scope=scope, fields=fields, pagination_mode=mode, iteration_token=request_token)
                fetched_pages += 1
                if confirmation["notices"] or confirmation["totalNoticeCount"] != total:
                    raise TedApiError("TED iteration exhaustion could not be confirmed; rerun the snapshot.")
                iteration_finished = True
                break
            for notice in page_notices:
                notice_id = notice.get("publication-number") if isinstance(notice, dict) else None
                if not isinstance(notice_id, str) or not notice_id or notice_id in seen_ids:
                    raise TedApiError("TED returned missing or duplicate publication numbers.")
                seen_ids.add(notice_id)
            notices.extend(page_notices)
            if len(notices) > MAX_FETCH_NOTICES:
                raise TedApiError("TED iteration exceeds the bounded 100,000-notice extraction limit.")
            page += 1

        if mode == "PAGE_NUMBER":
            notices = notices[:target]
        elif max_notices is not None:
            notices = notices[:max_notices]
        combined = dict(first)
        combined.update(
            {
                "notices": notices,
                "totalNoticeCount": total,
                "fetchedPageCount": fetched_pages,
                "isComplete": iteration_finished if mode == "ITERATION" else len(notices) >= total,
                "paginationMode": mode,
            }
        )
        combined.pop("iterationNextToken", None)
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
