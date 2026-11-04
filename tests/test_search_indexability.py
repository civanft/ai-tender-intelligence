from pathlib import Path
from runpy import run_path
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "deploy" / "vds" / "public"


def test_initial_html_has_a_real_title_description_and_canonical() -> None:
    patch_html = run_path(str(ROOT / "scripts" / "patch_streamlit_shell.py"))["patch_html"]
    result = patch_html("<head><title>Streamlit</title></head>")

    assert "<title>Tender Meridian | European public tender intelligence</title>" in result
    assert '<meta name="description"' in result
    assert '<link rel="canonical" href="https://tendermeridian.com/"' in result
    with pytest.raises(ValueError, match="title marker"):
        patch_html("<head><title>Something else</title></head>")

    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "!scripts/patch_streamlit_shell.py" in dockerignore


def test_public_crawl_files_and_indexable_about_page_are_packaged() -> None:
    sitemap = (PUBLIC / "sitemap.xml").read_text(encoding="utf-8").replace(
        "__SITE_DOMAIN__", "tendermeridian.com"
    )
    root = ET.fromstring(sitemap)
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [node.text for node in root.findall("s:url/s:loc", namespace)]
    assert urls == ["https://tendermeridian.com/", "https://tendermeridian.com/about/"]

    robots = (PUBLIC / "robots.txt").read_text(encoding="utf-8")
    assert "Sitemap: https://__SITE_DOMAIN__/sitemap.xml" in robots

    about = (PUBLIC / "about" / "index.html").read_text(encoding="utf-8")
    assert "<title>About Tender Meridian" in about
    assert "https://__SITE_DOMAIN__/about/" in about
    assert "EU Tenders Electronic Daily (TED)" in about

    nginx = (ROOT / "deploy" / "vds" / "nginx-site.conf.template").read_text(
        encoding="utf-8"
    )
    for path in ("/robots.txt", "/sitemap.xml"):
        assert f"location = {path}" in nginx
    assert "location ^~ /about/" in nginx


def test_live_migration_preserves_existing_certbot_server_blocks() -> None:
    updated_config = run_path(str(ROOT / "deploy" / "vds" / "apply-seo-live.py"))[
        "updated_config"
    ]
    existing = (
        "server {\n"
        "    server_name tendermeridian.com www.tendermeridian.com;\n"
        "    location / {\n        proxy_pass http://127.0.0.1:8501;\n    }\n"
        "    ssl_certificate /etc/letsencrypt/live/tendermeridian.com/fullchain.pem;\n"
        "}\n"
        "server {\n"
        "    server_name tendermeridian.com www.tendermeridian.com;\n"
        "    return 404;\n"
        "}\n"
    )
    result = updated_config(existing)
    assert "ssl_certificate /etc/letsencrypt/live/tendermeridian.com/fullchain.pem;" in result
    assert result.count("location = /robots.txt") == 1
    assert result.count("return 301 https://tendermeridian.com$request_uri;") == 1
    with pytest.raises(ValueError, match="already installed"):
        updated_config(result)
