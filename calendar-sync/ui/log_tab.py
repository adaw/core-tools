"""Change log viewer tab."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

from config import Config
from ui.theme import COLORS, FONTS


class LogTab(ttk.Frame):
    """Tab displaying sync change log."""

    def __init__(self, parent, config: Config):
        super().__init__(parent)
        self.config = config
        self._build_ui()
        self._load_history()

    def _build_ui(self):
        # Header
        header = ttk.Frame(self)
        header.pack(fill='x', padx=16, pady=(16, 8))

        ttk.Label(header, text="Sync History", style='Heading.TLabel').pack(side='left')

        btn_frame = ttk.Frame(header)
        btn_frame.pack(side='right')

        ttk.Button(btn_frame, text="Export Log", command=self._export_log).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Clear All", style='Danger.TButton',
                   command=self._clear_log).pack(side='left')

        # Filter
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill='x', padx=16, pady=(0, 8))

        ttk.Label(filter_frame, text="Filter:", style='Secondary.TLabel').pack(side='left')
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add('write', lambda *_: self._apply_filter())
        ttk.Entry(filter_frame, textvariable=self.filter_var, width=30).pack(side='left', padx=5)

        self.action_filter = tk.StringVar(value='all')
        for text, val in [("All", "all"), ("Added", "added"), ("Updated", "updated"),
                          ("Deleted", "deleted"), ("Conflicts", "conflict")]:
            ttk.Radiobutton(filter_frame, text=text, variable=self.action_filter,
                             value=val, command=self._apply_filter).pack(side='left', padx=3)

        # Treeview
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill='both', expand=True, padx=16, pady=(0, 8))

        columns = ('timestamp', 'action', 'event', 'source', 'target', 'details')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode='browse')
        self.tree.heading('timestamp', text='Time')
        self.tree.heading('action', text='Action')
        self.tree.heading('event', text='Event')
        self.tree.heading('source', text='Source')
        self.tree.heading('target', text='Target')
        self.tree.heading('details', text='Details')

        self.tree.column('timestamp', width=150, minwidth=120)
        self.tree.column('action', width=80, minwidth=60)
        self.tree.column('event', width=200, minwidth=120)
        self.tree.column('source', width=120, minwidth=80)
        self.tree.column('target', width=120, minwidth=80)
        self.tree.column('details', width=200, minwidth=100)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Summary
        self.summary_label = ttk.Label(self, text="", style='Secondary.TLabel')
        self.summary_label.pack(padx=16, pady=(0, 16), anchor='w')

        # Tag colors for actions
        self.tree.tag_configure('added', foreground=COLORS['success'])
        self.tree.tag_configure('updated', foreground=COLORS['warning'])
        self.tree.tag_configure('deleted', foreground=COLORS['error'])
        self.tree.tag_configure('conflict', foreground='#ff6688')
        self.tree.tag_configure('skipped', foreground=COLORS['text_dim'])

    def _load_history(self):
        entries = self.config.get('log_entries', [])
        for entry in entries:
            self._insert_entry(entry)
        self._update_summary()

    def _insert_entry(self, entry: dict, apply_filter: bool = False):
        action = entry.get('action', '?')
        values = (
            entry.get('timestamp', '')[:19].replace('T', ' '),
            self._action_icon(action),
            entry.get('event_summary', ''),
            entry.get('source', ''),
            entry.get('target', ''),
            entry.get('details', ''),
        )

        if apply_filter:
            if not self._matches_filter(entry):
                return

        self.tree.insert('', 0, values=values, tags=(action,))

    def _action_icon(self, action: str) -> str:
        icons = {
            'added': '➕ Added',
            'updated': '✏️ Updated',
            'deleted': '🗑 Deleted',
            'conflict': '⚠️ Conflict',
            'skipped': '⏭ Skipped',
        }
        return icons.get(action, action)

    def add_change(self, change):
        """Add a new change from sync engine."""
        entry = change.to_dict() if hasattr(change, 'to_dict') else change
        self._insert_entry(entry)
        self._update_summary()

    def _apply_filter(self):
        self.tree.delete(*self.tree.get_children())
        entries = self.config.get('log_entries', [])
        for entry in entries:
            if self._matches_filter(entry):
                self._insert_entry(entry)
        self._update_summary()

    def _matches_filter(self, entry: dict) -> bool:
        af = self.action_filter.get()
        if af != 'all' and entry.get('action') != af:
            return False
        text_filter = self.filter_var.get().strip().lower()
        if text_filter:
            searchable = ' '.join(str(v) for v in entry.values()).lower()
            if text_filter not in searchable:
                return False
        return True

    def _update_summary(self):
        count = len(self.tree.get_children())
        total = len(self.config.get('log_entries', []))
        self.summary_label.configure(text=f"Showing {count} of {total} entries")

    def _clear_log(self):
        if messagebox.askyesno("Clear Log", "Clear all log entries?"):
            self.config.clear_logs()
            self.tree.delete(*self.tree.get_children())
            self._update_summary()

    def _export_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return

        entries = self.config.get('log_entries', [])
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write("Timestamp,Action,Event,Source,Target,Details\n")
                for e in entries:
                    row = ','.join(f'"{e.get(k, "")}"' for k in
                                   ['timestamp', 'action', 'event_summary', 'source', 'target', 'details'])
                    f.write(row + '\n')
            messagebox.showinfo("Exported", f"Log exported to {path}")
        except OSError as e:
            messagebox.showerror("Error", f"Failed to export: {e}")
