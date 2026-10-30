from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "assets" / "dashboard_luxe.css"
APP_PATH = ROOT / "app.py"


def test_dashboard_uses_one_restrained_type_family() -> None:
    css = CSS_PATH.read_text(encoding="utf-8")

    assert "family=IBM+Plex+Sans" in css
    assert "font-family: var(--font)" in css
    # One family only: no display serif, no monospace labels.
    for retired in ("Source Serif", "IBM Plex Mono", "Public Sans", "Newsreader", "DM+Sans"):
        assert retired not in css


def test_markets_show_small_inline_flags() -> None:
    css = CSS_PATH.read_text(encoding="utf-8")
    app = APP_PATH.read_text(encoding="utf-8")

    from tender_intelligence.countries import EU_COUNTRY_CODES
    from xml.etree import ElementTree as ET
    for code in EU_COUNTRY_CODES:
        root = ET.fromstring((ROOT / "assets" / "flags" / f"{code}.svg").read_bytes())
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        for element in root.iter():
            assert element.tag.rsplit("}", 1)[-1] not in {"script", "foreignObject"}
            for attr, value in element.attrib.items():
                assert not attr.lower().startswith("on")
                if attr.rsplit("}", 1)[-1] == "href":
                    assert value.startswith("#")
    assert "COUNTRY_FLAG_STYLES" in app
    assert ".flag {" in css
    assert "flag--{code.lower()}" in app


def test_native_theme_choices_have_matching_workspace_colors() -> None:
    import tomllib
    config = tomllib.loads((ROOT / ".streamlit/config.toml").read_text())
    assert config["theme"]["light"]["backgroundColor"] == "#F6F6F4"
    assert config["theme"]["dark"]["backgroundColor"] == "#131518"
    css_text = CSS_PATH.read_text()
    assert "light-dark(#F6F6F4,#131518)" in css_text
    assert config["server"]["enableStaticServing"] is True
    css = CSS_PATH.read_text()
    assert "light-dark(" in css
    assert "prefers-color-scheme" not in css  # Native menu, not OS-only selection.
    assert '[data-testid="stMainMenuItem-print"] { display:none !important; }' in css


def test_brand_asset_replaces_letter_monogram() -> None:
    app = APP_PATH.read_text()
    assert "ti-monogram" not in app
    assert 'page_icon=str(LOGO_PATH)' in app
    logo = (ROOT / "assets/your-intelligence-coach-logo.png").read_bytes()
    assert logo.startswith(b"\x89PNG\r\n\x1a\n")
    assert (ROOT / "static/tender-meridian-logo.png").read_bytes() == logo
    assert 'LOGO_URI = "/app/static/tender-meridian-logo.png"' in app
    assert "data:image/png;base64," not in app


def test_motion_is_progressive_and_respects_reduced_motion() -> None:
    css = CSS_PATH.read_text()
    motion = (ROOT / "assets/motion.js").read_text()
    field_css = (ROOT / "assets/field/field.css").read_text()
    field_js = (ROOT / "assets/field/field.js").read_text()
    # Hidden states exist only behind classes the script adds, so content is
    # visible without JavaScript.
    assert ".tm-reveal {" in css and 'classList.add("tm-reveal")' in motion
    assert "prefers-reduced-motion" in motion and "prefers-reduced-motion" in field_js
    assert "@media (prefers-reduced-motion:reduce)" in field_css
    # The field never builds markup from notice text.
    assert "innerHTML" not in field_js.replace('labelsEl.innerHTML = ""', "")
