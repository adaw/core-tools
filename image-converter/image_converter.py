#!/usr/bin/env python3
"""
CORE Image Converter — Batch image format conversion tool.
Part of CORE SYSTEMS free utility suite.

Supports: PNG, JPG/JPEG, WebP, AVIF, BMP, TIFF, ICO
Features: batch conversion, resize, quality control, metadata stripping, preview
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from io import BytesIO

try:
    from PIL import Image, ImageTk, ExifTags
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_NAME = "CORE Image Converter"
VERSION = "1.0.0"

# Dark theme colors
BG = "#1a1a2e"
BG_SECONDARY = "#16213e"
BG_INPUT = "#0f3460"
FG = "#e0e0e0"
FG_DIM = "#888899"
ACCENT = "#00ff88"
ACCENT_DIM = "#00cc6a"
ERROR = "#ff4466"
BORDER = "#2a2a4a"

SUPPORTED_FORMATS = ["PNG", "JPEG", "WEBP", "BMP", "TIFF", "ICO"]
SUPPORTED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".avif",
    ".bmp", ".tiff", ".tif", ".ico", ".gif",
}

FORMAT_EXTENSIONS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tiff",
    "ICO": ".ico",
}

# Check for AVIF support (pillow-avif-plugin or Pillow >= 10.1)
try:
    _test = Image.registered_extensions()
    if ".avif" in _test:
        SUPPORTED_FORMATS.append("AVIF")
        FORMAT_EXTENSIONS["AVIF"] = ".avif"
except Exception:
    pass

# ICO max sizes
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def resource_path(relative_path: str) -> str:
    """Get path for PyInstaller bundled resources."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


def human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(nbytes) < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


def strip_metadata(img: Image.Image) -> Image.Image:
    """Return a copy of the image with all metadata removed."""
    data = list(img.getdata())
    clean = Image.new(img.mode, img.size)
    clean.putdata(data)
    return clean


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class ImageConverterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("960x720")
        self.root.minsize(800, 600)
        self.root.configure(bg=BG)

        # State
        self.files: list[Path] = []
        self.preview_image = None  # keep reference for GC
        self.converting = False

        self._setup_styles()
        self._build_ui()
        self._setup_dnd()

    # -- Styles ------------------------------------------------------------

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=BG, foreground=FG, fieldbackground=BG_INPUT,
                         borderwidth=0, font=("Helvetica", 11))
        style.configure("TFrame", background=BG)
        style.configure("Secondary.TFrame", background=BG_SECONDARY)
        style.configure("TLabel", background=BG, foreground=FG, font=("Helvetica", 11))
        style.configure("Title.TLabel", background=BG, foreground=ACCENT,
                         font=("Helvetica", 18, "bold"))
        style.configure("Subtitle.TLabel", background=BG, foreground=FG_DIM,
                         font=("Helvetica", 10))
        style.configure("Dim.TLabel", background=BG, foreground=FG_DIM,
                         font=("Helvetica", 10))
        style.configure("Status.TLabel", background=BG_SECONDARY, foreground=FG_DIM,
                         font=("Helvetica", 10))
        style.configure("Accent.TButton", background=ACCENT, foreground="#000000",
                         font=("Helvetica", 12, "bold"), padding=(20, 10))
        style.map("Accent.TButton",
                   background=[("active", ACCENT_DIM), ("disabled", BORDER)],
                   foreground=[("disabled", FG_DIM)])
        style.configure("TButton", background=BG_INPUT, foreground=FG,
                         font=("Helvetica", 11), padding=(12, 6))
        style.map("TButton",
                   background=[("active", BORDER)])
        style.configure("TCombobox", fieldbackground=BG_INPUT, background=BG_INPUT,
                         foreground=FG, selectbackground=ACCENT_DIM,
                         selectforeground="#000")
        style.configure("TCheckbutton", background=BG, foreground=FG,
                         font=("Helvetica", 11))
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("Horizontal.TScale", background=BG, troughcolor=BG_INPUT)

        # Progress bar
        style.configure("green.Horizontal.TProgressbar",
                         troughcolor=BG_INPUT, background=ACCENT, thickness=6)

    # -- UI ----------------------------------------------------------------

    def _build_ui(self):
        # Header
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=20, pady=(15, 5))
        ttk.Label(header, text="⬡ CORE Image Converter", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=f"v{VERSION}  •  CORE SYSTEMS", style="Subtitle.TLabel").pack(side="right", pady=(8, 0))

        # Main content — left (files) + right (preview)
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=20, pady=10)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        # Left panel
        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.rowconfigure(1, weight=1)

        # Drop zone / file list
        drop_frame = tk.Frame(left, bg=BG_SECONDARY, highlightbackground=ACCENT,
                               highlightthickness=1, relief="flat")
        drop_frame.grid(row=0, column=0, sticky="nsew", rowspan=2)
        left.columnconfigure(0, weight=1)

        self.drop_label = tk.Label(
            drop_frame, text="Drop images here\nor click to browse",
            bg=BG_SECONDARY, fg=FG_DIM, font=("Helvetica", 13),
            cursor="hand2", justify="center"
        )
        self.drop_label.pack(expand=True, fill="both", padx=10, pady=10)
        self.drop_label.bind("<Button-1>", lambda e: self._browse_files())

        # File listbox (hidden until files added)
        self.file_list_frame = tk.Frame(drop_frame, bg=BG_SECONDARY)
        self.file_listbox = tk.Listbox(
            self.file_list_frame, bg=BG_SECONDARY, fg=FG, font=("Helvetica", 10),
            selectbackground=ACCENT_DIM, selectforeground="#000",
            highlightthickness=0, borderwidth=0, activestyle="none"
        )
        scrollbar = tk.Scrollbar(self.file_list_frame, command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=scrollbar.set)
        self.file_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.file_listbox.bind("<<ListboxSelect>>", self._on_file_select)
        self.file_listbox.bind("<Button-1>", self._listbox_click)

        # File action buttons
        btn_row = ttk.Frame(left)
        btn_row.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(btn_row, text="+ Add Files", command=self._browse_files).pack(side="left", padx=(0, 5))
        ttk.Button(btn_row, text="+ Add Folder", command=self._browse_folder).pack(side="left", padx=(0, 5))
        ttk.Button(btn_row, text="✕ Clear All", command=self._clear_files).pack(side="right")

        # Right panel — preview + options
        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        # Preview area
        preview_frame = tk.Frame(right, bg=BG_SECONDARY, highlightbackground=BORDER,
                                  highlightthickness=1)
        preview_frame.grid(row=0, column=0, sticky="nsew")
        self.preview_label = tk.Label(preview_frame, text="Preview", bg=BG_SECONDARY,
                                       fg=FG_DIM, font=("Helvetica", 11))
        self.preview_label.pack(expand=True, fill="both")
        self.preview_info = tk.Label(preview_frame, text="", bg=BG_SECONDARY,
                                      fg=FG_DIM, font=("Helvetica", 9), anchor="w")
        self.preview_info.pack(fill="x", padx=8, pady=(0, 6))

        # Options panel
        opts = ttk.Frame(right)
        opts.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        opts.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(opts, text="Output Format:").grid(row=row, column=0, sticky="w", pady=4)
        self.format_var = tk.StringVar(value="PNG")
        fmt_combo = ttk.Combobox(opts, textvariable=self.format_var,
                                  values=SUPPORTED_FORMATS, state="readonly", width=12)
        fmt_combo.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=4)
        fmt_combo.bind("<<ComboboxSelected>>", self._on_format_change)

        row += 1
        ttk.Label(opts, text="Quality:").grid(row=row, column=0, sticky="w", pady=4)
        quality_frame = ttk.Frame(opts)
        quality_frame.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=4)
        self.quality_var = tk.IntVar(value=90)
        self.quality_scale = ttk.Scale(quality_frame, from_=1, to=100,
                                        variable=self.quality_var, orient="horizontal",
                                        command=self._on_quality_change)
        self.quality_scale.pack(side="left", fill="x", expand=True)
        self.quality_label = ttk.Label(quality_frame, text="90%", width=5, style="Dim.TLabel")
        self.quality_label.pack(side="right", padx=(6, 0))

        row += 1
        self.resize_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Resize", variable=self.resize_var,
                         command=self._toggle_resize).grid(row=row, column=0, sticky="w", pady=4)
        resize_frame = ttk.Frame(opts)
        resize_frame.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=4)
        self.width_var = tk.StringVar(value="1920")
        self.height_var = tk.StringVar(value="1080")
        self.width_entry = tk.Entry(resize_frame, textvariable=self.width_var, width=6,
                                     bg=BG_INPUT, fg=FG, insertbackground=FG,
                                     font=("Helvetica", 10), state="disabled",
                                     disabledbackground=BORDER, disabledforeground=FG_DIM)
        self.width_entry.pack(side="left")
        tk.Label(resize_frame, text="×", bg=BG, fg=FG_DIM).pack(side="left", padx=4)
        self.height_entry = tk.Entry(resize_frame, textvariable=self.height_var, width=6,
                                      bg=BG_INPUT, fg=FG, insertbackground=FG,
                                      font=("Helvetica", 10), state="disabled",
                                      disabledbackground=BORDER, disabledforeground=FG_DIM)
        self.height_entry.pack(side="left")

        row += 1
        self.strip_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Strip Metadata (EXIF, etc.)",
                         variable=self.strip_var).grid(row=row, column=0, columnspan=2,
                                                        sticky="w", pady=4)

        # Output directory
        row += 1
        ttk.Label(opts, text="Output Dir:").grid(row=row, column=0, sticky="w", pady=4)
        dir_frame = ttk.Frame(opts)
        dir_frame.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=4)
        dir_frame.columnconfigure(0, weight=1)
        self.output_var = tk.StringVar(value="(same as source)")
        self.output_entry = tk.Entry(dir_frame, textvariable=self.output_var,
                                      bg=BG_INPUT, fg=FG, insertbackground=FG,
                                      font=("Helvetica", 10), state="readonly",
                                      readonlybackground=BG_INPUT)
        self.output_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(dir_frame, text="…", command=self._browse_output, width=3).grid(row=0, column=1, padx=(4, 0))

        # Convert button + progress
        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", padx=20, pady=(5, 10))

        self.progress = ttk.Progressbar(bottom, style="green.Horizontal.TProgressbar",
                                         mode="determinate")
        self.progress.pack(fill="x", pady=(0, 8))

        btn_frame = ttk.Frame(bottom)
        btn_frame.pack(fill="x")
        self.convert_btn = ttk.Button(btn_frame, text="⚡ Convert All",
                                       style="Accent.TButton", command=self._start_convert)
        self.convert_btn.pack(side="right")
        self.status_label = ttk.Label(btn_frame, text="No files loaded", style="Status.TLabel")
        self.status_label.pack(side="left")

    # -- Drag & Drop -------------------------------------------------------

    def _setup_dnd(self):
        """Try to enable native drag & drop via tkinterdnd2, fallback gracefully."""
        try:
            from tkinterdnd2 import DND_FILES
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self._on_drop)
        except ImportError:
            # No tkinterdnd2 — drop label still works as browse button
            pass

    def _on_drop(self, event):
        """Handle dropped files."""
        raw = event.data
        # Parse tcl list (may have braces for paths with spaces)
        paths = self.root.tk.splitlist(raw)
        added = 0
        for p in paths:
            added += self._add_path(Path(p))
        if added:
            self._refresh_file_list()

    # -- File management ---------------------------------------------------

    def _add_path(self, path: Path) -> int:
        """Add a file or directory. Returns count of files added."""
        if path.is_dir():
            count = 0
            for child in sorted(path.iterdir()):
                if child.suffix.lower() in SUPPORTED_EXTENSIONS and child not in self.files:
                    self.files.append(child)
                    count += 1
            return count
        elif path.suffix.lower() in SUPPORTED_EXTENSIONS and path not in self.files:
            self.files.append(path)
            return 1
        return 0

    def _browse_files(self):
        paths = filedialog.askopenfilenames(
            title="Select Images",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.avif *.bmp *.tiff *.tif *.ico *.gif"),
                ("All files", "*.*"),
            ]
        )
        for p in paths:
            self._add_path(Path(p))
        self._refresh_file_list()

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Select Folder with Images")
        if folder:
            self._add_path(Path(folder))
            self._refresh_file_list()

    def _browse_output(self):
        folder = filedialog.askdirectory(title="Select Output Directory")
        if folder:
            self.output_var.set(folder)

    def _clear_files(self):
        self.files.clear()
        self._refresh_file_list()
        self.preview_label.configure(image="", text="Preview")
        self.preview_info.configure(text="")
        self.preview_image = None

    def _refresh_file_list(self):
        if not self.files:
            self.file_list_frame.pack_forget()
            self.drop_label.pack(expand=True, fill="both", padx=10, pady=10)
            self.status_label.configure(text="No files loaded")
            return

        self.drop_label.pack_forget()
        self.file_list_frame.pack(expand=True, fill="both", padx=4, pady=4)
        self.file_listbox.delete(0, "end")
        for f in self.files:
            size = human_size(f.stat().st_size) if f.exists() else "?"
            self.file_listbox.insert("end", f"  {f.name}  ({size})")

        n = len(self.files)
        self.status_label.configure(text=f"{n} file{'s' if n != 1 else ''} ready")

    def _listbox_click(self, event):
        """Allow clicking empty area to browse more files."""
        index = self.file_listbox.nearest(event.y)
        if index >= len(self.files):
            self._browse_files()

    def _on_file_select(self, event):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self.files):
            self._show_preview(self.files[idx])

    # -- Preview -----------------------------------------------------------

    def _show_preview(self, path: Path):
        try:
            img = Image.open(path)
            # Fit to preview area
            pw = self.preview_label.winfo_width() - 20
            ph = self.preview_label.winfo_height() - 20
            if pw < 50:
                pw, ph = 300, 250
            img.thumbnail((pw, ph), Image.LANCZOS)
            self.preview_image = ImageTk.PhotoImage(img)
            self.preview_label.configure(image=self.preview_image, text="")

            # Info
            orig = Image.open(path)
            info = f"{orig.size[0]}×{orig.size[1]}  •  {orig.mode}  •  {human_size(path.stat().st_size)}"
            self.preview_info.configure(text=info)
            orig.close()
        except Exception as e:
            self.preview_label.configure(image="", text=f"Cannot preview\n{e}")
            self.preview_info.configure(text="")

    # -- Options callbacks -------------------------------------------------

    def _on_format_change(self, event=None):
        fmt = self.format_var.get()
        # Quality only meaningful for JPEG/WEBP/AVIF
        lossy = fmt in ("JPEG", "WEBP", "AVIF")
        state = "normal" if lossy else "disabled"
        self.quality_scale.configure(state=state)

    def _on_quality_change(self, val):
        self.quality_label.configure(text=f"{int(float(val))}%")

    def _toggle_resize(self):
        state = "normal" if self.resize_var.get() else "disabled"
        self.width_entry.configure(state=state)
        self.height_entry.configure(state=state)

    # -- Conversion --------------------------------------------------------

    def _start_convert(self):
        if self.converting:
            return
        if not self.files:
            messagebox.showwarning("No files", "Add some images first.")
            return

        self.converting = True
        self.convert_btn.configure(state="disabled")
        self.progress["value"] = 0
        self.progress["maximum"] = len(self.files)

        thread = threading.Thread(target=self._convert_worker, daemon=True)
        thread.start()

    def _convert_worker(self):
        fmt = self.format_var.get()
        quality = self.quality_var.get()
        do_resize = self.resize_var.get()
        do_strip = self.strip_var.get()
        output_dir = self.output_var.get()

        try:
            width = int(self.width_var.get()) if do_resize else None
            height = int(self.height_var.get()) if do_resize else None
        except ValueError:
            self.root.after(0, lambda: messagebox.showerror("Error", "Invalid resize dimensions."))
            self._finish_convert(0, 0)
            return

        success = 0
        errors = 0
        ext = FORMAT_EXTENSIONS.get(fmt, ".png")

        for i, fpath in enumerate(self.files):
            try:
                img = Image.open(fpath)

                # Handle transparency for formats that don't support it
                if fmt in ("JPEG", "BMP") and img.mode in ("RGBA", "LA", "P"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
                    img = background
                elif fmt == "JPEG" and img.mode != "RGB":
                    img = img.convert("RGB")

                # Strip metadata
                if do_strip:
                    img = strip_metadata(img)

                # Resize
                if do_resize and width and height:
                    img = img.resize((width, height), Image.LANCZOS)

                # Output path
                if output_dir and output_dir != "(same as source)":
                    out_path = Path(output_dir) / (fpath.stem + ext)
                else:
                    out_path = fpath.with_suffix(ext)

                # Avoid overwriting source
                if out_path == fpath:
                    out_path = fpath.with_stem(fpath.stem + "_converted").with_suffix(ext)

                # Save
                save_kwargs = {}
                if fmt == "JPEG":
                    save_kwargs["quality"] = quality
                    save_kwargs["optimize"] = True
                elif fmt == "WEBP":
                    save_kwargs["quality"] = quality
                    save_kwargs["method"] = 4
                elif fmt == "AVIF":
                    save_kwargs["quality"] = quality
                elif fmt == "PNG":
                    save_kwargs["optimize"] = True
                elif fmt == "ICO":
                    # Generate multiple sizes for ICO
                    sizes = [s for s in ICO_SIZES if s[0] <= max(img.size)]
                    if not sizes:
                        sizes = [(16, 16)]
                    save_kwargs["sizes"] = sizes

                img.save(str(out_path), format=fmt, **save_kwargs)
                img.close()
                success += 1

            except Exception as e:
                errors += 1
                print(f"Error converting {fpath.name}: {e}")

            self.root.after(0, lambda v=i + 1: self.progress.configure(value=v))

        self._finish_convert(success, errors)

    def _finish_convert(self, success: int, errors: int):
        def _update():
            self.converting = False
            self.convert_btn.configure(state="normal")
            msg = f"✓ {success} converted"
            if errors:
                msg += f"  •  ✕ {errors} failed"
            self.status_label.configure(text=msg)
            if errors == 0 and success > 0:
                messagebox.showinfo("Done", f"Successfully converted {success} image(s).")
            elif errors > 0:
                messagebox.showwarning("Done", f"Converted {success}, failed {errors}. Check console for details.")
        self.root.after(0, _update)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if not HAS_PILLOW:
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Missing Dependency",
                                  "Pillow is required.\n\nInstall with:\n  pip install Pillow")
            sys.exit(1)
        except Exception:
            print("ERROR: Pillow is required. Install with: pip install Pillow")
            sys.exit(1)

    # Try to use tkinterdnd2 TkinterDnD root for native drag & drop
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
    except ImportError:
        root = tk.Tk()

    # Set icon if available
    icon_path = resource_path("icon.png")
    if os.path.exists(icon_path):
        try:
            icon = ImageTk.PhotoImage(Image.open(icon_path))
            root.iconphoto(True, icon)
        except Exception:
            pass

    app = ImageConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
