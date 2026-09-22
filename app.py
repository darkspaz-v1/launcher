import logging
import msvcrt
import queue
import threading
import time
import tkinter as tk
from logging.handlers import RotatingFileHandler
from pathlib import Path

import keyboard
import pystray
from PIL import ImageTk

from icon import app_icon
from items import build_items, load_config, plan_item_hotkeys
from launcher_actions import launch_item
from palette import LauncherPalette

APP_DIR = Path(__file__).parent
LOCK_PATH = APP_DIR / ".singleton.lock"
LOG_DIR = APP_DIR / "logs"
_lock_file = None

log = logging.getLogger("launcher")


def setup_logging():
    """Log to logs/launcher.log (rotating). Under pythonw there is no console, so print() output
    used to vanish; this file is where hotkey and launch failures show up now."""
    try:
        LOG_DIR.mkdir(exist_ok=True)
        handler = RotatingFileHandler(LOG_DIR / "launcher.log", maxBytes=256 * 1024,
                                      backupCount=3, encoding="utf-8")
    except OSError:
        return  # read-only folder: run without a log file rather than fail to start
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


def _acquire_single_instance_lock():
    """Best-effort single-instance guard via an exclusive OS file lock (stdlib
    msvcrt, Windows-only, no extra dependency). Held for the process's lifetime;
    a second launch fails to acquire it and exits immediately instead of spawning
    a duplicate tray icon and hotkey registration."""
    global _lock_file
    f = open(LOCK_PATH, "a+b")
    if f.tell() == 0:
        f.write(b"0")
        f.flush()
    f.seek(0)
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        return False
    _lock_file = f
    return True


class LauncherApp:
    def __init__(self):
        self.config = load_config()
        self.root = tk.Tk()
        self.root.withdraw()
        self._icon_photo = ImageTk.PhotoImage(app_icon())
        self.root.iconphoto(True, self._icon_photo)
        self.palette = LauncherPalette(self.root, self._get_items, self._on_select)
        self._stop = threading.Event()
        self.icon = None

        # The global hotkey and tray icon each run on their own thread and must
        # never touch Tk directly; they post callables here and this drain (always
        # running on the Tk thread via after()) is what actually applies them.
        self._ui_queue = queue.Queue()
        self.root.after(50, self._drain_ui_queue)
        self._item_hotkeys = []  # hotkey strings registered for individual items (besides the main palette hotkey)

    def _drain_ui_queue(self):
        try:
            while True:
                fn = self._ui_queue.get_nowait()
                fn()
        except queue.Empty:
            pass
        self.root.after(50, self._drain_ui_queue)

    def _post(self, fn):
        self._ui_queue.put(fn)

    def _get_items(self):
        return build_items(self.config)

    def _on_select(self, item):
        try:
            launch_item(item)
        except Exception:  # noqa: BLE001 - a bad target must never take down the tray app
            log.exception("Launch failed for %s", item.get("name"))

    def show_palette(self):
        self._post(self.palette.show)

    def quit_app(self, icon=None, item=None):
        self._stop.set()
        try:
            keyboard.remove_hotkey(self.config["hotkey"])
        except KeyError:
            log.debug("palette hotkey %s was not registered", self.config["hotkey"])
        for hk in self._item_hotkeys:
            try:
                keyboard.remove_hotkey(hk)
            except KeyError:
                log.debug("item hotkey %s was not registered", hk)
        if self.icon:
            self.icon.stop()
        self._post(self.root.quit)

    def _run_item(self, item):
        # Runs on the keyboard-hook thread; launch_item only touches the OS
        # (os.startfile / webbrowser.open), never Tk, so no _post() needed here.
        try:
            launch_item(item)
        except Exception:  # noqa: BLE001 - runs on the keyboard-hook thread; must not kill it
            log.exception("Hotkey launch failed for %s", item.get("name"))

    def _register_item_hotkeys(self):
        to_register, conflicts = plan_item_hotkeys(self._get_items(), self.config.get("hotkey"))
        for msg in conflicts:
            log.warning("hotkey conflict - %s", msg)
        for hk, item in to_register:
            try:
                keyboard.add_hotkey(hk, self._run_item, args=(item,))
                self._item_hotkeys.append(hk)
            except Exception as e:  # noqa: BLE001 - the keyboard lib raises assorted types; a bad hotkey must not stop the tray app
                log.warning("could not register hotkey %s for %s: %s", hk, item.get("name"), e)

    def run(self):
        menu = pystray.Menu(
            pystray.MenuItem(
                f"Open Shortcut Pad  ({self.config['hotkey']})",
                lambda icon, item: self.show_palette(),
                default=True,
            ),
            pystray.MenuItem("Quit", self.quit_app),
        )
        self.icon = pystray.Icon("shortcut-pad", app_icon(), "Shortcut Pad", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

        try:
            keyboard.add_hotkey(self.config["hotkey"], self.show_palette)
        except Exception as e:  # noqa: BLE001 - the keyboard lib raises assorted types; a bad hotkey must not stop the tray app
            log.warning("could not register hotkey %s: %s", self.config["hotkey"], e)

        self._register_item_hotkeys()

        self.root.mainloop()


def main():
    setup_logging()
    if not _acquire_single_instance_lock():
        return
    app = LauncherApp()
    app.run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        with open(APP_DIR / "app_error.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- {time.ctime()} ---\n")
            f.write(traceback.format_exc())
        raise
