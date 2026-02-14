#!/usr/bin/env python3
"""
CORE Clipboard Manager — Clipboard history with search.
Part of CORE SYSTEMS tool suite.

Features:
  - Automatic clipboard history (up to 1000 items)
  - Search / filter
  - Categories: text, links, images
  - Pinned items
  - Quick-paste via keyboard shortcut
  - Export history
  - Dark theme with CORE SYSTEMS branding
"""

import json
import os
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Constants ──────────────────────────────────────────────────────────────────

APP_NAME = "CORE Clipboard Manager"
VERSION = "1.0.0"
MAX_ITEMS = 1000
POLL_INTERVAL_MS = 500  # clipboard polling interval

# CORE SYSTEMS palette
BG_PRIMARY = "#0a0a0a"
BG_SECONDARY = "#141414"
BG_TERTIARY = "#1e1e1e"
BG_INPUT = "#1a1a1a"
FG_PRIMARY = "#e0e0e0"
FG_SECONDARY = "#888888"
FG_DIM = "#555555"
ACCENT = "#00ff88"
ACCENT_DIM = "#00cc6a"
ACCENT_BG = "#0a2a1a"
BORDER = "#2a2a2a"
PIN_COLOR = "#ffcc00"
LINK_COLOR = "#66bbff"
RED = "#ff4466"

# Data directory
if sys.platform == "darwin":
    DATA_DIR = Path.home() / "Library" / "Application Support" / "CORE Clipboard Manager"
elif sys.platform == "win32":
    DATA_DIR = Path(os.environ.get("APPDATA", "")) / "CORE Clipboard Manager"
else:
    DATA_DIR = Path.home() / ".config" / "core-clipboard-manager"

DATA_FILE = DATA_DIR / "history.json"

# URL regex
URL_RE = re.compile(
    r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE
)


# ── Data Model ─────────────────────────────────────────────────────────────────

class ClipItem:
    """Single clipboard history entry."""

    def __init__(self, content: str, category: str = "text",
                 pinned: bool = False, timestamp: Optional[str] = None):
        self.content = content
        self.category = category  # text | link | image
        self.pinned = pinned
        self.timestamp = timestamp or datetime.now().isoformat(timespec="seconds")

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "category": self.category,
            "pinned": self.pinned,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ClipItem":
        return cls(
            content=d["content"],
            category=d.get("category", "text"),
            pinned=d.get("pinned", False),
            timestamp=d.get("timestamp"),
        )


def categorize(text: str) -> str:
    """Auto-detect category from content."""
    stripped = text.strip()
    if URL_RE.match(stripped):
        return "link"
    # Check for base64 image data or common image markers
    if stripped.startswith(("data:image/", "\x89PNG", "iVBOR", "/9j/")):
        return "image"
    return "text"


# ── History Store ──────────────────────────────────────────────────────────────

class HistoryStore:
    """Persistent clipboard history."""

    def __init__(self):
        self.items: list[ClipItem] = []
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if DATA_FILE.exists():
            try:
                data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
                self.items = [ClipItem.from_dict(d) for d in data]
            except (json.JSONDecodeError, KeyError):
                self.items = []

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(
            json.dumps([it.to_dict() for it in self.items], ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def add(self, content: str) -> Optional[ClipItem]:
        """Add new item. Returns the item if added, None if duplicate of latest."""
        content = content.strip()
        if not content:
            return None

        with self._lock:
            # Skip if same as most recent non-pinned
            for it in self.items:
                if it.content == content:
                    # Move to top (unless pinned at top already)
                    self.items.remove(it)
                    self.items.insert(0, it)
                    self.save()
                    return it

            item = ClipItem(content=content, category=categorize(content))
            self.items.insert(0, item)

            # Enforce max (keep pinned even if over limit)
            unpinned = [i for i in self.items if not i.pinned]
            if len(unpinned) > MAX_ITEMS:
                to_remove = unpinned[MAX_ITEMS:]
                for it in to_remove:
                    self.items.remove(it)

            self.save()
            return item

    def delete(self, item: ClipItem):
        with self._lock:
            if item in self.items:
                self.items.remove(item)
                self.save()

    def toggle_pin(self, item: ClipItem):
        with self._lock:
            item.pinned = not item.pinned
            self.save()

    def clear_unpinned(self):
        with self._lock:
            self.items = [it for it in self.items if it.pinned]
            self.save()

    def search(self, query: str, category: str = "all") -> list[ClipItem]:
        results = self.items
        if category != "all":
            results = [it for it in results if it.category == category]
        if query:
            q = query.lower()
            results = [it for it in results if q in it.content.lower()]
        # Pinned first
        return sorted(results, key=lambda it: (not it.pinned, 0))

    def export_txt(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            for it in self.items:
                pin = "📌 " if it.pinned else ""
                f.write(f"[{it.timestamp}] [{it.category}] {pin}\n")
                f.write(it.content + "\n")
                f.write("─" * 60 + "\n")

    def export_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([it.to_dict() for it in self.items], f, ensure_ascii=False, indent=2)


# ── UI ─────────────────────────────────────────────────────────────────────────

class ClipboardManagerApp:
    """Main application window."""

    def __init__(self):
        self.store = HistoryStore()
        self._last_clipboard = ""
        self._monitoring = True

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("680x720")
        self.root.minsize(480, 500)
        self.root.configure(bg=BG_PRIMARY)

        # Set icon on macOS (no-op if fails)
        try:
            self.root.iconname(APP_NAME)
        except Exception:
            pass

        self._setup_styles()
        self._build_ui()
        self._bind_shortcuts()
        self._poll_clipboard()
        self._refresh_list()

    # ── Styles ─────────────────────────────────────────────────────────────

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=BG_PRIMARY, foreground=FG_PRIMARY,
                         fieldbackground=BG_INPUT, borderwidth=0)
        style.configure("TFrame", background=BG_PRIMARY)
        style.configure("TLabel", background=BG_PRIMARY, foreground=FG_PRIMARY,
                         font=("Helvetica", 11))
        style.configure("Title.TLabel", font=("Helvetica", 14, "bold"),
                         foreground=ACCENT)
        style.configure("Dim.TLabel", foreground=FG_SECONDARY, font=("Helvetica", 9))
        style.configure("TButton", background=BG_TERTIARY, foreground=FG_PRIMARY,
                         padding=(12, 6), font=("Helvetica", 10))
        style.map("TButton",
                   background=[("active", ACCENT_BG)],
                   foreground=[("active", ACCENT)])
        style.configure("Accent.TButton", background=ACCENT_BG, foreground=ACCENT)
        style.map("Accent.TButton",
                   background=[("active", ACCENT_DIM)])
        style.configure("Danger.TButton", foreground=RED)
        style.configure("TEntry", fieldbackground=BG_INPUT, foreground=FG_PRIMARY,
                         insertcolor=ACCENT, padding=8)
        style.configure("TRadiobutton", background=BG_PRIMARY, foreground=FG_PRIMARY,
                         font=("Helvetica", 10))
        style.map("TRadiobutton",
                   background=[("active", BG_SECONDARY)],
                   foreground=[("selected", ACCENT)])

    # ── Layout ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = self.root

        # Header
        header = ttk.Frame(root)
        header.pack(fill="x", padx=16, pady=(16, 8))

        ttk.Label(header, text="⬡ CORE", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="  Clipboard Manager",
                  font=("Helvetica", 14), foreground=FG_SECONDARY,
                  background=BG_PRIMARY).pack(side="left")

        # Status indicator
        self._status_var = tk.StringVar(value="● Monitoring")
        self._status_label = ttk.Label(header, textvariable=self._status_var,
                                        foreground=ACCENT, font=("Helvetica", 10),
                                        background=BG_PRIMARY)
        self._status_label.pack(side="right")

        # Count
        self._count_var = tk.StringVar(value="0 items")
        ttk.Label(header, textvariable=self._count_var,
                  style="Dim.TLabel").pack(side="right", padx=(0, 12))

        # Separator
        sep = tk.Frame(root, height=1, bg=BORDER)
        sep.pack(fill="x", padx=16, pady=4)

        # Search bar
        search_frame = ttk.Frame(root)
        search_frame.pack(fill="x", padx=16, pady=(8, 4))

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._refresh_list())

        search_entry = ttk.Entry(search_frame, textvariable=self._search_var,
                                  font=("Helvetica", 12))
        search_entry.pack(fill="x", ipady=4)
        search_entry.insert(0, "")
        # Placeholder
        self._search_entry = search_entry
        self._setup_placeholder(search_entry, "Search clipboard history…")

        # Category filter
        filter_frame = ttk.Frame(root)
        filter_frame.pack(fill="x", padx=16, pady=(4, 8))

        self._cat_var = tk.StringVar(value="all")
        for val, label in [("all", "All"), ("text", "📝 Text"),
                            ("link", "🔗 Links"), ("image", "🖼 Images")]:
            rb = ttk.Radiobutton(filter_frame, text=label, value=val,
                                  variable=self._cat_var,
                                  command=self._refresh_list)
            rb.pack(side="left", padx=(0, 12))

        # Toolbar
        toolbar = ttk.Frame(root)
        toolbar.pack(fill="x", padx=16, pady=(0, 8))

        ttk.Button(toolbar, text="Export…", command=self._export,
                   style="TButton").pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Clear All", command=self._clear_all,
                   style="Danger.TButton").pack(side="left", padx=(0, 6))

        self._monitor_btn_text = tk.StringVar(value="⏸ Pause")
        ttk.Button(toolbar, textvariable=self._monitor_btn_text,
                   command=self._toggle_monitoring).pack(side="right")

        # List area
        list_frame = ttk.Frame(root)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Canvas + scrollbar for custom item rendering
        self._canvas = tk.Canvas(list_frame, bg=BG_PRIMARY, highlightthickness=0,
                                  borderwidth=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                   command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner_frame = tk.Frame(self._canvas, bg=BG_PRIMARY)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._inner_frame, anchor="nw"
        )

        self._inner_frame.bind("<Configure>",
                                lambda e: self._canvas.configure(
                                    scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        # Mousewheel scrolling
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind_all("<Button-4>", self._on_mousewheel)
        self._canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        if sys.platform == "darwin":
            self._canvas.yview_scroll(-event.delta, "units")
        elif event.num == 4:
            self._canvas.yview_scroll(-3, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(3, "units")
        else:
            self._canvas.yview_scroll(-event.delta // 120, "units")

    # ── Placeholder ────────────────────────────────────────────────────────

    def _setup_placeholder(self, entry, text):
        entry._placeholder = text
        entry._has_placeholder = False

        def on_focus_in(_):
            if entry._has_placeholder:
                entry.delete(0, "end")
                entry.configure(foreground=FG_PRIMARY)
                entry._has_placeholder = False

        def on_focus_out(_):
            if not entry.get():
                entry.insert(0, text)
                entry.configure(foreground=FG_DIM)
                entry._has_placeholder = True

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        # Initial state
        on_focus_out(None)

    # ── Shortcuts ──────────────────────────────────────────────────────────

    def _bind_shortcuts(self):
        mod = "Command" if sys.platform == "darwin" else "Control"
        self.root.bind(f"<{mod}-f>", lambda _: self._search_entry.focus_set())
        self.root.bind(f"<{mod}-e>", lambda _: self._export())
        self.root.bind("<Escape>", lambda _: self._clear_search())

    def _clear_search(self):
        self._search_var.set("")
        self._search_entry.focus_set()

    # ── Clipboard Polling ──────────────────────────────────────────────────

    def _poll_clipboard(self):
        if self._monitoring:
            try:
                current = self.root.clipboard_get()
                if current and current != self._last_clipboard:
                    self._last_clipboard = current
                    item = self.store.add(current)
                    if item:
                        self._refresh_list()
            except (tk.TclError, Exception):
                pass  # Clipboard empty or unavailable

        self.root.after(POLL_INTERVAL_MS, self._poll_clipboard)

    def _toggle_monitoring(self):
        self._monitoring = not self._monitoring
        if self._monitoring:
            self._status_var.set("● Monitoring")
            self._status_label.configure(foreground=ACCENT)
            self._monitor_btn_text.set("⏸ Pause")
        else:
            self._status_var.set("○ Paused")
            self._status_label.configure(foreground=FG_DIM)
            self._monitor_btn_text.set("▶ Resume")

    # ── List Rendering ─────────────────────────────────────────────────────

    def _refresh_list(self):
        # Destroy existing items
        for w in self._inner_frame.winfo_children():
            w.destroy()

        query = self._search_var.get()
        if hasattr(self._search_entry, '_has_placeholder') and self._search_entry._has_placeholder:
            query = ""

        items = self.store.search(query, self._cat_var.get())
        self._count_var.set(f"{len(items)} item{'s' if len(items) != 1 else ''}")

        if not items:
            empty = tk.Label(self._inner_frame, text="No items",
                             font=("Helvetica", 12), fg=FG_DIM, bg=BG_PRIMARY)
            empty.pack(pady=40)
            return

        for item in items:
            self._render_item(item)

    def _render_item(self, item: ClipItem):
        bg = ACCENT_BG if item.pinned else BG_SECONDARY

        frame = tk.Frame(self._inner_frame, bg=bg, padx=12, pady=10,
                          highlightbackground=BORDER, highlightthickness=1)
        frame.pack(fill="x", pady=(0, 4))

        # Top row: category icon + timestamp + actions
        top = tk.Frame(frame, bg=bg)
        top.pack(fill="x")

        cat_icons = {"text": "📝", "link": "🔗", "image": "🖼"}
        icon = cat_icons.get(item.category, "📝")
        pin_icon = " 📌" if item.pinned else ""

        tk.Label(top, text=f"{icon}{pin_icon}", font=("Helvetica", 10),
                 fg=FG_SECONDARY, bg=bg).pack(side="left")

        # Time
        try:
            dt = datetime.fromisoformat(item.timestamp)
            time_str = dt.strftime("%H:%M · %b %d")
        except Exception:
            time_str = item.timestamp
        tk.Label(top, text=time_str, font=("Helvetica", 9),
                 fg=FG_DIM, bg=bg).pack(side="left", padx=(8, 0))

        # Action buttons
        btn_cfg = dict(font=("Helvetica", 9), bg=bg, bd=0,
                        activebackground=BG_TERTIARY, cursor="hand2", padx=4)

        tk.Button(top, text="✕", fg=RED, command=lambda i=item: self._delete(i),
                  **btn_cfg).pack(side="right")
        tk.Button(top, text="📌" if not item.pinned else "Unpin",
                  fg=PIN_COLOR, command=lambda i=item: self._pin(i),
                  **btn_cfg).pack(side="right")
        tk.Button(top, text="Copy", fg=ACCENT,
                  command=lambda i=item: self._copy(i),
                  **btn_cfg).pack(side="right")

        # Content preview (max 4 lines)
        preview = item.content[:500]
        lines = preview.split("\n")[:4]
        if len(lines) == 4 or len(item.content) > 500:
            lines.append("…")
        preview_text = "\n".join(lines)

        fg = LINK_COLOR if item.category == "link" else FG_PRIMARY
        content_label = tk.Label(frame, text=preview_text, font=("Menlo", 10),
                                  fg=fg, bg=bg, anchor="w", justify="left",
                                  wraplength=600)
        content_label.pack(fill="x", pady=(6, 0))

        # Click to copy
        for widget in [frame, content_label]:
            widget.bind("<Button-1>", lambda _, i=item: self._copy(i))
            widget.configure(cursor="hand2")

    # ── Actions ────────────────────────────────────────────────────────────

    def _copy(self, item: ClipItem):
        self._monitoring = False  # Temporarily pause to avoid re-adding
        self.root.clipboard_clear()
        self.root.clipboard_append(item.content)
        self._last_clipboard = item.content
        # Flash status
        old = self._status_var.get()
        self._status_var.set("✓ Copied!")
        self._status_label.configure(foreground=ACCENT)
        self.root.after(1000, lambda: (
            self._status_var.set(old),
            setattr(self, '_monitoring', True)
        ))

    def _pin(self, item: ClipItem):
        self.store.toggle_pin(item)
        self._refresh_list()

    def _delete(self, item: ClipItem):
        self.store.delete(item)
        self._refresh_list()

    def _clear_all(self):
        count = len([it for it in self.store.items if not it.pinned])
        if count == 0:
            return
        if messagebox.askyesno("Clear History",
                                f"Delete {count} unpinned items?",
                                parent=self.root):
            self.store.clear_unpinned()
            self._refresh_list()

    def _export(self):
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export Clipboard History",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Text", "*.txt")],
        )
        if not path:
            return
        try:
            if path.endswith(".txt"):
                self.store.export_txt(path)
            else:
                self.store.export_json(path)
            self._status_var.set(f"✓ Exported {len(self.store.items)} items")
            self.root.after(2000, lambda: self._status_var.set(
                "● Monitoring" if self._monitoring else "○ Paused"))
        except Exception as e:
            messagebox.showerror("Export Error", str(e), parent=self.root)

    # ── Run ────────────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()


# ── Entry Point ────────────────────────────────────────────────────────────────

def main():
    app = ClipboardManagerApp()
    app.run()


if __name__ == "__main__":
    main()
