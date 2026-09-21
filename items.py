import json
import logging
import os
import shutil
from pathlib import Path

log = logging.getLogger("launcher")

APP_DIR = Path(__file__).parent
CONFIG_PATH = APP_DIR / "config.json"
EXAMPLE_CONFIG_PATH = APP_DIR / "config.example.json"

DEFAULT_CONFIG = {
    "hotkey": "ctrl+alt+l",
    "items": [],
}

# Names some people type for the same modifier; only used to compare hotkeys, never to register them.
_MODIFIER_ALIASES = {"control": "ctrl", "win": "windows", "cmd": "windows", "super": "windows"}


def ensure_config(config_path=None, example_path=None):
    """First run: config.json is personal and gitignored, so copy config.example.json to it.
    Returns True when a copy was made."""
    config_path = Path(config_path or CONFIG_PATH)
    example_path = Path(example_path or EXAMPLE_CONFIG_PATH)
    if config_path.exists() or not example_path.exists():
        return False
    try:
        shutil.copyfile(example_path, config_path)
    except OSError as e:
        log.warning("could not create %s from %s: %s", config_path, example_path.name, e)
        return False
    log.info("created %s from %s", config_path.name, example_path.name)
    return True


def load_config(config_path=None, example_path=None):
    config_path = Path(config_path or CONFIG_PATH)
    ensure_config(config_path, example_path)
    config = dict(DEFAULT_CONFIG)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config.update(json.load(f))
    except FileNotFoundError:
        pass  # no config and no example: run with an empty palette
    return config


def expand_target(target, item_type=None):
    """Expand %VAR% / $VAR and a leading ~ in a path target. URLs are left alone, so a literal
    %20 in a link is never touched."""
    if item_type == "url":
        return target
    return os.path.expandvars(os.path.expanduser(target))


def build_items(config):
    """Only what's explicitly listed in config.json - no Start Menu scanning."""
    items = []
    for entry in config.get("items", []):
        if {"name", "type", "target"} <= entry.keys():
            item = dict(entry)
            item["target"] = expand_target(item["target"], item.get("type"))
            items.append(item)
    return items


def normalize_hotkey(hotkey):
    """Canonical form for comparing hotkeys: 'Ctrl + Alt+J' and 'alt+control+j' are the same key."""
    parts = [p.strip().lower() for p in str(hotkey).split("+")]
    parts = [_MODIFIER_ALIASES.get(p, p) for p in parts if p]
    return "+".join(sorted(parts))


def plan_item_hotkeys(items, main_hotkey):
    """Decide which per-item hotkeys to register.

    Returns (to_register, conflicts): to_register is a list of (hotkey, item); conflicts is a list
    of human-readable messages for hotkeys that were skipped. The palette hotkey always wins, and
    between items the first one listed wins - two actions must never fire on one key press.
    """
    taken = {normalize_hotkey(main_hotkey): "the palette hotkey"} if main_hotkey else {}
    to_register, conflicts = [], []
    for item in items:
        hk = item.get("hotkey")
        if not hk:
            continue
        key = normalize_hotkey(hk)
        if key in taken:
            if taken[key] == "the palette hotkey":
                conflicts.append(f"{item.get('name')}: {hk} is the palette hotkey, ignoring")
            else:
                conflicts.append(f"{item.get('name')}: {hk} is already used by {taken[key]}, ignoring")
            continue
        taken[key] = item.get("name")
        to_register.append((hk, item))
    return to_register, conflicts


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
