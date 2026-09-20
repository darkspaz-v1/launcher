# Shortcut Pad

One hotkey to reach any app in this suite, or fire a standalone action.

> The folder and the Python identifiers still say `launcher`. The rename to Shortcut Pad was
> deliberately display-only, to avoid path and import churn for a cosmetic change.

## How it works

- **`Ctrl+Alt+L`** opens a borderless palette. Type to filter, Enter to run.
- Entries come from `config.json`. Each one launches a target — usually another app's `run.bat`, but
  any script or executable works.
- **An entry can carry its own global hotkey** (optional `hotkey` key), registered by
  `_register_item_hotkeys()` independently of the palette. Those fire the action directly with no
  palette popup.

## Notes from building it

- **It does not index the Start Menu.** The first version did, which meant every installed program
  showed up. A launcher listing everything is just the Start Menu with extra steps.
- The palette hotkey was originally `Ctrl+Alt+Space` and had to move: it collided with the Claude
  desktop app Quick Window. Windows keyboard hooks are not exclusive, so both fired on every press.
- **`config.json` is read only at startup.** A hotkey that does not work is almost always a config the
  running tray process has never read — exit the tray icon fully and relaunch.

**Stack:** Python, Tkinter (custom borderless palette), `keyboard`, `pystray`.

## Part of a suite

One of seven small Windows tray utilities built as separate, self-contained apps: each has its own
folder, its own virtualenv and its own `run.bat`, with no shared runtime. They are deliberately not a
framework — the only thing they share is a set of conventions.

| Convention | Why |
|---|---|
| Single-instance guard via a `.singleton.lock` file | An earlier `.instance.lock` design could get stuck after a force-kill and leave the app permanently unlaunchable |
| Relaunch brings the existing window forward | Previously a second launch silently did nothing, which was indistinguishable from the app being broken |
| Config lives in `config.json`, read at startup | Edit it, then fully exit the tray icon and relaunch — a running process never re-reads it |
| Tray icon generated in code (`icon.py`) | No binary asset to keep in sync |

## Running it

```
run.bat
```

That creates the virtualenv on first run, installs `requirements.txt`, and starts the app. Windows
only — these use Win32 APIs and a system tray.

## License

MIT — see [LICENSE](LICENSE).
