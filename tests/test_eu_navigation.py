from test_workspace_navigation import workspace

from tender_intelligence.countries import EU_COUNTRY_CODES


def test_all_eu_countries_are_selectable_and_default_with_recovery(workspace):
    markets = workspace.multiselect(key="filter_countries")
    assert len(markets.options) == 27
    assert set(markets.value) == set(EU_COUNTRY_CODES)
    markets.set_value(["DEU"]).run()
    assert not workspace.exception
    assert any("No notices match" in w.value for w in workspace.warning)
    next(b for b in workspace.button if b.label == "Select all 27 EU markets").click().run()
    assert not workspace.exception
    assert set(workspace.multiselect(key="filter_countries").value) == set(EU_COUNTRY_CODES)


def test_overview_covers_27_countries_and_research_preferences_do_too(workspace):
    markup = " ".join(item.value for item in workspace.markdown)
    assert markup.count('class="market-row"') == 27
    assert not workspace.exception
    workspace.radio(key="workspace_page").set_value("Research desk").run()
    workspace.radio(key="research_tool").set_value("Fit lab").run()
    assert not workspace.exception
    assert set(workspace.multiselect(key="research_fit_markets").value) == set(EU_COUNTRY_CODES)


def test_market_comparison_keeps_empty_countries_honest(workspace):
    workspace.radio(key="workspace_page").set_value("Markets").run()
    assert not workspace.exception
    markup = " ".join(item.value for item in workspace.markdown)
    assert 'flag--deu" aria-hidden="true"></span>Germany</td>' in markup
    assert '<td class="num zero">0</td>' in markup


def test_timeline_handles_all_markets_and_an_empty_chart_selection(workspace):
    workspace.radio(key="workspace_page").set_value("Timeline").run()
    assert not workspace.exception
    workspace.radio(key="timeline_mode").set_value("By market").run()
    assert not workspace.exception
    assert len(workspace.multiselect(key="timeline_countries").options) == 27
    workspace.multiselect(key="timeline_countries").set_value([]).run()
    assert not workspace.exception
    assert any("Choose a market" in i.value for i in workspace.info)
