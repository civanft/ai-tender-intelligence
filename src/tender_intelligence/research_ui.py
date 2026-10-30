"""Session-isolated research desk UI built on the public notice snapshot."""
from __future__ import annotations

from datetime import date, datetime, timezone
import html
from typing import Callable

import pandas as pd
import streamlit as st

from .export import export_notices_csv, neutralize_spreadsheet_formula
from .countries import EU_COUNTRY_NAMES
from .research import (
    CHECKS, DEFAULT_WEIGHTS, MAX_SAVED, STAGES, actionable, buyer_summary,
    deadline_calendar, deadline_days, deadline_label, export_workspace,
    fresh_workspace, import_workspace, related_notices, research_brief,
    research_checks, scenario_scores, text, validate_workspace,
)

COUNTRIES = EU_COUNTRY_NAMES


def initialize_research() -> None:
    if "research_workspace" not in st.session_state:
        st.session_state["research_workspace"] = fresh_workspace()


def _workspace() -> dict:
    return st.session_state["research_workspace"]


def _display_frame(frame: pd.DataFrame) -> None:
    # Streamlit's built-in table CSV download must also be spreadsheet-safe.
    display = frame.copy()
    for column in display.select_dtypes(include=["object", "string"]).columns:
        display[column] = display[column].map(neutralize_spreadsheet_formula)
    labels = {"notice_id": "TED record", "buyer_name": "Buyer", "buyer_country": "Market", "title": "Notice", "primary_theme": "Technology theme", "deadline_date": "Deadline", "days_remaining": "Days remaining", "notices": "Visible notices", "screened": "Screened notices", "themes": "Technology themes", "upcoming": "Unexpired disclosed dates", "disclosed_eur": "Disclosed EUR estimates", "scenario_fit": "Scenario fit / 100", "fit_market": "Market points", "fit_theme": "Theme points", "fit_evidence": "Evidence points", "fit_runway": "Runway points", "fit_budget": "Disclosure points", "lifecycle_status": "Refresh status"}
    st.dataframe(display.rename(columns=labels), hide_index=True, width="stretch")


def _remove_notice(notice_id: str) -> None:
    _workspace()["saved"].pop(notice_id, None)
    for key in list(st.session_state):
        if key.startswith("research_edit_") and notice_id in key:
            del st.session_state[key]


def save_notice(notice_id: str) -> None:
    saved = _workspace()["saved"]
    if notice_id not in saved and len(saved) < MAX_SAVED:
        candidate = {**_workspace(), "saved": {**saved, notice_id: {"stage": STAGES[0], "note": "", "checks": {}}}}
        try:
            export_workspace(candidate)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["research_workspace"] = candidate


def _save_view() -> None:
    name = text(st.session_state.get("research_view_name", ""), 60).strip()
    views = _workspace()["views"]
    if name and (name in views or len(views) < 20):
        view = {"query": text(st.session_state["filter_query"], 200), "countries": st.session_state["filter_countries"].copy(), "themes": st.session_state["filter_themes"].copy(), "lifecycles": st.session_state["filter_lifecycles"].copy(), "relevant": st.session_state["filter_relevant"], "score": st.session_state["filter_score"], "sort": st.session_state["filter_sort"]}
        candidate = {**_workspace(), "views": {**views, name: view}}
        try:
            export_workspace(candidate)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["research_workspace"] = candidate


def _apply_view(name: str, countries: list, themes: list, statuses: list) -> None:
    view = _workspace()["views"][name]
    for key in ("query", "relevant", "score", "sort"):
        st.session_state["filter_" + key] = view[key]
    for field, allowed in (("countries", countries), ("themes", themes), ("lifecycles", statuses)):
        st.session_state["filter_" + field] = [v for v in view[field] if v in allowed]


def saved_search_controls(countries: list, themes: list, statuses: list) -> None:
    with st.expander("Saved searches"):
        st.text_input("Name this search", key="research_view_name", max_chars=60, placeholder="e.g. Italian data platforms")
        name = st.session_state.get("research_view_name", "").strip()
        st.button("Save current search", on_click=_save_view, disabled=not name or (name not in _workspace()["views"] and len(_workspace()["views"]) >= 20), use_container_width=True)
        names = list(_workspace()["views"])
        if names:
            selected = st.selectbox("Restore a search", names, key="research_restore_view")
            st.button("Apply saved search", on_click=_apply_view, args=(selected, countries, themes, statuses), use_container_width=True)
        st.caption("Saved for this session. Download your workspace in Research desk to keep searches for another visit.")


def _heading(title: str, description: str) -> None:
    st.markdown(f'<div class="section-head"><div class="section-title" role="heading" aria-level="2">{html.escape(title)}</div></div><p class="section-copy">{html.escape(description)}</p>', unsafe_allow_html=True)


def _intro(title: str, description: str) -> None:
    st.markdown(f'<div class="page-intro"><h1>{html.escape(title)}</h1><p>{html.escape(description)}</p></div>', unsafe_allow_html=True)


def _short_title(row: pd.Series) -> str:
    title = text(row["title"], 200)
    prefix = COUNTRIES.get(row["buyer_country"], "") + " – "
    return text(title[len(prefix):] if title.startswith(prefix) else title, 120)


def _notice_label(row: pd.Series) -> str:
    return f"[{row['buyer_country']}] {row['notice_id']} · {text(row['title'], 100)}"


def _select_notices(frame: pd.DataFrame, label: str, key: str, default: list | None = None, maximum: int = 4) -> list[str]:
    labels = {r["notice_id"]: _notice_label(r) for _, r in frame.iterrows()}
    options = list(labels)
    if key in st.session_state:
        st.session_state[key] = [i for i in st.session_state[key] if i in labels][:maximum]
    return st.multiselect(label, options, default=[i for i in (default or []) if i in labels][:maximum], format_func=lambda i: labels[i], max_selections=maximum, key=key)


def _metrics(items: list[tuple[str, str]]) -> None:
    blocks = "".join(f'<div><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>' for label, value in items)
    st.markdown(f'<div class="research-metrics">{blocks}</div>', unsafe_allow_html=True)


def _downloads(frame: pd.DataFrame, today: date, key: str, title: str) -> None:
    columns = st.columns(3)
    with columns[0]:
        st.download_button("Research brief · HTML", research_brief(frame, today, title), file_name="tender-research-brief.html", mime="text/html", key=key + "_brief", disabled=frame.empty, use_container_width=True)
    with columns[1]:
        st.download_button("Notice data · CSV", export_notices_csv(frame.head(MAX_SAVED)), file_name="tender-research.csv", mime="text/csv", key=key + "_csv", disabled=frame.empty, use_container_width=True)
    with columns[2]:
        dates = actionable(frame, today)["deadline_date"].map(lambda v: deadline_days(v, today)).notna().any()
        st.download_button("Deadlines · Calendar", deadline_calendar(frame, today), file_name="tender-deadlines.ics", mime="text/calendar", key=key + "_calendar", disabled=not dates, use_container_width=True)
    st.caption("Exports include up to 100 notices. Calendar events are date-only reminders; verify the exact time at TED. Brief and CSV exclude personal notes.")


def _portable_workspace() -> None:
    with st.expander("Keep your watchlist for next time"):
        st.caption("Notes and saved searches only last for this session; a disconnect or restart can clear them. Download the file to keep them and import it on your next visit. It holds your notes in plain text.")
        st.download_button("Download my workspace", export_workspace(_workspace()), file_name="tender-workspace.json", mime="application/json", key="research_export_workspace")
        with st.form("research_import"):
            uploaded = st.file_uploader("Import a workspace JSON file (maximum 500 KB)", type=["json"], key="research_import_file")
            submitted = st.form_submit_button("Import and merge workspace")
        if submitted:
            if uploaded is None:
                st.warning("Choose your downloaded workspace file first.")
            else:
                try:
                    incoming = import_workspace(uploaded.getvalue())
                    merged = validate_workspace({"schema_version": 1, "saved": {**_workspace()["saved"], **incoming["saved"]}, "views": {**_workspace()["views"], **incoming["views"]}})
                    export_workspace(merged)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["research_workspace"] = merged
                    for key in list(st.session_state):
                        if key.startswith("research_edit_"):
                            del st.session_state[key]
                    st.success("Workspace imported. Matching notice IDs were updated from your file.")


def _watchlist(data: pd.DataFrame, filtered: pd.DataFrame, today: date, open_page: Callable) -> None:
    _heading("Watchlist", "Save notices, move them through your stages and keep notes. Room for up to 100.")
    _portable_workspace()
    choices = _select_notices(filtered, "Add notices from the current view", "research_add_selection", maximum=20)
    if st.button("Add to watchlist", disabled=not choices, key="research_add"):
        remaining = MAX_SAVED - len(_workspace()["saved"])
        new = [i for i in choices if i not in _workspace()["saved"]]
        if len(new) > remaining:
            st.warning(f"Your workspace has room for {remaining} more notices. Select fewer records.")
        else:
            candidate = {**_workspace(), "saved": {**_workspace()["saved"], **{i: {"stage": STAGES[0], "note": "", "checks": {}} for i in new}}}
            try:
                export_workspace(candidate)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["research_workspace"] = candidate
                st.success("Watchlist updated.")
    saved = _workspace()["saved"]
    if not saved:
        st.info("Nothing saved yet. Add notices above, or use “Save to watchlist” on a dossier.")
        return
    _metrics([(stage, str(sum(e["stage"] == stage for e in saved.values()))) for stage in STAGES])
    shown_stages = st.multiselect("Show research stages", STAGES, default=list(STAGES[:3]), key="research_stage_filter")
    lookup = data.set_index("notice_id")
    eligible_ids = [i for i, e in saved.items() if e["stage"] in shown_stages]
    page_count = max(1, (len(eligible_ids) + 9) // 10)
    if st.session_state.get("research_watchlist_page", 1) > page_count:
        st.session_state["research_watchlist_page"] = 1
    page = st.selectbox("Watchlist page", list(range(1, page_count + 1)), key="research_watchlist_page")
    st.caption(f"{len(eligible_ids)} saved notices in these stages · showing up to 10 per page")
    for notice_id in eligible_ids[(page - 1) * 10:page * 10]:
        entry = saved[notice_id]
        if notice_id not in lookup.index:
            st.warning(f"{notice_id} is saved but is absent from this snapshot. Its note is retained in your workspace export.")
            st.button("Remove unavailable record " + notice_id, key="research_remove_" + notice_id, on_click=_remove_notice, args=(notice_id,))
            continue
        row = lookup.loc[notice_id]
        with st.container(border=True):
            st.markdown(f'<div class="research-notice"><span>{html.escape(notice_id)} · {html.escape(text(row["buyer_country"]))}</span><h3>{html.escape(text(row["title"]))}</h3><p>{html.escape(text(row["buyer_name"]))}</p><b>{html.escape(deadline_label(row, today))}</b></div>', unsafe_allow_html=True)
            with st.form("research_edit_" + notice_id):
                stage = st.selectbox("Research stage", STAGES, index=STAGES.index(entry["stage"]), key="research_edit_stage_" + notice_id)
                note = st.text_area("Your research note", value=entry["note"], max_chars=4000, key="research_edit_note_" + notice_id, placeholder="What needs checking? Who could help? What is the next step?")
                checks = {key: st.checkbox(label, value=entry["checks"].get(key, False), key=f"research_edit_check_{notice_id}_{key}") for key, label in CHECKS.items()}
                if st.form_submit_button("Save research"):
                    candidate = {**_workspace(), "saved": {**saved, notice_id: {"stage": stage, "note": text(note, 4000), "checks": checks}}}
                    try:
                        export_workspace(candidate)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["research_workspace"] = candidate
                        st.rerun()
            st.caption(f"{sum(entry['checks'].values())} / {len(CHECKS)} checks recorded by you. These are not independently verified.")
            st.button("Open dossier →", key="research_open_" + notice_id, on_click=open_page, args=("Dossier", notice_id))
            with st.expander("Remove from this workspace"):
                st.caption("Removing a notice also removes its session note and checks. Download a workspace copy first if you want to keep them.")
                st.button("Remove saved notice", key="research_remove_" + notice_id, on_click=_remove_notice, args=(notice_id,))
    _downloads(data[data["notice_id"].isin(eligible_ids)], today, "watchlist", "Shortlist research brief")


def _compare(data: pd.DataFrame, filtered: pd.DataFrame, today: date, open_page: Callable) -> None:
    _heading("Compare notices", "Pick two to four notices. Missing values are shown as missing.")
    saved_ids = list(_workspace()["saved"])
    pool = pd.concat([filtered, data[data["notice_id"].isin(saved_ids)]]).drop_duplicates("notice_id")
    ids = _select_notices(pool, "Choose notices to compare", "research_compare", saved_ids, maximum=4)
    if len(ids) < 2:
        st.info("Choose at least two notices to compare.")
        return
    selected = pool.set_index("notice_id").loc[ids].reset_index()
    columns = st.columns(len(ids))
    for column, (_, row) in zip(columns, selected.iterrows()):
        with column:
            with st.container(border=True):
                st.markdown(f'<div class="research-notice"><span>{html.escape(row["notice_id"])}</span><h3>{html.escape(text(row["title"]))}</h3></div>', unsafe_allow_html=True)
                st.write("Buyer: " + text(row["buyer_name"]))
                st.write("Market: " + COUNTRIES.get(row["buyer_country"], row["buyer_country"]))
                st.write("Technology: " + text(row["primary_theme"]))
                st.write(deadline_label(row, today))
                st.write("Procedure estimate: " + (text(row["estimated_value"]) or "Not disclosed") + " " + text(row["currency"]))
                st.write(f"Snapshot profile fit: {row['opportunity_score']:g} / 100")
                st.write(f"Classification evidence: {row['classification_score']:g} / 10")
                st.caption("Stored fit was assessed at extraction; deadline information above uses today's UTC date.")
                st.button("Inspect evidence →", key="research_compare_open_" + row["notice_id"], on_click=open_page, args=("Dossier", row["notice_id"]))
    _downloads(selected, today, "compare", "Side-by-side research brief")


def _radar(filtered: pd.DataFrame, today: date, open_page: Callable) -> None:
    _heading("Upcoming deadlines", "Notices in the current view with a disclosed deadline. Closed and expired notices are left out.")
    horizon = st.select_slider("Planning horizon", options=[7, 14, 30, 60, 90], value=30, key="research_horizon")
    candidates = actionable(filtered, today)
    candidates["days_remaining"] = candidates["deadline_date"].map(lambda v: deadline_days(v, today))
    dated = candidates[candidates["days_remaining"].between(0, horizon)].sort_values("days_remaining")
    undated = candidates[candidates["days_remaining"].isna()]
    _metrics([(f"Due within {horizon} days", str(len(dated))), ("Deadline not disclosed", str(len(undated))), ("New / updated in this view", str(filtered["lifecycle_status"].isin(["new", "updated"]).sum()))])
    if dated.empty:
        st.info("No disclosed deadlines fall within this horizon. Try a longer horizon or broaden your filters.")
    else:
        display = dated[["notice_id", "buyer_name", "primary_theme", "deadline_date", "days_remaining"]].copy()
        _display_frame(display.head(100))
        _downloads(dated, today, "radar", "Deadline planning brief")
    with st.expander(f"Inspect {len(undated)} notices with missing deadlines"):
        _display_frame(undated[["notice_id", "title", "buyer_name"]].head(50))
    changes = filtered[filtered["lifecycle_status"].isin(["new", "updated"])].head(8)
    if not changes.empty:
        st.subheader("Latest refresh signals")
        st.caption("New / updated are ingestion states, not proof of a newly opened procedure. Revisions are not field-level diffs.")
        for _, row in changes.iterrows():
            st.button(f"{text(row['lifecycle_status']).title()} · {_notice_label(row)}", key="research_signal_" + row["notice_id"], on_click=open_page, args=("Dossier", row["notice_id"]))


def _fit_lab(data: pd.DataFrame, today: date, open_page: Callable) -> None:
    _heading("Custom ranking", "Set your own weights to re-rank every screened notice that is still open. Sidebar filters do not apply here.")
    controls = st.columns(2)
    with controls[0]:
        market_options = list(COUNTRIES)
        markets = st.multiselect("Preferred markets", market_options, default=[c for c in COUNTRIES if c in market_options], format_func=lambda c: COUNTRIES.get(c, c), key="research_fit_markets")
    with controls[1]:
        themes = st.multiselect("Preferred technology themes", sorted(data["primary_theme"].dropna().unique()), default=sorted(data["primary_theme"].dropna().unique()), key="research_fit_themes")
    with st.expander("Adjust the five ranking weights", expanded=True):
        columns = st.columns(5)
        weights = {}
        labels = {"market": "Market preference", "theme": "Technology preference", "evidence": "Classification evidence", "runway": "Preparation time", "budget": "Budget disclosure"}
        for column, (key, default) in zip(columns, DEFAULT_WEIGHTS.items()):
            with column:
                weights[key] = st.slider(labels[key], 0, 100, default, step=5, key="research_weight_" + key)
    if not sum(weights.values()):
        st.warning("Set at least one weight above zero to calculate a ranking.")
        return
    st.caption("Normalized to 100 points: " + " · ".join(f"{labels[k]} {100*v/sum(weights.values()):.1f}" for k, v in weights.items()))
    pool = actionable(data[data["is_relevant"].eq(1)], today)
    ranked = scenario_scores(pool, markets, themes, weights, today)
    st.caption(f"Assessed {today.isoformat()} UTC. No preferred match gets zero preference points. Evidence scales to 10, runway scales to 45 days; missing deadlines get zero runway points. Budget measures disclosure, not affordability. This is not win probability or eligibility.")
    if ranked.empty:
        st.info("No screened notices currently satisfy the non-closed / non-expired pool rules.")
        return
    _display_frame(ranked[["notice_id", "title", "buyer_country", "scenario_fit", "fit_market", "fit_theme", "fit_evidence", "fit_runway", "fit_budget"]].head(30))
    for _, row in ranked.head(3).iterrows():
        st.button(f"{row['scenario_fit']:.1f} / 100 · {_notice_label(row)}", key="research_fit_open_" + row["notice_id"], on_click=open_page, args=("Dossier", row["notice_id"]))


def render_research_desk(data: pd.DataFrame, filtered: pd.DataFrame, open_page: Callable) -> None:
    today = datetime.now(timezone.utc).date()
    _intro("Research desk", "Your watchlist, side-by-side comparisons, upcoming deadlines and a custom ranking.")
    fetched = pd.to_datetime(data["fetched_at"], utc=True, errors="coerce").max()
    if pd.notna(fetched) and (today - fetched.date()).days > 2:
        st.warning(f"This snapshot was last extracted on {fetched.date()}. Refresh the source before relying on availability or dates.")
    tool = st.radio("Research tools", ["Watchlist", "Compare", "Deadline radar", "Fit lab"], horizontal=True, key="research_tool", label_visibility="collapsed")
    if tool == "Watchlist":
        _watchlist(data, filtered, today, open_page)
    elif tool == "Compare":
        _compare(data, filtered, today, open_page)
    elif tool == "Deadline radar":
        _radar(filtered, today, open_page)
    else:
        _fit_lab(data, today, open_page)


def render_buyers(data: pd.DataFrame, filtered: pd.DataFrame, open_page: Callable) -> None:
    today = datetime.now(timezone.utc).date()
    _intro("Buyers", "Organisations publishing notices in the current view. Grouped by exact name and country, so one organisation can appear under more than one name.")
    summary = buyer_summary(filtered, today)
    if summary.empty:
        st.info("No buyers match this view. Loosen a filter in the sidebar.")
        return
    _metrics([("Buyers", f"{len(summary):,}"), ("Notices", f"{summary['notices'].sum():,}"), ("AI and data notices", f"{summary['screened'].sum():,}")])
    _display_frame(summary.head(30))
    st.caption("Disclosed EUR is a sum of notice-level estimates, not spend. Related notices may describe the same procedure; values are not deduplicated by procedure.")
    options = [(row["buyer_country"], row["buyer_name"]) for _, row in summary.iterrows()]
    if st.session_state.get("research_buyer") not in options:
        st.session_state["research_buyer"] = options[0]
    country, buyer = st.selectbox("Inspect a buyer", options, format_func=lambda v: f"[{v[0]}] {v[1]}", key="research_buyer")
    records = data[data["buyer_country"].eq(country) & data["buyer_name"].eq(buyer)].copy()
    st.markdown(f'<div class="buyer-identity"><span>{html.escape(COUNTRIES.get(country, country))}</span><h2>{html.escape(text(buyer))}</h2><p>Every notice under this exact name and country in the snapshot, including closed ones.</p></div>', unsafe_allow_html=True)
    count = records["primary_theme"].value_counts().rename_axis("Technology theme").reset_index(name="Visible notices")
    _display_frame(count)
    st.caption("These counts describe the loaded extract only. One organisation may use several names; unrelated organisations may share a name. No procurement forecast is inferred.")
    _display_frame(records[["notice_id", "title", "deadline_date", "lifecycle_status", "primary_theme"]].head(50))
    for _, row in records.sort_values("opportunity_score", ascending=False).head(3).iterrows():
        st.button("Open dossier · " + text(row["notice_id"]), key="research_buyer_open_" + row["notice_id"], on_click=open_page, args=("Dossier", row["notice_id"]))
    _downloads(records, today, "buyer", "Buyer snapshot research brief")


def render_dossier_actions(selected: pd.Series, ted_url: str) -> None:
    today = datetime.now(timezone.utc).date()
    notice_id = selected["notice_id"]
    with st.container(horizontal=True, key="dossier_actions"):
        st.link_button("Open on TED ↗", ted_url, type="primary")
        is_saved = notice_id in _workspace()["saved"]
        st.button("Saved to watchlist" if is_saved else "Save to watchlist", key="research_save_dossier", disabled=is_saved or len(_workspace()["saved"]) >= MAX_SAVED, on_click=save_notice, args=(notice_id,))
        st.download_button("Download brief", research_brief(pd.DataFrame([selected]), today), file_name=f"tender-{notice_id}.html", mime="text/html", key="research_dossier_brief")
        st.button("Go to watchlist →", key="research_dossier_desk", on_click=_open_desk, type="tertiary")


def _open_desk() -> None:
    st.session_state["workspace_page"] = "Research desk"


def render_dossier_tools(selected: pd.Series, data: pd.DataFrame, open_page: Callable) -> None:
    today = datetime.now(timezone.utc).date()
    _heading("Open questions", "Gaps in this notice's data, checked against today's date (UTC). Only the official documents set the requirements.")
    issues = research_checks(selected, today)
    items = "".join(f'<div><strong>{html.escape(issue["label"])}</strong><p>{html.escape(issue["detail"])}</p></div>' for issue in issues)
    st.markdown(f'<div class="research-checks">{items}</div>', unsafe_allow_html=True)
    related = related_notices(data, selected, today)
    _heading("Related notices", "Scored by shared theme (45), five-digit CPV family (25), market (15) and buyer (15).")
    if related.empty:
        st.caption("No open, related notice in this snapshot.")
    else:
        for _, relation in related.iterrows():
            row = data.loc[data["notice_id"].eq(relation["notice_id"])].iloc[0]
            with st.container(key="related_" + row["notice_id"]):
                st.button(_short_title(row), key="research_related_" + row["notice_id"], on_click=open_page, args=("Dossier", row["notice_id"]), type="tertiary")
                st.caption(f"{COUNTRIES.get(row['buyer_country'], row['buyer_country'])} · {row['notice_id']} · similarity {relation['similarity']} / 100 · {relation['reason']}")
