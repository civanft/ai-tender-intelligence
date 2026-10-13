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
from tender_intelligence.export import export_notices_csv
from tender_intelligence.normalize import trusted_ted_url
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
LOGO_PATH = PROJECT_ROOT / "assets" / "tender-intelligence-logo.png"
LOGO_URI = "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
LOGO_HTML = f'<img class="brand-logo" src="{LOGO_URI}" alt="Tender Intelligence logo" width="52" height="52">'
COUNTRY_NAMES = {"BEL": "Belgium", "ITA": "Italy", "FIN": "Finland"}
COUNTRY_COLORS = {"BEL": "#315EAA", "ITA": "#A75048", "FIN": "#34796F"}

INK = "#1B304C"
MUTED = "#5B6C80"
RULE = "#DAE1EA"
SURFACE = "#FFFFFF"


st.set_page_config(
    page_title="Tender Intelligence — European Market Desk",
    page_icon=str(LOGO_PATH),
    layout="wide",
    initial_sidebar_state="collapsed",
)


st.markdown(
    f"<style>{LUXE_STYLE_PATH.read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)
st.markdown(
    '<a class="skip-link" href="#dashboard-content">Skip to dashboard content</a>',
    unsafe_allow_html=True,
)


@st.cache_data(ttl=60, show_spinner=False)
def load_notices(source_path: str, modified_at: float) -> tuple[pd.DataFrame, str]:
    del source_path, modified_at
    return load_dashboard_data(
        database_path=DB_PATH,
        parquet_path=PUBLICATION_PARQUET_PATH,
        json_path=PUBLICATION_JSON_PATH,
    )


def source_signature() -> tuple[str, float] | None:
    for path in (DB_PATH, PUBLICATION_PARQUET_PATH, PUBLICATION_JSON_PATH):
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


def section_heading(index: str, title: str, copy: str) -> None:
    st.markdown(
        f'<div class="section-head"><span>{html.escape(index)}</span>'
        f'<div class="section-title" role="heading" aria-level="2">{html.escape(title)}</div></div>'
        f'<p class="section-copy">{html.escape(copy)}</p>',
        unsafe_allow_html=True,
    )


def registry_markup(frame: pd.DataFrame) -> str:
    headers = [
        "Record",
        "Notice & buyer",
        "Technology theme",
        "Deadline",
        "Estimate",
        "Fit / 100",
        "Source",
    ]
    header_cells = "".join(
        f'<div class="registry-list__cell" role="columnheader">{html.escape(label)}</div>'
        for label in headers
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
            '<div class="registry-list__cell registry-list__cell--record registry-list__mono" '
            f'role="cell" data-label="Record"><strong translate="no">{safe(notice["notice_id"])}</strong>'
            f'<small>{safe(market)} / {safe(notice["buyer_country"])}</small>'
            f'<span class="lifecycle-chip lifecycle-{lifecycle}">{html.escape(lifecycle)}</span></div>'
            '<div class="registry-list__cell registry-list__cell--title" role="cell" data-label="Notice & buyer">'
            f'<strong>{safe(notice["title"])}</strong><small>{safe(notice["buyer_name"])}</small></div>'
            '<div class="registry-list__cell registry-list__cell--theme" role="cell" data-label="Technology theme">'
            f'{safe(notice["primary_theme"])}</div>'
            '<div class="registry-list__cell registry-list__mono" role="cell" data-label="Deadline">'
            f'{safe(notice["deadline_date"])}</div>'
            '<div class="registry-list__cell registry-list__mono" role="cell" data-label="Estimate">'
            f'{full_money(notice["estimated_value"], notice["currency"])}</div>'
            '<div class="registry-list__cell registry-list__fit" role="cell" data-label="Profile fit">'
            f'{score:.0f}</div>'
            '<div class="registry-list__cell registry-list__cell--source" role="cell" data-label="Source">'
            f'<a href="{html.escape(ted_url, quote=True)}" target="_blank" rel="noopener noreferrer">View at TED ↗</a></div>'
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
        font={"family": "Public Sans, sans-serif", "color": INK, "size": 13},
        showlegend=legend,
        legend={
            "orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0,
            "title": None, "font": {"family": "IBM Plex Mono, monospace", "size": 10},
        },
        margin={"l": 40, "r": 24, "t": 55 if legend else 24, "b": 38},
        hoverlabel={
            "bgcolor": INK, "bordercolor": INK,
            "font": {"family": "IBM Plex Mono, monospace", "color": "#FFFFFF"},
        },
    )
    figure.update_xaxes(
        showgrid=False, linecolor=RULE,
        tickfont={"family": "IBM Plex Mono, monospace", "size": 10, "color": MUTED},
        title_font={"family": "Public Sans, sans-serif", "size": 12, "color": MUTED},
    )
    figure.update_yaxes(
        gridcolor=RULE, zeroline=False, linecolor=RULE,
        tickfont={"family": "IBM Plex Mono, monospace", "size": 10, "color": MUTED},
        title_font={"family": "Public Sans, sans-serif", "size": 12, "color": MUTED},
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


available_source = source_signature()
if available_source is None:
    st.markdown(
        '<div class="registry-shell" id="dashboard-content" tabindex="-1"><div class="registry-topline"><strong>Tender Intelligence / Public record</strong>'
        '<span>TED Search API</span><span>Local extract unavailable</span></div>'
        '<div class="registry-main"><div><div class="brand-index">European procurement observatory</div>'
        '<h1 class="registry-title"><span class="title-line">Tender <span class="slash">/</span></span>'
        '<span class="title-line">Intelligence</span></h1>'
        '<p class="registry-deck">Create the local extract to open the signal desk.</p></div></div></div>',
        unsafe_allow_html=True,
    )
    st.info(
        "No local database or published snapshot exists yet. Run the fetch command, then refresh this page."
    )
    st.code("python scripts/fetch_tenders.py", language="bash")
    st.stop()

data, data_source_label = load_notices(*available_source)
if data.empty:
    st.warning("The available data source contains no tender notices.")
    st.stop()

data["lifecycle_status"] = (
    data["lifecycle_status"].fillna("unchanged").astype(str).str.lower()
)
active_data = data[data["lifecycle_status"] != "closed"].copy()

available_countries = sorted(data["buyer_country"].dropna().unique())
default_countries = [
    code for code in ("BEL", "ITA", "FIN") if code in available_countries
] or available_countries
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

with st.sidebar:
    st.markdown(
        f'<div class="query-desk">{LOGO_HTML}<span>RESEARCH WORKSPACE</span>'
        '<strong>Find your focus.</strong>'
        '<p>Choose the markets and technologies you want to explore.</p></div>',
        unsafe_allow_html=True,
    )
    search_query = st.text_input(
        "Search registry",
        placeholder="Notice, buyer, ID or theme…",
        type="search",
        autocomplete="off",
        key="filter_query",
        help="Searches the currently loaded snapshot without changing the TED source data.",
    )
    relevant_only = st.checkbox(
        "Show screened opportunities only",
        key="filter_relevant",
        help="Uses the CPV + keyword evidence threshold in config/taxonomy.json.",
    )
    selected_countries = st.multiselect(
        "Buyer market", options=available_countries,
        format_func=lambda code: COUNTRY_NAMES.get(code, code),
        key="filter_countries",
    )
    selected_themes = st.multiselect(
        "Technology theme", options=available_themes,
        key="filter_themes",
    )
    selected_lifecycles = st.multiselect(
        "Record status",
        options=available_lifecycles,
        key="filter_lifecycles",
        format_func=lambda status: status.title(),
        help="New and updated refer to the latest successful refresh. Closed means the notice disappeared from a complete ACTIVE-scope refresh.",
    )
    minimum_score = st.slider(
        "Minimum profile fit", min_value=0, max_value=100, step=5,
        key="filter_score",
        help="A ranking filter, not a success-probability threshold.",
    )
    sort_mode = st.selectbox(
        "Sort records",
        options=sort_options,
        key="filter_sort",
    )
    st.button(
        "Reset all filters",
        on_click=reset_query_desk,
        use_container_width=True,
    )
    st.divider()
    st.caption(f"Loaded from: {data_source_label}")
    st.caption(
        "Source: EU TED Search API. The official notice and procurement documents remain the source of truth."
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
freshness_text = freshness.strftime("%Y-%m-%d / %H:%M UTC") if pd.notna(freshness) else "Unknown"
latest_publication = pd.to_datetime(data["publication_date"], errors="coerce").max()
edition_text = latest_publication.strftime("%Y.%m.%d") if pd.notna(latest_publication) else "UNDATED"

country_cells = []
for code in ("BEL", "ITA", "FIN"):
    country_data = active_data[active_data["buyer_country"] == code]
    screened = int(country_data["is_relevant"].sum())
    share = 100 * screened / len(country_data) if len(country_data) else 0
    country_cells.append(
        f'<div class="country-cell country-cell--{code.lower()}">'
        f'<span class="country-name">{COUNTRY_NAMES[code]}<small translate="no">{code}</small></span>'
        f'<strong>{screened:,}<small>screened</small></strong>'
        f'<div class="country-track" aria-hidden="true"><i style="width:{share:.2f}%"></i></div>'
        f'<em>{len(country_data):,} active notices · {share:.0f}% screened</em>'
        "</div>"
    )


def open_workspace(page: str, notice_id: str | None = None) -> None:
    st.session_state["workspace_page"] = page
    if notice_id is not None:
        st.session_state["dossier_notice"] = notice_id


st.markdown(
    '<header class="product-header" id="dashboard-content" tabindex="-1">'
    f'<div class="product-brand">{LOGO_HTML}'
    '<div><strong>Tender Intelligence</strong><small>European procurement research</small></div></div>'
    '<div class="product-scope">BELGIUM <i>/</i> ITALY <i>/</i> FINLAND</div>'
    '<span class="source-badge">Public data · EU TED</span></header>',
    unsafe_allow_html=True,
)
page = st.radio(
    "Workspace navigation",
    ["Overview", "Opportunities", "Markets", "Timeline", "Dossier", "Method"],
    horizontal=True,
    key="workspace_page",
    label_visibility="collapsed",
)

if page == "Overview":
    st.markdown(
        '<section class="overview-hero"><div class="hero-copy">'
        '<div class="eyebrow">THE EUROPEAN MARKET DESK</div>'
        '<h1>Public contracts.<br><em>A clearer perspective.</em></h1>'
        '<p>Explore the organisations, technologies and opportunities shaping '
        'Europe’s AI and data markets. Start with the landscape. Follow the evidence.</p>'
        '<div class="hero-caption"><span class="scope-mark" aria-hidden="true"></span>'
        'Three markets. One connected view.</div></div>'
        '<div class="coverage-panel"><div class="coverage-label">'
        '<span>Market coverage</span><span>ACTIVE SNAPSHOT</span></div>'
        '<div class="country-rail">' + "".join(country_cells) + '</div>'
        f'<div class="extract-stamp">Last extraction<br><strong>{freshness_text}</strong></div>'
        '</div></section>',
        unsafe_allow_html=True,
    )
    entry_actions = st.columns([1, 1, 2])
    with entry_actions[0]:
        st.button("Explore opportunities →", type="primary", use_container_width=True,
                  on_click=open_workspace, args=("Opportunities",))
    with entry_actions[1]:
        st.button("Compare markets", use_container_width=True,
                  on_click=open_workspace, args=("Markets",))

visible_eur = filtered.loc[filtered["currency"] == "EUR", "estimated_value"].sum(min_count=1)
new_count = int((data["lifecycle_status"] == "new").sum())
updated_count = int((data["lifecycle_status"] == "updated").sum())
st.markdown(
    '<div class="signal-strip" role="group" aria-label="Current extract summary">'
    f'<div class="signal-metric"><span>Matching notices</span><strong>{len(filtered):,}</strong><small>in your current view</small></div>'
    f'<div class="signal-metric"><span>Active pool</span><strong>{len(active_data):,}</strong><small>closed records excluded</small></div>'
    f'<div class="signal-metric"><span>Change set</span><strong>{new_count} / {updated_count}</strong><small>new / updated</small></div>'
    f'<div class="signal-metric"><span>Disclosed EUR</span><strong>{compact_money(visible_eur)}</strong><small>visible procedures only</small></div>'
    "</div>", unsafe_allow_html=True,
)
st.markdown(
    '<div class="reading-note"><span>Opportunity score is a transparent fit with the configured learning profile.</span></div>',
    unsafe_allow_html=True,
)

filter_tokens = [
    f"{len(selected_countries)} markets",
    f"{len(selected_themes)} themes",
    f"Fit ≥ {minimum_score}",
    sort_mode,
]
if search_query.strip():
    filter_tokens.insert(0, f'Search: “{search_query.strip()}”')
st.markdown(
    '<div class="active-filter-bar" aria-label="Active filter summary">'
    '<span>Current view</span>'
    + "".join(
        f'<span class="filter-token">{safe(token)}</span>'
        for token in filter_tokens
    )
    + "</div>",
    unsafe_allow_html=True,
)

if filtered.empty and page != "Method":
    st.warning("No notices match the current filters. Broaden a filter in the query desk.")
    st.button("Reset filters and show notices", on_click=reset_query_desk)
    st.stop()


if page == "Overview":
    section_heading("Research brief", "Inside the current view",
                    "A starting point for your research, drawn from the notices matching your filters.")
    brief_columns = st.columns([1.45, 1], gap="large")
    with brief_columns[0]:
        with st.container(border=True, key="theme_panel"):
            st.markdown('<div class="panel-kicker">TECHNOLOGY LANDSCAPE</div>'
                        '<h3 class="panel-title">What is being procured?</h3>',
                        unsafe_allow_html=True)
            theme_counts = filtered["primary_theme"].fillna("Unclassified").value_counts()
            theme_rows = []
            for theme, count in theme_counts.items():
                percent = 100 * int(count) / len(filtered)
                theme_rows.append(
                    '<div class="theme-row"><div>'
                    f'<span>{safe(theme)}</span><strong>{int(count):,}</strong></div>'
                    f'<div class="theme-track"><i style="width:{percent:.2f}%"></i></div></div>'
                )
            st.markdown('<div class="theme-landscape">' + "".join(theme_rows) + '</div>',
                        unsafe_allow_html=True)
            st.caption("Notice counts by primary technology theme · current filters")
    with brief_columns[1]:
        with st.container(border=True, key="explanation_panel"):
            st.markdown(
                '<div class="panel-kicker">READ THE EVIDENCE</div>'
                '<h3 class="panel-title">A score you can question.</h3>'
                '<p class="panel-copy">Every profile-fit score has five visible components. '
                'Open a dossier to see what matched, which details are missing, and why a notice ranks where it does.</p>'
                '<div class="evidence-preview">'
                '<span>Country fit</span><b>20</b><span>Technology theme</span><b>30</b>'
                '<span>Classification evidence</span><b>20</b><span>Deadline runway</span><b>20</b>'
                '<span>Budget clarity</span><b>10</b></div>'
                '<p class="panel-note">Maximum points per component. Profile fit is not a probability of winning.</p>',
                unsafe_allow_html=True,
            )
            st.button("How the method works →", use_container_width=True,
                      on_click=open_workspace, args=("Method",))
    section_heading("Notice selection", "From the register",
                    "The first three notices in your current sort order. Inspect a dossier before assessing suitability.")
    featured_columns = [st.container() for _ in range(min(3, len(filtered)))]
    for column, (_, notice) in zip(featured_columns, filtered.head(3).iterrows()):
        with column:
            with st.container(border=True, key=f"featured_{notice['notice_id']}"):
                st.markdown(
                    '<article class="featured-notice">'
                    f'<div class="featured-meta"><span>{safe(COUNTRY_NAMES.get(notice["buyer_country"], notice["buyer_country"]))}</span>'
                    f'<span>{safe(notice["notice_id"])}</span></div>'
                    f'<h3>{safe(notice["title"])}</h3>'
                    f'<p>{safe(notice["buyer_name"])}</p>'
                    f'<div class="featured-theme">{safe(notice["primary_theme"])}</div>'
                    '<dl class="featured-facts">'
                    f'<div><dt>Profile fit</dt><dd>{float(notice["opportunity_score"]):.0f}<small> / 100</small></dd></div>'
                    f'<div><dt>Estimate</dt><dd>{compact_money(notice["estimated_value"], notice["currency"])}</dd></div>'
                    '</dl></article>',
                    unsafe_allow_html=True,
                )
                st.button("Inspect dossier →", key=f"inspect_{notice['notice_id']}",
                          use_container_width=False, on_click=open_workspace,
                          args=("Dossier", str(notice["notice_id"])))
    st.markdown(
        '<aside class="research-note"><div class="panel-kicker">A NOTE ON COVERAGE</div>'
        '<p>One extract is a view of the market, not the whole market.</p>'
        '<span>TED covers published European procurement notices. National and below-threshold opportunities '
        'may be absent. Always verify requirements and deadlines in the official notice.</span></aside>',
        unsafe_allow_html=True,
    )

if page == "Opportunities":
    section_heading(
        "Registry / 01", "Opportunity register",
        "Search, rank and export the current evidence set. Open the TED source record before interpreting eligibility, scope or commercial value.",
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
            f'<span><strong>{page_start + 1:,}–{page_end:,}</strong> of {len(filtered):,} records</span>'
            f'<span>Page {page_number} / {page_count}</span></div>',
            unsafe_allow_html=True,
        )
    with registry_controls[3]:
        st.download_button(
            "Download filtered CSV",
            data=export_notices_csv(filtered),
            file_name=f"tender-intelligence-{edition_text.replace('.', '-')}.csv",
            mime="text/csv",
            use_container_width=True,
            help="Exports the complete filtered result, not only the visible page. Formula-like source text is neutralized for spreadsheet safety.",
        )
    st.markdown(registry_markup(page_frame), unsafe_allow_html=True)
    st.caption(
        "Open Dossier to review the classification evidence and profile-fit breakdown for any notice."
    )

if page == "Markets":
    section_heading(
        "Markets / 02", "Three-market comparison",
        "Counts and averages describe the filtered local extract, not the total addressable procurement market.",
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
    ledger_items = []
    for code in ("BEL", "ITA", "FIN"):
        row = comparison[comparison["buyer_country"] == code]
        if row.empty:
            count, average = 0, "—"
        else:
            count = int(row.iloc[0]["notice_count"])
            average = f'{row.iloc[0]["average_profile_fit"]:.1f}'
        ledger_items.append(
            f'<article><span>{COUNTRY_NAMES[code]} / {code}</span><strong>{count} signals</strong>'
            f'<em>average fit {average}</em></article>'
        )
    st.markdown(f'<div class="market-ledger">{"".join(ledger_items)}</div>', unsafe_allow_html=True)
    chart = px.bar(
        comparison, x="market", y="notice_count", color="buyer_country",
        color_discrete_map=COUNTRY_COLORS,
        labels={"notice_count": "Visible notices", "market": "Buyer market"},
        text="notice_count",
    )
    chart.update_traces(marker_line_width=0, textposition="outside", cliponaxis=False)
    style_chart(chart, legend=False)
    st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})
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
    section_heading(
        "Timeline / 03", "Publication cadence",
        "Monthly publication counts in the filtered extract. Short snapshots can be sparse and should not be treated as a forecast.",
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
        chart_arguments = {
            "data_frame": trends, "x": "publication_month", "y": "notice_count",
            "color": "buyer_country", "color_discrete_map": COUNTRY_COLORS,
            "labels": {
                "publication_month": "Publication month", "notice_count": "Visible notices",
                "buyer_country": "Buyer market",
            },
        }
        if trends["publication_month"].nunique() >= 4:
            chart = px.line(**chart_arguments, markers=True, line_dash="buyer_country")
            chart.update_traces(line={"width": 2.5}, marker={"size": 8})
        else:
            chart = px.bar(**chart_arguments, barmode="group", text="notice_count")
            chart.update_traces(marker_line_width=0, textposition="outside")
        style_chart(chart, legend=True)
        st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})
        with st.expander("Open accessible timeline data"):
            st.dataframe(trends, width="stretch", hide_index=True)

if page == "Dossier":
    section_heading(
        "Dossier / 04", "Inspect one notice",
        "Read the source record, fit components and exact classification evidence together.",
    )
    detail_options = filtered.sort_values("opportunity_score", ascending=False)
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
        "Tender record", key="dossier_notice", options=detail_options["notice_id"].tolist(),
        format_func=lambda notice_id: detail_labels[str(notice_id)],
    )
    selected = detail_options.loc[detail_options["notice_id"].eq(selected_id)].iloc[0]
    st.markdown(
        '<div class="dossier"><div>'
        f'<div class="dossier-code">TED record {safe(selected["notice_id"])} / {safe(selected["buyer_country"])}</div>'
        f'<div class="dossier-title">{safe(selected["title"])}</div>'
        '<div class="dossier-meta">'
        f'<span><b>Buyer</b> {safe(selected["buyer_name"])}</span>'
        f'<span><b>Theme</b> {safe(selected["primary_theme"])}</span>'
        f'<span><b>Status</b> {safe(str(selected["lifecycle_status"]).title())}</span>'
        f'<span><b>Deadline</b> {safe(selected["deadline_date"])}</span>'
        f'<span><b>Estimate</b> {full_money(selected["estimated_value"], selected["currency"])}</span>'
        '</div></div><div class="fit-stamp"><span>Profile fit / 100</span>'
        f'<strong>{selected["opportunity_score"]:.0f}</strong><small>ranking aid only</small></div></div>',
        unsafe_allow_html=True,
    )
    st.link_button(
        "Open official TED record",
        trusted_ted_url(selected.get("ted_url"), str(selected["notice_id"])),
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
            f'<span>{html.escape(name.replace("_", " ").title())}</span>'
            f'<div class="fit-track"><i style="width:{percent:.1f}%"></i></div>'
            f'<b>{points:g} / {maximum:g}</b>'
            f'<p>{safe(details.get("reason"), "")}</p></div>'
        )
    st.markdown(
        '<div class="section-head"><span>Fit model</span>'
        '<div class="section-title" role="heading" aria-level="2">Component ledger</div></div>'
        f'<div class="fit-ruler">{"".join(fit_rows)}</div>', unsafe_allow_html=True,
    )
    keyword_frame, cpv_frame = evidence_frames(selected)
    evidence_columns = st.columns(2)
    with evidence_columns[0]:
        st.markdown(
            '<div class="evidence-title" role="heading" aria-level="3">Keyword evidence</div>',
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
            '<div class="evidence-title" role="heading" aria-level="3">CPV evidence</div>',
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

if page == "Method":
    section_heading(
        "Method / 05", "From public notice to inspectable signal",
        "The MVP stays rule-based so every transformation and ranking decision can be audited.",
    )
    st.markdown(
        '<div class="method-grid">'
        '<article><span>01 / Retrieve</span><div class="method-title" role="heading" aria-level="3">Build the candidate pool</div><p>Query active TED notices by market, broad CPV families and explicit AI/data phrases.</p></article>'
        '<article><span>02 / Normalize</span><div class="method-title" role="heading" aria-level="3">Create one analysis row</div><p>Standardize buyer, country, date, CPV, value, currency and notice links.</p></article>'
        '<article><span>03 / Screen</span><div class="method-title" role="heading" aria-level="3">Keep visible evidence</div><p>Apply versioned multilingual keywords and narrower CPV rules. Retain every match.</p></article>'
        '<article><span>04 / Track & rank</span><div class="method-title" role="heading" aria-level="3">Explain change and fit</div><p>Compare complete active snapshots, then combine country, theme, evidence, deadline runway and budget clarity without predicting a win.</p></article>'
        '</div>', unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="limits-note"><strong>Interpretation boundary.</strong> Buyer country may differ from delivery location; budgets may be absent or lot-specific; active-scope counts move over time; and the classifier remains a baseline until a labelled validation set reports precision and recall.</div>',
        unsafe_allow_html=True,
    )
    st.link_button(
        "Read official TED Search API documentation",
        "https://docs.ted.europa.eu/api/latest/search.html",
    )

st.markdown(
    '<footer class="workspace-footer"><strong>Tender Intelligence</strong>'
    '<span>Independent research project · Source: EU TED</span>'
    '<a href="https://ted.europa.eu/en/" target="_blank" rel="noopener noreferrer">Visit the official source ↗</a>'
    '</footer>', unsafe_allow_html=True,
)
