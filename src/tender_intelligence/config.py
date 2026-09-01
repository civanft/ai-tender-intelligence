import json
from pathlib import Path
from typing import Any

from .paths import CONFIG_DIR


def load_json(path: Path) -> dict[str, Any]:
    """Load a UTF-8 JSON configuration file."""
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def load_taxonomy() -> dict[str, Any]:
    return load_json(CONFIG_DIR / "taxonomy.json")


def load_profile() -> dict[str, Any]:
    return load_json(CONFIG_DIR / "profile.json")
