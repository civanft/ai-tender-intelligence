import tomllib
from pathlib import Path


CONFIG = Path(__file__).resolve().parents[1] / ".streamlit/config.toml"


def test_streamlit_security_controls_are_explicitly_enabled():
    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))

    assert config["server"]["enableCORS"] is True
    assert config["server"]["enableXsrfProtection"] is True
    assert config["server"]["xsrfCookieSameSite"] == "strict"
    assert config["client"]["showErrorDetails"] == "none"
    assert config["client"]["showErrorLinks"] is False
