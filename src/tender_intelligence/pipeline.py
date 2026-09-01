from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .classifier import classify_notice
from .config import load_profile, load_taxonomy
from .database import (
    connect_database,
    initialize_database,
    record_fetch_run,
    sync_notices,
)
from .normalize import normalize_notice
from .paths import DEFAULT_DB_PATH, PUBLISHED_DATA_DIR, RAW_DATA_DIR
from .publication import export_publication, restore_publication
from .scoring import score_opportunity
from .ted_client import TedClient, build_candidate_query


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_pipeline(
    *,
    countries: Iterable[str] = ("BEL", "ITA", "FIN"),
    limit: int | None = None,
    page_size: int = 250,
    scope: str = "ACTIVE",
    dry_run: bool = False,
    client: TedClient | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    raw_dir: Path = RAW_DATA_DIR,
    published_dir: Path = PUBLISHED_DATA_DIR,
) -> dict[str, Any]:
    countries = sorted({country.upper() for country in countries})
    taxonomy = load_taxonomy()
    profile = load_profile()
    client = client or TedClient()
    query = build_candidate_query(countries, taxonomy)

    validation = client.validate_query(query, scope=scope)
    if dry_run:
        return {
            "status": "validated",
            "query": query,
            "validation_timed_out": validation.get("timedOut", False),
        }

    started_at = _utc_now()
    connection = connect_database(db_path)
    initialize_database(connection)
    try:
        existing_count = connection.execute(
            "SELECT COUNT(*) FROM tender_notices"
        ).fetchone()[0]
        publication_json = published_dir / "tenders.json"
        if existing_count == 0 and publication_json.exists():
            restore_publication(connection, publication_json)

        response = client.search_all(
            query, page_size=page_size, max_notices=limit, scope=scope
        )
        fetched_at = _utc_now()
        raw_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snapshot_path = raw_dir / f"ted_search_{timestamp}.json"
        snapshot = {
            "source": client.base_url,
            "query": query,
            "countries": countries,
            "scope": scope,
            "fetched_at": fetched_at,
            "response": response,
        }
        snapshot_path.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        snapshot_path.chmod(0o600)

        processed = []
        for notice in response.get("notices", []):
            record = normalize_notice(notice, fetched_at)
            classification = classify_notice(record, taxonomy)
            score = score_opportunity(record, classification, profile)
            record.update(
                {
                    "primary_theme": classification["primary_theme"],
                    "matched_keywords": classification["matched_keywords"],
                    "matched_cpv": classification["matched_cpv"],
                    "classification_score": classification["classification_score"],
                    "is_relevant": classification["is_relevant"],
                    "opportunity_score": score["total"],
                    "score_explanation": score,
                }
            )
            processed.append(record)

        is_complete = bool(response.get("isComplete"))
        lifecycle = sync_notices(
            connection,
            processed,
            close_missing=scope == "ACTIVE" and is_complete,
            countries=countries,
            observed_at=fetched_at,
        )
        relevant_count = sum(record["is_relevant"] for record in processed)
        completed_at = _utc_now()
        publication_paths = export_publication(
            connection,
            published_dir,
            metadata={
                "generated_at": completed_at,
                "source": client.base_url,
                "query": query,
                "countries": countries,
                "scope": scope,
                "api_match_count": response.get("totalNoticeCount"),
                "received_count": len(processed),
                "fetched_page_count": response.get("fetchedPageCount", 1),
                "is_complete": is_complete,
                "lifecycle": lifecycle,
            },
        )
        record_fetch_run(
            connection,
            {
                "query": query,
                "countries": ",".join(countries),
                "scope": scope,
                "requested_limit": limit or 0,
                "api_match_count": response.get("totalNoticeCount"),
                "received_count": len(processed),
                "relevant_count": relevant_count,
                "started_at": started_at,
                "completed_at": completed_at,
                "status": "success",
                "error_message": None,
                "raw_snapshot_path": str(snapshot_path),
                "fetched_page_count": response.get("fetchedPageCount", 1),
                "is_complete": int(is_complete),
                "new_count": lifecycle["new"],
                "updated_count": lifecycle["updated"],
                "unchanged_count": lifecycle["unchanged"],
                "closed_count": lifecycle["closed"],
                "publication_json_path": str(publication_paths["json"]),
                "publication_parquet_path": str(publication_paths["parquet"]),
            },
        )
        return {
            "status": "success",
            "query": query,
            "api_match_count": response.get("totalNoticeCount"),
            "received_count": len(processed),
            "relevant_count": relevant_count,
            "fetched_page_count": response.get("fetchedPageCount", 1),
            "is_complete": is_complete,
            "lifecycle": lifecycle,
            "database_path": str(db_path),
            "raw_snapshot_path": str(snapshot_path),
            "publication_json_path": str(publication_paths["json"]),
            "publication_parquet_path": str(publication_paths["parquet"]),
        }
    except Exception as exc:
        completed_at = _utc_now()
        record_fetch_run(
            connection,
            {
                "query": query,
                "countries": ",".join(countries),
                "scope": scope,
                "requested_limit": limit or 0,
                "api_match_count": None,
                "received_count": 0,
                "relevant_count": 0,
                "started_at": started_at,
                "completed_at": completed_at,
                "status": "error",
                "error_message": str(exc)[:1000],
                "raw_snapshot_path": None,
                "fetched_page_count": 0,
                "is_complete": 0,
                "new_count": 0,
                "updated_count": 0,
                "unchanged_count": 0,
                "closed_count": 0,
                "publication_json_path": None,
                "publication_parquet_path": None,
            },
        )
        raise
    finally:
        connection.close()
