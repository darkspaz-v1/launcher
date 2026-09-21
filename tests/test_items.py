"""items.py: config loading, item validation, path expansion, ranking, hotkey conflict detection.

Pure logic only - no Tk, no keyboard hooks, no real config.json.
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import items  # noqa: E402
import launcher_actions  # noqa: E402


def item(name, hotkey=None, target="x.exe", type_="app"):
    d = {"name": name, "type": type_, "target": target}
    if hotkey:
        d["hotkey"] = hotkey
    return d


# ---------------------------------------------------------------- build_items / validation

def test_build_items_requires_name_type_target():
    cfg = {"items": [
        {"name": "ok", "type": "app", "target": "a.exe"},
        {"name": "no target", "type": "app"},
        {"name": "no type", "target": "a.exe"},
        {"type": "app", "target": "a.exe"},
        {},
    ]}
    assert [i["name"] for i in items.build_items(cfg)] == ["ok"]


def test_build_items_empty_and_missing_items_key():
    assert items.build_items({}) == []
    assert items.build_items({"items": []}) == []


def test_build_items_keeps_extra_keys_and_does_not_mutate_config():
    cfg = {"items": [item("Jarvis", hotkey="ctrl+alt+j", target="%USERPROFILE%\\j.vbs")]}
    built = items.build_items(cfg)
    assert built[0]["hotkey"] == "ctrl+alt+j"
    assert cfg["items"][0]["target"] == "%USERPROFILE%\\j.vbs"  # original untouched


# ---------------------------------------------------------------- env-var expansion

def test_target_expands_percent_env_vars(monkeypatch):
    monkeypatch.setenv("USERPROFILE", r"C:\Users\someone")
    monkeypatch.setenv("MY_APPS", r"D:\apps")
    built = items.build_items({"items": [
        item("A", target=r"%USERPROFILE%\Desktop\Claude\x\run.bat"),
        item("B", target=r"%MY_APPS%\b.exe"),
    ]})
    if os.name == "nt":  # %VAR% expansion is Windows-native; on POSIX os.path.expandvars ignores it
        assert built[0]["target"] == r"C:\Users\someone\Desktop\Claude\x\run.bat"
        assert built[1]["target"] == r"D:\apps\b.exe"


def test_target_expands_dollar_vars_and_tilde(monkeypatch):
    monkeypatch.setenv("LAUNCHER_TEST_DIR", "somewhere")
    assert items.expand_target("$LAUNCHER_TEST_DIR/run.bat") == "somewhere/run.bat"
    assert "~" not in items.expand_target("~/run.bat")


def test_unknown_env_var_is_left_as_is(monkeypatch):
    monkeypatch.delenv("DEFINITELY_NOT_SET_12345", raising=False)
    assert items.expand_target(r"%DEFINITELY_NOT_SET_12345%\a.exe") == r"%DEFINITELY_NOT_SET_12345%\a.exe"


def test_url_targets_are_not_expanded(monkeypatch):
    monkeypatch.setenv("LAUNCHER_TEST_DIR", "x")
    url = "https://example.com/a%20b?q=$LAUNCHER_TEST_DIR"
    assert items.expand_target(url, "url") == url
    built = items.build_items({"items": [item("Site", target=url, type_="url")]})
    assert built[0]["target"] == url


def test_launch_item_opens_urls_and_paths(monkeypatch):
    opened = {}
    monkeypatch.setattr(launcher_actions.webbrowser, "open", lambda t: opened.setdefault("url", t))
    monkeypatch.setattr(launcher_actions.os, "startfile", lambda t: opened.setdefault("path", t), raising=False)
    launcher_actions.launch_item({"type": "url", "target": "https://example.com"})
    launcher_actions.launch_item({"type": "app", "target": "C:/x/run.bat"})
    assert opened == {"url": "https://example.com", "path": "C:/x/run.bat"}


# ---------------------------------------------------------------- config load / first run

def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_load_config_defaults_when_nothing_exists(tmp_path):
    cfg = items.load_config(tmp_path / "config.json", tmp_path / "config.example.json")
    assert cfg == {"hotkey": "ctrl+alt+l", "items": []}
    assert not (tmp_path / "config.json").exists()


def test_first_run_copies_example_to_config(tmp_path):
    example = tmp_path / "config.example.json"
    write_json(example, {"hotkey": "ctrl+alt+p", "items": [item("Demo")]})
    cfg = items.load_config(tmp_path / "config.json", example)
    assert (tmp_path / "config.json").exists()
    assert cfg["hotkey"] == "ctrl+alt+p" and cfg["items"][0]["name"] == "Demo"


def test_existing_config_is_never_overwritten(tmp_path):
    write_json(tmp_path / "config.example.json", {"hotkey": "ctrl+alt+p"})
    write_json(tmp_path / "config.json", {"hotkey": "ctrl+alt+q"})
    cfg = items.load_config(tmp_path / "config.json", tmp_path / "config.example.json")
    assert cfg["hotkey"] == "ctrl+alt+q"
    assert json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))["hotkey"] == "ctrl+alt+q"


def test_ensure_config_reports_whether_it_copied(tmp_path):
    write_json(tmp_path / "config.example.json", {})
    assert items.ensure_config(tmp_path / "config.json", tmp_path / "config.example.json") is True
    assert items.ensure_config(tmp_path / "config.json", tmp_path / "config.example.json") is False


def test_ensure_config_without_example_does_nothing(tmp_path):
    assert items.ensure_config(tmp_path / "config.json", tmp_path / "config.example.json") is False


def test_shipped_example_config_is_valid_and_portable():
    example = Path(__file__).resolve().parent.parent / "config.example.json"
    data = json.loads(example.read_text(encoding="utf-8"))
    assert data["hotkey"] and data["items"]
    for it in data["items"]:
        assert {"name", "type", "target"} <= it.keys()
        assert it["target"].startswith("%USERPROFILE%")  # no drive-letter or user-specific path


def test_shipped_example_has_no_hotkey_conflicts():
    example = Path(__file__).resolve().parent.parent / "config.example.json"
    data = json.loads(example.read_text(encoding="utf-8"))
    _, conflicts = items.plan_item_hotkeys(data["items"], data["hotkey"])
    assert conflicts == []


# ---------------------------------------------------------------- ranking

def test_rank_empty_query_is_alphabetical_case_insensitive():
    got = items.rank([item("banana"), item("Apple"), item("cherry")], "")
    assert [i["name"] for i in got] == ["Apple", "banana", "cherry"]


def test_rank_prefix_before_substring():
    got = items.rank([item("Task Watcher"), item("Watch Later"), item("Downloads Watcher")], "watch")
    assert [i["name"] for i in got] == ["Watch Later", "Downloads Watcher", "Task Watcher"]


def test_rank_no_match_and_case_insensitive():
    assert items.rank([item("Apple")], "zzz") == []
    assert [i["name"] for i in items.rank([item("Apple")], "APP")] == ["Apple"]


# ---------------------------------------------------------------- hotkey conflict detection

@pytest.mark.parametrize("a,b", [
    ("ctrl+alt+j", "Ctrl+Alt+J"),
    ("ctrl+alt+j", "alt+ctrl+j"),
    ("ctrl + alt + j", "ctrl+alt+j"),
    ("control+alt+j", "ctrl+alt+j"),
    ("win+e", "windows+e"),
])
def test_normalize_hotkey_treats_equivalents_as_equal(a, b):
    assert items.normalize_hotkey(a) == items.normalize_hotkey(b)


def test_normalize_hotkey_distinguishes_different_keys():
    assert items.normalize_hotkey("ctrl+alt+j") != items.normalize_hotkey("ctrl+alt+k")
    assert items.normalize_hotkey("ctrl+j") != items.normalize_hotkey("ctrl+alt+j")


def test_no_hotkeys_means_nothing_to_register():
    assert items.plan_item_hotkeys([item("A"), item("B")], "ctrl+alt+l") == ([], [])


def test_distinct_hotkeys_all_register_in_order():
    a, b = item("A", "ctrl+alt+j"), item("B", "ctrl+alt+x")
    reg, conflicts = items.plan_item_hotkeys([a, b], "ctrl+alt+l")
    assert reg == [("ctrl+alt+j", a), ("ctrl+alt+x", b)] and conflicts == []


def test_item_hotkey_equal_to_palette_hotkey_is_dropped():
    reg, conflicts = items.plan_item_hotkeys([item("A", "Alt+Ctrl+L")], "ctrl+alt+l")
    assert reg == []
    assert len(conflicts) == 1 and "palette hotkey" in conflicts[0]


def test_first_item_wins_a_duplicate_hotkey():
    a, b = item("First", "ctrl+alt+j"), item("Second", "ALT+CTRL+J")
    reg, conflicts = items.plan_item_hotkeys([a, b], "ctrl+alt+l")
    assert reg == [("ctrl+alt+j", a)]
    assert len(conflicts) == 1 and "Second" in conflicts[0] and "First" in conflicts[0]


def test_conflict_detection_with_no_palette_hotkey():
    reg, conflicts = items.plan_item_hotkeys([item("A", "ctrl+j"), item("B", "ctrl+j")], None)
    assert len(reg) == 1 and len(conflicts) == 1
