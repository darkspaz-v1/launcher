import msvcrt
import queue
import threading
import time
import tkinter as tk
from pathlib import Path

import keyboard
import pystray
from PIL import ImageTk

from icon import app_icon
from items import build_items, load_config
from launcher_actions import launch_item
from palette import LauncherPalette

APP_DIR = Path(__file__).parent
LOCK_PATH = APP_DIR / ".singleton.lock"
_lock_file = None


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
        except Exception as e:
            print(f"Launch failed for {item.get('name')}: {e}")

    def show_palette(self):
        self._post(self.palette.show)

    def quit_app(self, icon=None, item=None):
        self._stop.set()
        try:
            keyboard.remove_hotkey(self.config["hotkey"])
        except Exception:
            pass
        for hk in self._item_hotkeys:
            try:
                keyboard.remove_hotkey(hk)
            except Exception:
                pass
        if self.icon:
            self.icon.stop()
        self._post(self.root.quit)

    def _run_item(self, item):
        # Runs on the keyboard-hook thread; launch_item only touches the OS
        # (os.startfile / webbrowser.open), never Tk, so no _post() needed here.
        try:
            launch_item(item)
        except Exception as e:
            print(f"Hotkey launch failed for {item.get('name')}: {e}")

    def _register_item_hotkeys(self):
        for item in self._get_items():
            hk = item.get("hotkey")
            if not hk or hk == self.config.get("hotkey"):
                continue
            try:
                keyboard.add_hotkey(hk, self._run_item, args=(item,))
                self._item_hotkeys.append(hk)
            except Exception as e:
                print(f"Warning: could not register hotkey {hk} for {item.get('name')}: {e}")

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
        except Exception as e:
            print(f"Warning: could not register hotkey {self.config['hotkey']}: {e}")

        self._register_item_hotkeys()

        self.root.mainloop()


def main():
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
