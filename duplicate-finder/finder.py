#!/usr/bin/env python3
"""
CORE Duplicate File Finder — Find and remove duplicate files.
Part of CORE SYSTEMS tools suite.
"""

import hashlib
import json
import os
import platform
import queue
import stat
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Optional: perceptual hashing for images
try:
    from PIL import Image
    import imagehash
    HAS_PHASH = True
except ImportError:
    HAS_PHASH = False

# Optional: send2trash for safe deletion
try:
    from send2trash import send2trash
    HAS_TRASH = True
except ImportError:
    HAS_TRASH = False

VERSION = "1.0.0"
BRAND_GREEN = "#00ff88"
BRAND_DARK = "#1a1a2e"
BRAND_DARKER = "#16213e"
BRAND_PANEL = "#0f3460"
BRAND_TEXT = "#e0e0e0"
BRAND_DIM = "#888888"
BRAND_RED = "#ff4466"
BRAND_YELLOW = "#ffcc00"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
CHUNK_SIZE = 65536  # 64KB for hashing


# ─── Scanning Engine ───────────────────────────────────────────────────────

class DuplicateScanner:
    """Multi-threaded duplicate file scanner with size pre-filter."""

    def __init__(self):
        self.cancel_flag = threading.Event()
        self.duplicates = []  # list of groups: [{"hash":..., "files": [path,...]}]
        self.stats = {"files_scanned": 0, "duplicates_found": 0, "wasted_bytes": 0}

    def cancel(self):
        self.cancel_flag.set()

    def scan(self, folders, method="sha256", min_size=0, max_size=0,
             extensions=None, date_from=None, date_to=None,
             phash_similar=False, phash_threshold=5,
             progress_cb=None, done_cb=None, workers=4):
        """Run scan in background thread."""
        self.cancel_flag.clear()
        self.duplicates = []
        self.stats = {"files_scanned": 0, "duplicates_found": 0, "wasted_bytes": 0}

        def _run():
            try:
                self._do_scan(folders, method, min_size, max_size,
                              extensions, date_from, date_to,
                              phash_similar, phash_threshold,
                              progress_cb, workers)
            except Exception as e:
                if progress_cb:
                    progress_cb(f"Error: {e}", -1, -1)
            finally:
                if done_cb:
                    done_cb(self.duplicates, self.stats)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t

    def _collect_files(self, folders, min_size, max_size, extensions, date_from, date_to, progress_cb):
        """Collect all files matching filters."""
        all_files = []
        for folder in folders:
            for root, dirs, files in os.walk(folder):
                if self.cancel_flag.is_set():
                    return []
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        st = os.stat(fpath)
                        if not stat.S_ISREG(st.st_mode):
                            continue
                        size = st.st_size
                        if size == 0:
                            continue
                        if min_size and size < min_size:
                            continue
                        if max_size and size > max_size:
                            continue
                        if extensions:
                            ext = os.path.splitext(fname)[1].lower()
                            if ext not in extensions:
                                continue
                        if date_from:
                            mtime = datetime.fromtimestamp(st.st_mtime)
                            if mtime < date_from:
                                continue
                        if date_to:
                            mtime = datetime.fromtimestamp(st.st_mtime)
                            if mtime > date_to:
                                continue
                        all_files.append((fpath, size, st.st_mtime))
                    except (OSError, PermissionError):
                        continue
        if progress_cb:
            progress_cb(f"Found {len(all_files)} files", 0, 1)
        return all_files

    def _do_scan(self, folders, method, min_size, max_size,
                 extensions, date_from, date_to,
                 phash_similar, phash_threshold,
                 progress_cb, workers):
        # Phase 1: collect files
        if progress_cb:
            progress_cb("Collecting files...", 0, 0)
        all_files = self._collect_files(folders, min_size, max_size, extensions, date_from, date_to, progress_cb)
        if not all_files or self.cancel_flag.is_set():
            return

        self.stats["files_scanned"] = len(all_files)

        # Phase 2: group by size (pre-filter)
        if progress_cb:
            progress_cb("Grouping by size...", 0, len(all_files))
        size_groups = defaultdict(list)
        for fpath, size, mtime in all_files:
            size_groups[size].append((fpath, mtime))
        # Keep only sizes with >1 file
        candidates = {s: fs for s, fs in size_groups.items() if len(fs) > 1}

        total_candidates = sum(len(fs) for fs in candidates.values())
        if progress_cb:
            progress_cb(f"{total_candidates} candidates in {len(candidates)} size groups", 0, total_candidates)

        if method == "size+name":
            self._match_size_name(candidates, progress_cb)
        elif phash_similar and HAS_PHASH:
            self._match_phash(candidates, phash_threshold, progress_cb, workers)
        else:
            self._match_hash(candidates, method, progress_cb, workers)

    def _match_size_name(self, candidates, progress_cb):
        """Match by size + filename."""
        groups = defaultdict(list)
        done = 0
        for size, files in candidates.items():
            for fpath, mtime in files:
                key = (size, os.path.basename(fpath).lower())
                groups[key].append(fpath)
                done += 1
                if progress_cb and done % 500 == 0:
                    progress_cb(f"Comparing names... {done}", done, done)

        self._build_results(groups, progress_cb)

    def _hash_file(self, fpath, method):
        """Hash a single file."""
        if self.cancel_flag.is_set():
            return None
        h = hashlib.new(method)
        try:
            with open(fpath, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except (OSError, PermissionError):
            return None

    def _match_hash(self, candidates, method, progress_cb, workers):
        """Match by full file hash, multi-threaded."""
        # First pass: hash first chunk only for quick elimination
        all_candidate_files = []
        for size, files in candidates.items():
            for fpath, mtime in files:
                all_candidate_files.append((fpath, size))

        total = len(all_candidate_files)
        done = [0]
        lock = threading.Lock()

        # Quick hash (first chunk)
        quick_groups = defaultdict(list)

        def quick_hash(item):
            fpath, size = item
            if self.cancel_flag.is_set():
                return
            try:
                h = hashlib.new(method)
                with open(fpath, "rb") as f:
                    chunk = f.read(CHUNK_SIZE)
                    h.update(chunk)
                key = (size, h.hexdigest())
                with lock:
                    quick_groups[key].append(fpath)
                    done[0] += 1
                    if progress_cb and done[0] % 100 == 0:
                        progress_cb(f"Quick hash... {done[0]}/{total}", done[0], total)
            except (OSError, PermissionError):
                pass

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(quick_hash, all_candidate_files))

        if self.cancel_flag.is_set():
            return

        # Full hash only for quick-hash collisions
        full_candidates = {k: v for k, v in quick_groups.items() if len(v) > 1}
        full_files = []
        for key, files in full_candidates.items():
            for f in files:
                full_files.append(f)

        if not full_files:
            self._build_results({}, progress_cb)
            return

        total2 = len(full_files)
        done[0] = 0
        hash_groups = defaultdict(list)

        def full_hash(fpath):
            if self.cancel_flag.is_set():
                return
            digest = self._hash_file(fpath, method)
            if digest:
                with lock:
                    hash_groups[digest].append(fpath)
                    done[0] += 1
                    if progress_cb and done[0] % 50 == 0:
                        progress_cb(f"Full hash... {done[0]}/{total2}", done[0], total2)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(full_hash, full_files))

        self._build_results(hash_groups, progress_cb)

    def _match_phash(self, candidates, threshold, progress_cb, workers):
        """Match images by perceptual hash."""
        image_files = []
        for size, files in candidates.items():
            for fpath, mtime in files:
                ext = os.path.splitext(fpath)[1].lower()
                if ext in IMAGE_EXTS:
                    image_files.append(fpath)

        if not image_files:
            self._build_results({}, progress_cb)
            return

        total = len(image_files)
        done = [0]
        lock = threading.Lock()
        hashes = []  # (fpath, phash)

        def compute_phash(fpath):
            if self.cancel_flag.is_set():
                return
            try:
                img = Image.open(fpath)
                h = imagehash.phash(img)
                with lock:
                    hashes.append((fpath, h))
                    done[0] += 1
                    if progress_cb and done[0] % 20 == 0:
                        progress_cb(f"Perceptual hash... {done[0]}/{total}", done[0], total)
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(compute_phash, image_files))

        # Group by similarity
        used = set()
        groups = defaultdict(list)
        gid = 0
        for i, (fp1, h1) in enumerate(hashes):
            if i in used:
                continue
            group = [fp1]
            used.add(i)
            for j in range(i + 1, len(hashes)):
                if j in used:
                    continue
                fp2, h2 = hashes[j]
                if h1 - h2 <= threshold:
                    group.append(fp2)
                    used.add(j)
            if len(group) > 1:
                groups[f"phash_group_{gid}"] = group
                gid += 1

        self._build_results(groups, progress_cb)

    def _build_results(self, groups, progress_cb):
        """Build final results from groups dict."""
        self.duplicates = []
        for key, files in groups.items():
            if len(files) > 1:
                # Calculate wasted space (all but one copy)
                try:
                    size = os.path.getsize(files[0])
                except OSError:
                    size = 0
                wasted = size * (len(files) - 1)
                self.stats["wasted_bytes"] += wasted
                self.stats["duplicates_found"] += len(files) - 1
                self.duplicates.append({
                    "key": str(key),
                    "files": sorted(files),
                    "size": size,
                    "count": len(files),
                    "wasted": wasted,
                })
        # Sort by wasted space descending
        self.duplicates.sort(key=lambda g: g["wasted"], reverse=True)
        if progress_cb:
            progress_cb("Done!", 1, 1)


# ─── GUI ───────────────────────────────────────────────────────────────────

class DuplicateFinderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"CORE Duplicate Finder v{VERSION}")
        self.root.geometry("1100x750")
        self.root.minsize(900, 600)
        self.root.configure(bg=BRAND_DARK)

        self.scanner = DuplicateScanner()
        self.folders = []
        self.scan_running = False
        self.results = []

        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=BRAND_DARK, foreground=BRAND_TEXT,
                         fieldbackground=BRAND_DARKER, borderwidth=0)
        style.configure("TFrame", background=BRAND_DARK)
        style.configure("TLabel", background=BRAND_DARK, foreground=BRAND_TEXT, font=("Helvetica", 11))
        style.configure("TButton", background=BRAND_PANEL, foreground=BRAND_GREEN,
                         font=("Helvetica", 11, "bold"), padding=8)
        style.map("TButton",
                   background=[("active", BRAND_GREEN), ("disabled", BRAND_DARKER)],
                   foreground=[("active", BRAND_DARK), ("disabled", BRAND_DIM)])
        style.configure("Accent.TButton", background=BRAND_GREEN, foreground=BRAND_DARK)
        style.map("Accent.TButton",
                   background=[("active", "#00cc66"), ("disabled", BRAND_DIM)])
        style.configure("Danger.TButton", background=BRAND_RED, foreground="#ffffff")
        style.map("Danger.TButton", background=[("active", "#cc3355")])
        style.configure("TCheckbutton", background=BRAND_DARK, foreground=BRAND_TEXT, font=("Helvetica", 10))
        style.configure("TRadiobutton", background=BRAND_DARK, foreground=BRAND_TEXT, font=("Helvetica", 10))
        style.configure("TCombobox", fieldbackground=BRAND_DARKER, foreground=BRAND_TEXT)
        style.configure("TEntry", fieldbackground=BRAND_DARKER, foreground=BRAND_TEXT)
        style.configure("TLabelframe", background=BRAND_DARK, foreground=BRAND_GREEN, font=("Helvetica", 11, "bold"))
        style.configure("TLabelframe.Label", background=BRAND_DARK, foreground=BRAND_GREEN)
        style.configure("Treeview", background=BRAND_DARKER, foreground=BRAND_TEXT,
                         fieldbackground=BRAND_DARKER, font=("Helvetica", 10), rowheight=24)
        style.configure("Treeview.Heading", background=BRAND_PANEL, foreground=BRAND_GREEN,
                         font=("Helvetica", 10, "bold"))
        style.map("Treeview", background=[("selected", BRAND_PANEL)],
                   foreground=[("selected", BRAND_GREEN)])

        style.configure("green.Horizontal.TProgressbar", troughcolor=BRAND_DARKER,
                         background=BRAND_GREEN, thickness=6)

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=BRAND_DARKER, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="⬡ CORE", font=("Helvetica", 18, "bold"),
                 fg=BRAND_GREEN, bg=BRAND_DARKER).pack(side="left", padx=15)
        tk.Label(header, text="DUPLICATE FINDER", font=("Helvetica", 14),
                 fg=BRAND_TEXT, bg=BRAND_DARKER).pack(side="left")
        tk.Label(header, text=f"v{VERSION}", font=("Helvetica", 10),
                 fg=BRAND_DIM, bg=BRAND_DARKER).pack(side="right", padx=15)

        # Main content
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=10, pady=5)

        # Top: folders + options
        top = ttk.Frame(main)
        top.pack(fill="x", pady=(0, 5))

        # Folders panel
        folder_frame = ttk.LabelFrame(top, text="Scan Folders")
        folder_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.folder_listbox = tk.Listbox(folder_frame, bg=BRAND_DARKER, fg=BRAND_TEXT,
                                          selectbackground=BRAND_PANEL, font=("Helvetica", 10),
                                          height=4, borderwidth=0, highlightthickness=0)
        self.folder_listbox.pack(fill="both", expand=True, padx=5, pady=5)

        btn_row = ttk.Frame(folder_frame)
        btn_row.pack(fill="x", padx=5, pady=(0, 5))
        ttk.Button(btn_row, text="+ Add Folder", command=self._add_folder).pack(side="left", padx=2)
        ttk.Button(btn_row, text="− Remove", command=self._remove_folder).pack(side="left", padx=2)

        # Options panel
        opts_frame = ttk.LabelFrame(top, text="Options")
        opts_frame.pack(side="right", fill="y", padx=(5, 0))

        self.method_var = tk.StringVar(value="sha256")
        r1 = ttk.Frame(opts_frame)
        r1.pack(fill="x", padx=5, pady=2)
        ttk.Label(r1, text="Method:").pack(side="left")
        for text, val in [("SHA-256", "sha256"), ("MD5", "md5"), ("Size+Name", "size+name")]:
            ttk.Radiobutton(r1, text=text, variable=self.method_var, value=val).pack(side="left", padx=3)

        self.phash_var = tk.BooleanVar(value=False)
        phash_state = "normal" if HAS_PHASH else "disabled"
        phash_text = "Perceptual hash (similar images)" if HAS_PHASH else "Perceptual hash (install Pillow + imagehash)"
        ttk.Checkbutton(opts_frame, text=phash_text, variable=self.phash_var,
                         state=phash_state).pack(fill="x", padx=5, pady=2)

        self.trash_var = tk.BooleanVar(value=True)
        trash_text = "Move to Trash" if HAS_TRASH else "Move to Trash (install send2trash)"
        trash_state = "normal" if HAS_TRASH else "disabled"
        ttk.Checkbutton(opts_frame, text=trash_text, variable=self.trash_var,
                         state=trash_state).pack(fill="x", padx=5, pady=2)

        self.dryrun_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts_frame, text="Dry Run (no actual deletion)", variable=self.dryrun_var).pack(fill="x", padx=5, pady=2)

        # Filters row
        filt = ttk.Frame(opts_frame)
        filt.pack(fill="x", padx=5, pady=2)
        ttk.Label(filt, text="Min size:").pack(side="left")
        self.min_size_var = tk.StringVar(value="")
        ttk.Entry(filt, textvariable=self.min_size_var, width=8).pack(side="left", padx=2)
        ttk.Label(filt, text="KB  Max:").pack(side="left")
        self.max_size_var = tk.StringVar(value="")
        ttk.Entry(filt, textvariable=self.max_size_var, width=8).pack(side="left", padx=2)
        ttk.Label(filt, text="KB").pack(side="left")

        filt2 = ttk.Frame(opts_frame)
        filt2.pack(fill="x", padx=5, pady=2)
        ttk.Label(filt2, text="Extensions:").pack(side="left")
        self.ext_var = tk.StringVar(value="")
        ttk.Entry(filt2, textvariable=self.ext_var, width=25).pack(side="left", padx=2)
        ttk.Label(filt2, text="(e.g. .jpg,.png)", foreground=BRAND_DIM).pack(side="left")

        # Scan button row
        scan_row = ttk.Frame(main)
        scan_row.pack(fill="x", pady=5)
        self.scan_btn = ttk.Button(scan_row, text="⬡ SCAN FOR DUPLICATES",
                                    style="Accent.TButton", command=self._start_scan)
        self.scan_btn.pack(side="left", padx=5)
        self.cancel_btn = ttk.Button(scan_row, text="Cancel", command=self._cancel_scan, state="disabled")
        self.cancel_btn.pack(side="left", padx=5)

        self.progress_label = ttk.Label(scan_row, text="Ready", foreground=BRAND_DIM)
        self.progress_label.pack(side="left", padx=10)

        self.progress_bar = ttk.Progressbar(scan_row, mode="determinate",
                                             style="green.Horizontal.TProgressbar", length=200)
        self.progress_bar.pack(side="right", padx=5)

        # Results tree
        result_frame = ttk.Frame(main)
        result_frame.pack(fill="both", expand=True)

        cols = ("status", "path", "size", "modified")
        self.tree = ttk.Treeview(result_frame, columns=cols, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="Group")
        self.tree.heading("status", text="✓")
        self.tree.heading("path", text="File Path")
        self.tree.heading("size", text="Size")
        self.tree.heading("modified", text="Modified")
        self.tree.column("#0", width=200, minwidth=100)
        self.tree.column("status", width=30, minwidth=30, anchor="center")
        self.tree.column("path", width=500, minwidth=200)
        self.tree.column("size", width=100, minwidth=80, anchor="e")
        self.tree.column("modified", width=150, minwidth=100)

        vsb = ttk.Scrollbar(result_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._toggle_item)

        # Tag for marked-for-deletion
        self.tree.tag_configure("delete", foreground=BRAND_RED)
        self.tree.tag_configure("keep", foreground=BRAND_GREEN)

        # Bottom action bar
        bottom = ttk.Frame(main)
        bottom.pack(fill="x", pady=5)

        self.stats_label = tk.Label(bottom, text="No results yet", font=("Helvetica", 11),
                                     fg=BRAND_DIM, bg=BRAND_DARK)
        self.stats_label.pack(side="left", padx=5)

        ttk.Button(bottom, text="Export Report", command=self._export_report).pack(side="right", padx=5)
        ttk.Button(bottom, text="DELETE SELECTED", style="Danger.TButton",
                    command=self._delete_selected).pack(side="right", padx=5)

        # Auto-select dropdown
        ttk.Label(bottom, text="Auto-select:").pack(side="right", padx=(10, 2))
        self.autoselect_var = tk.StringVar(value="keep_newest")
        autosel = ttk.Combobox(bottom, textvariable=self.autoselect_var, width=18, state="readonly",
                                values=["keep_newest", "keep_oldest", "keep_shortest_path", "select_none"])
        autosel.pack(side="right", padx=2)
        ttk.Button(bottom, text="Apply", command=self._auto_select).pack(side="right", padx=2)

        # Track which items are marked for deletion
        self.marked = set()  # set of tree item ids

    def _add_folder(self):
        d = filedialog.askdirectory(title="Select folder to scan")
        if d and d not in self.folders:
            self.folders.append(d)
            self.folder_listbox.insert("end", d)

    def _remove_folder(self):
        sel = self.folder_listbox.curselection()
        if sel:
            idx = sel[0]
            self.folders.pop(idx)
            self.folder_listbox.delete(idx)

    def _parse_size_kb(self, val):
        try:
            return int(val.strip()) * 1024 if val.strip() else 0
        except ValueError:
            return 0

    def _start_scan(self):
        if not self.folders:
            messagebox.showwarning("No folders", "Add at least one folder to scan.")
            return

        self.scan_running = True
        self.scan_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.tree.delete(*self.tree.get_children())
        self.marked.clear()

        min_sz = self._parse_size_kb(self.min_size_var.get())
        max_sz = self._parse_size_kb(self.max_size_var.get())
        exts = None
        if self.ext_var.get().strip():
            exts = set(e.strip().lower() if e.strip().startswith(".") else f".{e.strip().lower()}"
                       for e in self.ext_var.get().split(",") if e.strip())

        self.progress_queue = queue.Queue()

        def progress_cb(msg, current, total):
            self.progress_queue.put(("progress", msg, current, total))

        def done_cb(duplicates, stats):
            self.progress_queue.put(("done", duplicates, stats))

        self.scanner.scan(
            self.folders,
            method=self.method_var.get(),
            min_size=min_sz,
            max_size=max_sz,
            extensions=exts,
            phash_similar=self.phash_var.get(),
            progress_cb=progress_cb,
            done_cb=done_cb,
        )
        self._poll_progress()

    def _poll_progress(self):
        try:
            while True:
                item = self.progress_queue.get_nowait()
                if item[0] == "progress":
                    _, msg, current, total = item
                    self.progress_label.configure(text=msg)
                    if total > 0:
                        self.progress_bar.configure(maximum=total, value=current)
                elif item[0] == "done":
                    _, duplicates, stats = item
                    self._show_results(duplicates, stats)
                    self.scan_running = False
                    self.scan_btn.configure(state="normal")
                    self.cancel_btn.configure(state="disabled")
                    return
        except queue.Empty:
            pass
        if self.scan_running:
            self.root.after(100, self._poll_progress)

    def _cancel_scan(self):
        self.scanner.cancel()
        self.progress_label.configure(text="Cancelled")
        self.scan_running = False
        self.scan_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")

    def _format_size(self, size):
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def _show_results(self, duplicates, stats):
        self.results = duplicates
        self.tree.delete(*self.tree.get_children())
        self.marked.clear()

        for i, group in enumerate(duplicates):
            gid = self.tree.insert("", "end",
                                    text=f"Group {i + 1} — {group['count']} files × {self._format_size(group['size'])}",
                                    values=("", "", self._format_size(group['wasted']) + " wasted", ""),
                                    open=True)
            for fpath in group["files"]:
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M")
                except OSError:
                    mtime = "?"
                self.tree.insert(gid, "end", text="", values=("○", fpath, self._format_size(group["size"]), mtime),
                                  tags=("keep",))

        self.stats_label.configure(
            text=f"Scanned {stats['files_scanned']} files | "
                 f"{stats['duplicates_found']} duplicates in {len(duplicates)} groups | "
                 f"Potential savings: {self._format_size(stats['wasted_bytes'])}",
            fg=BRAND_GREEN
        )
        self.progress_label.configure(text="Scan complete")

    def _toggle_item(self, event):
        item = self.tree.identify_row(event.y)
        if not item or not self.tree.parent(item):
            return  # skip group headers
        if item in self.marked:
            self.marked.discard(item)
            self.tree.item(item, tags=("keep",))
            vals = list(self.tree.item(item, "values"))
            vals[0] = "○"
            self.tree.item(item, values=vals)
        else:
            self.marked.add(item)
            self.tree.item(item, tags=("delete",))
            vals = list(self.tree.item(item, "values"))
            vals[0] = "✕"
            self.tree.item(item, values=vals)

    def _auto_select(self):
        strategy = self.autoselect_var.get()
        self.marked.clear()

        for group_item in self.tree.get_children():
            children = self.tree.get_children(group_item)
            if len(children) < 2:
                continue

            file_info = []
            for child in children:
                vals = self.tree.item(child, "values")
                fpath = vals[1]
                try:
                    mtime = os.path.getmtime(fpath)
                except OSError:
                    mtime = 0
                file_info.append((child, fpath, mtime))

            if strategy == "select_none":
                keep_idx = -1  # keep all
            elif strategy == "keep_newest":
                keep_idx = max(range(len(file_info)), key=lambda i: file_info[i][2])
            elif strategy == "keep_oldest":
                keep_idx = min(range(len(file_info)), key=lambda i: file_info[i][2])
            elif strategy == "keep_shortest_path":
                keep_idx = min(range(len(file_info)), key=lambda i: len(file_info[i][1]))
            else:
                keep_idx = 0

            for i, (child, fpath, mtime) in enumerate(file_info):
                if strategy == "select_none" or i == keep_idx:
                    self.marked.discard(child)
                    self.tree.item(child, tags=("keep",))
                    vals = list(self.tree.item(child, "values"))
                    vals[0] = "○"
                    self.tree.item(child, values=vals)
                else:
                    self.marked.add(child)
                    self.tree.item(child, tags=("delete",))
                    vals = list(self.tree.item(child, "values"))
                    vals[0] = "✕"
                    self.tree.item(child, values=vals)

    def _delete_selected(self):
        if not self.marked:
            messagebox.showinfo("Nothing selected", "Double-click files to mark them for deletion, or use Auto-select.")
            return

        files = []
        for item in self.marked:
            vals = self.tree.item(item, "values")
            files.append(vals[1])

        total_size = sum(os.path.getsize(f) for f in files if os.path.exists(f))
        dry = self.dryrun_var.get()
        action = "DRY RUN — would delete" if dry else "Delete"
        method = "move to Trash" if (self.trash_var.get() and HAS_TRASH) else "permanently delete"

        if not dry:
            ok = messagebox.askyesno(
                "Confirm Deletion",
                f"{action} {len(files)} files ({self._format_size(total_size)})?\n"
                f"Method: {method}"
            )
            if not ok:
                return

        deleted = 0
        errors = []
        for fpath in files:
            try:
                if dry:
                    deleted += 1
                    continue
                if self.trash_var.get() and HAS_TRASH:
                    send2trash(fpath)
                else:
                    os.remove(fpath)
                deleted += 1
            except Exception as e:
                errors.append(f"{fpath}: {e}")

        # Remove deleted items from tree
        if not dry:
            for item in list(self.marked):
                self.tree.delete(item)
            self.marked.clear()

        msg = f"{'[DRY RUN] ' if dry else ''}Processed {deleted}/{len(files)} files."
        if errors:
            msg += f"\n{len(errors)} errors:\n" + "\n".join(errors[:5])
        messagebox.showinfo("Done", msg)

    def _export_report(self):
        if not self.results:
            messagebox.showinfo("No results", "Run a scan first.")
            return

        path = filedialog.asksaveasfilename(
            title="Export Report",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Text", "*.txt"), ("All", "*.*")]
        )
        if not path:
            return

        report = {
            "tool": "CORE Duplicate Finder",
            "version": VERSION,
            "timestamp": datetime.now().isoformat(),
            "folders": self.folders,
            "groups": self.results,
            "stats": self.scanner.stats,
        }

        if path.endswith(".txt"):
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"CORE Duplicate Finder Report — {report['timestamp']}\n")
                f.write(f"Folders: {', '.join(self.folders)}\n")
                f.write(f"Files scanned: {self.scanner.stats['files_scanned']}\n")
                f.write(f"Duplicates: {self.scanner.stats['duplicates_found']}\n")
                f.write(f"Wasted: {self._format_size(self.scanner.stats['wasted_bytes'])}\n\n")
                for i, g in enumerate(self.results):
                    f.write(f"--- Group {i + 1} ({self._format_size(g['size'])}) ---\n")
                    for fp in g["files"]:
                        f.write(f"  {fp}\n")
                    f.write("\n")
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

        messagebox.showinfo("Exported", f"Report saved to:\n{path}")


def main():
    root = tk.Tk()

    # Dark title bar on macOS
    if platform.system() == "Darwin":
        try:
            root.tk.call("tk::unsupported::MacWindowStyle", "style", root._w, "moveableModal", "")
        except tk.TclError:
            pass

    app = DuplicateFinderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
