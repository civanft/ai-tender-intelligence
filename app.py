from __future__ import annotations

import html
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
COUNTRY_NAMES = {"BEL": "Belgium", "ITA": "Italy", "FIN": "Finland"}
COUNTRY_COLORS = {"BEL": "#315F83", "ITA": "#8F4035", "FIN": "#286F6C"}

INK = "#071D2A"
MUTED = "#56686C"
RULE = "#D4CEC2"
SURFACE = "#FBFAF6"


st.set_page_config(
    page_title="AI Tender Intelligence — European Market Desk",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Public+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&display=swap');

    :root {
        --ink: #102A34;
        --ink-soft: #314A53;
        --muted: #5B6C72;
        --paper: #EDF1F2;
        --paper-deep: #E3E9EA;
        --surface: #F8FAFA;
        --signal: #C44F36;
        --signal-deep: #8F3325;
        --rule: #CBD4D7;
        --rule-dark: #9CABB0;
        --white: #FFFFFF;
    }

    html, body, .stApp {
        font-family: "Public Sans", -apple-system, BlinkMacSystemFont, sans-serif;
        color: var(--ink);
    }
    *, *::before, *::after { box-sizing: border-box; }
    .stApp { background: var(--paper); }
    .block-container { max-width: 1440px; padding: 1.35rem 2.35rem 4.5rem; }
    header[data-testid="stHeader"] { background: transparent; }
    [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {
        display: none !important;
    }
    [data-testid="stSkillsNudgeAnchor"], [data-testid="stHeaderActionElements"] {
        display: none !important;
    }
    h1, h2, h3, h4 {
        font-family: "Source Serif 4", Georgia, serif;
        color: var(--ink);
        letter-spacing: -0.025em;
    }
    h2 { font-size: 2rem; font-weight: 600; }
    h3 { font-size: 1.55rem; font-weight: 600; }
    p, li { line-height: 1.55; overflow-wrap: anywhere; }
    a:focus-visible, button:focus-visible, input:focus-visible, [tabindex="0"]:focus-visible {
        outline: 3px solid var(--signal) !important;
        outline-offset: 3px !important;
    }

    .registry-shell {
        border-top: 5px solid var(--ink);
        border-bottom: 1px solid var(--ink);
        margin: 0 0 1.15rem;
    }
    .registry-topline {
        display: grid;
        grid-template-columns: 1fr auto auto;
        gap: 1.25rem;
        align-items: center;
        padding: 0.62rem 0;
        border-bottom: 1px solid var(--rule-dark);
        color: var(--muted);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.73rem;
        font-weight: 500;
        letter-spacing: 0.075em;
        text-transform: uppercase;
    }
    .registry-topline strong { color: var(--ink); font-weight: 600; }
    .registry-main {
        display: grid;
        grid-template-columns: minmax(0, 1.15fr) minmax(420px, 0.85fr);
        gap: 2.5rem;
        align-items: end;
        padding: 1.75rem 0 1.55rem;
    }
    .brand-index {
        color: var(--signal-deep);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.11em;
        margin-bottom: 0.55rem;
        text-transform: uppercase;
    }
    .registry-title {
        margin: 0;
        color: var(--ink);
        font-family: "Source Serif 4", Georgia, serif;
        font-size: clamp(3.25rem, 6.2vw, 6.4rem);
        font-weight: 600;
        letter-spacing: -0.055em;
        line-height: 0.86;
        text-wrap: balance;
        text-transform: uppercase;
    }
    .registry-title .slash { color: var(--signal); font-weight: 500; }
    .registry-deck {
        max-width: 710px;
        margin: 1.05rem 0 0;
        color: var(--ink-soft);
        font-size: 1.04rem;
        line-height: 1.5;
    }
    .coverage-label {
        display: flex;
        justify-content: space-between;
        padding-bottom: 0.5rem;
        color: var(--muted);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.69rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .country-rail {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        border-top: 1px solid var(--ink);
        border-bottom: 1px solid var(--ink);
    }
    .country-cell {
        min-width: 0;
        padding: 0.85rem 0.85rem 0.75rem;
        border-right: 1px solid var(--rule-dark);
    }
    .country-cell:last-child { border-right: 0; }
    .country-cell span { display: block; color: var(--muted); font-size: 0.74rem; line-height: 1.15; }
    .country-cell strong {
        display: block;
        margin: 0.18rem 0 0.12rem;
        color: var(--ink);
        font-family: "Source Serif 4", Georgia, serif;
        font-size: 2.15rem;
        font-weight: 600;
        letter-spacing: -0.03em;
        line-height: 1;
    }
    .country-cell em {
        display: block;
        color: var(--muted);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.67rem;
        font-style: normal;
        line-height: 1.3;
        overflow-wrap: anywhere;
    }

    .signal-strip {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        margin: 0 0 0.72rem;
        background: var(--surface);
        border: 1px solid var(--rule-dark);
    }
    .signal-metric { min-width: 0; padding: 0.82rem 1rem 0.78rem; border-right: 1px solid var(--rule); }
    .signal-metric:last-child { border-right: 0; }
    .signal-metric span {
        display: block;
        color: var(--muted);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.65rem;
        font-weight: 500;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .signal-metric strong {
        display: block;
        margin: 0.12rem 0 0.02rem;
        color: var(--ink);
        font-family: "Source Serif 4", Georgia, serif;
        font-size: clamp(1.55rem, 3vw, 2.05rem);
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.035em;
        line-height: 1.08;
        overflow-wrap: anywhere;
    }
    .signal-metric small { color: var(--muted); font-size: 0.74rem; }
    .reading-note {
        display: grid;
        grid-template-columns: auto 1fr auto;
        gap: 0.8rem;
        align-items: center;
        margin: 0 0 1.45rem;
        color: var(--muted);
        font-size: 0.79rem;
    }
    .reading-note::before {
        content: "Reading note";
        color: var(--signal-deep);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.66rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .reading-note::after {
        content: "Profile fit ≠ win probability";
        color: var(--ink);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.65rem;
        white-space: nowrap;
    }

    section[data-testid="stSidebar"] { background: var(--paper-deep); border-right: 1px solid var(--rule-dark); }
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 1.15rem; }
    .query-desk { margin: 0 0 1.1rem; padding: 0 0 0.85rem; border-bottom: 3px solid var(--ink); }
    .query-desk span {
        display: block;
        color: var(--signal-deep);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.66rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .query-desk strong {
        display: block;
        margin: 0.18rem 0 0.25rem;
        font-family: "Source Serif 4", Georgia, serif;
        font-size: 1.8rem;
        font-weight: 600;
        letter-spacing: -0.025em;
    }
    .query-desk p { margin: 0; color: var(--muted); font-size: 0.82rem; }
    section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] .stMarkdown p {
        color: var(--ink); font-size: 0.84rem;
    }
    [data-baseweb="select"] > div, [data-testid="stSelectbox"] [role="group"],
    [data-testid="stNumberInput"] input, [data-testid="stTextInput"] input {
        background: var(--surface) !important;
        border-color: var(--rule-dark) !important;
        border-radius: 0 !important;
        box-shadow: none !important;
    }
    [data-testid="stSelectbox"] input {
        min-width: 0;
        background: var(--surface) !important;
        color: var(--ink) !important;
        text-overflow: ellipsis;
    }
    [data-baseweb="tag"] { background: var(--ink) !important; border-radius: 0 !important; }
    [data-baseweb="tag"] span { color: var(--white) !important; }
    [data-testid="stSlider"] [role="slider"] {
        background: var(--signal) !important; border-color: var(--signal) !important;
    }

    [role="tablist"] {
        display: flex;
        gap: 0;
        overflow-x: auto;
        border-top: 1px solid var(--ink);
        border-bottom: 1px solid var(--ink);
        scrollbar-width: none;
    }
    [role="tablist"]::-webkit-scrollbar { display: none; }
    [data-testid="stTab"] {
        flex: 0 0 auto;
        min-height: 46px;
        padding: 0 1rem;
        border-right: 1px solid var(--rule) !important;
        color: var(--muted) !important;
        cursor: pointer;
        font-family: "IBM Plex Mono", monospace !important;
        font-size: 0.69rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.055em;
        touch-action: manipulation;
        text-transform: uppercase;
    }
    [data-testid="stTab"] p {
        margin: 0;
        color: inherit !important;
        font-family: inherit !important;
        font-size: inherit !important;
        white-space: nowrap;
    }
    [data-testid="stTab"]:hover { background: var(--paper-deep); color: var(--ink) !important; }
    [data-testid="stTab"][aria-selected="true"] {
        background: var(--ink) !important;
        color: var(--white) !important;
    }
    [data-testid="stTab"] .react-aria-SelectionIndicator { display: none; }
    .section-head {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 1rem;
        align-items: end;
        margin: 1.8rem 0 0.85rem;
        padding-bottom: 0.6rem;
        border-bottom: 1px solid var(--rule-dark);
    }
    .section-head > span {
        color: var(--signal-deep);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.67rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .section-title {
        margin: 0;
        color: var(--ink);
        font-family: "Source Serif 4", Georgia, serif;
        font-size: 2.1rem;
        font-weight: 600;
        letter-spacing: -0.025em;
        line-height: 1;
        overflow-wrap: anywhere;
        text-wrap: balance;
    }
    .section-copy {
        max-width: 760px;
        margin: -0.2rem 0 1.1rem;
        color: var(--muted);
        font-size: 0.93rem;
        overflow-wrap: anywhere;
    }

    .registry-list {
        overflow: hidden;
        background: var(--surface);
        border: 1px solid var(--rule-dark);
    }
    .registry-list__row {
        display: grid;
        grid-template-columns: 108px minmax(250px, 2.2fr) minmax(150px, 1fr) 105px 108px 68px 88px;
        min-width: 0;
        border-bottom: 1px solid var(--rule);
    }
    .registry-list__row:last-child { border-bottom: 0; }
    .registry-list__row--closed {
        background: color-mix(in srgb, var(--paper-deep) 55%, var(--surface));
    }
    .registry-list__row--closed .registry-list__cell { color: var(--muted); }
    .registry-list__head {
        background: var(--paper-deep);
        color: var(--muted);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.65rem;
        font-weight: 600;
        letter-spacing: 0.055em;
        text-transform: uppercase;
    }
    .registry-list__cell {
        min-width: 0;
        padding: 0.72rem 0.7rem;
        border-right: 1px solid var(--rule);
        color: var(--ink-soft);
        font-size: 0.8rem;
        line-height: 1.35;
        overflow-wrap: anywhere;
    }
    .registry-list__cell:last-child { border-right: 0; }
    .registry-list__cell strong {
        display: block;
        color: var(--ink);
        font-size: 0.84rem;
        font-weight: 600;
        line-height: 1.35;
    }
    .registry-list__cell small {
        display: block;
        margin-top: 0.18rem;
        color: var(--muted);
        font-size: 0.72rem;
        line-height: 1.35;
    }
    .registry-list__mono {
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.7rem;
        font-variant-numeric: tabular-nums;
    }
    .registry-list__fit {
        color: var(--signal-deep);
        font-family: "Source Serif 4", Georgia, serif;
        font-size: 1.45rem;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
    }
    .lifecycle-chip {
        display: inline-flex;
        align-items: center;
        margin-top: 0.38rem;
        padding: 0.12rem 0.32rem;
        border: 1px solid currentColor;
        color: var(--muted);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.58rem;
        font-weight: 600;
        letter-spacing: 0.055em;
        line-height: 1.2;
        text-transform: uppercase;
    }
    .lifecycle-new { color: var(--signal-deep); }
    .lifecycle-updated { color: #173F5F; }
    .lifecycle-closed { color: var(--muted); border-style: dashed; }
    .registry-list a, .evidence-table a {
        color: var(--signal-deep);
        font-weight: 600;
        text-decoration-thickness: 1px;
        text-underline-offset: 3px;
    }
    .registry-list a:hover, .evidence-table a:hover { color: var(--ink); }

    [data-testid="stDataFrame"] {
        background: var(--surface); border: 1px solid var(--rule-dark); border-radius: 0 !important;
    }
    [data-testid="stPlotlyChart"] { background: var(--surface); border: 1px solid var(--rule-dark); }
    [data-testid="stExpander"] {
        background: transparent; border: 1px solid var(--rule-dark); border-radius: 0;
    }
    [data-testid="stLinkButton"] a {
        min-height: 44px;
        padding: 0.55rem 0.95rem;
        background: var(--ink) !important;
        border: 1px solid var(--ink) !important;
        border-radius: 0 !important;
        color: var(--white) !important;
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.72rem;
        font-weight: 500;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        transition: background 160ms ease, border-color 160ms ease;
    }
    [data-testid="stLinkButton"] a:hover {
        background: var(--signal-deep) !important; border-color: var(--signal-deep) !important;
    }
    [data-testid="stLinkButton"] a * {
        color: var(--white) !important;
        font-family: "IBM Plex Mono", monospace !important;
    }

    .market-ledger {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        margin: 0 0 1rem;
        background: var(--surface);
        border: 1px solid var(--rule-dark);
    }
    .market-ledger article { padding: 0.85rem 1rem; border-right: 1px solid var(--rule); }
    .market-ledger article:last-child { border-right: 0; }
    .market-ledger span { color: var(--muted); font-size: 0.72rem; }
    .market-ledger strong {
        display: block;
        color: var(--ink);
        font-family: "Source Serif 4", Georgia, serif;
        font-size: 1.55rem;
        line-height: 1.15;
    }
    .market-ledger em {
        color: var(--muted);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.66rem;
        font-style: normal;
    }
    .dossier {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 160px;
        gap: 1.5rem;
        margin: 0.85rem 0 1rem;
        padding: 1.2rem 1.25rem;
        background: var(--surface);
        border-top: 4px solid var(--ink);
        border-bottom: 1px solid var(--ink);
    }
    .dossier-code {
        color: var(--signal-deep);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.67rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .dossier-title {
        max-width: 950px;
        margin: 0.38rem 0 0.75rem;
        color: var(--ink);
        font-family: "Source Serif 4", Georgia, serif;
        font-size: 1.75rem;
        font-weight: 600;
        letter-spacing: -0.025em;
        line-height: 1.08;
    }
    .dossier-meta { display: flex; flex-wrap: wrap; gap: 0.5rem 1.3rem; color: var(--muted); font-size: 0.82rem; }
    .dossier-meta b { color: var(--ink); font-weight: 600; }
    .fit-stamp {
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 128px;
        padding-left: 1rem;
        border-left: 1px solid var(--rule-dark);
    }
    .fit-stamp span {
        color: var(--muted);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.65rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    .fit-stamp strong {
        color: var(--signal-deep);
        font-family: "Source Serif 4", Georgia, serif;
        font-size: 3.6rem;
        font-weight: 600;
        letter-spacing: -0.055em;
        line-height: 0.9;
    }
    .fit-stamp small { color: var(--muted); font-family: "IBM Plex Mono", monospace; }
    .fit-ruler { margin: 1rem 0 1.4rem; border-top: 1px solid var(--ink); }
    .fit-row {
        display: grid;
        grid-template-columns: minmax(145px, 0.7fr) minmax(160px, 1.3fr) 66px minmax(230px, 1.7fr);
        gap: 0.9rem;
        align-items: center;
        padding: 0.7rem 0;
        border-bottom: 1px solid var(--rule);
    }
    .fit-row > span { color: var(--ink); font-size: 0.84rem; font-weight: 600; }
    .fit-track { height: 8px; background: var(--rule); }
    .fit-track i { display: block; height: 100%; background: var(--signal); }
    .fit-row b {
        color: var(--ink);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.73rem;
        font-weight: 600;
    }
    .fit-row p { margin: 0; color: var(--muted); font-size: 0.78rem; line-height: 1.35; }
    .evidence-title {
        margin: 0.85rem 0 0.55rem;
        color: var(--ink);
        font-family: "Source Serif 4", Georgia, serif;
        font-size: 1.45rem;
        font-weight: 600;
        line-height: 1.1;
    }
    .evidence-table { background: var(--surface); border: 1px solid var(--rule-dark); }
    .evidence-row {
        display: grid;
        grid-template-columns: repeat(var(--evidence-cols), minmax(0, 1fr));
        border-bottom: 1px solid var(--rule);
    }
    .evidence-row:last-child { border-bottom: 0; }
    .evidence-head {
        background: var(--paper-deep);
        color: var(--muted);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.63rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .evidence-cell {
        min-width: 0;
        padding: 0.58rem 0.65rem;
        border-right: 1px solid var(--rule);
        color: var(--ink-soft);
        font-size: 0.76rem;
        line-height: 1.35;
        overflow-wrap: anywhere;
    }
    .evidence-cell:last-child { border-right: 0; }
    .method-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        margin: 0 0 1.2rem;
        border-top: 1px solid var(--ink);
        border-bottom: 1px solid var(--ink);
    }
    .method-grid article { min-height: 168px; padding: 0.9rem 1rem; border-right: 1px solid var(--rule-dark); }
    .method-grid article:last-child { border-right: 0; }
    .method-grid span {
        color: var(--signal-deep);
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.7rem;
        font-weight: 600;
    }
    .method-title {
        margin: 1.2rem 0 0.45rem;
        color: var(--ink);
        font-family: "Source Serif 4", Georgia, serif;
        font-size: 1.25rem;
        font-weight: 600;
        line-height: 1.2;
        overflow-wrap: anywhere;
    }
    .method-grid p { margin: 0; color: var(--muted); font-size: 0.82rem; line-height: 1.4; }
    .limits-note {
        margin: 1rem 0;
        padding: 0.9rem 1rem;
        background: var(--surface);
        border-left: 5px solid var(--signal);
        color: var(--ink-soft);
        font-size: 0.88rem;
    }

    @media (max-width: 1000px) {
        .block-container { padding-left: 1.25rem; padding-right: 1.25rem; }
        .registry-main { grid-template-columns: 1fr; gap: 1.5rem; }
        .signal-strip { grid-template-columns: repeat(2, 1fr); }
        .signal-metric:nth-child(2) { border-right: 0; }
        .signal-metric:nth-child(-n+2) { border-bottom: 1px solid var(--rule); }
        .fit-row { grid-template-columns: 150px 1fr 58px; }
        .fit-row p { grid-column: 1 / -1; }
        .method-grid { grid-template-columns: repeat(2, 1fr); }
        .method-grid article:nth-child(2) { border-right: 0; }
        .method-grid article:nth-child(-n+2) { border-bottom: 1px solid var(--rule-dark); }
        .registry-list { overflow: visible; background: transparent; border: 0; }
        .registry-list__head { display: none; }
        .registry-list__row {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin-bottom: 0.75rem;
            background: var(--surface);
            border: 1px solid var(--rule-dark);
        }
        .registry-list__cell {
            border-right: 0;
            border-bottom: 1px solid var(--rule);
        }
        .registry-list__cell::before {
            content: attr(data-label);
            display: block;
            margin-bottom: 0.22rem;
            color: var(--muted);
            font-family: "IBM Plex Mono", monospace;
            font-size: 0.6rem;
            font-weight: 600;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }
        .registry-list__cell--record, .registry-list__cell--title,
        .registry-list__cell--theme, .registry-list__cell--source {
            grid-column: 1 / -1;
        }
        .registry-list__cell--source { border-bottom: 0; }
    }
    @media (max-width: 640px) {
        .block-container { padding: 0.75rem 0.85rem 3rem; }
        .registry-topline { grid-template-columns: 1fr auto; gap: 0.5rem; }
        .registry-topline span:nth-child(2) { display: none; }
        .registry-main { padding: 1.2rem 0; }
        .registry-title { font-size: clamp(2.7rem, 16vw, 4.4rem); }
        .registry-deck { font-size: 0.93rem; }
        .country-cell { padding: 0.7rem 0.48rem; }
        .country-cell strong { font-size: 1.6rem; }
        .country-cell span { font-size: 0.66rem; }
        .country-cell em { font-size: 0.58rem; }
        .signal-metric { padding: 0.72rem; }
        .signal-metric strong { font-size: 1.65rem; }
        .reading-note { grid-template-columns: 1fr; gap: 0.25rem; }
        .reading-note::after { white-space: normal; }
        [data-testid="stTab"] { padding: 0 0.28rem; font-size: 0.62rem !important; }
        .section-head { grid-template-columns: 1fr; gap: 0.35rem; align-items: start; }
        .section-title { font-size: 1.9rem; line-height: 1.02; text-wrap: pretty; }
        .market-ledger { grid-template-columns: 1fr; }
        .market-ledger article { border-right: 0; border-bottom: 1px solid var(--rule); }
        .market-ledger article:last-child { border-bottom: 0; }
        .dossier { grid-template-columns: 1fr; }
        .fit-stamp { min-height: 0; padding: 0.8rem 0 0; border-left: 0; border-top: 1px solid var(--rule-dark); }
        .fit-row { grid-template-columns: 1fr 55px; }
        .fit-track { grid-column: 1 / -1; }
        .fit-row p { grid-column: 1 / -1; }
        .method-grid { grid-template-columns: 1fr; }
        .method-grid article { min-height: 0; border-right: 0; border-bottom: 1px solid var(--rule-dark); }
        .evidence-cell::before {
            content: attr(data-label);
            display: block;
            margin-bottom: 0.22rem;
            color: var(--muted);
            font-family: "IBM Plex Mono", monospace;
            font-size: 0.6rem;
            font-weight: 600;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }
        .evidence-row { display: block; padding: 0.22rem 0; }
        .evidence-row.evidence-head { display: none; }
        .evidence-cell { border-right: 0; border-bottom: 1px solid var(--rule); }
        .evidence-cell:last-child { border-bottom: 0; }
    }
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            scroll-behavior: auto !important;
            transition-duration: 0.01ms !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
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
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
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
        gridcolor="#E3DED4", zeroline=False, linecolor=RULE,
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
        '<div class="registry-shell" id="dashboard-content" tabindex="-1"><div class="registry-topline"><strong>ATI / Public record</strong>'
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
        '<div class="query-desk"><span>Query desk / available snapshot</span>'
        '<strong>Refine the registry</strong>'
        '<p>Filters apply to the current TED snapshot. They do not change the source data.</p></div>',
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
    country_cells.append(
        f'<div class="country-cell country-cell--{code.lower()}">'
        f'<span>{COUNTRY_NAMES[code]}</span><strong translate="no">{code}</strong>'
        f'<em>{int(country_data["is_relevant"].sum())} / {len(country_data)} screened</em>'
        "</div>"
    )

st.markdown(
    '<div class="registry-shell" id="dashboard-content" tabindex="-1">'
    '<div class="registry-topline"><strong>ATI / Live public record</strong>'
    f'<span>{safe(data_source_label)} / TED active scope</span>'
    f'<span>Edition {edition_text}</span></div>'
    '<div class="registry-main"><div>'
    '<div class="brand-index">European market entry desk — Belgium / Italy / Finland</div>'
    '<h1 class="registry-title"><span class="title-line">Tender <span class="slash">/</span></span>'
    '<span class="title-line">Intelligence</span></h1>'
    '<p class="registry-deck">A curated view of public AI, data and infrastructure procurement — built to move from market context to source evidence without hiding the reasoning in a black box.</p>'
    '</div><div><div class="coverage-label"><span>Market coverage</span>'
    f'<span>Extract {freshness_text}</span></div><div class="country-rail">{"".join(country_cells)}</div>'
    '</div></div></div>',
    unsafe_allow_html=True,
)

visible_eur = filtered.loc[filtered["currency"] == "EUR", "estimated_value"].sum(min_count=1)
new_count = int((data["lifecycle_status"] == "new").sum())
updated_count = int((data["lifecycle_status"] == "updated").sum())
st.markdown(
    '<div class="signal-strip" role="group" aria-label="Current extract summary">'
    f'<div class="signal-metric"><span>Visible signals</span><strong>{len(filtered):,}</strong><small>after active filters</small></div>'
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

if filtered.empty:
    st.warning("No notices match the current filters. Broaden a filter in the query desk.")
    st.stop()

registry_tab, markets_tab, timeline_tab, dossier_tab, method_tab = st.tabs(
    ["Registry", "Markets", "Timeline", "Dossier", "Method"]
)

with registry_tab:
    section_heading(
        "Registry / 01", "Screened opportunity register",
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
            file_name=f"ati-tenders-{edition_text.replace('.', '-')}.csv",
            mime="text/csv",
            use_container_width=True,
            help="Exports the complete filtered result, not only the visible page. Formula-like source text is neutralized for spreadsheet safety.",
        )
    st.markdown(registry_markup(page_frame), unsafe_allow_html=True)
    st.caption(
        "Records are paginated for clarity and performance. Open Dossier for scoring evidence and record-level context."
    )

with markets_tab:
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

with timeline_tab:
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

with dossier_tab:
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
    selected_id = st.selectbox(
        "Tender record", options=detail_options["notice_id"].tolist(),
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

with method_tab:
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
