from __future__ import annotations

import html
import base64
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from tender_intelligence.data_source import load_dashboard_data
from tender_intelligence.countries import EU_COUNTRY_NAMES
from tender_intelligence.publication import resolve_publication_json
from tender_intelligence.export import export_notices_csv
from tender_intelligence.normalize import trusted_ted_url
from tender_intelligence.research_ui import (
    initialize_research, render_buyers, render_dossier_actions, render_dossier_tools,
    render_research_desk, saved_search_controls,
)
from tender_intelligence.paths import (
    DEFAULT_DB_PATH,
    PUBLISHED_JSON_PATH,
    PUBLISHED_PARQUET_PATH,
)


PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = DEFAULT_DB_PATH
PUBLICATION_JSON_PATH = PUBLISHED_JSON_PATH
PUBLICATION_PARQUET_PATH = PUBLISHED_PARQUET_PATH
LUXE_STYLE_PATH = PROJECT_ROOT / "assets" / "dashboard_luxe.css"
FIELD_ASSETS = PROJECT_ROOT / "assets" / "field"
MOTION_SCRIPT_PATH = PROJECT_ROOT / "assets" / "motion.js"
LOGO_PATH = PROJECT_ROOT / "assets" / "your-intelligence-coach-logo.png"
LOGO_URI = "/app/static/tender-meridian-logo.png"
LOGO_HTML = f'<img class="brand-logo" src="{LOGO_URI}" alt="" width="26" height="26">'
COUNTRY_NAMES = EU_COUNTRY_NAMES
COUNTRY_FLAG_STYLES = "\n".join(
    f'.flag--{code.lower()} {{ background-image:url("data:image/svg+xml;base64,'
    + base64.b64encode((PROJECT_ROOT / "assets" / "flags" / f"{code}.svg").read_bytes()).decode("ascii")
    + '"); }'
    for code in COUNTRY_NAMES
)

INK = "#17191C"
MUTED = "#686E76"
RULE = "#E2E2DF"
ACCENT = "#1E4F8F"
FIT_LABELS = {
    "country_fit": "Country", "theme_fit": "Technology theme",
    "classification_evidence": "Classification evidence",
    "deadline_runway": "Time until deadline", "budget_clarity": "Budget disclosed",
}
# Up to six series on one chart; distinguishable without being loud.
SERIES_COLORS = ("#1E4F8F", "#B5651D", "#2D6A4B", "#7A4E8C", "#8A8F96", "#A23B3B")


st.set_page_config(
    page_title="Tender Meridian · EU AI and data tenders",
    page_icon=str(LOGO_PATH),
    layout="wide",
    initial_sidebar_state="auto",
)


st.markdown(
    f"<style>{LUXE_STYLE_PATH.read_text(encoding='utf-8')}\n{COUNTRY_FLAG_STYLES}</style>",
    unsafe_allow_html=True,
)
st.markdown(
    '<a class="skip-link" href="#dashboard-content">Skip to dashboard content</a>',
    unsafe_allow_html=True,
)


def interface_components() -> tuple[Any, Any]:
    """Register the two script components; re-registering identical definitions is a no-op."""
    field = st.components.v2.component(
        "tender_field",
        html=(FIELD_ASSETS / "field.html").read_text(encoding="utf-8"),
        css=(FIELD_ASSETS / "field.css").read_text(encoding="utf-8"),
        js=(FIELD_ASSETS / "field.js").read_text(encoding="utf-8"),
    )
    motion = st.components.v2.component(
        "tender_motion",
        js=MOTION_SCRIPT_PATH.read_text(encoding="utf-8"),
        isolate_styles=False,
    )
    return field, motion


DEADLINE_BUCKETS = (
    "Deadline passed", "Within 7 days", "8–30 days", "31–90 days", "Over 90 days", "Not disclosed",
)


def plain_title(notice: pd.Series, limit: int = 96) -> str:
    title = " ".join(str(notice["title"] or "").split())
    country = COUNTRY_NAMES.get(notice["buyer_country"], "")
    for separator in (" – ", " - "):
        prefix = f"{country}{separator}"
        if country and title.startswith(prefix) and len(title) > len(prefix):
            title = title[len(prefix):]
            break
    return title if len(title) <= limit else f"{title[:limit - 1].rstrip()}…"


def field_payload(frame: pd.DataFrame, themes: list[str], noun: str, updated: str) -> dict[str, Any]:
    """Compact column arrays for the opening field: one entry per notice."""
    today = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    days = (pd.to_datetime(frame["deadline_date"], errors="coerce") - today).dt.days
    buckets = (
        pd.cut(days, bins=[-math.inf, -1, 7, 30, 90, math.inf], labels=False)
        .fillna(len(DEADLINE_BUCKETS) - 1).astype(int)
    )
    theme_index = {theme: index for index, theme in enumerate(themes)}
    country_codes = list(COUNTRY_NAMES)
    country_index = {code: index for index, code in enumerate(country_codes)}
    ids = frame["notice_id"].astype(str).tolist()
    market_count = frame["buyer_country"].nunique()
    return {
        "signature": f"{len(ids)}:{hash(tuple(ids))}",
        "updated": updated,
        "titleRest": f"{noun}, published across {market_count} EU "
                     f"{'country' if market_count == 1 else 'countries'}.",
        "themes": themes,
        "countries": country_codes,
        "countryNames": [COUNTRY_NAMES[code] for code in country_codes],
        "buckets": list(DEADLINE_BUCKETS),
        "id": ids,
        "t": [plain_title(notice) for _, notice in frame.iterrows()],
        "th": [theme_index.get(theme, 0) for theme in frame["primary_theme"].fillna("Unclassified")],
        "c": [country_index[code] for code in frame["buyer_country"]],
        "f": [int(round(score)) for score in frame["opportunity_score"].fillna(0)],
        "d": buckets.tolist(),
        "dl": [safe(value, "") for value in frame["deadline_date"]],
        "v": [
            "" if pd.isna(amount) else compact_money(amount, currency)
            for amount, currency in zip(frame["estimated_value"], frame["currency"])
        ],
    }


@st.cache_resource(ttl=60, show_spinner=False)
def load_notices(source_path: str, modified_at: float) -> tuple[pd.DataFrame, str]:
    # Callers filter into a copy before modifying the shared snapshot.
    del source_path, modified_at
    return load_dashboard_data(
        database_path=DB_PATH,
        parquet_path=PUBLICATION_PARQUET_PATH,
        json_path=PUBLICATION_JSON_PATH,
    )


def source_signature() -> tuple[str, float] | None:
    for path in (DB_PATH, PUBLICATION_PARQUET_PATH, resolve_publication_json(PUBLICATION_JSON_PATH)):
        if path.exists():
            return str(path), path.stat().st_mtime
    return None


def parse_json(value: object, fallback: object) -> object:
    if not isinstance(value, str) or not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def safe(value: object, fallback: str = "Not disclosed") -> str:
    if value is None or pd.isna(value):
        return fallback
    normalized = str(value).strip()
    if normalized == "" or normalized.lower() in {"none", "nan", "nat"}:
        return fallback
    return html.escape(normalized)


def compact_money(amount: object, currency: object = "EUR") -> str:
    if amount is None or pd.isna(amount):
        return "—"
    value = float(amount)
    prefix = "€" if currency == "EUR" else f"{safe(currency, '')} "
    if abs(value) >= 1_000_000_000:
        return f"{prefix}{value / 1_000_000_000:.1f}bn"
    if abs(value) >= 1_000_000:
        return f"{prefix}{value / 1_000_000:.1f}m"
    if abs(value) >= 1_000:
        return f"{prefix}{value / 1_000:.0f}k"
    return f"{prefix}{value:,.0f}"


def full_money(amount: object, currency: object) -> str:
    if amount is None or pd.isna(amount):
        return "Not disclosed"
    currency_text = "" if currency is None or pd.isna(currency) else f" {safe(currency)}"
    return f"{float(amount):,.0f}{currency_text}"


def flag(code: object) -> str:
    code_text = str(code or "")
    if code_text not in COUNTRY_NAMES:
        return ""
    return f'<span class="flag flag--{code_text.lower()}" aria-hidden="true"></span>'


def display_title(notice: pd.Series) -> str:
    """TED titles repeat the buyer country ("Italy – …"); the flag line already shows it."""
    title = str(notice["title"] or "")
    country = COUNTRY_NAMES.get(notice["buyer_country"], "")
    for separator in (" – ", " - "):
        prefix = f"{country}{separator}"
        if country and title.startswith(prefix) and len(title) > len(prefix):
            return safe(title[len(prefix):])
    return safe(title)


def page_intro(title: str, copy: str) -> None:
    st.markdown(
        f'<div class="page-intro"><h1>{html.escape(title)}</h1>'
        f'<p>{html.escape(copy)}</p></div>',
        unsafe_allow_html=True,
    )


def section_heading(title: str, copy: str = "") -> None:
    copy_markup = f'<p class="section-copy">{html.escape(copy)}</p>' if copy else ""
    st.markdown(
        f'<div class="section-head"><div class="section-title" role="heading" aria-level="2">'
        f'{html.escape(title)}</div></div>{copy_markup}',
        unsafe_allow_html=True,
    )


def registry_markup(frame: pd.DataFrame) -> str:
    headers = [
        ("Market", ""),
        ("Notice and buyer", ""),
        ("Theme", ""),
        ("Deadline", ""),
        ("Estimate", " registry-list__cell--num"),
        ("Fit", " registry-list__cell--num"),
        ("", ""),
    ]
    header_cells = "".join(
        f'<div class="registry-list__cell{modifier}" role="columnheader">{html.escape(label)}</div>'
        for label, modifier in headers
    )
    rows: list[str] = []
    for _, notice in frame.iterrows():
        market = COUNTRY_NAMES.get(notice["buyer_country"], notice["buyer_country"])
        score = float(notice["opportunity_score"]) if pd.notna(notice["opportunity_score"]) else 0
        lifecycle = str(notice.get("lifecycle_status") or "unchanged").lower()
        if lifecycle not in {"new", "updated", "unchanged", "closed"}:
            lifecycle = "unchanged"
        ted_url = trusted_ted_url(notice.get("ted_url"), str(notice["notice_id"]))
        rows.append(
            f'<div class="registry-list__row registry-list__row--{lifecycle}" role="row">'
            '<div class="registry-list__cell registry-list__cell--record" '
            f'role="cell" data-label="Market"><strong>{flag(notice["buyer_country"])}{safe(market)}</strong>'
            f'<small translate="no">{safe(notice["notice_id"])}</small>'
            f'<span class="lifecycle-chip lifecycle-{lifecycle}">{html.escape(lifecycle.title())}</span></div>'
            '<div class="registry-list__cell registry-list__cell--title" role="cell" data-label="Notice and buyer">'
            f'<strong>{display_title(notice)}</strong><small>{safe(notice["buyer_name"])}</small></div>'
            '<div class="registry-list__cell registry-list__cell--theme" role="cell" data-label="Theme">'
            f'{safe(notice["primary_theme"])}</div>'
            '<div class="registry-list__cell registry-list__mono" role="cell" data-label="Deadline">'
            f'{safe(notice["deadline_date"], "—")}</div>'
            '<div class="registry-list__cell registry-list__mono registry-list__cell--num" role="cell" data-label="Estimate">'
            f'{compact_money(notice["estimated_value"], notice["currency"])}</div>'
            '<div class="registry-list__cell registry-list__fit" role="cell" data-label="Profile fit">'
            f'{score:.0f}</div>'
            '<div class="registry-list__cell registry-list__cell--source" role="cell" data-label="Source">'
            f'<a href="{html.escape(ted_url, quote=True)}" target="_blank" rel="noopener noreferrer" '
            f'aria-label="Open {safe(notice["notice_id"])} on TED">TED ↗</a></div>'
            '</div>'
        )
    return (
        '<div class="registry-list" role="table" aria-label="Screened tender opportunities">'
        f'<div class="registry-list__row registry-list__head" role="row">{header_cells}</div>'
        f'{"".join(rows)}</div>'
    )


def evidence_table_markup(
    frame: pd.DataFrame, columns: list[tuple[str, str]], table_label: str
) -> str:
    header = "".join(
        f'<div class="evidence-cell" role="columnheader">{html.escape(label)}</div>'
        for _, label in columns
    )
    rows: list[str] = []
    for _, evidence in frame.iterrows():
        cells = "".join(
            '<div class="evidence-cell" role="cell" '
            f'data-label="{html.escape(label, quote=True)}">{safe(evidence[column])}</div>'
            for column, label in columns
        )
        rows.append(f'<div class="evidence-row" role="row">{cells}</div>')
    return (
        f'<div class="evidence-table" role="table" aria-label="{html.escape(table_label, quote=True)}" '
        f'style="--evidence-cols:{len(columns)}">'
        f'<div class="evidence-row evidence-head" role="row">{header}</div>{"".join(rows)}</div>'
    )


def style_chart(figure: Any, *, legend: bool = True) -> Any:
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "IBM Plex Sans, sans-serif", "color": INK, "size": 13},
        showlegend=legend,
        legend={
            "orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0,
            "title": None, "font": {"size": 12},
        },
        margin={"l": 40, "r": 24, "t": 48 if legend else 20, "b": 36},
        hoverlabel={
            "bgcolor": INK, "bordercolor": INK,
            "font": {"family": "IBM Plex Sans, sans-serif", "color": "#FFFFFF", "size": 13},
        },
    )
    figure.update_xaxes(
        showgrid=False, linecolor=RULE,
        tickfont={"size": 12, "color": MUTED},
        title_font={"size": 12, "color": MUTED},
    )
    figure.update_yaxes(
        gridcolor=RULE, zeroline=False, linecolor=RULE,
        tickfont={"size": 12, "color": MUTED},
        title_font={"size": 12, "color": MUTED},
    )
    return figure


def evidence_frames(selected: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    keyword_matches = parse_json(selected["matched_keywords_json"], {})
    cpv_matches = parse_json(selected["matched_cpv_json"], {})
    keyword_rows: list[dict[str, object]] = []
    if isinstance(keyword_matches, dict):
        for theme, matches in keyword_matches.items():
            for match in matches:
                keyword_rows.append(
                    {"theme": theme, "matched term": match.get("term"), "weight": match.get("weight")}
                )
    cpv_rows: list[dict[str, object]] = []
    if isinstance(cpv_matches, dict):
        for theme, matches in cpv_matches.items():
            for match in matches:
                cpv_rows.append(
                    {
                        "theme": theme, "CPV code": match.get("code"),
                        "rule": match.get("label"), "weight": match.get("weight"),
                    }
                )
    return pd.DataFrame(keyword_rows), pd.DataFrame(cpv_rows)



def main() -> None:
    initialize_research()
    available_source = source_signature()
    if available_source is None:
        st.markdown(
            '<div class="registry-shell" id="dashboard-content" tabindex="-1">'
            f'<div class="brand">{LOGO_HTML}<strong>Tender Meridian</strong></div>'
            '<div class="page-intro"><h1>No data loaded yet</h1>'
            '<p>Fetch a snapshot from TED to fill the workspace.</p></div></div>',
            unsafe_allow_html=True,
        )
        st.info(
            "No local database or published snapshot exists yet. Run the fetch command, then refresh this page."
        )
        st.code("python scripts/fetch_tenders.py", language="bash")
        st.stop()

    data, data_source_label = load_notices(*available_source)
    if not data.empty:
        data = data[data["buyer_country"].isin(COUNTRY_NAMES)].copy()
    if data.empty:
        st.warning("The available data source contains no tender notices.")
        st.stop()

    data["lifecycle_status"] = (
        data["lifecycle_status"].fillna("unchanged").astype(str).str.lower()
    )
    active_data = data[data["lifecycle_status"] != "closed"].copy()

    available_countries = list(COUNTRY_NAMES)
    default_countries = available_countries.copy()
    available_themes = sorted(data["primary_theme"].dropna().unique())
    lifecycle_order = ["new", "updated", "unchanged", "closed"]
    available_lifecycles = [
        status for status in lifecycle_order
        if status in set(data["lifecycle_status"])
    ]
    default_lifecycles = [
        status for status in available_lifecycles if status != "closed"
    ]
    sort_options = (
        "Highest profile fit",
        "Newest publication",
        "Nearest deadline",
        "Largest disclosed value",
    )


    def reset_query_desk() -> None:
        st.session_state["filter_query"] = ""
        st.session_state["filter_relevant"] = True
        st.session_state["filter_countries"] = default_countries
        st.session_state["filter_themes"] = available_themes
        st.session_state["filter_lifecycles"] = default_lifecycles
        st.session_state["filter_score"] = 0
        st.session_state["filter_sort"] = sort_options[0]


    def select_all_eu_markets() -> None:
        st.session_state["filter_countries"] = list(COUNTRY_NAMES)


    filter_defaults = {
        "filter_query": "",
        "filter_relevant": True,
        "filter_countries": default_countries,
        "filter_themes": available_themes,
        "filter_lifecycles": default_lifecycles,
        "filter_score": 0,
        "filter_sort": sort_options[0],
    }
    for state_key, default_value in filter_defaults.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = default_value
    if st.session_state.get("eu_country_scope_version") != 1:
        reset_query_desk()
        st.session_state["eu_country_scope_version"] = 1
    previous_lifecycle_defaults = st.session_state.get("lifecycle_auto_defaults")
    if previous_lifecycle_defaults is None or set(st.session_state["filter_lifecycles"]) == set(previous_lifecycle_defaults):
        st.session_state["filter_lifecycles"] = default_lifecycles.copy()
    st.session_state["lifecycle_auto_defaults"] = default_lifecycles.copy()

    with st.sidebar:
        st.markdown('<div class="sidebar-title">Filters</div>', unsafe_allow_html=True)
        search_query = st.text_input(
            "Search",
            placeholder="Title, buyer, notice ID or theme",
            type="search",
            autocomplete="off",
            key="filter_query",
            help="Searches the currently loaded snapshot without changing the TED source data.",
        )
        relevant_only = st.checkbox(
            "AI and data notices only",
            key="filter_relevant",
            help="Keeps notices that pass the CPV and keyword screen in config/taxonomy.json.",
        )
        with st.container(key="desk_scope"):
            country_count = len(st.session_state["filter_countries"])
            market_summary = "all 27" if country_count == 27 else f"{country_count} selected"
            with st.expander(f"Markets: {market_summary}", key="market_picker"):
                selected_countries = st.multiselect(
                    "Buyer market", options=available_countries,
                    format_func=lambda code: COUNTRY_NAMES.get(code, code),
                    key="filter_countries",
                    help="All 27 EU member states. Counts describe the loaded extract; an empty result does not prove a market has no tenders.",
                )
                st.button("Select all 27 EU markets", on_click=select_all_eu_markets, use_container_width=True)
            theme_count = len(st.session_state["filter_themes"])
            theme_summary = "all" if theme_count == len(available_themes) else f"{theme_count} selected"
            with st.expander(f"Themes: {theme_summary}", key="theme_picker"):
                selected_themes = st.multiselect(
                    "Technology theme", options=available_themes, key="filter_themes",
                )
            status_summary = ", ".join(status for status in st.session_state["filter_lifecycles"]) or "none"
            with st.expander(f"Status: {status_summary}", key="status_picker"):
                selected_lifecycles = st.multiselect(
                    "Record status", options=available_lifecycles, key="filter_lifecycles",
                    format_func=lambda status: status.title(),
                    help="New and updated refer to the latest successful refresh. Closed means the notice disappeared from a complete ACTIVE-scope refresh.",
                )
        minimum_score = st.slider(
            "Minimum profile fit", min_value=0, max_value=100, step=5,
            key="filter_score",
            help="Hides notices below this fit. Fit is a ranking aid, not a chance of winning.",
        )
        sort_mode = st.selectbox(
            "Sort by",
            options=sort_options,
            key="filter_sort",
        )
        st.button(
            "Reset all filters",
            on_click=reset_query_desk,
            use_container_width=True,
        )
        saved_search_controls(available_countries, available_themes, available_lifecycles)
        st.divider()
        st.caption(
            f"Data: EU TED Search API ({data_source_label.lower()}). "
            "The official notice and its documents are the source of truth."
        )

    filtered = data.copy()
    if relevant_only:
        filtered = filtered[filtered["is_relevant"] == 1]
    filtered = filtered[
        filtered["buyer_country"].isin(selected_countries)
        & filtered["primary_theme"].isin(selected_themes)
        & filtered["lifecycle_status"].isin(selected_lifecycles)
        & (filtered["opportunity_score"] >= minimum_score)
    ]
    if search_query.strip():
        searchable_columns = ["notice_id", "title", "buyer_name", "primary_theme"]
        search_index = (
            filtered[searchable_columns]
            .fillna("")
            .astype(str)
            .agg(" ".join, axis=1)
        )
        filtered = filtered[
            search_index.str.contains(search_query.strip(), case=False, regex=False)
        ]

    if sort_mode == "Newest publication":
        filtered = (
            filtered.assign(
                _sort_publication=pd.to_datetime(
                    filtered["publication_date"], errors="coerce"
                )
            )
            .sort_values(
                ["_sort_publication", "opportunity_score"],
                ascending=[False, False],
                na_position="last",
            )
            .drop(columns="_sort_publication")
        )
    elif sort_mode == "Nearest deadline":
        filtered = (
            filtered.assign(
                _sort_deadline=pd.to_datetime(filtered["deadline_date"], errors="coerce")
            )
            .sort_values(
                ["_sort_deadline", "opportunity_score"],
                ascending=[True, False],
                na_position="last",
            )
            .drop(columns="_sort_deadline")
        )
    elif sort_mode == "Largest disclosed value":
        filtered = filtered.sort_values(
            ["estimated_value", "opportunity_score"],
            ascending=[False, False],
            na_position="last",
        )
    else:
        filtered = filtered.sort_values(
            ["opportunity_score", "publication_date"],
            ascending=[False, False],
            na_position="last",
        )

    freshness = pd.to_datetime(data["fetched_at"], errors="coerce", utc=True).max()
    freshness_text = f"{freshness.day} {freshness:%b %Y, %H:%M} UTC" if pd.notna(freshness) else "date unknown"
    latest_publication = pd.to_datetime(data["publication_date"], errors="coerce").max()
    edition_text = latest_publication.strftime("%Y.%m.%d") if pd.notna(latest_publication) else "UNDATED"

    country_counts = active_data.groupby("buyer_country")["is_relevant"].agg(["size", "sum"])
    market_coverage = sorted(
        (
            (
                code,
                int(country_counts.at[code, "sum"]) if code in country_counts.index else 0,
                int(country_counts.at[code, "size"]) if code in country_counts.index else 0,
            )
            for code in COUNTRY_NAMES
        ),
        key=lambda item: (-item[1], COUNTRY_NAMES[item[0]]),
    )
    busiest_market = max((screened for _, screened, _ in market_coverage), default=0) or 1
    market_rows = "".join(
        f'<tr class="market-row"><td>{flag(code)}{COUNTRY_NAMES[code]}</td>'
        f'<td class="bar" aria-hidden="true"><i style="width:{100 * screened / busiest_market:.1f}%"></i></td>'
        f'<td class="num{" zero" if screened == 0 else ""}">{screened:,}</td>'
        f'<td class="num"><small>{total:,}</small></td></tr>'
        for code, screened, total in market_coverage
    )


    def open_workspace(page: str, notice_id: str | None = None) -> None:
        st.session_state["workspace_page"] = page
        if notice_id is not None:
            st.session_state["dossier_notice"] = notice_id


    st.markdown(
        '<header class="topbar">'
        f'<div class="brand">{LOGO_HTML}<strong>Tender Meridian</strong></div>'
        f'<div class="topbar-meta">TED data, updated {html.escape(freshness_text)}</div></header>',
        unsafe_allow_html=True,
    )
    page = st.radio(
        "Workspace navigation",
        ["Overview", "Opportunities", "Research desk", "Buyers", "Markets", "Timeline", "Dossier", "Method"],
        horizontal=True,
        key="workspace_page",
        label_visibility="collapsed",
    )

    st.markdown('<div id="dashboard-content" tabindex="-1"></div>', unsafe_allow_html=True)
    field_component, motion_component = interface_components()
    motion_component(key="tm_motion", data={"page": page})

    visible_eur = filtered.loc[filtered["currency"] == "EUR", "estimated_value"].sum(min_count=1)
    new_count = int((data["lifecycle_status"] == "new").sum())
    updated_count = int((data["lifecycle_status"] == "updated").sum())

    if page == "Overview" and not filtered.empty:
        def open_field_notice() -> None:
            state = st.session_state.get("tender_field")
            notice_id = getattr(state, "open", None)
            if notice_id is None and isinstance(state, dict):
                notice_id = state.get("open")
            if notice_id in set(data["notice_id"]):
                open_workspace("Dossier", str(notice_id))

        field_themes = sorted(set(available_themes) | set(filtered["primary_theme"].fillna("Unclassified")))
        field_component(
            key="tender_field",
            data=field_payload(
                filtered, field_themes,
                "AI and data tenders" if relevant_only else "public tenders",
                f"TED snapshot, updated {freshness_text}",
            ),
            on_open_change=open_field_notice,
        )
        st.markdown(
            '<div class="figures" role="group" aria-label="Summary of the current view">'
            f'<div class="figure"><span>Notices in this view</span><strong>{len(filtered):,}</strong>'
            '<small>after your filters</small></div>'
            f'<div class="figure"><span>Open notices</span><strong>{len(active_data):,}</strong>'
            '<small>all themes, closed excluded</small></div>'
            f'<div class="figure"><span>New and updated</span><strong>{new_count:,} / {updated_count:,}</strong>'
            '<small>in the latest refresh</small></div>'
            f'<div class="figure"><span>Disclosed value</span><strong>{compact_money(visible_eur)}</strong>'
            '<small>EUR estimates in this view</small></div>'
            "</div>", unsafe_allow_html=True,
        )

    filter_tokens = [
        "all 27 markets" if len(selected_countries) == 27 else f"{len(selected_countries)} markets",
        "all themes" if len(selected_themes) == len(available_themes) else f"{len(selected_themes)} themes",
        f"fit {minimum_score} or higher" if minimum_score else "any fit",
        f"sorted by {sort_mode.lower()}",
    ]
    if search_query.strip():
        filter_tokens.insert(0, f'matching “{search_query.strip()}”')
    if page in {"Opportunities", "Markets", "Timeline", "Buyers"}:
        st.markdown(
            '<div class="view-summary" aria-label="Active filter summary">'
            f'<span><strong>{len(filtered):,}</strong> notices</span>'
            + "".join(f"<span>{safe(token)}</span>" for token in filter_tokens)
            + "</div>",
            unsafe_allow_html=True,
        )

    selected_dossier_available = st.session_state.get("dossier_notice") in set(data["notice_id"])
    if filtered.empty and page not in {"Method", "Research desk", "Buyers"} and not (page == "Dossier" and selected_dossier_available):
        st.warning("No notices match the current filters. Loosen a filter in the sidebar, or reset them.")
        st.button("Reset filters and show notices", on_click=reset_query_desk)
        st.stop()


    if page == "Overview":
        overview_columns = st.columns([1.6, 1], gap="large")
        with overview_columns[0]:
            st.markdown(
                '<div class="section-head block-head"><h2>Top of the list</h2>'
                f'<span>{safe(sort_mode)}</span></div>',
                unsafe_allow_html=True,
            )
            with st.container(key="top_notices"):
                for _, notice in filtered.head(8).iterrows():
                    with st.container(key=f"featured_{notice['notice_id']}"):
                        deadline = safe(notice["deadline_date"], "")
                        facts = [safe(notice["primary_theme"])]
                        if deadline:
                            facts.append(f"Deadline {deadline}")
                        if pd.notna(notice["estimated_value"]):
                            facts.append(compact_money(notice["estimated_value"], notice["currency"]))
                        st.markdown(
                            '<article class="notice-line"><div>'
                            f'<div class="meta">{flag(notice["buyer_country"])}'
                            f'<span>{safe(COUNTRY_NAMES.get(notice["buyer_country"], notice["buyer_country"]))}</span>'
                            f'<span translate="no">{safe(notice["notice_id"])}</span></div>'
                            f'<h3>{display_title(notice)}</h3>'
                            f'<p>{safe(notice["buyer_name"])}</p>'
                            f'<div class="facts">{" · ".join(facts)}</div></div>'
                            f'<div class="score"><strong>{float(notice["opportunity_score"]):.0f}</strong>'
                            '<span>fit / 100</span></div></article>',
                            unsafe_allow_html=True,
                        )
                        st.button("Open dossier", key=f"inspect_{notice['notice_id']}",
                                  type="tertiary", on_click=open_workspace,
                                  args=("Dossier", str(notice["notice_id"])))
            with st.container(key="all_notices"):
                st.button(f"See all {len(filtered):,} notices →", type="tertiary",
                          on_click=open_workspace, args=("Opportunities",))
        with overview_columns[1]:
            theme_counts = filtered["primary_theme"].fillna("Unclassified").value_counts()
            theme_rows = "".join(
                f'<div class="theme-row"><span>{safe(theme)}</span><strong>{int(count):,}</strong>'
                f'<div class="theme-track" aria-hidden="true"><i style="width:{100 * int(count) / len(filtered):.2f}%"></i></div></div>'
                for theme, count in theme_counts.items()
            )
            st.markdown(
                '<div class="section-head block-head"><h2>By theme</h2><span>in this view</span></div>'
                f'<div class="theme-list">{theme_rows}</div>'
                '<div class="section-head block-head"><h2>By market</h2><span>open notices</span></div>'
                '<table class="market-table">'
                '<caption class="sr-only">AI and data notices and all open notices per EU member state</caption>'
                '<thead><tr><th scope="col">Country</th><th scope="col"><span class="sr-only">Share</span></th>'
                '<th scope="col" class="num">AI/data</th><th scope="col" class="num">All</th></tr></thead>'
                f'<tbody>{market_rows}</tbody></table>'
                '<div class="section-head block-head"><h2>How fit is scored</h2><span>max points</span></div>'
                '<dl class="fit-summary">'
                '<div><dt>Technology theme</dt><dd>30</dd></div>'
                '<div><dt>Country</dt><dd>20</dd></div>'
                '<div><dt>Classification evidence</dt><dd>20</dd></div>'
                '<div><dt>Time until deadline</dt><dd>20</dd></div>'
                '<div><dt>Budget disclosed</dt><dd>10</dd></div></dl>'
                '<p class="footnote">Fit ranks notices against a configured profile. '
                'It does not estimate the chance of winning.</p>',
                unsafe_allow_html=True,
            )
            with st.container(key="method_link"):
                st.button("Read the method →", type="tertiary",
                          on_click=open_workspace, args=("Method",))
        st.markdown(
            '<p class="footnote footnote--page">TED lists notices published under EU '
            'procurement rules. National and below-threshold tenders may be missing. Check '
            'requirements and deadlines in the official notice before acting on anything here.</p>',
            unsafe_allow_html=True,
        )

    if page == "Opportunities":
        page_intro(
            "Opportunities",
            "Every notice that matches your filters. Open the TED record before judging scope, "
            "eligibility or value.",
        )
        registry_controls = st.columns([2.1, 0.72, 0.72, 1.15], vertical_alignment="bottom")
        with registry_controls[1]:
            page_size = st.selectbox(
                "Rows per page",
                options=(10, 20, 40),
                index=1,
                key="registry_page_size",
            )
        page_count = max(1, math.ceil(len(filtered) / page_size))
        if st.session_state.get("registry_page", 1) > page_count:
            st.session_state["registry_page"] = 1
        with registry_controls[2]:
            page_number = st.selectbox(
                "Page",
                options=tuple(range(1, page_count + 1)),
                key="registry_page",
            )
        page_start = (page_number - 1) * page_size
        page_end = min(page_start + page_size, len(filtered))
        page_frame = filtered.iloc[page_start:page_end]
        with registry_controls[0]:
            st.markdown(
                '<div class="registry-toolbar">'
                f'Showing <strong>{page_start + 1:,}–{page_end:,}</strong> of {len(filtered):,}</div>',
                unsafe_allow_html=True,
            )
        with registry_controls[3]:
            st.download_button(
                "Download CSV",
                data=export_notices_csv(filtered),
                file_name=f"tender-meridian-{edition_text.replace('.', '-')}.csv",
                mime="text/csv",
                use_container_width=True,
                help="Exports the complete filtered result, not only the visible page. Formula-like source text is neutralized for spreadsheet safety.",
            )
        st.markdown(registry_markup(page_frame), unsafe_allow_html=True)
        st.caption(
            "The Dossier tab shows why each notice was included and how its fit was calculated."
        )

    if page == "Markets":
        page_intro(
            "Markets",
            "Notices and average fit per buyer country for the current filters. These are counts "
            "from one snapshot, not the size of each market.",
        )
        comparison = (
            filtered.groupby("buyer_country", dropna=False)
            .agg(
                notice_count=("notice_id", "count"),
                average_profile_fit=("opportunity_score", "mean"),
                disclosed_eur_value=(
                    "estimated_value",
                    lambda values: values[
                        filtered.loc[values.index, "currency"].eq("EUR")
                    ].sum(min_count=1),
                ),
            )
            .reset_index()
        )
        comparison["market"] = comparison["buyer_country"].map(COUNTRY_NAMES).fillna(
            comparison["buyer_country"]
        )
        ledger = []
        for code in selected_countries:
            row = comparison[comparison["buyer_country"] == code]
            if row.empty:
                ledger.append((code, 0, None, None))
            else:
                ledger.append((
                    code, int(row.iloc[0]["notice_count"]),
                    float(row.iloc[0]["average_profile_fit"]), row.iloc[0]["disclosed_eur_value"],
                ))
        ledger.sort(key=lambda item: (-item[1], COUNTRY_NAMES[item[0]]))
        largest = max((count for _, count, _, _ in ledger), default=0) or 1
        ledger_rows = "".join(
            f'<tr><td>{flag(code)}{COUNTRY_NAMES[code]}</td>'
            f'<td class="bar" aria-hidden="true"><i style="width:{100 * count / largest:.1f}%"></i></td>'
            f'<td class="num{" zero" if count == 0 else ""}">{count:,}</td>'
            f'<td class="num">{"—" if average is None else f"{average:.1f}"}</td>'
            f'<td class="num">{compact_money(value)}</td></tr>'
            for code, count, average, value in ledger
        )
        st.markdown(
            '<div class="market-ledger"><table class="market-table">'
            '<caption class="sr-only">Notices, average fit and disclosed value per selected market</caption>'
            '<thead><tr><th scope="col">Country</th><th scope="col"><span class="sr-only">Share</span></th>'
            '<th scope="col" class="num">Notices</th><th scope="col" class="num">Avg. fit</th>'
            '<th scope="col" class="num">Disclosed EUR</th></tr></thead>'
            f'<tbody>{ledger_rows}</tbody></table></div>',
            unsafe_allow_html=True,
        )
        with st.expander("Sortable table"):
            st.dataframe(
                comparison[["market", "notice_count", "average_profile_fit", "disclosed_eur_value"]],
                width="stretch", hide_index=True,
                column_config={
                    "market": "Buyer market", "notice_count": "Visible notices",
                    "average_profile_fit": st.column_config.NumberColumn("Average fit", format="%.1f"),
                    "disclosed_eur_value": st.column_config.NumberColumn("Disclosed EUR", format="€%.0f"),
                },
            )

    if page == "Timeline":
        page_intro(
            "Timeline",
            "Notices published per month for the current filters. A short snapshot can look "
            "uneven; this is not a forecast.",
        )
        trends = filtered.copy()
        trends["publication_month"] = pd.to_datetime(
            trends["publication_date"], errors="coerce"
        ).dt.to_period("M").dt.to_timestamp()
        trends = (
            trends.dropna(subset=["publication_month"])
            .groupby(["publication_month", "buyer_country"])
            .size().reset_index(name="notice_count")
        )
        if trends.empty:
            st.info("No valid publication dates are available for the selected notices.")
        else:
            trend_mode = st.radio("Show", ["Combined view", "By market"], horizontal=True, key="timeline_mode")
            if trend_mode == "Combined view":
                plotted = trends.groupby("publication_month", as_index=False)["notice_count"].sum()
                plotted["buyer_country"] = "Selected markets combined"
            else:
                if "timeline_countries" in st.session_state:
                    st.session_state["timeline_countries"] = [c for c in st.session_state["timeline_countries"] if c in selected_countries][:6]
                trend_default = [c for c in filtered["buyer_country"].value_counts().index if c in selected_countries][:6]
                trend_countries = st.multiselect(
                    "Markets on chart (up to six for readability)", options=selected_countries,
                    default=trend_default if "timeline_countries" not in st.session_state else None,
                    format_func=lambda c: COUNTRY_NAMES[c], max_selections=6, key="timeline_countries",
                )
                plotted = trends[trends["buyer_country"].isin(trend_countries)]
                st.caption("Choose any of the 27 EU markets. The accessible table below includes every market in the filtered view.")
            chart_arguments = {
                "data_frame": plotted, "x": "publication_month", "y": "notice_count",
                "color": "buyer_country", "color_discrete_sequence": SERIES_COLORS,
                "labels": {
                    "publication_month": "Publication month", "notice_count": "Visible notices",
                    "buyer_country": "Buyer market",
                },
            }
            if plotted["publication_month"].nunique() >= 4:
                chart = px.line(**chart_arguments, markers=True, line_dash="buyer_country")
                chart.update_traces(line={"width": 2}, marker={"size": 6})
            else:
                chart = px.bar(**chart_arguments, barmode="group", text="notice_count")
                chart.update_traces(marker_line_width=0, textposition="outside")
            style_chart(chart, legend=trend_mode == "By market")
            if plotted.empty:
                st.info("Choose a market with dated notices to draw the chart.")
            else:
                st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})
            with st.expander("Data table"):
                trends["market"] = trends["buyer_country"].map(COUNTRY_NAMES)
                st.dataframe(trends, width="stretch", hide_index=True)

    if page == "Research desk":
        render_research_desk(data, filtered, open_workspace)

    if page == "Buyers":
        render_buyers(data, filtered, open_workspace)

    if page == "Dossier":
        page_intro(
            "Dossier",
            "One notice in full: the source record, how its fit was calculated and what matched.",
        )
        detail_options = filtered.sort_values("opportunity_score", ascending=False)
        routed_id = st.session_state.get("dossier_notice")
        if routed_id in set(data["notice_id"]) and routed_id not in set(detail_options["notice_id"]):
            detail_options = pd.concat([data[data["notice_id"].eq(routed_id)], detail_options])
            st.caption("This notice is outside your current filters. It stays available here.")
        detail_lookup = detail_options.set_index("notice_id")
        detail_labels: dict[str, str] = {}
        for notice_id, notice in detail_lookup.iterrows():
            title = str(notice["title"])
            concise_title = title if len(title) <= 74 else f"{title[:73].rstrip()}…"
            detail_labels[str(notice_id)] = (
                f'[{notice["buyer_country"]}] {notice_id} — {concise_title}'
            )
        if st.session_state.get("dossier_notice") not in detail_options["notice_id"].tolist():
            st.session_state["dossier_notice"] = detail_options["notice_id"].iloc[0]
        selected_id = st.selectbox(
            "Notice", key="dossier_notice", options=detail_options["notice_id"].tolist(),
            format_func=lambda notice_id: detail_labels[str(notice_id)],
        )
        selected = detail_options.loc[detail_options["notice_id"].eq(selected_id)].iloc[0]
        st.markdown(
            '<div class="dossier"><div>'
            f'<div class="dossier-code">{flag(selected["buyer_country"])}'
            f'<span>{safe(COUNTRY_NAMES.get(selected["buyer_country"], selected["buyer_country"]))}</span>'
            f'<span translate="no">TED {safe(selected["notice_id"])}</span></div>'
            f'<div class="dossier-title" role="heading" aria-level="2">{display_title(selected)}</div>'
            f'<p class="dossier-buyer">{safe(selected["buyer_name"])}</p></div>'
            '<dl class="dossier-facts">'
            f'<div class="fit"><dt>Profile fit</dt><dd>{selected["opportunity_score"]:.0f} / 100</dd></div>'
            f'<div><dt>Deadline</dt><dd>{safe(selected["deadline_date"])}</dd></div>'
            f'<div><dt>Estimate</dt><dd>{full_money(selected["estimated_value"], selected["currency"])}</dd></div>'
            f'<div><dt>Theme</dt><dd>{safe(selected["primary_theme"])}</dd></div>'
            f'<div><dt>Status</dt><dd>{safe(str(selected["lifecycle_status"]).title())}</dd></div>'
            '</dl></div>',
            unsafe_allow_html=True,
        )
        render_dossier_actions(
            selected, trusted_ted_url(selected.get("ted_url"), str(selected["notice_id"]))
        )
        score_details = parse_json(selected["score_explanation_json"], {})
        components = score_details.get("components", {}) if isinstance(score_details, dict) else {}
        fit_rows = []
        for name, details in components.items():
            points = float(details.get("points", 0))
            maximum = float(details.get("max", 0))
            percent = 0 if maximum <= 0 else min(100, 100 * points / maximum)
            fit_rows.append(
                '<div class="fit-row">'
                f'<span>{html.escape(FIT_LABELS.get(name, name.replace("_", " ").capitalize()))}</span>'
                f'<div class="fit-track"><i style="width:{percent:.1f}%"></i></div>'
                f'<b>{points:g} / {maximum:g}</b>'
                f'<p>{safe(details.get("reason"), "")}</p></div>'
            )
        section_heading("How the fit was calculated", "Points per component, with the reason for each.")
        st.markdown(f'<div class="fit-ruler">{"".join(fit_rows)}</div>', unsafe_allow_html=True)
        keyword_frame, cpv_frame = evidence_frames(selected)
        evidence_columns = st.columns(2)
        with evidence_columns[0]:
            st.markdown(
                '<div class="evidence-title" role="heading" aria-level="3">Matched keywords</div>',
                unsafe_allow_html=True,
            )
            if keyword_frame.empty:
                st.caption("No configured keyword matched this notice.")
            else:
                st.markdown(
                    evidence_table_markup(
                        keyword_frame,
                        [("theme", "Theme"), ("matched term", "Matched term"), ("weight", "Weight")],
                        "Matched keyword evidence",
                    ),
                    unsafe_allow_html=True,
                )
        with evidence_columns[1]:
            st.markdown(
                '<div class="evidence-title" role="heading" aria-level="3">Matched CPV codes</div>',
                unsafe_allow_html=True,
            )
            if cpv_frame.empty:
                st.caption("No configured CPV rule matched this notice.")
            else:
                st.markdown(
                    evidence_table_markup(
                        cpv_frame,
                        [
                            ("theme", "Theme"), ("CPV code", "CPV code"),
                            ("rule", "Rule"), ("weight", "Weight"),
                        ],
                        "Matched CPV evidence",
                    ),
                    unsafe_allow_html=True,
                )
        render_dossier_tools(selected, data, open_workspace)

    if page == "Method":
        page_intro(
            "Method",
            "Every step is rule-based, so any ranking can be traced back to the notice text "
            "and the configured rules.",
        )
        st.markdown(
            '<ol class="method-steps">'
            '<li><div class="method-title" role="heading" aria-level="3">Build the candidate pool</div><p>Query open TED notices by country, broad CPV families and explicit AI and data phrases.</p></li>'
            '<li><div class="method-title" role="heading" aria-level="3">Normalise each notice</div><p>Standardise buyer, country, dates, CPV codes, value, currency and the link to the source.</p></li>'
            '<li><div class="method-title" role="heading" aria-level="3">Screen with visible rules</div><p>Apply versioned multilingual keywords and narrower CPV rules. Every match is kept so it can be checked.</p></li>'
            '<li><div class="method-title" role="heading" aria-level="3">Track changes and rank</div><p>Compare complete snapshots to mark new, updated and closed notices. Fit adds country, theme, evidence, time until deadline and budget disclosure. It does not predict a win.</p></li>'
            '</ol>', unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="limits-note"><strong>Limits.</strong> The buyer country may differ from where the work is delivered. '
            'Budgets can be missing or apply to a single lot. Counts of open notices change daily. The classifier is a '
            'baseline until a labelled validation set reports its precision and recall.</div>',
            unsafe_allow_html=True,
        )
        st.link_button(
            "TED Search API documentation ↗",
            "https://docs.ted.europa.eu/api/latest/search.html",
        )

    st.markdown(
        '<footer class="workspace-footer"><span><strong>Tender Meridian</strong> · an independent research project</span>'
        '<span>Data from <a href="https://ted.europa.eu/en/" target="_blank" rel="noopener noreferrer">TED, Publications Office of the EU</a></span>'
        '</footer>', unsafe_allow_html=True,
    )


main()
