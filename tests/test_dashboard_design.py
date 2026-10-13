from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "assets" / "dashboard_luxe.css"
APP_PATH = ROOT / "app.py"


def test_dashboard_uses_formal_typography_system() -> None:
    css = CSS_PATH.read_text(encoding="utf-8")

    assert 'font-family: "Public Sans"' in css
    assert 'font-family: "Source Serif 4"' in css
    assert "Newsreader" not in css
    assert "DM+Sans" not in css


def test_market_aperture_has_subtle_css_flag_watermarks() -> None:
    css = CSS_PATH.read_text(encoding="utf-8")
    app = APP_PATH.read_text(encoding="utf-8")

    assert ".country-cell--bel::before" in css
    assert ".country-cell--ita::before" in css
    assert ".country-cell--fin::before" in css
    assert "opacity: 0.08" in css
    assert 'country-cell--{code.lower()}' in app


def test_native_theme_choices_have_matching_workspace_colors() -> None:
    import tomllib
    config = tomllib.loads((ROOT / ".streamlit/config.toml").read_text())
    assert config["theme"]["light"]["backgroundColor"] == "#F2F5F8"
    assert config["theme"]["dark"]["backgroundColor"] == "#101923"
    css = CSS_PATH.read_text()
    assert "light-dark(" in css
    assert "prefers-color-scheme" not in css  # Native menu, not OS-only selection.
    assert '[data-testid="stMainMenuItem-print"] { display:none !important; }' in css


def test_brand_asset_replaces_letter_monogram() -> None:
    app = APP_PATH.read_text()
    assert "ti-monogram" not in app
    assert 'page_icon=str(LOGO_PATH)' in app
    assert (ROOT / "assets/tender-intelligence-logo.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
