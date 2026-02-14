"""Main application — Calendar Sync by CORE SYSTEMS."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

from config import Config
from ui.theme import apply_theme, branded_header, COLORS, FONTS
from ui.sources_tab import SourcesTab
from ui.sync_tab import SyncTab
from ui.log_tab import LogTab
from ui.dialogs import ImportExportDialog


class CalendarSyncApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.title("Calendar Sync — CORE SYSTEMS")
        self.config_mgr = Config()
        geometry = self.config_mgr.get('window_geometry', '1100x750')
        self.geometry(geometry)
        self.minsize(900, 600)

        # Apply dark theme
        apply_theme(self)

        # Icon (try to set)
        try:
            if sys.platform == 'darwin':
                pass  # macOS handles icons via .app bundle
            # Windows icon would go here
        except Exception:
            pass

        self._build_ui()

        # Save geometry on close
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def _build_ui(self):
        # Header
        header = branded_header(self)
        header.pack(fill='x')

        # Menu bar
        self._build_menu()

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        # Sources tab
        self.sources_tab = SourcesTab(self.notebook, self.config_mgr)
        self.notebook.add(self.sources_tab, text="  📂 Sources  ")

        # Log tab (create before sync tab since sync tab references it)
        self.log_tab = LogTab(self.notebook, self.config_mgr)

        # Sync tab
        self.sync_tab = SyncTab(self.notebook, self.config_mgr,
                                 self.sources_tab, self.log_tab.add_change)
        self.notebook.add(self.sync_tab, text="  🔄 Sync  ")

        # Log tab
        self.notebook.add(self.log_tab, text="  📋 Log  ")

        # Status bar
        self.status_bar = ttk.Frame(self, style='Surface.TFrame')
        self.status_bar.pack(fill='x', side='bottom')

        self.status_text = ttk.Label(self.status_bar, text="Ready",
                                      style='Surface.TLabel', font=FONTS['small'])
        self.status_text.pack(side='left', padx=12, pady=4)

        version_label = ttk.Label(self.status_bar, text="v1.0.0",
                                   style='Surface.TLabel', font=FONTS['small'],
                                   foreground=COLORS['text_dim'])
        version_label.pack(side='right', padx=12, pady=4)

    def _build_menu(self):
        menubar = tk.Menu(self, bg=COLORS['bg_secondary'], fg=COLORS['text'],
                          activebackground=COLORS['accent_bg'],
                          activeforeground=COLORS['accent'],
                          borderwidth=0)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0,
                            bg=COLORS['bg_secondary'], fg=COLORS['text'],
                            activebackground=COLORS['accent_bg'],
                            activeforeground=COLORS['accent'])
        file_menu.add_command(label="Import ICS...", command=self._import_ics)
        file_menu.add_command(label="Export ICS...", command=self._export_ics)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self._on_close,
                              accelerator="Cmd+Q" if sys.platform == 'darwin' else "Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0,
                            bg=COLORS['bg_secondary'], fg=COLORS['text'],
                            activebackground=COLORS['accent_bg'],
                            activeforeground=COLORS['accent'])
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menubar)

        # Keyboard shortcuts
        key = 'Command' if sys.platform == 'darwin' else 'Control'
        self.bind(f'<{key}-q>', lambda e: self._on_close())

    def _import_ics(self):
        dlg = ImportExportDialog(self, mode="import")
        self.wait_window(dlg)
        if dlg.result:
            path = dlg.result
            try:
                from providers.ics_file import ICSFileProvider
                provider = ICSFileProvider("import", {'file_path': path})
                if provider.connect():
                    events = provider.fetch_events()
                    provider.disconnect()
                    messagebox.showinfo("Import Complete",
                                        f"Imported {len(events)} events from:\n{path}")
                else:
                    messagebox.showerror("Import Failed", "Could not read the ICS file.")
            except Exception as e:
                messagebox.showerror("Import Error", str(e))

    def _export_ics(self):
        dlg = ImportExportDialog(self, mode="export")
        self.wait_window(dlg)
        if dlg.result:
            path = dlg.result
            try:
                from icalendar import Calendar
                cal = Calendar()
                cal.add('prodid', '-//CORE SYSTEMS//Calendar Sync//EN')
                cal.add('version', '2.0')

                # Export from first connected source
                sources = self.sources_tab.get_sources()
                if not sources:
                    messagebox.showwarning("No Sources", "Add a calendar source first.")
                    return

                from providers import PROVIDER_TYPES
                src = sources[0]
                provider_cls = PROVIDER_TYPES.get(src['type'])
                if not provider_cls:
                    messagebox.showerror("Error", "Unknown provider type.")
                    return

                provider = provider_cls(src['name'], src.get('config', {}))
                if not provider.connect():
                    messagebox.showerror("Error", f"Could not connect to {src['name']}.")
                    return

                events = provider.fetch_events()
                provider.disconnect()

                # Write combined ICS
                ics_content = ""
                for ev in events:
                    ics_content += ev.to_ical_string() + "\n"

                # Simple approach: write each event as separate VCALENDAR (valid ICS)
                # Better: combine into one
                from icalendar import Event as IEvent
                for ev in events:
                    iev = IEvent()
                    iev.add('uid', ev.uid)
                    iev.add('summary', ev.summary)
                    if ev.description:
                        iev.add('description', ev.description)
                    if ev.location:
                        iev.add('location', ev.location)
                    if ev.dtstart:
                        if ev.all_day:
                            iev.add('dtstart', ev.dtstart.date())
                        else:
                            iev.add('dtstart', ev.dtstart)
                    if ev.dtend:
                        if ev.all_day:
                            iev.add('dtend', ev.dtend.date())
                        else:
                            iev.add('dtend', ev.dtend)
                    cal.add_component(iev)

                Path(path).write_bytes(cal.to_ical())
                messagebox.showinfo("Export Complete",
                                    f"Exported {len(events)} events to:\n{path}")

            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def _show_about(self):
        messagebox.showinfo(
            "About Calendar Sync",
            "Calendar Sync v1.0.0\n\n"
            "Cross-platform calendar synchronization.\n\n"
            "Google Calendar • Outlook • CalDAV • ICS Files\n\n"
            "© CORE SYSTEMS\n"
            "Free & Open Source"
        )

    def _on_close(self):
        self.config_mgr.set('window_geometry', self.geometry())
        self.destroy()
