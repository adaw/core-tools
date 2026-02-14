#!/usr/bin/env python3
"""
CORE Media Converter — FFmpeg-based Video/Audio Converter
Part of CORE SYSTEMS tool suite.

A clean, modern GUI wrapper around FFmpeg for batch media conversion.
Supports drag & drop, multiple formats, quality presets, and progress tracking.
"""

import os
import sys
import re
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path
from tkinter import (
    Tk, Frame, Label, Button, Listbox, Scrollbar, StringVar, IntVar,
    OptionMenu, filedialog, messagebox, ttk, Canvas, HORIZONTAL,
    VERTICAL, BOTH, LEFT, RIGHT, TOP, BOTTOM, X, Y, END, NORMAL,
    DISABLED, WORD, N, S, E, W, NW, SE, NSEW, MULTIPLE, EXTENDED,
    SINGLE, BROWSE, PhotoImage
)

# ─── Constants ────────────────────────────────────────────────────────────────

APP_NAME = "CORE Media Converter"
APP_VERSION = "1.0.0"

# CORE SYSTEMS branding
COLOR_BG = "#1a1a2e"
COLOR_BG_SECONDARY = "#16213e"
COLOR_BG_INPUT = "#0f3460"
COLOR_ACCENT = "#00ff88"
COLOR_ACCENT_DIM = "#00cc6a"
COLOR_TEXT = "#e0e0e0"
COLOR_TEXT_DIM = "#888888"
COLOR_ERROR = "#ff4444"
COLOR_BORDER = "#2a2a4a"
COLOR_PROGRESS_BG = "#0a0a1a"
COLOR_ITEM_BG = "#1e1e3a"
COLOR_ITEM_HOVER = "#2a2a5a"
COLOR_REMOVE = "#cc3333"

# Supported formats
VIDEO_FORMATS = ["MP4", "MKV", "AVI", "MOV"]
AUDIO_FORMATS = ["MP3", "WAV", "FLAC", "AAC", "OGG"]
ALL_FORMATS = VIDEO_FORMATS + AUDIO_FORMATS

# Input extensions we accept
INPUT_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg",
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus", ".aiff", ".aif",
    ".ts", ".3gp", ".vob",
}

# Quality presets — maps (format_type, quality) -> ffmpeg args
QUALITY_PRESETS = {
    # Video presets (H.264 for MP4/MOV, native for MKV/AVI)
    ("video", "High"): {
        "MP4":  ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-c:a", "aac", "-b:a", "256k"],
        "MKV":  ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-c:a", "libvorbis", "-q:a", "7"],
        "AVI":  ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-c:a", "mp3", "-b:a", "256k"],
        "MOV":  ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-c:a", "aac", "-b:a", "256k"],
    },
    ("video", "Medium"): {
        "MP4":  ["-c:v", "libx264", "-crf", "23", "-preset", "medium", "-c:a", "aac", "-b:a", "192k"],
        "MKV":  ["-c:v", "libx264", "-crf", "23", "-preset", "medium", "-c:a", "libvorbis", "-q:a", "5"],
        "AVI":  ["-c:v", "libx264", "-crf", "23", "-preset", "medium", "-c:a", "mp3", "-b:a", "192k"],
        "MOV":  ["-c:v", "libx264", "-crf", "23", "-preset", "medium", "-c:a", "aac", "-b:a", "192k"],
    },
    ("video", "Low"): {
        "MP4":  ["-c:v", "libx264", "-crf", "28", "-preset", "fast", "-c:a", "aac", "-b:a", "128k"],
        "MKV":  ["-c:v", "libx264", "-crf", "28", "-preset", "fast", "-c:a", "libvorbis", "-q:a", "3"],
        "AVI":  ["-c:v", "libx264", "-crf", "28", "-preset", "fast", "-c:a", "mp3", "-b:a", "128k"],
        "MOV":  ["-c:v", "libx264", "-crf", "28", "-preset", "fast", "-c:a", "aac", "-b:a", "128k"],
    },
    # Audio presets
    ("audio", "High"): {
        "MP3":  ["-c:a", "libmp3lame", "-b:a", "320k"],
        "WAV":  ["-c:a", "pcm_s24le"],
        "FLAC": ["-c:a", "flac", "-compression_level", "8"],
        "AAC":  ["-c:a", "aac", "-b:a", "256k"],
        "OGG":  ["-c:a", "libvorbis", "-q:a", "8"],
    },
    ("audio", "Medium"): {
        "MP3":  ["-c:a", "libmp3lame", "-b:a", "192k"],
        "WAV":  ["-c:a", "pcm_s16le"],
        "FLAC": ["-c:a", "flac", "-compression_level", "5"],
        "AAC":  ["-c:a", "aac", "-b:a", "192k"],
        "OGG":  ["-c:a", "libvorbis", "-q:a", "5"],
    },
    ("audio", "Low"): {
        "MP3":  ["-c:a", "libmp3lame", "-b:a", "128k"],
        "WAV":  ["-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2"],
        "FLAC": ["-c:a", "flac", "-compression_level", "0"],
        "AAC":  ["-c:a", "aac", "-b:a", "128k"],
        "OGG":  ["-c:a", "libvorbis", "-q:a", "3"],
    },
}


# ─── Utilities ────────────────────────────────────────────────────────────────

def find_ffmpeg() -> str | None:
    """Find ffmpeg binary. Check bundled location first, then PATH."""
    # Check bundled (PyInstaller)
    if getattr(sys, '_MEIPASS', None):
        bundled = os.path.join(sys._MEIPASS, "ffmpeg")
        if sys.platform == "win32":
            bundled += ".exe"
        if os.path.isfile(bundled):
            return bundled

    # Check next to executable
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    local = os.path.join(app_dir, "ffmpeg")
    if sys.platform == "win32":
        local += ".exe"
    if os.path.isfile(local):
        return local

    # Check PATH
    return shutil.which("ffmpeg")


def find_ffprobe() -> str | None:
    """Find ffprobe binary."""
    if getattr(sys, '_MEIPASS', None):
        bundled = os.path.join(sys._MEIPASS, "ffprobe")
        if sys.platform == "win32":
            bundled += ".exe"
        if os.path.isfile(bundled):
            return bundled

    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    local = os.path.join(app_dir, "ffprobe")
    if sys.platform == "win32":
        local += ".exe"
    if os.path.isfile(local):
        return local

    return shutil.which("ffprobe")


def get_duration(filepath: str, ffprobe_path: str) -> float | None:
    """Get media duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [ffprobe_path, "-v", "quiet", "-print_format", "json",
             "-show_format", filepath],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:
        return None


def is_video_format(fmt: str) -> bool:
    return fmt.upper() in VIDEO_FORMATS


def is_audio_format(fmt: str) -> bool:
    return fmt.upper() in AUDIO_FORMATS


def format_time(seconds: float) -> str:
    """Format seconds to HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ─── File Item ────────────────────────────────────────────────────────────────

class FileItem:
    """Represents a queued file for conversion."""
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.size = os.path.getsize(filepath) if os.path.isfile(filepath) else 0
        self.duration: float | None = None
        self.status = "Queued"  # Queued, Converting, Done, Error
        self.progress = 0.0
        self.error_msg = ""
        self.output_path = ""


# ─── Custom Widgets ───────────────────────────────────────────────────────────

class FileListItem(Frame):
    """A single file row in the file list."""

    def __init__(self, parent, file_item: FileItem, on_remove=None, **kwargs):
        super().__init__(parent, bg=COLOR_ITEM_BG, padx=10, pady=8, **kwargs)
        self.file_item = file_item
        self.on_remove = on_remove

        # Filename
        name_frame = Frame(self, bg=COLOR_ITEM_BG)
        name_frame.pack(fill=X, expand=True)

        self.name_label = Label(
            name_frame, text=file_item.filename,
            bg=COLOR_ITEM_BG, fg=COLOR_TEXT,
            font=("Helvetica", 12, "bold"), anchor="w"
        )
        self.name_label.pack(side=LEFT, fill=X, expand=True)

        # Remove button
        self.remove_btn = Label(
            name_frame, text="✕", bg=COLOR_ITEM_BG, fg=COLOR_TEXT_DIM,
            font=("Helvetica", 14), cursor="hand2"
        )
        self.remove_btn.pack(side=RIGHT, padx=(10, 0))
        self.remove_btn.bind("<Button-1>", lambda e: self._on_remove())
        self.remove_btn.bind("<Enter>", lambda e: self.remove_btn.config(fg=COLOR_REMOVE))
        self.remove_btn.bind("<Leave>", lambda e: self.remove_btn.config(fg=COLOR_TEXT_DIM))

        # Info line
        info_parts = [format_size(file_item.size)]
        ext = Path(file_item.filepath).suffix.upper().lstrip(".")
        info_parts.append(ext)
        info_text = "  •  ".join(info_parts)

        self.info_label = Label(
            self, text=info_text,
            bg=COLOR_ITEM_BG, fg=COLOR_TEXT_DIM,
            font=("Helvetica", 10), anchor="w"
        )
        self.info_label.pack(fill=X, pady=(2, 0))

        # Status / Progress
        self.status_frame = Frame(self, bg=COLOR_ITEM_BG)
        self.status_frame.pack(fill=X, pady=(4, 0))

        self.status_label = Label(
            self.status_frame, text="Queued",
            bg=COLOR_ITEM_BG, fg=COLOR_TEXT_DIM,
            font=("Helvetica", 10), anchor="w"
        )
        self.status_label.pack(side=LEFT)

        # Progress bar (canvas-based for custom colors)
        self.progress_canvas = Canvas(
            self.status_frame, height=6, bg=COLOR_PROGRESS_BG,
            highlightthickness=0, bd=0
        )
        self.progress_canvas.pack(side=RIGHT, fill=X, expand=True, padx=(10, 0))
        self.progress_bar = self.progress_canvas.create_rectangle(
            0, 0, 0, 6, fill=COLOR_ACCENT, width=0
        )
        self.progress_canvas.bind("<Configure>", self._draw_progress)

    def _draw_progress(self, event=None):
        width = self.progress_canvas.winfo_width()
        fill_width = int(width * (self.file_item.progress / 100.0))
        self.progress_canvas.coords(self.progress_bar, 0, 0, fill_width, 6)

    def _on_remove(self):
        if self.on_remove:
            self.on_remove(self.file_item)

    def update_status(self):
        fi = self.file_item
        if fi.status == "Queued":
            self.status_label.config(text="Queued", fg=COLOR_TEXT_DIM)
        elif fi.status == "Converting":
            pct = f"{fi.progress:.0f}%"
            self.status_label.config(text=f"Converting… {pct}", fg=COLOR_ACCENT)
        elif fi.status == "Done":
            self.status_label.config(text="✓ Done", fg=COLOR_ACCENT)
            fi.progress = 100
        elif fi.status == "Error":
            self.status_label.config(text=f"✕ {fi.error_msg[:50]}", fg=COLOR_ERROR)
        self._draw_progress()


# ─── Main Application ────────────────────────────────────────────────────────

class MediaConverterApp:
    def __init__(self):
        self.root = Tk()
        self.root.title(APP_NAME)
        self.root.geometry("800x700")
        self.root.minsize(650, 550)
        self.root.configure(bg=COLOR_BG)

        # Try to set dark title bar on macOS
        try:
            self.root.tk.call("tk::unsupported::MacWindowStyle", "style",
                              self.root, "moveableModal", "")
        except Exception:
            pass

        # State
        self.files: list[FileItem] = []
        self.file_widgets: list[FileListItem] = []
        self.converting = False
        self.cancel_flag = False
        self.current_process: subprocess.Popen | None = None

        # FFmpeg
        self.ffmpeg_path = find_ffmpeg()
        self.ffprobe_path = find_ffprobe()

        # Variables
        self.output_format = StringVar(value="MP4")
        self.quality_preset = StringVar(value="Medium")
        self.output_dir = StringVar(value="")

        self._build_ui()
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        if not self.ffmpeg_path:
            self.root.after(500, lambda: messagebox.showwarning(
                "FFmpeg Not Found",
                "FFmpeg was not found on your system.\n\n"
                "Please install FFmpeg and ensure it's in your PATH:\n"
                "  • macOS: brew install ffmpeg\n"
                "  • Windows: choco install ffmpeg\n"
                "  • Linux: sudo apt install ffmpeg\n\n"
                "The converter will not work without FFmpeg."
            ))

    def _build_ui(self):
        root = self.root

        # ── Header ──
        header = Frame(root, bg=COLOR_BG, padx=20, pady=15)
        header.pack(fill=X)

        title_frame = Frame(header, bg=COLOR_BG)
        title_frame.pack(fill=X)

        Label(title_frame, text="◆", bg=COLOR_BG, fg=COLOR_ACCENT,
              font=("Helvetica", 20)).pack(side=LEFT, padx=(0, 8))
        Label(title_frame, text="CORE", bg=COLOR_BG, fg=COLOR_ACCENT,
              font=("Helvetica", 18, "bold")).pack(side=LEFT)
        Label(title_frame, text="Media Converter", bg=COLOR_BG, fg=COLOR_TEXT,
              font=("Helvetica", 18)).pack(side=LEFT, padx=(8, 0))
        Label(title_frame, text=f"v{APP_VERSION}", bg=COLOR_BG, fg=COLOR_TEXT_DIM,
              font=("Helvetica", 10)).pack(side=LEFT, padx=(10, 0), pady=(6, 0))

        # Separator
        Frame(root, bg=COLOR_BORDER, height=1).pack(fill=X)

        # ── Drop zone / File list ──
        self.list_container = Frame(root, bg=COLOR_BG, padx=20, pady=10)
        self.list_container.pack(fill=BOTH, expand=True)

        # Drop zone (shown when no files)
        self.drop_zone = Frame(self.list_container, bg=COLOR_BG_SECONDARY,
                               highlightbackground=COLOR_BORDER, highlightthickness=2,
                               padx=30, pady=40)

        Label(self.drop_zone, text="📂", bg=COLOR_BG_SECONDARY,
              font=("Helvetica", 36)).pack()
        Label(self.drop_zone, text="Drop files here or click to browse",
              bg=COLOR_BG_SECONDARY, fg=COLOR_TEXT,
              font=("Helvetica", 14)).pack(pady=(10, 5))
        Label(self.drop_zone, text="Supports: MP4, MKV, AVI, MOV, MP3, WAV, FLAC, AAC, OGG and more",
              bg=COLOR_BG_SECONDARY, fg=COLOR_TEXT_DIM,
              font=("Helvetica", 10)).pack()

        browse_btn = Label(self.drop_zone, text="  Browse Files  ",
                           bg=COLOR_ACCENT, fg=COLOR_BG,
                           font=("Helvetica", 12, "bold"),
                           cursor="hand2", padx=20, pady=8)
        browse_btn.pack(pady=(15, 0))
        browse_btn.bind("<Button-1>", lambda e: self._browse_files())
        browse_btn.bind("<Enter>", lambda e: browse_btn.config(bg=COLOR_ACCENT_DIM))
        browse_btn.bind("<Leave>", lambda e: browse_btn.config(bg=COLOR_ACCENT))

        self.drop_zone.pack(fill=BOTH, expand=True, pady=5)
        self.drop_zone.bind("<Button-1>", lambda e: self._browse_files())

        # Scrollable file list (hidden initially)
        self.file_list_frame = Frame(self.list_container, bg=COLOR_BG)
        self.file_scroll_canvas = Canvas(self.file_list_frame, bg=COLOR_BG,
                                         highlightthickness=0, bd=0)
        self.file_scroll_inner = Frame(self.file_scroll_canvas, bg=COLOR_BG)
        self.file_scroll_canvas.create_window((0, 0), window=self.file_scroll_inner,
                                               anchor=NW, tags="inner")

        scrollbar = Scrollbar(self.file_list_frame, orient=VERTICAL,
                              command=self.file_scroll_canvas.yview)
        self.file_scroll_canvas.configure(yscrollcommand=scrollbar.set)

        self.file_scroll_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.file_scroll_inner.bind("<Configure>", lambda e:
            self.file_scroll_canvas.configure(scrollregion=self.file_scroll_canvas.bbox("all")))
        self.file_scroll_canvas.bind("<Configure>", lambda e:
            self.file_scroll_canvas.itemconfig("inner", width=e.width))

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            self.file_scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.file_scroll_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ── File list toolbar ──
        self.toolbar = Frame(root, bg=COLOR_BG, padx=20, pady=5)

        add_btn = Label(self.toolbar, text="+ Add Files", bg=COLOR_BG_INPUT,
                        fg=COLOR_ACCENT, font=("Helvetica", 11),
                        cursor="hand2", padx=12, pady=4)
        add_btn.pack(side=LEFT)
        add_btn.bind("<Button-1>", lambda e: self._browse_files())

        clear_btn = Label(self.toolbar, text="Clear All", bg=COLOR_BG_INPUT,
                          fg=COLOR_TEXT_DIM, font=("Helvetica", 11),
                          cursor="hand2", padx=12, pady=4)
        clear_btn.pack(side=LEFT, padx=(10, 0))
        clear_btn.bind("<Button-1>", lambda e: self._clear_files())

        self.file_count_label = Label(self.toolbar, text="0 files",
                                       bg=COLOR_BG, fg=COLOR_TEXT_DIM,
                                       font=("Helvetica", 11))
        self.file_count_label.pack(side=RIGHT)

        # Separator
        Frame(root, bg=COLOR_BORDER, height=1).pack(fill=X)

        # ── Settings ──
        settings = Frame(root, bg=COLOR_BG_SECONDARY, padx=20, pady=12)
        settings.pack(fill=X)

        # Row 1: Format + Quality
        row1 = Frame(settings, bg=COLOR_BG_SECONDARY)
        row1.pack(fill=X)

        # Format
        Label(row1, text="Output Format", bg=COLOR_BG_SECONDARY,
              fg=COLOR_TEXT_DIM, font=("Helvetica", 10)).pack(side=LEFT)

        fmt_menu = OptionMenu(row1, self.output_format, *ALL_FORMATS)
        fmt_menu.config(bg=COLOR_BG_INPUT, fg=COLOR_TEXT, activebackground=COLOR_BG_INPUT,
                        activeforeground=COLOR_ACCENT, highlightthickness=0,
                        font=("Helvetica", 11), width=6, relief="flat")
        fmt_menu["menu"].config(bg=COLOR_BG_INPUT, fg=COLOR_TEXT,
                                activebackground=COLOR_ACCENT, activeforeground=COLOR_BG,
                                font=("Helvetica", 11))
        fmt_menu.pack(side=LEFT, padx=(8, 30))

        # Quality
        Label(row1, text="Quality", bg=COLOR_BG_SECONDARY,
              fg=COLOR_TEXT_DIM, font=("Helvetica", 10)).pack(side=LEFT)

        quality_menu = OptionMenu(row1, self.quality_preset, "High", "Medium", "Low")
        quality_menu.config(bg=COLOR_BG_INPUT, fg=COLOR_TEXT, activebackground=COLOR_BG_INPUT,
                            activeforeground=COLOR_ACCENT, highlightthickness=0,
                            font=("Helvetica", 11), width=8, relief="flat")
        quality_menu["menu"].config(bg=COLOR_BG_INPUT, fg=COLOR_TEXT,
                                    activebackground=COLOR_ACCENT, activeforeground=COLOR_BG,
                                    font=("Helvetica", 11))
        quality_menu.pack(side=LEFT, padx=(8, 30))

        # Output directory
        Label(row1, text="Output", bg=COLOR_BG_SECONDARY,
              fg=COLOR_TEXT_DIM, font=("Helvetica", 10)).pack(side=LEFT)

        self.output_dir_label = Label(
            row1, text="Same as source", bg=COLOR_BG_INPUT,
            fg=COLOR_TEXT, font=("Helvetica", 10),
            padx=10, pady=3, cursor="hand2", anchor="w"
        )
        self.output_dir_label.pack(side=LEFT, fill=X, expand=True, padx=(8, 0))
        self.output_dir_label.bind("<Button-1>", lambda e: self._choose_output_dir())

        # ── Bottom bar ──
        bottom = Frame(root, bg=COLOR_BG, padx=20, pady=12)
        bottom.pack(fill=X)

        # Convert button
        self.convert_btn = Label(
            bottom, text="  ▶  Convert  ", bg=COLOR_ACCENT, fg=COLOR_BG,
            font=("Helvetica", 14, "bold"), cursor="hand2", padx=25, pady=10
        )
        self.convert_btn.pack(side=RIGHT)
        self.convert_btn.bind("<Button-1>", lambda e: self._start_conversion())
        self.convert_btn.bind("<Enter>", lambda e: self.convert_btn.config(bg=COLOR_ACCENT_DIM))
        self.convert_btn.bind("<Leave>", lambda e: self.convert_btn.config(bg=COLOR_ACCENT))

        # Cancel button (hidden initially)
        self.cancel_btn = Label(
            bottom, text="  ■  Cancel  ", bg=COLOR_ERROR, fg=COLOR_TEXT,
            font=("Helvetica", 14, "bold"), cursor="hand2", padx=25, pady=10
        )
        self.cancel_btn.bind("<Button-1>", lambda e: self._cancel_conversion())

        # Overall progress
        self.overall_label = Label(bottom, text="", bg=COLOR_BG, fg=COLOR_TEXT_DIM,
                                    font=("Helvetica", 11))
        self.overall_label.pack(side=LEFT)

        # Status bar
        self.status_bar = Label(root, text=f"FFmpeg: {'Found ✓' if self.ffmpeg_path else 'Not found ✕'}",
                                bg=COLOR_BG_SECONDARY, fg=COLOR_TEXT_DIM if self.ffmpeg_path else COLOR_ERROR,
                                font=("Helvetica", 9), anchor="w", padx=20, pady=4)
        self.status_bar.pack(fill=X, side=BOTTOM)

        # Try to enable TkDND for drag & drop
        self._setup_dnd()

    def _setup_dnd(self):
        """Try to set up drag and drop using tkdnd if available."""
        try:
            self.root.tk.eval('package require tkdnd')
            # Register drop target
            self.root.tk.eval(f'''
                tkdnd::drop_target register {self.drop_zone} *
            ''')
            self.drop_zone.bind("<<Drop>>", self._on_drop)
        except Exception:
            # tkdnd not available — that's fine, we have the browse button
            pass

    def _on_drop(self, event):
        """Handle file drop."""
        data = event.data if hasattr(event, 'data') else ""
        # Parse dropped file paths
        paths = []
        if data.startswith("{"):
            # Tcl list format
            for item in re.findall(r'\{([^}]+)\}|(\S+)', data):
                path = item[0] or item[1]
                if path:
                    paths.append(path)
        else:
            paths = data.split()

        for p in paths:
            self._add_file(p.strip())

    def _browse_files(self):
        filetypes = [
            ("Media files", " ".join(f"*{ext}" for ext in INPUT_EXTENSIONS)),
            ("Video files", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm"),
            ("Audio files", "*.mp3 *.wav *.flac *.aac *.ogg *.wma *.m4a"),
            ("All files", "*.*"),
        ]
        paths = filedialog.askopenfilenames(
            title="Select media files",
            filetypes=filetypes
        )
        for p in paths:
            self._add_file(p)

    def _add_file(self, filepath: str):
        """Add a file to the queue."""
        filepath = os.path.abspath(filepath)

        # Check extension
        ext = Path(filepath).suffix.lower()
        if ext not in INPUT_EXTENSIONS:
            return

        # Check if already added
        if any(f.filepath == filepath for f in self.files):
            return

        if not os.path.isfile(filepath):
            return

        fi = FileItem(filepath)
        self.files.append(fi)

        # Get duration in background
        if self.ffprobe_path:
            threading.Thread(target=self._probe_file, args=(fi,), daemon=True).start()

        self._refresh_file_list()

    def _probe_file(self, fi: FileItem):
        fi.duration = get_duration(fi.filepath, self.ffprobe_path)
        self.root.after(0, self._refresh_file_list)

    def _remove_file(self, fi: FileItem):
        if fi in self.files:
            self.files.remove(fi)
            self._refresh_file_list()

    def _clear_files(self):
        if self.converting:
            return
        self.files.clear()
        self._refresh_file_list()

    def _refresh_file_list(self):
        """Rebuild the file list UI."""
        # Clear existing widgets
        for w in self.file_widgets:
            w.destroy()
        self.file_widgets.clear()

        if not self.files:
            # Show drop zone
            self.file_list_frame.pack_forget()
            self.toolbar.pack_forget()
            self.drop_zone.pack(fill=BOTH, expand=True, pady=5)
        else:
            # Show file list
            self.drop_zone.pack_forget()
            self.toolbar.pack(fill=X, before=self.root.winfo_children()[-3])  # Before separator
            self.file_list_frame.pack(fill=BOTH, expand=True, in_=self.list_container)

            for fi in self.files:
                widget = FileListItem(
                    self.file_scroll_inner, fi,
                    on_remove=self._remove_file if not self.converting else None
                )
                widget.pack(fill=X, pady=2)
                self.file_widgets.append(widget)

        self.file_count_label.config(text=f"{len(self.files)} file{'s' if len(self.files) != 1 else ''}")

    def _choose_output_dir(self):
        d = filedialog.askdirectory(title="Select output directory")
        if d:
            self.output_dir.set(d)
            display = d if len(d) < 40 else "…" + d[-37:]
            self.output_dir_label.config(text=display)

    def _get_output_path(self, fi: FileItem, fmt: str) -> str:
        """Generate output path for a file."""
        out_dir = self.output_dir.get() or os.path.dirname(fi.filepath)
        stem = Path(fi.filepath).stem
        ext = fmt.lower()
        out_path = os.path.join(out_dir, f"{stem}.{ext}")

        # Avoid overwriting source
        if os.path.abspath(out_path) == os.path.abspath(fi.filepath):
            out_path = os.path.join(out_dir, f"{stem}_converted.{ext}")

        # Avoid overwriting existing
        counter = 1
        base_path = out_path
        while os.path.exists(out_path):
            stem_base = Path(base_path).stem
            out_path = os.path.join(out_dir, f"{stem_base}_{counter}.{ext}")
            counter += 1

        return out_path

    def _get_ffmpeg_args(self, fi: FileItem, fmt: str, quality: str) -> list[str]:
        """Build ffmpeg arguments for conversion."""
        fmt_upper = fmt.upper()

        if is_video_format(fmt_upper):
            fmt_type = "video"
        else:
            fmt_type = "audio"

        preset_key = (fmt_type, quality)
        presets = QUALITY_PRESETS.get(preset_key, {})
        args = presets.get(fmt_upper, [])

        # For audio output from video source, strip video
        if fmt_type == "audio":
            args = ["-vn"] + args

        return args

    def _start_conversion(self):
        if self.converting or not self.files:
            return

        if not self.ffmpeg_path:
            messagebox.showerror("FFmpeg Required",
                                 "FFmpeg is not installed. Please install it first.")
            return

        # Filter only queued files
        queued = [f for f in self.files if f.status in ("Queued", "Error")]
        if not queued:
            messagebox.showinfo("Nothing to convert", "All files are already converted.")
            return

        self.converting = True
        self.cancel_flag = False

        # UI updates
        self.convert_btn.pack_forget()
        self.cancel_btn.pack(side=RIGHT)

        # Start conversion thread
        threading.Thread(target=self._convert_thread, args=(queued,), daemon=True).start()

    def _convert_thread(self, files: list[FileItem]):
        fmt = self.output_format.get()
        quality = self.quality_preset.get()
        total = len(files)

        for idx, fi in enumerate(files, 1):
            if self.cancel_flag:
                fi.status = "Error"
                fi.error_msg = "Cancelled"
                self.root.after(0, self._update_file_widget, fi)
                continue

            fi.status = "Converting"
            fi.progress = 0
            self.root.after(0, self._update_file_widget, fi)
            self.root.after(0, lambda i=idx, t=total:
                self.overall_label.config(text=f"Converting {i}/{t}…"))

            output_path = self._get_output_path(fi, fmt)
            fi.output_path = output_path
            ffmpeg_args = self._get_ffmpeg_args(fi, fmt, quality)

            # Build command
            cmd = [
                self.ffmpeg_path, "-y", "-i", fi.filepath,
                *ffmpeg_args,
                "-progress", "pipe:1", "-nostats",
                output_path
            ]

            try:
                creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    universal_newlines=True,
                    creationflags=creation_flags,
                )
                self.current_process = proc

                # Get duration for progress calculation
                duration = fi.duration
                if duration is None and self.ffprobe_path:
                    duration = get_duration(fi.filepath, self.ffprobe_path)

                # Parse progress from ffmpeg
                for line in proc.stdout:
                    if self.cancel_flag:
                        proc.kill()
                        break

                    line = line.strip()
                    if line.startswith("out_time_ms="):
                        try:
                            time_us = int(line.split("=")[1])
                            time_s = time_us / 1_000_000
                            if duration and duration > 0:
                                fi.progress = min(99.0, (time_s / duration) * 100)
                                self.root.after(0, self._update_file_widget, fi)
                        except (ValueError, ZeroDivisionError):
                            pass
                    elif line.startswith("progress=end"):
                        fi.progress = 100

                proc.wait()
                self.current_process = None

                if self.cancel_flag:
                    fi.status = "Error"
                    fi.error_msg = "Cancelled"
                    # Clean up partial file
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except OSError:
                            pass
                elif proc.returncode == 0:
                    fi.status = "Done"
                    fi.progress = 100
                else:
                    fi.status = "Error"
                    stderr = proc.stderr.read() if proc.stderr else ""
                    fi.error_msg = stderr.strip().split('\n')[-1][:100] if stderr else f"Exit code {proc.returncode}"

            except Exception as e:
                fi.status = "Error"
                fi.error_msg = str(e)[:100]

            self.root.after(0, self._update_file_widget, fi)

        # Done
        self.root.after(0, self._conversion_finished)

    def _update_file_widget(self, fi: FileItem):
        for w in self.file_widgets:
            if w.file_item is fi:
                w.update_status()
                break

    def _conversion_finished(self):
        self.converting = False
        self.cancel_btn.pack_forget()
        self.convert_btn.pack(side=RIGHT)

        done = sum(1 for f in self.files if f.status == "Done")
        errors = sum(1 for f in self.files if f.status == "Error")

        if errors == 0:
            self.overall_label.config(text=f"✓ {done} file{'s' if done != 1 else ''} converted",
                                      fg=COLOR_ACCENT)
        else:
            self.overall_label.config(text=f"Done: {done} ✓  Errors: {errors} ✕",
                                      fg=COLOR_ERROR if done == 0 else COLOR_TEXT)

    def _cancel_conversion(self):
        self.cancel_flag = True
        if self.current_process:
            try:
                self.current_process.kill()
            except Exception:
                pass

    def run(self):
        self.root.mainloop()


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    app = MediaConverterApp()
    app.run()


if __name__ == "__main__":
    main()
