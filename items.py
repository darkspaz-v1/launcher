import json
from pathlib import Path

APP_DIR = Path(__file__).parent
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_CONFIG = {
    "hotkey": "ctrl+alt+l",
    "items": [],
}


def load_config():
    config = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config.update(json.load(f))
    except FileNotFoundError:
        pass
    return config


def build_items(config):
    """Only what's explicitly listed in config.json - no Start Menu scanning."""
    items = []
    for entry in config.get("items", []):
        if {"name", "type", "target"} <= entry.keys():
            items.append(dict(entry))
    return items


def rank(items, query):
    """Prefix matches first (alphabetical), then substring matches (alphabetical)."""
    if not query:
        return sorted(items, key=lambda it: it["name"].lower())
    q = query.lower()
    starts, contains = [], []
    for it in items:
        name_l = it["name"].lower()
        if q in name_l:
            (starts if name_l.startswith(q) else contains).append(it)
    starts.sort(key=lambda it: it["name"].lower())
    contains.sort(key=lambda it: it["name"].lower())
    return starts + contains
