#!/usr/bin/env python3
"""
CORE SYSTEMS — PDF Tools v1.0
Merge, split, compress, convert, rotate, watermark, encrypt/decrypt PDF files.
"""

import os
import sys
import io
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path

try:
    from PyPDF2 import PdfReader, PdfWriter, PdfMerger
except ImportError:
    PdfReader = PdfWriter = PdfMerger = None

try:
    import pikepdf
except ImportError:
    pikepdf = None

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
except ImportError:
    rl_canvas = None

# ─── Theme ────────────────────────────────────────────────────────────────────
BG = "#1a1a2e"
BG2 = "#16213e"
BG3 = "#0f3460"
FG = "#e0e0e0"
ACCENT = "#00ff88"
ACCENT2 = "#00cc6a"
ERR = "#ff4757"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_SM = ("Segoe UI", 9)


class StatusBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG2, height=28)
        self.pack_propagate(False)
        self.label = tk.Label(self, text="Ready", bg=BG2, fg=FG, font=FONT_SM, anchor="w")
        self.label.pack(fill="x", padx=8, pady=4)

    def set(self, text, error=False):
        self.label.config(text=text, fg=ERR if error else ACCENT)
        self.update_idletasks()


class FileListWidget(tk.Frame):
    """Reusable file list with drag & drop reorder and add/remove."""
    def __init__(self, parent, filetypes=(("PDF files", "*.pdf"),), multi=True):
        super().__init__(parent, bg=BG)
        self.filetypes = filetypes
        self.multi = multi
        self.files = []

        # Listbox
        frame = tk.Frame(self, bg=BG)
        frame.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(
            frame, bg=BG2, fg=FG, font=FONT, selectbackground=BG3,
            selectforeground=ACCENT, borderwidth=0, highlightthickness=1,
            highlightcolor=ACCENT, activestyle="none"
        )
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.listbox.yview)
        self.listbox.config(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Buttons
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", pady=(4, 0))

        for text, cmd in [("+ Add", self.add_files), ("− Remove", self.remove_selected),
                          ("▲ Up", self.move_up), ("▼ Down", self.move_down), ("Clear", self.clear)]:
            b = tk.Button(btn_frame, text=text, command=cmd, bg=BG3, fg=FG,
                          font=FONT_SM, borderwidth=0, padx=8, pady=2,
                          activebackground=ACCENT, activeforeground=BG)
            b.pack(side="left", padx=2)

        # DnD via TkDnD if available, else just button-based
        self._setup_drop()

    def _setup_drop(self):
        """Try to enable native file drop."""
        try:
            self.listbox.drop_target_register("DND_Files")
            self.listbox.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            pass

    def _on_drop(self, event):
        files = self.tk.splitlist(event.data)
        for f in files:
            f = f.strip("{}")
            if f.lower().endswith(tuple(ext for _, pat in self.filetypes for ext in pat.split(";"))):
                self._add(f)

    def add_files(self):
        paths = filedialog.askopenfilenames(filetypes=self.filetypes)
        for p in paths:
            self._add(p)

    def _add(self, path):
        if path not in self.files:
            self.files.append(path)
            self.listbox.insert("end", os.path.basename(path))

    def remove_selected(self):
        sel = self.listbox.curselection()
        for i in reversed(sel):
            self.listbox.delete(i)
            del self.files[i]

    def move_up(self):
        sel = self.listbox.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        self.files[i-1], self.files[i] = self.files[i], self.files[i-1]
        self._refresh()
        self.listbox.selection_set(i-1)

    def move_down(self):
        sel = self.listbox.curselection()
        if not sel or sel[0] >= len(self.files) - 1:
            return
        i = sel[0]
        self.files[i], self.files[i+1] = self.files[i+1], self.files[i]
        self._refresh()
        self.listbox.selection_set(i+1)

    def clear(self):
        self.files.clear()
        self.listbox.delete(0, "end")

    def _refresh(self):
        self.listbox.delete(0, "end")
        for f in self.files:
            self.listbox.insert("end", os.path.basename(f))


class PDFToolsApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CORE SYSTEMS — PDF Tools")
        self.geometry("900x680")
        self.configure(bg=BG)
        self.minsize(800, 600)

        # Style
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG2, foreground=FG,
                         padding=[14, 6], font=FONT_BOLD)
        style.map("TNotebook.Tab",
                   background=[("selected", BG3)],
                   foreground=[("selected", ACCENT)])
        style.configure("TScrollbar", background=BG3, troughcolor=BG2)
        style.configure("Horizontal.TScale", background=BG, troughcolor=BG3)

        self._build_header()
        self._build_tabs()
        self.status = StatusBar(self)
        self.status.pack(fill="x", side="bottom")

    # ─── Header ───────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=BG, height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="◆ CORE SYSTEMS", bg=BG, fg=ACCENT, font=("Segoe UI", 11, "bold")).pack(side="left", padx=12)
        tk.Label(hdr, text="PDF Tools v1.0", bg=BG, fg=FG, font=FONT_TITLE).pack(side="left", padx=4)

    # ─── Tabs ─────────────────────────────────────────────────────────────────
    def _build_tabs(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self._tab_merge(nb)
        self._tab_split(nb)
        self._tab_compress(nb)
        self._tab_convert(nb)
        self._tab_rotate(nb)
        self._tab_text(nb)
        self._tab_watermark(nb)
        self._tab_security(nb)

    def _make_tab(self, nb, title):
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text=title)
        return f

    def _btn(self, parent, text, cmd, **kw):
        b = tk.Button(parent, text=text, command=cmd, bg=ACCENT, fg=BG,
                      font=FONT_BOLD, borderwidth=0, padx=16, pady=6, cursor="hand2",
                      activebackground=ACCENT2, activeforeground=BG, **kw)
        return b

    def _run_async(self, func, *args):
        """Run func in background thread."""
        def wrapper():
            try:
                func(*args)
            except Exception as e:
                self.after(0, lambda: self.status.set(f"Error: {e}", error=True))
        threading.Thread(target=wrapper, daemon=True).start()

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB: Merge
    # ═══════════════════════════════════════════════════════════════════════════
    def _tab_merge(self, nb):
        tab = self._make_tab(nb, "Merge")
        tk.Label(tab, text="Merge multiple PDFs into one", bg=BG, fg=FG, font=FONT_BOLD).pack(pady=(12, 4))
        self.merge_list = FileListWidget(tab)
        self.merge_list.pack(fill="both", expand=True, padx=12, pady=4)
        self._btn(tab, "⬇ Merge PDFs", self._do_merge).pack(pady=8)

    def _do_merge(self):
        files = self.merge_list.files
        if len(files) < 2:
            messagebox.showwarning("Merge", "Add at least 2 PDF files.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out:
            return
        self.status.set("Merging...")
        self._run_async(self._merge_worker, files, out)

    def _merge_worker(self, files, out):
        merger = PdfMerger()
        for f in files:
            merger.append(f)
        merger.write(out)
        merger.close()
        self.after(0, lambda: self.status.set(f"Merged {len(files)} files → {os.path.basename(out)}"))

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB: Split
    # ═══════════════════════════════════════════════════════════════════════════
    def _tab_split(self, nb):
        tab = self._make_tab(nb, "Split")
        tk.Label(tab, text="Split PDF into pages", bg=BG, fg=FG, font=FONT_BOLD).pack(pady=(12, 4))

        row = tk.Frame(tab, bg=BG)
        row.pack(fill="x", padx=12, pady=4)
        tk.Label(row, text="Input PDF:", bg=BG, fg=FG, font=FONT).pack(side="left")
        self.split_path = tk.StringVar()
        tk.Entry(row, textvariable=self.split_path, bg=BG2, fg=FG, font=FONT,
                 insertbackground=FG, borderwidth=1, relief="solid").pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(row, text="Browse", command=self._split_browse, bg=BG3, fg=FG,
                  font=FONT_SM, borderwidth=0).pack(side="left")

        row2 = tk.Frame(tab, bg=BG)
        row2.pack(fill="x", padx=12, pady=4)
        self.split_mode = tk.StringVar(value="each")
        tk.Radiobutton(row2, text="Each page", variable=self.split_mode, value="each",
                       bg=BG, fg=FG, selectcolor=BG2, font=FONT, activebackground=BG).pack(side="left")
        tk.Radiobutton(row2, text="Range:", variable=self.split_mode, value="range",
                       bg=BG, fg=FG, selectcolor=BG2, font=FONT, activebackground=BG).pack(side="left", padx=(12, 4))
        self.split_range = tk.StringVar(value="1-3,5,7-10")
        tk.Entry(row2, textvariable=self.split_range, bg=BG2, fg=FG, font=FONT,
                 insertbackground=FG, width=20, borderwidth=1, relief="solid").pack(side="left")

        self._btn(tab, "✂ Split PDF", self._do_split).pack(pady=8)

    def _split_browse(self):
        p = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if p:
            self.split_path.set(p)

    def _do_split(self):
        src = self.split_path.get()
        if not src or not os.path.isfile(src):
            messagebox.showwarning("Split", "Select a valid PDF file.")
            return
        outdir = filedialog.askdirectory(title="Output directory")
        if not outdir:
            return
        self.status.set("Splitting...")
        self._run_async(self._split_worker, src, outdir)

    def _split_worker(self, src, outdir):
        reader = PdfReader(src)
        total = len(reader.pages)
        basename = Path(src).stem

        if self.split_mode.get() == "each":
            pages = list(range(total))
        else:
            pages = self._parse_range(self.split_range.get(), total)

        if self.split_mode.get() == "each":
            for i in pages:
                writer = PdfWriter()
                writer.add_page(reader.pages[i])
                out = os.path.join(outdir, f"{basename}_page{i+1}.pdf")
                with open(out, "wb") as f:
                    writer.write(f)
            self.after(0, lambda: self.status.set(f"Split into {len(pages)} files"))
        else:
            writer = PdfWriter()
            for i in pages:
                writer.add_page(reader.pages[i])
            out = os.path.join(outdir, f"{basename}_split.pdf")
            with open(out, "wb") as f:
                writer.write(f)
            self.after(0, lambda: self.status.set(f"Extracted {len(pages)} pages → {os.path.basename(out)}"))

    def _parse_range(self, s, total):
        pages = []
        for part in s.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                a, b = int(a) - 1, int(b) - 1
                pages.extend(range(max(0, a), min(total, b + 1)))
            else:
                p = int(part) - 1
                if 0 <= p < total:
                    pages.append(p)
        return pages

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB: Compress
    # ═══════════════════════════════════════════════════════════════════════════
    def _tab_compress(self, nb):
        tab = self._make_tab(nb, "Compress")
        tk.Label(tab, text="Compress PDF (reduce file size)", bg=BG, fg=FG, font=FONT_BOLD).pack(pady=(12, 4))

        row = tk.Frame(tab, bg=BG)
        row.pack(fill="x", padx=12, pady=4)
        tk.Label(row, text="Input PDF:", bg=BG, fg=FG, font=FONT).pack(side="left")
        self.compress_path = tk.StringVar()
        tk.Entry(row, textvariable=self.compress_path, bg=BG2, fg=FG, font=FONT,
                 insertbackground=FG, borderwidth=1, relief="solid").pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(row, text="Browse", command=lambda: self._browse_to(self.compress_path), bg=BG3, fg=FG,
                  font=FONT_SM, borderwidth=0).pack(side="left")

        row2 = tk.Frame(tab, bg=BG)
        row2.pack(fill="x", padx=12, pady=8)
        tk.Label(row2, text="Quality:", bg=BG, fg=FG, font=FONT).pack(side="left")
        self.compress_quality = tk.IntVar(value=50)
        tk.Label(row2, text="Low", bg=BG, fg="#888", font=FONT_SM).pack(side="left", padx=(8, 0))
        ttk.Scale(row2, from_=10, to=100, variable=self.compress_quality,
                  orient="horizontal").pack(side="left", fill="x", expand=True, padx=4)
        tk.Label(row2, text="High", bg=BG, fg="#888", font=FONT_SM).pack(side="left")
        self.quality_label = tk.Label(row2, text="50", bg=BG, fg=ACCENT, font=FONT_BOLD, width=4)
        self.quality_label.pack(side="left", padx=4)
        self.compress_quality.trace_add("write", lambda *_: self.quality_label.config(
            text=str(self.compress_quality.get())))

        self._btn(tab, "📦 Compress PDF", self._do_compress).pack(pady=8)

    def _browse_to(self, var):
        p = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if p:
            var.set(p)

    def _do_compress(self):
        src = self.compress_path.get()
        if not src or not os.path.isfile(src):
            messagebox.showwarning("Compress", "Select a valid PDF file.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out:
            return
        self.status.set("Compressing...")
        self._run_async(self._compress_worker, src, out)

    def _compress_worker(self, src, out):
        if pikepdf is None:
            self.after(0, lambda: self.status.set("pikepdf not installed!", error=True))
            return
        quality = self.compress_quality.get()
        pdf = pikepdf.Pdf.open(src)

        # Compress images inside the PDF
        for page in pdf.pages:
            if "/Resources" not in page:
                continue
            resources = page["/Resources"]
            if "/XObject" not in resources:
                continue
            xobjects = resources["/XObject"]
            for key in list(xobjects.keys()):
                obj = xobjects[key]
                if not isinstance(obj, pikepdf.Stream):
                    continue
                if obj.get("/Subtype") != "/Image":
                    continue
                try:
                    raw = obj.read_raw_bytes()
                    img = Image.open(io.BytesIO(raw))
                except Exception:
                    try:
                        raw = obj.read_bytes()
                        img = Image.open(io.BytesIO(raw))
                    except Exception:
                        continue

                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                xobjects[key] = pdf.make_stream(buf.getvalue())
                xobjects[key]["/Filter"] = pikepdf.Name("/DCTDecode")
                xobjects[key]["/Width"] = obj.get("/Width", 0)
                xobjects[key]["/Height"] = obj.get("/Height", 0)
                xobjects[key]["/ColorSpace"] = pikepdf.Name("/DeviceRGB")
                xobjects[key]["/BitsPerComponent"] = 8
                xobjects[key]["/Subtype"] = pikepdf.Name("/Image")

        pdf.save(out, linearize=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
        pdf.close()

        orig = os.path.getsize(src)
        comp = os.path.getsize(out)
        pct = (1 - comp / orig) * 100 if orig > 0 else 0
        self.after(0, lambda: self.status.set(
            f"Compressed: {orig//1024}KB → {comp//1024}KB ({pct:.1f}% reduction)"))

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB: Convert
    # ═══════════════════════════════════════════════════════════════════════════
    def _tab_convert(self, nb):
        tab = self._make_tab(nb, "Convert")
        tk.Label(tab, text="PDF ↔ Images", bg=BG, fg=FG, font=FONT_BOLD).pack(pady=(12, 4))

        # PDF → Images
        f1 = tk.LabelFrame(tab, text=" PDF → Images ", bg=BG, fg=ACCENT, font=FONT_BOLD,
                           borderwidth=1, relief="solid")
        f1.pack(fill="x", padx=12, pady=4)

        row = tk.Frame(f1, bg=BG)
        row.pack(fill="x", padx=8, pady=4)
        self.pdf2img_path = tk.StringVar()
        tk.Entry(row, textvariable=self.pdf2img_path, bg=BG2, fg=FG, font=FONT,
                 insertbackground=FG, borderwidth=1, relief="solid").pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(row, text="Browse", command=lambda: self._browse_to(self.pdf2img_path),
                  bg=BG3, fg=FG, font=FONT_SM, borderwidth=0).pack(side="left")

        row2 = tk.Frame(f1, bg=BG)
        row2.pack(fill="x", padx=8, pady=(0, 4))
        self.img_format = tk.StringVar(value="PNG")
        for fmt in ("PNG", "JPEG"):
            tk.Radiobutton(row2, text=fmt, variable=self.img_format, value=fmt,
                           bg=BG, fg=FG, selectcolor=BG2, font=FONT, activebackground=BG).pack(side="left")
        self._btn(row2, "Export Images", self._do_pdf2img).pack(side="right", padx=4)

        # Images → PDF
        f2 = tk.LabelFrame(tab, text=" Images → PDF ", bg=BG, fg=ACCENT, font=FONT_BOLD,
                           borderwidth=1, relief="solid")
        f2.pack(fill="both", expand=True, padx=12, pady=4)

        self.img2pdf_list = FileListWidget(f2, filetypes=[
            ("Images", "*.png *.jpg *.jpeg *.bmp *.tiff *.gif")])
        self.img2pdf_list.pack(fill="both", expand=True, padx=8, pady=4)
        self._btn(f2, "Create PDF from Images", self._do_img2pdf).pack(pady=4)

    def _do_pdf2img(self):
        src = self.pdf2img_path.get()
        if not src or not os.path.isfile(src):
            messagebox.showwarning("Convert", "Select a PDF file.")
            return
        outdir = filedialog.askdirectory(title="Output directory")
        if not outdir:
            return
        self.status.set("Converting PDF → images (requires pdf2image/poppler)...")
        self._run_async(self._pdf2img_worker, src, outdir)

    def _pdf2img_worker(self, src, outdir):
        """Convert PDF pages to images using pikepdf + PIL for embedded images,
        or fallback info."""
        try:
            from pdf2image import convert_from_path
            fmt = self.img_format.get().lower()
            images = convert_from_path(src, dpi=200)
            basename = Path(src).stem
            for i, img in enumerate(images):
                out = os.path.join(outdir, f"{basename}_page{i+1}.{fmt}")
                img.save(out, fmt.upper())
            self.after(0, lambda: self.status.set(f"Exported {len(images)} page images"))
        except ImportError:
            # Fallback: extract embedded images via pikepdf
            if pikepdf is None:
                self.after(0, lambda: self.status.set("Install pdf2image + poppler for PDF→image", error=True))
                return
            pdf = pikepdf.Pdf.open(src)
            basename = Path(src).stem
            fmt = self.img_format.get().lower()
            count = 0
            for i, page in enumerate(pdf.pages):
                if "/Resources" not in page or "/XObject" not in page["/Resources"]:
                    continue
                for key, obj in page["/Resources"]["/XObject"].items():
                    if not isinstance(obj, pikepdf.Stream):
                        continue
                    if obj.get("/Subtype") != "/Image":
                        continue
                    try:
                        raw = obj.read_bytes()
                        img = Image.open(io.BytesIO(raw))
                        out = os.path.join(outdir, f"{basename}_p{i+1}_{key.lstrip('/')}.{fmt}")
                        img.save(out)
                        count += 1
                    except Exception:
                        pass
            pdf.close()
            if count:
                self.after(0, lambda: self.status.set(f"Extracted {count} embedded images"))
            else:
                self.after(0, lambda: self.status.set(
                    "No images extracted. Install pdf2image + poppler for full page rendering.", error=True))

    def _do_img2pdf(self):
        files = self.img2pdf_list.files
        if not files:
            messagebox.showwarning("Convert", "Add image files first.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out:
            return
        self.status.set("Creating PDF from images...")
        self._run_async(self._img2pdf_worker, files, out)

    def _img2pdf_worker(self, files, out):
        images = []
        for f in files:
            img = Image.open(f)
            if img.mode == "RGBA":
                img = img.convert("RGB")
            images.append(img)
        if images:
            first = images[0]
            rest = images[1:] if len(images) > 1 else []
            first.save(out, "PDF", save_all=True, append_images=rest, resolution=150)
            self.after(0, lambda: self.status.set(f"Created PDF with {len(images)} pages"))

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB: Rotate
    # ═══════════════════════════════════════════════════════════════════════════
    def _tab_rotate(self, nb):
        tab = self._make_tab(nb, "Rotate")
        tk.Label(tab, text="Rotate PDF pages", bg=BG, fg=FG, font=FONT_BOLD).pack(pady=(12, 4))

        row = tk.Frame(tab, bg=BG)
        row.pack(fill="x", padx=12, pady=4)
        tk.Label(row, text="Input PDF:", bg=BG, fg=FG, font=FONT).pack(side="left")
        self.rotate_path = tk.StringVar()
        tk.Entry(row, textvariable=self.rotate_path, bg=BG2, fg=FG, font=FONT,
                 insertbackground=FG, borderwidth=1, relief="solid").pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(row, text="Browse", command=lambda: self._browse_to(self.rotate_path),
                  bg=BG3, fg=FG, font=FONT_SM, borderwidth=0).pack(side="left")

        row2 = tk.Frame(tab, bg=BG)
        row2.pack(fill="x", padx=12, pady=8)
        tk.Label(row2, text="Rotation:", bg=BG, fg=FG, font=FONT).pack(side="left")
        self.rotate_angle = tk.IntVar(value=90)
        for angle in (90, 180, 270):
            tk.Radiobutton(row2, text=f"{angle}°", variable=self.rotate_angle, value=angle,
                           bg=BG, fg=FG, selectcolor=BG2, font=FONT, activebackground=BG).pack(side="left", padx=8)

        row3 = tk.Frame(tab, bg=BG)
        row3.pack(fill="x", padx=12, pady=4)
        tk.Label(row3, text="Pages (empty=all):", bg=BG, fg=FG, font=FONT).pack(side="left")
        self.rotate_pages = tk.StringVar()
        tk.Entry(row3, textvariable=self.rotate_pages, bg=BG2, fg=FG, font=FONT,
                 insertbackground=FG, width=20, borderwidth=1, relief="solid").pack(side="left", padx=4)
        tk.Label(row3, text="e.g. 1,3-5", bg=BG, fg="#888", font=FONT_SM).pack(side="left")

        self._btn(tab, "🔄 Rotate Pages", self._do_rotate).pack(pady=8)

    def _do_rotate(self):
        src = self.rotate_path.get()
        if not src or not os.path.isfile(src):
            messagebox.showwarning("Rotate", "Select a valid PDF.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out:
            return
        self.status.set("Rotating...")
        self._run_async(self._rotate_worker, src, out)

    def _rotate_worker(self, src, out):
        reader = PdfReader(src)
        writer = PdfWriter()
        total = len(reader.pages)
        angle = self.rotate_angle.get()
        pages_str = self.rotate_pages.get().strip()
        target_pages = self._parse_range(pages_str, total) if pages_str else list(range(total))
        target_set = set(target_pages)

        for i, page in enumerate(reader.pages):
            if i in target_set:
                page.rotate(angle)
            writer.add_page(page)

        with open(out, "wb") as f:
            writer.write(f)
        self.after(0, lambda: self.status.set(f"Rotated {len(target_set)} pages by {angle}°"))

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB: Extract Text
    # ═══════════════════════════════════════════════════════════════════════════
    def _tab_text(self, nb):
        tab = self._make_tab(nb, "Text")
        tk.Label(tab, text="Extract text from PDF", bg=BG, fg=FG, font=FONT_BOLD).pack(pady=(12, 4))

        row = tk.Frame(tab, bg=BG)
        row.pack(fill="x", padx=12, pady=4)
        self.text_path = tk.StringVar()
        tk.Entry(row, textvariable=self.text_path, bg=BG2, fg=FG, font=FONT,
                 insertbackground=FG, borderwidth=1, relief="solid").pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(row, text="Browse", command=lambda: self._browse_to(self.text_path),
                  bg=BG3, fg=FG, font=FONT_SM, borderwidth=0).pack(side="left")

        btn_row = tk.Frame(tab, bg=BG)
        btn_row.pack(fill="x", padx=12, pady=4)
        self._btn(btn_row, "📋 Extract to Window", self._do_text_extract).pack(side="left", padx=4)
        self._btn(btn_row, "💾 Save as .txt", self._do_text_save).pack(side="left", padx=4)

        self.text_output = tk.Text(tab, bg=BG2, fg=FG, font=("Consolas", 10),
                                    insertbackground=FG, borderwidth=1, relief="solid", wrap="word")
        self.text_output.pack(fill="both", expand=True, padx=12, pady=(4, 8))

    def _extract_text(self, src):
        reader = PdfReader(src)
        texts = []
        for i, page in enumerate(reader.pages):
            t = page.extract_text() or ""
            texts.append(f"--- Page {i+1} ---\n{t}")
        return "\n\n".join(texts)

    def _do_text_extract(self):
        src = self.text_path.get()
        if not src or not os.path.isfile(src):
            messagebox.showwarning("Text", "Select a PDF.")
            return
        self.status.set("Extracting text...")
        def work():
            text = self._extract_text(src)
            self.after(0, lambda: self._show_text(text))
        self._run_async(work)

    def _show_text(self, text):
        self.text_output.delete("1.0", "end")
        self.text_output.insert("1.0", text)
        self.status.set("Text extracted")

    def _do_text_save(self):
        src = self.text_path.get()
        if not src or not os.path.isfile(src):
            messagebox.showwarning("Text", "Select a PDF.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if not out:
            return
        self.status.set("Extracting text...")
        def work():
            text = self._extract_text(src)
            with open(out, "w", encoding="utf-8") as f:
                f.write(text)
            self.after(0, lambda: self.status.set(f"Text saved → {os.path.basename(out)}"))
        self._run_async(work)

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB: Watermark
    # ═══════════════════════════════════════════════════════════════════════════
    def _tab_watermark(self, nb):
        tab = self._make_tab(nb, "Watermark")
        tk.Label(tab, text="Add text watermark to PDF", bg=BG, fg=FG, font=FONT_BOLD).pack(pady=(12, 4))

        row = tk.Frame(tab, bg=BG)
        row.pack(fill="x", padx=12, pady=4)
        tk.Label(row, text="Input PDF:", bg=BG, fg=FG, font=FONT).pack(side="left")
        self.wm_path = tk.StringVar()
        tk.Entry(row, textvariable=self.wm_path, bg=BG2, fg=FG, font=FONT,
                 insertbackground=FG, borderwidth=1, relief="solid").pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(row, text="Browse", command=lambda: self._browse_to(self.wm_path),
                  bg=BG3, fg=FG, font=FONT_SM, borderwidth=0).pack(side="left")

        row2 = tk.Frame(tab, bg=BG)
        row2.pack(fill="x", padx=12, pady=4)
        tk.Label(row2, text="Watermark text:", bg=BG, fg=FG, font=FONT).pack(side="left")
        self.wm_text = tk.StringVar(value="CONFIDENTIAL")
        tk.Entry(row2, textvariable=self.wm_text, bg=BG2, fg=FG, font=FONT,
                 insertbackground=FG, borderwidth=1, relief="solid").pack(side="left", fill="x", expand=True, padx=4)

        row3 = tk.Frame(tab, bg=BG)
        row3.pack(fill="x", padx=12, pady=4)
        tk.Label(row3, text="Opacity:", bg=BG, fg=FG, font=FONT).pack(side="left")
        self.wm_opacity = tk.IntVar(value=30)
        ttk.Scale(row3, from_=5, to=100, variable=self.wm_opacity,
                  orient="horizontal").pack(side="left", fill="x", expand=True, padx=4)
        tk.Label(row3, text="Font size:", bg=BG, fg=FG, font=FONT).pack(side="left", padx=(8, 0))
        self.wm_fontsize = tk.IntVar(value=60)
        tk.Spinbox(row3, from_=10, to=200, textvariable=self.wm_fontsize, width=5,
                   bg=BG2, fg=FG, font=FONT, borderwidth=1, relief="solid").pack(side="left", padx=4)

        self._btn(tab, "💧 Add Watermark", self._do_watermark).pack(pady=8)

    def _do_watermark(self):
        if rl_canvas is None:
            messagebox.showerror("Watermark", "reportlab is required for watermarks.")
            return
        src = self.wm_path.get()
        if not src or not os.path.isfile(src):
            messagebox.showwarning("Watermark", "Select a PDF.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out:
            return
        self.status.set("Adding watermark...")
        self._run_async(self._watermark_worker, src, out)

    def _watermark_worker(self, src, out):
        reader = PdfReader(src)
        writer = PdfWriter()
        text = self.wm_text.get()
        opacity = self.wm_opacity.get() / 100.0
        fontsize = self.wm_fontsize.get()

        # Create watermark PDF in memory
        buf = io.BytesIO()
        page0 = reader.pages[0]
        w = float(page0.mediabox.width)
        h = float(page0.mediabox.height)
        c = rl_canvas.Canvas(buf, pagesize=(w, h))
        c.saveState()
        c.setFont("Helvetica-Bold", fontsize)
        c.setFillColorRGB(0.5, 0.5, 0.5, opacity)
        c.translate(w / 2, h / 2)
        c.rotate(45)
        c.drawCentredString(0, 0, text)
        c.restoreState()
        c.save()
        buf.seek(0)
        wm_reader = PdfReader(buf)
        wm_page = wm_reader.pages[0]

        for page in reader.pages:
            page.merge_page(wm_page)
            writer.add_page(page)

        with open(out, "wb") as f:
            writer.write(f)

        self.after(0, lambda: self.status.set(f"Watermark added → {os.path.basename(out)}"))

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB: Security
    # ═══════════════════════════════════════════════════════════════════════════
    def _tab_security(self, nb):
        tab = self._make_tab(nb, "Security")
        tk.Label(tab, text="Password protect / remove password", bg=BG, fg=FG, font=FONT_BOLD).pack(pady=(12, 4))

        # Encrypt
        f1 = tk.LabelFrame(tab, text=" 🔒 Encrypt PDF ", bg=BG, fg=ACCENT, font=FONT_BOLD,
                           borderwidth=1, relief="solid")
        f1.pack(fill="x", padx=12, pady=4)

        row = tk.Frame(f1, bg=BG)
        row.pack(fill="x", padx=8, pady=4)
        self.enc_path = tk.StringVar()
        tk.Entry(row, textvariable=self.enc_path, bg=BG2, fg=FG, font=FONT,
                 insertbackground=FG, borderwidth=1, relief="solid").pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(row, text="Browse", command=lambda: self._browse_to(self.enc_path),
                  bg=BG3, fg=FG, font=FONT_SM, borderwidth=0).pack(side="left")

        row2 = tk.Frame(f1, bg=BG)
        row2.pack(fill="x", padx=8, pady=(0, 4))
        tk.Label(row2, text="Password:", bg=BG, fg=FG, font=FONT).pack(side="left")
        self.enc_pw = tk.StringVar()
        tk.Entry(row2, textvariable=self.enc_pw, bg=BG2, fg=FG, font=FONT, show="•",
                 insertbackground=FG, borderwidth=1, relief="solid").pack(side="left", fill="x", expand=True, padx=4)
        self._btn(row2, "Encrypt", self._do_encrypt).pack(side="right", padx=4)

        # Decrypt
        f2 = tk.LabelFrame(tab, text=" 🔓 Remove Password ", bg=BG, fg=ACCENT, font=FONT_BOLD,
                           borderwidth=1, relief="solid")
        f2.pack(fill="x", padx=12, pady=4)

        row = tk.Frame(f2, bg=BG)
        row.pack(fill="x", padx=8, pady=4)
        self.dec_path = tk.StringVar()
        tk.Entry(row, textvariable=self.dec_path, bg=BG2, fg=FG, font=FONT,
                 insertbackground=FG, borderwidth=1, relief="solid").pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(row, text="Browse", command=lambda: self._browse_to(self.dec_path),
                  bg=BG3, fg=FG, font=FONT_SM, borderwidth=0).pack(side="left")

        row2 = tk.Frame(f2, bg=BG)
        row2.pack(fill="x", padx=8, pady=(0, 4))
        tk.Label(row2, text="Password:", bg=BG, fg=FG, font=FONT).pack(side="left")
        self.dec_pw = tk.StringVar()
        tk.Entry(row2, textvariable=self.dec_pw, bg=BG2, fg=FG, font=FONT, show="•",
                 insertbackground=FG, borderwidth=1, relief="solid").pack(side="left", fill="x", expand=True, padx=4)
        self._btn(row2, "Decrypt", self._do_decrypt).pack(side="right", padx=4)

    def _do_encrypt(self):
        src = self.enc_path.get()
        pw = self.enc_pw.get()
        if not src or not os.path.isfile(src):
            messagebox.showwarning("Encrypt", "Select a PDF.")
            return
        if not pw:
            messagebox.showwarning("Encrypt", "Enter a password.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out:
            return
        self.status.set("Encrypting...")
        self._run_async(self._encrypt_worker, src, out, pw)

    def _encrypt_worker(self, src, out, pw):
        if pikepdf:
            pdf = pikepdf.Pdf.open(src)
            pdf.save(out, encryption=pikepdf.Encryption(owner=pw, user=pw, R=6))
            pdf.close()
        else:
            reader = PdfReader(src)
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            writer.encrypt(pw)
            with open(out, "wb") as f:
                writer.write(f)
        self.after(0, lambda: self.status.set(f"Encrypted → {os.path.basename(out)}"))

    def _do_decrypt(self):
        src = self.dec_path.get()
        pw = self.dec_pw.get()
        if not src or not os.path.isfile(src):
            messagebox.showwarning("Decrypt", "Select a PDF.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out:
            return
        self.status.set("Decrypting...")
        self._run_async(self._decrypt_worker, src, out, pw)

    def _decrypt_worker(self, src, out, pw):
        if pikepdf:
            pdf = pikepdf.Pdf.open(src, password=pw)
            pdf.save(out)
            pdf.close()
        else:
            reader = PdfReader(src)
            if reader.is_encrypted:
                reader.decrypt(pw)
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            with open(out, "wb") as f:
                writer.write(f)
        self.after(0, lambda: self.status.set(f"Decrypted → {os.path.basename(out)}"))


def main():
    # Check deps
    missing = []
    if PdfReader is None:
        missing.append("PyPDF2")
    if pikepdf is None:
        missing.append("pikepdf")
    if Image is None:
        missing.append("Pillow")
    if missing:
        print(f"⚠ Optional dependencies not found: {', '.join(missing)}")
        print("  Install with: pip install " + " ".join(missing))

    app = PDFToolsApp()
    app.mainloop()


if __name__ == "__main__":
    main()
