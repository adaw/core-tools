"""Sync configuration and execution tab."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timezone

from config import Config
from ui.theme import COLORS, FONTS
from sync.engine import SyncEngine, SyncDirection
from sync.conflict import ConflictStrategy, ConflictResolver
from sync.dedup import DedupStrategy
from providers import PROVIDER_TYPES


class SyncTab(ttk.Frame):
    """Tab for configuring and running sync operations."""

    def __init__(self, parent, config: Config, sources_tab, log_callback):
        super().__init__(parent)
        self.config = config
        self.sources_tab = sources_tab
        self.log_callback = log_callback
        self._scheduler_id = None
        self._running = False
        self._build_ui()

    def _build_ui(self):
        # --- Sync Pair Configuration ---
        pair_frame = ttk.LabelFrame(self, text="Sync Configuration")
        pair_frame.pack(fill='x', padx=16, pady=(16, 8))

        # Source & Target selection
        row1 = ttk.Frame(pair_frame)
        row1.pack(fill='x', padx=12, pady=(8, 4))

        ttk.Label(row1, text="Source:", width=12, anchor='w').pack(side='left')
        self.source_var = tk.StringVar()
        self.source_combo = ttk.Combobox(row1, textvariable=self.source_var,
                                          state='readonly', width=30)
        self.source_combo.pack(side='left', padx=(0, 15))

        ttk.Label(row1, text="Target:", width=12, anchor='w').pack(side='left')
        self.target_var = tk.StringVar()
        self.target_combo = ttk.Combobox(row1, textvariable=self.target_var,
                                          state='readonly', width=30)
        self.target_combo.pack(side='left')

        ttk.Button(row1, text="↻ Refresh", command=self._refresh_sources).pack(side='left', padx=(10, 0))

        # Direction
        row2 = ttk.Frame(pair_frame)
        row2.pack(fill='x', padx=12, pady=4)

        ttk.Label(row2, text="Direction:", width=12, anchor='w').pack(side='left')
        self.direction_var = tk.StringVar(value='two_way')
        ttk.Radiobutton(row2, text="Two-way ↔", variable=self.direction_var,
                         value='two_way').pack(side='left', padx=(0, 15))
        ttk.Radiobutton(row2, text="One-way →", variable=self.direction_var,
                         value='one_way').pack(side='left')

        # Conflict resolution
        row3 = ttk.Frame(pair_frame)
        row3.pack(fill='x', padx=12, pady=4)

        ttk.Label(row3, text="Conflicts:", width=12, anchor='w').pack(side='left')
        self.conflict_var = tk.StringVar(value=self.config.get('conflict_resolution', 'newer_wins'))
        conflicts = [
            ('Newer Wins', 'newer_wins'),
            ('Keep Both', 'keep_both'),
            ('Source Wins', 'source_wins'),
            ('Target Wins', 'target_wins'),
            ('Manual', 'manual'),
        ]
        for text, val in conflicts:
            ttk.Radiobutton(row3, text=text, variable=self.conflict_var,
                             value=val).pack(side='left', padx=(0, 10))

        # Dedup strategy
        row4 = ttk.Frame(pair_frame)
        row4.pack(fill='x', padx=12, pady=(4, 8))

        ttk.Label(row4, text="Dedup:", width=12, anchor='w').pack(side='left')
        self.dedup_var = tk.StringVar(value=self.config.get('dedup_strategy', 'uid'))
        dedups = [
            ('UID Match', 'uid'),
            ('Summary + Time', 'summary_time'),
            ('Fuzzy Match', 'fuzzy'),
        ]
        for text, val in dedups:
            ttk.Radiobutton(row4, text=text, variable=self.dedup_var,
                             value=val).pack(side='left', padx=(0, 10))

        # --- Scheduling ---
        sched_frame = ttk.LabelFrame(self, text="Auto Sync Schedule")
        sched_frame.pack(fill='x', padx=16, pady=8)

        srow = ttk.Frame(sched_frame)
        srow.pack(fill='x', padx=12, pady=8)

        ttk.Label(srow, text="Auto sync every:", anchor='w').pack(side='left')
        self.schedule_var = tk.IntVar(value=self.config.get('schedule_minutes', 0))
        self.schedule_spin = ttk.Spinbox(srow, from_=0, to=1440,
                                          textvariable=self.schedule_var, width=6)
        self.schedule_spin.pack(side='left', padx=5)
        ttk.Label(srow, text="minutes (0 = disabled)", style='Secondary.TLabel').pack(side='left')

        self.schedule_btn = ttk.Button(srow, text="Start Schedule",
                                        command=self._toggle_schedule)
        self.schedule_btn.pack(side='right')

        self.schedule_status = ttk.Label(srow, text="Scheduler: Off",
                                          style='Secondary.TLabel')
        self.schedule_status.pack(side='right', padx=10)

        # --- Action Buttons ---
        action_frame = ttk.Frame(self)
        action_frame.pack(fill='x', padx=16, pady=8)

        self.sync_btn = ttk.Button(action_frame, text="▶  Sync Now",
                                    style='Accent.TButton', command=self._sync_now)
        self.sync_btn.pack(side='left', padx=(0, 10))

        self.stop_btn = ttk.Button(action_frame, text="⏹  Stop",
                                    style='Danger.TButton', command=self._stop_sync,
                                    state='disabled')
        self.stop_btn.pack(side='left')

        # --- Progress ---
        prog_frame = ttk.Frame(self)
        prog_frame.pack(fill='x', padx=16, pady=(8, 4))

        self.progress = ttk.Progressbar(prog_frame, mode='indeterminate')
        self.progress.pack(fill='x')

        self.status_label = ttk.Label(self, text="Ready.", style='Secondary.TLabel')
        self.status_label.pack(padx=16, anchor='w')

        # --- Output ---
        out_frame = ttk.LabelFrame(self, text="Sync Output")
        out_frame.pack(fill='both', expand=True, padx=16, pady=(8, 16))

        self.output = tk.Text(out_frame, height=10, wrap='word',
                               bg=COLORS['input_bg'], fg=COLORS['text'],
                               font=FONTS['mono_small'], insertbackground=COLORS['accent'],
                               relief='flat', borderwidth=0, state='disabled')
        scrollbar = ttk.Scrollbar(out_frame, orient='vertical', command=self.output.yview)
        self.output.configure(yscrollcommand=scrollbar.set)
        self.output.pack(side='left', fill='both', expand=True, padx=(8, 0), pady=8)
        scrollbar.pack(side='right', fill='y', pady=8)

        self._refresh_sources()

    def _refresh_sources(self):
        sources = self.sources_tab.get_sources()
        names = [s.get('name', 'Unnamed') for s in sources]
        self.source_combo['values'] = names
        self.target_combo['values'] = names
        if names and not self.source_var.get():
            self.source_var.set(names[0] if len(names) > 0 else '')
            self.target_var.set(names[1] if len(names) > 1 else '')

    def _log(self, msg: str):
        self.output.configure(state='normal')
        self.output.insert('end', msg + '\n')
        self.output.see('end')
        self.output.configure(state='disabled')

    def _set_status(self, text: str):
        self.status_label.configure(text=text)

    def _get_provider(self, name: str):
        sources = self.sources_tab.get_sources()
        for src in sources:
            if src.get('name') == name:
                provider_cls = PROVIDER_TYPES.get(src['type'])
                if provider_cls:
                    return provider_cls(src['name'], src.get('config', {}))
        return None

    def _sync_now(self):
        src_name = self.source_var.get()
        tgt_name = self.target_var.get()

        if not src_name or not tgt_name:
            messagebox.showwarning("Select Sources", "Please select both source and target.")
            return
        if src_name == tgt_name:
            messagebox.showwarning("Same Source", "Source and target must be different.")
            return

        self._running = True
        self.sync_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.progress.start(15)
        self._set_status("Syncing...")

        # Save preferences
        self.config.set('conflict_resolution', self.conflict_var.get())
        self.config.set('dedup_strategy', self.dedup_var.get())

        def run():
            try:
                source = self._get_provider(src_name)
                target = self._get_provider(tgt_name)

                if not source or not target:
                    self.after(0, lambda: self._log("❌ Could not create providers."))
                    return

                self.after(0, lambda: self._log(f"Connecting to {src_name}..."))
                if not source.connect():
                    self.after(0, lambda: self._log(f"❌ Failed to connect to {src_name}"))
                    return

                self.after(0, lambda: self._log(f"Connecting to {tgt_name}..."))
                if not target.connect():
                    self.after(0, lambda: self._log(f"❌ Failed to connect to {tgt_name}"))
                    source.disconnect()
                    return

                direction = SyncDirection(self.direction_var.get())
                conflict = ConflictStrategy(self.conflict_var.get())
                dedup = DedupStrategy(self.dedup_var.get())

                engine = SyncEngine(
                    source=source,
                    target=target,
                    direction=direction,
                    conflict_strategy=conflict,
                    dedup_strategy=dedup,
                    progress_callback=lambda msg: self.after(0, lambda m=msg: self._log(m)),
                )

                result = engine.sync()

                # Log changes
                for change in result.changes:
                    entry = change.to_dict()
                    self.config.add_log_entry(entry)
                    self.after(0, lambda c=change: self.log_callback(c))

                summary = result.summary()
                self.after(0, lambda: self._log(f"\n✅ Sync complete: {summary}"))
                self.after(0, lambda: self._set_status(f"Done: {summary}"))

                source.disconnect()
                target.disconnect()

            except Exception as e:
                self.after(0, lambda: self._log(f"\n❌ Error: {e}"))
                self.after(0, lambda: self._set_status(f"Error: {e}"))
            finally:
                self._running = False
                self.after(0, lambda: self.progress.stop())
                self.after(0, lambda: self.sync_btn.configure(state='normal'))
                self.after(0, lambda: self.stop_btn.configure(state='disabled'))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def _stop_sync(self):
        self._running = False
        self._set_status("Stopped.")
        self.progress.stop()
        self.sync_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')

    def _toggle_schedule(self):
        if self._scheduler_id:
            # Stop scheduler
            self.after_cancel(self._scheduler_id)
            self._scheduler_id = None
            self.schedule_btn.configure(text="Start Schedule")
            self.schedule_status.configure(text="Scheduler: Off")
            self.config.set('schedule_minutes', 0)
            self._log("⏹ Scheduler stopped.")
        else:
            minutes = self.schedule_var.get()
            if minutes <= 0:
                messagebox.showinfo("Schedule", "Set minutes > 0 to enable scheduling.")
                return
            self.config.set('schedule_minutes', minutes)
            self.schedule_btn.configure(text="Stop Schedule")
            self.schedule_status.configure(text=f"Scheduler: Every {minutes} min")
            self._log(f"⏱ Scheduler started: every {minutes} minutes.")
            self._schedule_tick(minutes)

    def _schedule_tick(self, minutes: int):
        if not self._running:
            self._sync_now()
        self._scheduler_id = self.after(minutes * 60 * 1000, lambda: self._schedule_tick(minutes))
