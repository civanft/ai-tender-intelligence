"""Add SEO routes to an existing Certbot-managed Nginx installation.

The initial installer uses nginx-site.conf.template. This migration preserves
the TLS configuration Certbot subsequently added to the live file.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


DOMAIN = "tendermeridian.com"
CONFIG = Path("/etc/nginx/sites-available/ai-tender-intelligence.conf")
PUBLIC = Path("/var/www/tender-meridian")
SOURCE = Path(__file__).resolve().parent / "public"


def updated_config(current: str) -> str:
    server_name = f"    server_name {DOMAIN} www.{DOMAIN};\n"
    if current.count(server_name) != 2:
        raise ValueError("Expected the existing Certbot HTTPS and HTTP server blocks")
    if "location = /robots.txt" in current or "location ^~ /about/" in current:
        raise ValueError("SEO locations are already installed; inspect before reapplying")
    if current.count("    location / {\n") != 1:
        raise ValueError("Expected one Streamlit proxy location")

    redirect = (
        f"\n    if ($host = www.{DOMAIN}) {{\n"
        f"        return 301 https://{DOMAIN}$request_uri;\n"
        "    }\n"
    )
    locations = """
    location = /robots.txt {
        alias /var/www/tender-meridian/robots.txt;
    }

    location = /sitemap.xml {
        alias /var/www/tender-meridian/sitemap.xml;
    }

    location = /about {
        return 308 /about/;
    }

    location ^~ /about/ {
        alias /var/www/tender-meridian/about/;
        index index.html;
    }

"""
    return current.replace(server_name, server_name + redirect, 1).replace(
        "    location / {\n", locations + "    location / {\n", 1
    )


def main() -> None:
    if os.geteuid() != 0:
        raise PermissionError("Run as root")
    if not CONFIG.is_file():
        raise FileNotFoundError(CONFIG)
    current = CONFIG.read_text(encoding="utf-8")
    updated = updated_config(current)

    backup = CONFIG.with_suffix(".conf.pre-seo")
    if backup.exists():
        raise FileExistsError(backup)

    PUBLIC.mkdir(parents=True, exist_ok=True)
    PUBLIC.chmod(0o755)
    PUBLIC.joinpath("about").mkdir(exist_ok=True)
    PUBLIC.joinpath("about").chmod(0o755)
    for relative in ("robots.txt", "sitemap.xml", "about/index.html"):
        destination = PUBLIC / relative
        contents = (SOURCE / relative).read_text(encoding="utf-8").replace(
            "__SITE_DOMAIN__", DOMAIN
        )
        destination.write_text(contents, encoding="utf-8")
        destination.chmod(0o644)

    shutil.copy2(CONFIG, backup)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=CONFIG.parent, delete=False
        ) as temporary:
            temporary.write(updated)
            temporary_path = Path(temporary.name)
        temporary_path.chmod(CONFIG.stat().st_mode & 0o777)
        temporary_path.replace(CONFIG)
        subprocess.run(["nginx", "-t"], check=True)
        subprocess.run(["systemctl", "reload", "nginx"], check=True)
    except Exception:
        shutil.copy2(backup, CONFIG)
        subprocess.run(["nginx", "-t"], check=True)
        raise
    print("SEO routes installed; Nginx syntax passed and service reloaded.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
