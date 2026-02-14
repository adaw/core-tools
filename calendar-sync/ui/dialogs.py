"""Modal dialogs for Calendar Sync."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional

from ui.theme import COLORS, FONTS


class BaseDialog(tk.Toplevel):
    """Base dark-themed dialog."""

    def __init__(self, parent, title: str, width: int = 450, height: int = 350):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=COLORS['bg'])
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result = None

        # Center on parent
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        self.geometry(f"+{px}+{py}")

    def ok(self):
        self.grab_release()
        self.destroy()

    def cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


class AddSourceDialog(BaseDialog):
    """Dialog to add a new calendar source."""

    def __init__(self, parent):
        super().__init__(parent, "Add Calendar Source", 500, 420)

        main = ttk.Frame(self)
        main.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main, text="Source Type:", style='Heading.TLabel').pack(anchor='w', pady=(0, 5))

        self.source_type = tk.StringVar(value='ics_file')
        types = [
            ('Local ICS File', 'ics_file'),
            ('Google Calendar', 'google'),
            ('Outlook / Exchange', 'outlook'),
            ('CalDAV (Apple, Nextcloud, etc.)', 'caldav'),
        ]
        for text, val in types:
            ttk.Radiobutton(main, text=text, variable=self.source_type,
                            value=val, command=self._update_fields).pack(anchor='w', pady=2)

        ttk.Separator(main, orient='horizontal').pack(fill='x', pady=10)

        self.fields_frame = ttk.Frame(main)
        self.fields_frame.pack(fill='both', expand=True)

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side='right', padx=(5, 0))
        ttk.Button(btn_frame, text="Add", style='Accent.TButton',
                   command=self._on_add).pack(side='right')

        self._entries = {}
        self._update_fields()

    def _clear_fields(self):
        for w in self.fields_frame.winfo_children():
            w.destroy()
        self._entries = {}

    def _add_field(self, label: str, key: str, browse: bool = False, show: str = ""):
        row = ttk.Frame(self.fields_frame)
        row.pack(fill='x', pady=3)
        ttk.Label(row, text=label, width=18, anchor='w').pack(side='left')
        entry = ttk.Entry(row, show=show)
        entry.pack(side='left', fill='x', expand=True)
        if browse:
            def _browse():
                path = filedialog.askopenfilename(
                    filetypes=[("ICS files", "*.ics"), ("All files", "*.*")]
                )
                if path:
                    entry.delete(0, 'end')
                    entry.insert(0, path)
            ttk.Button(row, text="Browse", command=_browse).pack(side='left', padx=(5, 0))
        self._entries[key] = entry

    def _update_fields(self):
        self._clear_fields()
        st = self.source_type.get()

        self._add_field("Name:", "name")

        if st == 'ics_file':
            self._add_field("File Path:", "file_path", browse=True)
        elif st == 'google':
            self._add_field("Credentials JSON:", "credentials_file", browse=True)
            self._add_field("Calendar ID:", "calendar_id")
            self._entries['calendar_id'].insert(0, 'primary')
        elif st == 'outlook':
            self._add_field("Client ID:", "client_id")
            self._add_field("Tenant ID:", "tenant_id")
            self._entries['tenant_id'].insert(0, 'common')
        elif st == 'caldav':
            self._add_field("Server URL:", "url")
            self._add_field("Username:", "username")
            self._add_field("Password:", "password", show="•")
            self._add_field("Calendar Name:", "calendar_name")

    def _on_add(self):
        name = self._entries.get('name')
        if not name or not name.get().strip():
            messagebox.showwarning("Missing Name", "Please enter a name for this source.")
            return

        config = {}
        for key, entry in self._entries.items():
            if key != 'name':
                config[key] = entry.get().strip()

        self.result = {
            'type': self.source_type.get(),
            'name': name.get().strip(),
            'config': config,
        }
        self.ok()


class ConflictDialog(BaseDialog):
    """Dialog to manually resolve a sync conflict."""

    def __init__(self, parent, source_event, target_event):
        super().__init__(parent, "Resolve Conflict", 600, 450)

        main = ttk.Frame(self)
        main.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main, text="Conflicting Event", style='Heading.TLabel').pack(anchor='w')
        ttk.Label(main, text=source_event.summary, style='Accent.TLabel',
                  font=FONTS['heading']).pack(anchor='w', pady=(0, 10))

        # Side by side
        cols = ttk.Frame(main)
        cols.pack(fill='both', expand=True)
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)

        # Source
        src_frame = ttk.LabelFrame(cols, text="Source Version")
        src_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        self._show_event(src_frame, source_event)

        # Target
        tgt_frame = ttk.LabelFrame(cols, text="Target Version")
        tgt_frame.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
        self._show_event(tgt_frame, target_event)

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(15, 0))
        ttk.Button(btn_frame, text="Keep Source", style='Accent.TButton',
                   command=lambda: self._choose(True)).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Keep Target",
                   command=lambda: self._choose(False)).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Skip", command=self.cancel).pack(side='right')

    def _show_event(self, parent, event):
        fields = [
            ("Summary", event.summary),
            ("Start", str(event.dtstart or "N/A")),
            ("End", str(event.dtend or "N/A")),
            ("Location", event.location or "—"),
            ("Modified", str(event.last_modified or "N/A")),
        ]
        for label, value in fields:
            row = ttk.Frame(parent)
            row.pack(fill='x', padx=8, pady=2)
            ttk.Label(row, text=f"{label}:", font=FONTS['small'],
                      foreground=COLORS['text_secondary']).pack(anchor='w')
            ttk.Label(row, text=value, font=FONTS['small'],
                      wraplength=220).pack(anchor='w')

    def _choose(self, use_source: bool):
        self.result = use_source
        self.ok()


class ImportExportDialog(BaseDialog):
    """Dialog for ICS import/export."""

    def __init__(self, parent, mode: str = "import"):
        self.mode = mode
        title = "Import ICS" if mode == "import" else "Export ICS"
        super().__init__(parent, title, 450, 200)

        main = ttk.Frame(self)
        main.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main, text=f"{'Select file to import:' if mode == 'import' else 'Export to file:'}",
                  style='Heading.TLabel').pack(anchor='w', pady=(0, 10))

        row = ttk.Frame(main)
        row.pack(fill='x')
        self.path_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.path_var).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text="Browse", command=self._browse).pack(side='left', padx=(5, 0))

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(20, 0))
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side='right', padx=(5, 0))
        action = "Import" if mode == "import" else "Export"
        ttk.Button(btn_frame, text=action, style='Accent.TButton',
                   command=self._on_ok).pack(side='right')

    def _browse(self):
        if self.mode == "import":
            path = filedialog.askopenfilename(
                filetypes=[("ICS files", "*.ics"), ("All files", "*.*")]
            )
        else:
            path = filedialog.asksaveasfilename(
                defaultextension=".ics",
                filetypes=[("ICS files", "*.ics"), ("All files", "*.*")]
            )
        if path:
            self.path_var.set(path)

    def _on_ok(self):
        path = self.path_var.get().strip()
        if not path:
            messagebox.showwarning("No File", "Please select a file.")
            return
        self.result = path
        self.ok()
