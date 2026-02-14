#!/usr/bin/env python3
"""
CORE Batch File Renamer
Bulk file renaming tool with regex support, preview, and undo.
© CORE SYSTEMS — https://core.cz
"""

import os
import re
import sys
import json
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional

# ─── Constants ────────────────────────────────────────────────────────────────

APP_NAME = "CORE Batch Renamer"
APP_VERSION = "1.0.0"
BRAND_GREEN = "#00ff88"
BRAND_GREEN_DIM = "#00cc6a"
BRAND_GREEN_DARK = "#00994d"
BG_DARK = "#1a1a2e"
BG_PANEL = "#16213e"
BG_INPUT = "#0f3460"
BG_LIST = "#1a1a2e"
FG_TEXT = "#e0e0e0"
FG_DIM = "#8888aa"
FG_ERROR = "#ff4466"
FG_ADDED = "#00ff88"
FG_REMOVED = "#ff6644"
FONT_FAMILY = "Helvetica"
FONT_MONO = "Menlo" if sys.platform == "darwin" else "Consolas"


# ─── Rename Engine ────────────────────────────────────────────────────────────

class RenameRule:
    """Represents a single rename operation."""

    def __init__(self, mode: str = "find_replace", **kwargs):
        self.mode = mode
        self.params = kwargs

    def apply(self, filename: str, index: int, total: int) -> str:
        name, ext = os.path.splitext(filename)

        if self.mode == "find_replace":
            find = self.params.get("find", "")
            replace = self.params.get("replace", "")
            use_regex = self.params.get("use_regex", False)
            if not find:
                return filename
            if use_regex:
                try:
                    new_name = re.sub(find, replace, name)
                except re.error:
                    return filename
            else:
                new_name = name.replace(find, replace)
            return new_name + ext

        elif self.mode == "numbering":
            start = self.params.get("start", 1)
            padding = self.params.get("padding", 3)
            prefix = self.params.get("prefix", "")
            suffix = self.params.get("suffix", "")
            num = str(start + index).zfill(padding)
            return f"{prefix}{num}{suffix}{ext}"

        elif self.mode == "add_date":
            fmt = self.params.get("format", "%Y-%m-%d")
            position = self.params.get("position", "prefix")
            separator = self.params.get("separator", "_")
            date_str = datetime.now().strftime(fmt)
            if position == "prefix":
                return f"{date_str}{separator}{name}{ext}"
            else:
                return f"{name}{separator}{date_str}{ext}"

        elif self.mode == "change_ext":
            new_ext = self.params.get("new_ext", "")
            if new_ext and not new_ext.startswith("."):
                new_ext = "." + new_ext
            return name + new_ext

        elif self.mode == "case":
            case_type = self.params.get("case_type", "lower")
            if case_type == "lower":
                return name.lower() + ext
            elif case_type == "upper":
                return name.upper() + ext
            elif case_type == "title":
                return name.title() + ext
            return filename

        elif self.mode == "regex_replace":
            pattern = self.params.get("pattern", "")
            replacement = self.params.get("replacement", "")
            apply_to = self.params.get("apply_to", "name")
            if not pattern:
                return filename
            try:
                if apply_to == "full":
                    return re.sub(pattern, replacement, filename)
                else:
                    new_name = re.sub(pattern, replacement, name)
                    return new_name + ext
            except re.error:
                return filename

        return filename


class RenameEngine:
    """Manages file list, previews, and undo history."""

    def __init__(self):
        self.files: List[str] = []  # full paths
        self.history: List[List[Tuple[str, str]]] = []  # undo stack

    def add_files(self, paths: List[str]):
        for p in paths:
            p = p.strip().strip("'\"")
            if p and os.path.isfile(p) and p not in self.files:
                self.files.append(p)

    def add_folder(self, folder: str):
        if os.path.isdir(folder):
            for f in sorted(os.listdir(folder)):
                fp = os.path.join(folder, f)
                if os.path.isfile(fp) and fp not in self.files:
                    self.files.append(fp)

    def remove_files(self, indices: List[int]):
        for i in sorted(indices, reverse=True):
            if 0 <= i < len(self.files):
                self.files.pop(i)

    def clear_files(self):
        self.files.clear()

    def preview(self, rule: RenameRule) -> List[Tuple[str, str, str]]:
        """Returns list of (old_path, old_name, new_name)."""
        results = []
        total = len(self.files)
        for i, fp in enumerate(self.files):
            old_name = os.path.basename(fp)
            new_name = rule.apply(old_name, i, total)
            results.append((fp, old_name, new_name))
        return results

    def execute(self, rule: RenameRule) -> Tuple[int, List[str]]:
        """Execute rename. Returns (count, errors)."""
        preview = self.preview(rule)
        batch = []
        errors = []
        renamed_count = 0

        for fp, old_name, new_name in preview:
            if old_name == new_name:
                continue
            dir_path = os.path.dirname(fp)
            new_path = os.path.join(dir_path, new_name)
            if os.path.exists(new_path) and fp != new_path:
                errors.append(f"Target exists: {new_name}")
                continue
            batch.append((fp, new_path))

        # Execute
        done = []
        for old_path, new_path in batch:
            try:
                os.rename(old_path, new_path)
                done.append((old_path, new_path))
                renamed_count += 1
            except OSError as e:
                errors.append(f"Error: {os.path.basename(old_path)} → {e}")

        if done:
            self.history.append(done)
            # Update internal file list
            for old_path, new_path in done:
                idx = self.files.index(old_path)
                self.files[idx] = new_path

        return renamed_count, errors

    def undo(self) -> Tuple[int, List[str]]:
        """Undo last batch rename."""
        if not self.history:
            return 0, ["Nothing to undo"]

        batch = self.history.pop()
        undone = 0
        errors = []

        for old_path, new_path in reversed(batch):
            try:
                os.rename(new_path, old_path)
                idx = self.files.index(new_path)
                self.files[idx] = old_path
                undone += 1
            except (OSError, ValueError) as e:
                errors.append(str(e))

        return undone, errors

    @property
    def can_undo(self) -> bool:
        return len(self.history) > 0


# ─── GUI ──────────────────────────────────────────────────────────────────────

class CoreStyle:
    """Dark theme styling helper."""

    @staticmethod
    def configure(root):
        style = ttk.Style(root)
        style.theme_use("clam")

        style.configure(".", background=BG_DARK, foreground=FG_TEXT,
                        font=(FONT_FAMILY, 12))
        style.configure("TFrame", background=BG_DARK)
        style.configure("TLabel", background=BG_DARK, foreground=FG_TEXT,
                        font=(FONT_FAMILY, 12))
        style.configure("TButton", background=BG_INPUT, foreground=FG_TEXT,
                        font=(FONT_FAMILY, 11, "bold"), padding=(12, 6))
        style.map("TButton",
                  background=[("active", BRAND_GREEN_DARK), ("pressed", BRAND_GREEN_DIM)])

        style.configure("Accent.TButton", background=BRAND_GREEN_DARK,
                        foreground="#000000", font=(FONT_FAMILY, 11, "bold"),
                        padding=(16, 8))
        style.map("Accent.TButton",
                  background=[("active", BRAND_GREEN), ("pressed", BRAND_GREEN_DIM)])

        style.configure("Danger.TButton", background="#662222",
                        foreground="#ff4466", font=(FONT_FAMILY, 11, "bold"),
                        padding=(12, 6))
        style.map("Danger.TButton",
                  background=[("active", "#883333")])

        style.configure("TEntry", fieldbackground=BG_INPUT, foreground=FG_TEXT,
                        insertcolor=FG_TEXT, font=(FONT_MONO, 12))

        style.configure("TCheckbutton", background=BG_DARK, foreground=FG_TEXT,
                        font=(FONT_FAMILY, 11))
        style.map("TCheckbutton", background=[("active", BG_DARK)])

        style.configure("TRadiobutton", background=BG_DARK, foreground=FG_TEXT,
                        font=(FONT_FAMILY, 11))
        style.map("TRadiobutton", background=[("active", BG_DARK)])

        style.configure("TCombobox", fieldbackground=BG_INPUT, foreground=FG_TEXT,
                        font=(FONT_FAMILY, 11))

        style.configure("TLabelframe", background=BG_DARK, foreground=BRAND_GREEN,
                        font=(FONT_FAMILY, 11, "bold"))
        style.configure("TLabelframe.Label", background=BG_DARK,
                        foreground=BRAND_GREEN, font=(FONT_FAMILY, 11, "bold"))

        style.configure("Treeview", background=BG_LIST, foreground=FG_TEXT,
                        fieldbackground=BG_LIST, font=(FONT_MONO, 11),
                        rowheight=26)
        style.configure("Treeview.Heading", background=BG_PANEL,
                        foreground=BRAND_GREEN, font=(FONT_FAMILY, 11, "bold"))
        style.map("Treeview", background=[("selected", BG_INPUT)])

        style.configure("TNotebook", background=BG_DARK)
        style.configure("TNotebook.Tab", background=BG_PANEL, foreground=FG_DIM,
                        font=(FONT_FAMILY, 11), padding=(14, 6))
        style.map("TNotebook.Tab",
                  background=[("selected", BG_DARK)],
                  foreground=[("selected", BRAND_GREEN)])

        root.configure(bg=BG_DARK)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.engine = RenameEngine()

        self.root.title(APP_NAME)
        self.root.geometry("960x720")
        self.root.minsize(800, 600)

        CoreStyle.configure(self.root)

        # ─── Variables ────────────────────────────────────────────────
        self.var_find = tk.StringVar()
        self.var_replace = tk.StringVar()
        self.var_regex = tk.BooleanVar(value=False)
        self.var_num_start = tk.StringVar(value="1")
        self.var_num_padding = tk.StringVar(value="3")
        self.var_num_prefix = tk.StringVar()
        self.var_num_suffix = tk.StringVar()
        self.var_date_fmt = tk.StringVar(value="%Y-%m-%d")
        self.var_date_pos = tk.StringVar(value="prefix")
        self.var_date_sep = tk.StringVar(value="_")
        self.var_ext = tk.StringVar()
        self.var_case = tk.StringVar(value="lower")
        self.var_regex_pattern = tk.StringVar()
        self.var_regex_repl = tk.StringVar()
        self.var_regex_scope = tk.StringVar(value="name")

        self._build_ui()
        self._setup_dnd()

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=BG_PANEL, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        title = tk.Label(header, text="⬡ CORE BATCH RENAMER",
                         font=(FONT_FAMILY, 16, "bold"),
                         fg=BRAND_GREEN, bg=BG_PANEL)
        title.pack(side=tk.LEFT, padx=16)

        ver = tk.Label(header, text=f"v{APP_VERSION}",
                       font=(FONT_FAMILY, 10), fg=FG_DIM, bg=BG_PANEL)
        ver.pack(side=tk.LEFT)

        # Main paned
        main = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Left: controls
        left = ttk.Frame(main)
        main.add(left, weight=1)

        # File buttons
        btn_frame = ttk.Frame(left)
        btn_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(btn_frame, text="📁 Add Files", command=self._add_files).pack(
            side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_frame, text="📂 Add Folder", command=self._add_folder).pack(
            side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_frame, text="✕ Clear", style="Danger.TButton",
                   command=self._clear_files).pack(side=tk.LEFT)

        # File count
        self.lbl_count = tk.Label(left, text="0 files loaded",
                                  font=(FONT_FAMILY, 10), fg=FG_DIM, bg=BG_DARK)
        self.lbl_count.pack(anchor=tk.W, pady=(0, 4))

        # Notebook with rename modes
        notebook = ttk.Notebook(left)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # Tab: Find & Replace
        tab_fr = ttk.Frame(notebook)
        notebook.add(tab_fr, text="Find & Replace")
        self._build_find_replace(tab_fr)

        # Tab: Numbering
        tab_num = ttk.Frame(notebook)
        notebook.add(tab_num, text="Numbering")
        self._build_numbering(tab_num)

        # Tab: Date
        tab_date = ttk.Frame(notebook)
        notebook.add(tab_date, text="Date Stamp")
        self._build_date(tab_date)

        # Tab: Extension
        tab_ext = ttk.Frame(notebook)
        notebook.add(tab_ext, text="Extension")
        self._build_extension(tab_ext)

        # Tab: Case
        tab_case = ttk.Frame(notebook)
        notebook.add(tab_case, text="Case")
        self._build_case(tab_case)

        # Tab: Regex
        tab_regex = ttk.Frame(notebook)
        notebook.add(tab_regex, text="Regex")
        self._build_regex(tab_regex)

        self.notebook = notebook

        # Action buttons
        action_frame = ttk.Frame(left)
        action_frame.pack(fill=tk.X, pady=(0, 4))

        ttk.Button(action_frame, text="👁 Preview", command=self._preview).pack(
            side=tk.LEFT, padx=(0, 4))
        ttk.Button(action_frame, text="✓ RENAME", style="Accent.TButton",
                   command=self._execute).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(action_frame, text="↩ Undo", command=self._undo).pack(
            side=tk.LEFT)

        # Right: preview tree
        right = ttk.Frame(main)
        main.add(right, weight=2)

        ttk.Label(right, text="Preview", font=(FONT_FAMILY, 12, "bold"),
                  foreground=BRAND_GREEN).pack(anchor=tk.W, pady=(0, 4))

        tree_frame = ttk.Frame(right)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=("old", "new"),
                                 show="headings", selectmode="extended")
        self.tree.heading("old", text="Current Name")
        self.tree.heading("new", text="New Name")
        self.tree.column("old", width=250)
        self.tree.column("new", width=250)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status bar
        self.status = tk.Label(self.root, text="Ready — drop files or use Add Files",
                               font=(FONT_FAMILY, 10), fg=FG_DIM, bg=BG_PANEL,
                               anchor=tk.W, padx=12, pady=4)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

    def _build_find_replace(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill=tk.X, padx=12, pady=12)

        ttk.Label(f, text="Find:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(f, textvariable=self.var_find, width=30).grid(
            row=0, column=1, sticky=tk.EW, pady=4, padx=(8, 0))

        ttk.Label(f, text="Replace:").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(f, textvariable=self.var_replace, width=30).grid(
            row=1, column=1, sticky=tk.EW, pady=4, padx=(8, 0))

        ttk.Checkbutton(f, text="Use regex", variable=self.var_regex).grid(
            row=2, column=1, sticky=tk.W, pady=4, padx=(8, 0))

        f.columnconfigure(1, weight=1)

    def _build_numbering(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill=tk.X, padx=12, pady=12)

        ttk.Label(f, text="Prefix:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(f, textvariable=self.var_num_prefix, width=20).grid(
            row=0, column=1, sticky=tk.EW, pady=4, padx=(8, 0))

        ttk.Label(f, text="Suffix:").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(f, textvariable=self.var_num_suffix, width=20).grid(
            row=1, column=1, sticky=tk.EW, pady=4, padx=(8, 0))

        ttk.Label(f, text="Start #:").grid(row=2, column=0, sticky=tk.W, pady=4)
        ttk.Entry(f, textvariable=self.var_num_start, width=8).grid(
            row=2, column=1, sticky=tk.W, pady=4, padx=(8, 0))

        ttk.Label(f, text="Padding:").grid(row=3, column=0, sticky=tk.W, pady=4)
        ttk.Entry(f, textvariable=self.var_num_padding, width=8).grid(
            row=3, column=1, sticky=tk.W, pady=4, padx=(8, 0))

        f.columnconfigure(1, weight=1)

    def _build_date(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill=tk.X, padx=12, pady=12)

        ttk.Label(f, text="Format:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(f, textvariable=self.var_date_fmt, width=20).grid(
            row=0, column=1, sticky=tk.EW, pady=4, padx=(8, 0))

        ttk.Label(f, text="Position:").grid(row=1, column=0, sticky=tk.W, pady=4)
        pos_frame = ttk.Frame(f)
        pos_frame.grid(row=1, column=1, sticky=tk.W, pady=4, padx=(8, 0))
        ttk.Radiobutton(pos_frame, text="Prefix", variable=self.var_date_pos,
                        value="prefix").pack(side=tk.LEFT)
        ttk.Radiobutton(pos_frame, text="Suffix", variable=self.var_date_pos,
                        value="suffix").pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(f, text="Separator:").grid(row=2, column=0, sticky=tk.W, pady=4)
        ttk.Entry(f, textvariable=self.var_date_sep, width=8).grid(
            row=2, column=1, sticky=tk.W, pady=4, padx=(8, 0))

        f.columnconfigure(1, weight=1)

    def _build_extension(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill=tk.X, padx=12, pady=12)

        ttk.Label(f, text="New extension:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(f, textvariable=self.var_ext, width=12).grid(
            row=0, column=1, sticky=tk.W, pady=4, padx=(8, 0))
        ttk.Label(f, text="e.g. .txt, .jpg, .png",
                  foreground=FG_DIM).grid(row=1, column=1, sticky=tk.W, padx=(8, 0))

    def _build_case(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill=tk.X, padx=12, pady=12)

        for val, label in [("lower", "lowercase"), ("upper", "UPPERCASE"),
                           ("title", "Title Case")]:
            ttk.Radiobutton(f, text=label, variable=self.var_case,
                            value=val).pack(anchor=tk.W, pady=2)

    def _build_regex(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill=tk.X, padx=12, pady=12)

        ttk.Label(f, text="Pattern:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(f, textvariable=self.var_regex_pattern, width=30).grid(
            row=0, column=1, sticky=tk.EW, pady=4, padx=(8, 0))

        ttk.Label(f, text="Replace:").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(f, textvariable=self.var_regex_repl, width=30).grid(
            row=1, column=1, sticky=tk.EW, pady=4, padx=(8, 0))

        ttk.Label(f, text="Apply to:").grid(row=2, column=0, sticky=tk.W, pady=4)
        scope_frame = ttk.Frame(f)
        scope_frame.grid(row=2, column=1, sticky=tk.W, pady=4, padx=(8, 0))
        ttk.Radiobutton(scope_frame, text="Name only", variable=self.var_regex_scope,
                        value="name").pack(side=tk.LEFT)
        ttk.Radiobutton(scope_frame, text="Full filename", variable=self.var_regex_scope,
                        value="full").pack(side=tk.LEFT, padx=(12, 0))

        f.columnconfigure(1, weight=1)

    def _setup_dnd(self):
        """Setup drag and drop via TkDND if available, otherwise skip."""
        try:
            self.root.tk.eval('package require tkdnd')
            # TkDND available
            from tkinterdnd2 import DND_FILES, TkinterDnD
        except Exception:
            pass  # DnD not available, use file dialog

    def _get_current_rule(self) -> RenameRule:
        tab_idx = self.notebook.index(self.notebook.select())

        if tab_idx == 0:  # Find & Replace
            return RenameRule("find_replace",
                              find=self.var_find.get(),
                              replace=self.var_replace.get(),
                              use_regex=self.var_regex.get())
        elif tab_idx == 1:  # Numbering
            try:
                start = int(self.var_num_start.get())
            except ValueError:
                start = 1
            try:
                padding = int(self.var_num_padding.get())
            except ValueError:
                padding = 3
            return RenameRule("numbering",
                              start=start, padding=padding,
                              prefix=self.var_num_prefix.get(),
                              suffix=self.var_num_suffix.get())
        elif tab_idx == 2:  # Date
            return RenameRule("add_date",
                              format=self.var_date_fmt.get(),
                              position=self.var_date_pos.get(),
                              separator=self.var_date_sep.get())
        elif tab_idx == 3:  # Extension
            return RenameRule("change_ext", new_ext=self.var_ext.get())
        elif tab_idx == 4:  # Case
            return RenameRule("case", case_type=self.var_case.get())
        elif tab_idx == 5:  # Regex
            return RenameRule("regex_replace",
                              pattern=self.var_regex_pattern.get(),
                              replacement=self.var_regex_repl.get(),
                              apply_to=self.var_regex_scope.get())

        return RenameRule()

    def _update_file_count(self):
        n = len(self.engine.files)
        self.lbl_count.config(text=f"{n} file{'s' if n != 1 else ''} loaded")

    def _add_files(self):
        paths = filedialog.askopenfilenames(title="Select files to rename")
        if paths:
            self.engine.add_files(list(paths))
            self._update_file_count()
            self._preview()

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select folder")
        if folder:
            self.engine.add_folder(folder)
            self._update_file_count()
            self._preview()

    def _clear_files(self):
        self.engine.clear_files()
        self._update_file_count()
        self.tree.delete(*self.tree.get_children())
        self.status.config(text="Cleared all files")

    def _preview(self):
        self.tree.delete(*self.tree.get_children())

        if not self.engine.files:
            self.status.config(text="No files loaded")
            return

        rule = self._get_current_rule()
        results = self.engine.preview(rule)

        for fp, old_name, new_name in results:
            tag = "changed" if old_name != new_name else "unchanged"
            self.tree.insert("", tk.END, values=(old_name, new_name), tags=(tag,))

        self.tree.tag_configure("changed", foreground=FG_ADDED)
        self.tree.tag_configure("unchanged", foreground=FG_DIM)

        changed = sum(1 for _, o, n in results if o != n)
        self.status.config(text=f"Preview: {changed} of {len(results)} files will be renamed")

    def _execute(self):
        if not self.engine.files:
            messagebox.showwarning("No Files", "Add files first.")
            return

        rule = self._get_current_rule()
        preview = self.engine.preview(rule)
        changed = sum(1 for _, o, n in preview if o != n)

        if changed == 0:
            messagebox.showinfo("Nothing to do", "No files would be renamed with current settings.")
            return

        if not messagebox.askyesno("Confirm Rename",
                                   f"Rename {changed} file(s)?\n\nThis can be undone."):
            return

        count, errors = self.engine.execute(rule)

        if errors:
            messagebox.showwarning("Rename Complete",
                                   f"Renamed {count} files.\n\nErrors:\n" + "\n".join(errors[:10]))
        else:
            self.status.config(text=f"✓ Renamed {count} files successfully")

        self._preview()
        self._update_file_count()

    def _undo(self):
        if not self.engine.can_undo:
            messagebox.showinfo("Undo", "Nothing to undo.")
            return

        count, errors = self.engine.undo()
        if errors:
            messagebox.showwarning("Undo", f"Undone {count} renames.\nErrors: {', '.join(errors[:5])}")
        else:
            self.status.config(text=f"↩ Undone {count} renames")

        self._preview()
        self._update_file_count()


def main():
    root = tk.Tk()

    # Set icon if available
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
    if os.path.exists(icon_path):
        try:
            img = tk.PhotoImage(file=icon_path)
            root.iconphoto(True, img)
        except Exception:
            pass

    app = App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
