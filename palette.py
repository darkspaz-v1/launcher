import tkinter as tk

from items import rank

INK = "#12131C"
PANEL_SELECTED = "#262A44"
HAIRLINE = "#2E3044"
TEXT = "#EDEEF7"
MUTED = "#8688A6"
ACCENT = "#9B7BFF"
DANGER = "#F0576B"


class LauncherPalette:
    """Simple dark popup. Type to filter, click/Enter to launch."""

    MAX_VISIBLE = 8
    WIDTH = 520

    def __init__(self, root, get_items, on_select):
        self.root = root
        self.get_items = get_items
        self.on_select = on_select
        self.win = None
        self._filtered = []
        self._selected = 0
        self._row_widgets = []
        self._drag_x = 0
        self._drag_y = 0

    def show(self):
        if self.win is not None and self.win.winfo_exists():
            self.win.lift()
            self.win.focus_force()
            return

        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=INK, highlightthickness=1, highlightbackground=HAIRLINE)
        self.win.bind("<Escape>", lambda e: self._close())

        self._build_chrome()
        self._refresh()
        self._position()

        self.win.deiconify()
        self.win.focus_force()
        self.entry.focus_set()

    def _build_chrome(self):
        header = tk.Frame(self.win, bg=INK)
        header.pack(fill="x", padx=16, pady=(14, 8))
        header.bind("<ButtonPress-1>", self._start_drag)
        header.bind("<B1-Motion>", self._do_drag)

        title = tk.Label(header, text="Shortcut Pad", bg=INK, fg=TEXT, font=("Segoe UI", 12, "bold"))
        title.pack(side="left")
        title.bind("<ButtonPress-1>", self._start_drag)
        title.bind("<B1-Motion>", self._do_drag)

        close_btn = tk.Label(header, text="×", bg=INK, fg=MUTED, font=("Segoe UI", 14), cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: self._close())
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg=DANGER))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=MUTED))

        entry_wrap = tk.Frame(self.win, bg=INK)
        entry_wrap.pack(fill="x", padx=16, pady=(0, 10))

        self.entry = tk.Entry(
            entry_wrap,
            bg=INK,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 14),
            highlightthickness=0,
            bd=0,
        )
        self.entry.pack(fill="x", ipady=4)

        self._underline = tk.Frame(entry_wrap, bg=HAIRLINE, height=2)
        self._underline.pack(fill="x", pady=(4, 0))
        self.entry.bind("<FocusIn>", lambda e: self._underline.config(bg=ACCENT))
        self.entry.bind("<FocusOut>", lambda e: self._underline.config(bg=HAIRLINE))

        self.results_frame = tk.Frame(self.win, bg=INK)
        self.results_frame.pack(fill="both", expand=True, padx=10, pady=(0, 14))

        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Return>", lambda e: self._launch_index(self._selected))
        self.entry.bind("<Down>", self._on_down)
        self.entry.bind("<Up>", self._on_up)

    def _on_down(self, event):
        self._move(1)
        return "break"

    def _on_up(self, event):
        self._move(-1)
        return "break"

    def _on_key(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape"):
            return
        self._refresh()

    def _refresh(self):
        query = self.entry.get().strip()
        all_items = self.get_items()
        self._filtered = rank(all_items, query)[: self.MAX_VISIBLE]
        self._selected = 0
        self._render_rows()

    def _move(self, delta):
        if not self._filtered:
            return
        new_index = max(0, min(self._selected + delta, len(self._filtered) - 1))
        self._set_selected(new_index)

    def _hover(self, index):
        self._set_selected(index)

    def _set_selected(self, index):
        """Restyle only the previously- and newly-selected rows in place, rather
        than destroying/rebuilding the whole list - full rebuilds on every mouse
        move or arrow key caused visible flicker."""
        if index == self._selected or not (0 <= index < len(self._row_widgets)):
            return
        old_index = self._selected
        self._selected = index
        if 0 <= old_index < len(self._row_widgets):
            self._style_row(self._row_widgets[old_index], False)
        self._style_row(self._row_widgets[index], True)

    def _style_row(self, row, selected):
        bg = PANEL_SELECTED if selected else INK
        for w in row.bg_widgets:
            w.config(bg=bg)

    def _render_rows(self):
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets = []

        if not self._filtered:
            empty = tk.Label(self.results_frame, text="No matches", bg=INK, fg=MUTED, font=("Segoe UI", 10), pady=20)
            empty.pack(fill="x")
            self._row_widgets.append(empty)
            return

        for i, item in enumerate(self._filtered):
            row = self._build_row(i, item)
            row.pack(fill="x")
            self._row_widgets.append(row)

    def _build_row(self, index, item):
        selected = index == self._selected
        bg = PANEL_SELECTED if selected else INK

        row = tk.Frame(self.results_frame, bg=bg)
        name = tk.Label(row, text=item["name"], bg=bg, fg=TEXT, font=("Segoe UI", 11), anchor="w")
        name.pack(fill="x", padx=12, pady=9)

        row.bg_widgets = [row, name]

        for widget in (row, name):
            widget.bind("<Button-1>", lambda e, i=index: self._launch_index(i))
            widget.bind("<Enter>", lambda e, i=index: self._hover(i))

        return row

    def _launch_index(self, index):
        if 0 <= index < len(self._filtered):
            item = self._filtered[index]
            self._close()
            self.on_select(item)

    def _start_drag(self, event):
        self._drag_x = event.x_root - self.win.winfo_x()
        self._drag_y = event.y_root - self.win.winfo_y()

    def _do_drag(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.win.geometry(f"+{x}+{y}")

    def _position(self):
        self.win.update_idletasks()
        height = self.win.winfo_reqheight()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = (sw - self.WIDTH) // 2
        y = (sh - height) // 3
        self.win.geometry(f"{self.WIDTH}x{height}+{x}+{y}")

    def _close(self):
        if self.win is not None:
            self.win.destroy()
            self.win = None
