"""Sources management tab."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from config import Config
from ui.theme import COLORS, FONTS
from ui.dialogs import AddSourceDialog


class SourcesTab(ttk.Frame):
    """Tab for managing calendar sources."""

    def __init__(self, parent, config: Config):
        super().__init__(parent)
        self.config = config
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        # Header
        header = ttk.Frame(self)
        header.pack(fill='x', padx=16, pady=(16, 8))

        ttk.Label(header, text="Calendar Sources", style='Heading.TLabel').pack(side='left')

        btn_frame = ttk.Frame(header)
        btn_frame.pack(side='right')

        ttk.Button(btn_frame, text="+ Add Source", style='Accent.TButton',
                   command=self._add_source).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Remove", style='Danger.TButton',
                   command=self._remove_source).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Test Connection",
                   command=self._test_connection).pack(side='left')

        # Treeview
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill='both', expand=True, padx=16, pady=8)

        columns = ('name', 'type', 'details', 'status')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode='browse')
        self.tree.heading('name', text='Name')
        self.tree.heading('type', text='Type')
        self.tree.heading('details', text='Details')
        self.tree.heading('status', text='Status')

        self.tree.column('name', width=180, minwidth=120)
        self.tree.column('type', width=120, minwidth=80)
        self.tree.column('details', width=300, minwidth=150)
        self.tree.column('status', width=100, minwidth=80)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Info panel
        info = ttk.LabelFrame(self, text="Source Info")
        info.pack(fill='x', padx=16, pady=(8, 16))

        self.info_label = ttk.Label(info, text="Select a source to see details.",
                                    style='Secondary.TLabel', wraplength=600)
        self.info_label.pack(padx=12, pady=8)

        self.tree.bind('<<TreeviewSelect>>', self._on_select)

    def _refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        for src in self.config.get('sources', []):
            details = self._source_details(src)
            self.tree.insert('', 'end', values=(
                src.get('name', 'Unnamed'),
                self._type_label(src.get('type', '')),
                details,
                '—',
            ))

    def _type_label(self, t: str) -> str:
        labels = {
            'ics_file': '📄 ICS File',
            'google': '🔵 Google',
            'outlook': '🟦 Outlook',
            'caldav': '🟢 CalDAV',
        }
        return labels.get(t, t)

    def _source_details(self, src: dict) -> str:
        cfg = src.get('config', {})
        t = src.get('type', '')
        if t == 'ics_file':
            return cfg.get('file_path', '')
        elif t == 'google':
            return f"Calendar: {cfg.get('calendar_id', 'primary')}"
        elif t == 'outlook':
            return f"Tenant: {cfg.get('tenant_id', 'common')}"
        elif t == 'caldav':
            return cfg.get('url', '')
        return ''

    def _add_source(self):
        dlg = AddSourceDialog(self.winfo_toplevel())
        self.wait_window(dlg)
        if dlg.result:
            self.config.add_source(dlg.result)
            self._refresh_list()

    def _remove_source(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a source to remove.")
            return
        idx = self.tree.index(sel[0])
        name = self.tree.item(sel[0])['values'][0]
        if messagebox.askyesno("Remove Source", f"Remove '{name}'?"):
            self.config.remove_source(idx)
            self._refresh_list()

    def _test_connection(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a source to test.")
            return

        idx = self.tree.index(sel[0])
        sources = self.config.get('sources', [])
        if idx >= len(sources):
            return

        src = sources[idx]
        try:
            from providers import PROVIDER_TYPES
            provider_cls = PROVIDER_TYPES.get(src['type'])
            if not provider_cls:
                messagebox.showerror("Error", f"Unknown provider type: {src['type']}")
                return

            provider = provider_cls(src['name'], src.get('config', {}))
            if provider.connect():
                events = provider.fetch_events()
                provider.disconnect()
                self.tree.set(sel[0], 'status', f'✅ {len(events)} events')
                messagebox.showinfo("Success",
                                    f"Connected to '{src['name']}'.\nFound {len(events)} events.")
            else:
                self.tree.set(sel[0], 'status', '❌ Failed')
                messagebox.showerror("Failed", f"Could not connect to '{src['name']}'.")
        except Exception as e:
            self.tree.set(sel[0], 'status', '❌ Error')
            messagebox.showerror("Error", str(e))

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        sources = self.config.get('sources', [])
        if idx < len(sources):
            src = sources[idx]
            info = f"Type: {src.get('type', '?')}  |  Name: {src.get('name', '?')}\n"
            for k, v in src.get('config', {}).items():
                if k == 'password':
                    v = '••••••'
                info += f"  {k}: {v}\n"
            self.info_label.configure(text=info.strip())

    def get_sources(self) -> list[dict]:
        """Return configured sources for sync tab."""
        return self.config.get('sources', [])
