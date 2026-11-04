"""Give Streamlit's initial HTML response useful public page metadata.

Streamlit updates the browser title after its WebSocket connects. Search crawlers
also inspect the initial response, before that connection is available.
"""

from __future__ import annotations

from pathlib import Path


TITLE = "Tender Meridian | European public tender intelligence"
DESCRIPTION = (
    "Explore public EU procurement notices for AI, data analytics and data "
    "infrastructure across 27 member states. Research sourced from EU TED."
)
CANONICAL_URL = "https://tendermeridian.com/"


def patch_html(source: str) -> str:
    marker = "<title>Streamlit</title>"
    if source.count(marker) != 1:
        raise ValueError("Unexpected Streamlit HTML shell: title marker missing or duplicated")
    metadata = "\n".join(
        [
            f"<title>{TITLE}</title>",
            f'<meta name="description" content="{DESCRIPTION}" />',
            f'<link rel="canonical" href="{CANONICAL_URL}" />',
            '<meta property="og:type" content="website" />',
            f'<meta property="og:title" content="{TITLE}" />',
            f'<meta property="og:description" content="{DESCRIPTION}" />',
            f'<meta property="og:url" content="{CANONICAL_URL}" />',
        ]
    )
    return source.replace(marker, metadata, 1)


def main() -> None:
    import streamlit

    shell = Path(streamlit.__file__).parent / "static" / "index.html"
    shell.write_text(patch_html(shell.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
