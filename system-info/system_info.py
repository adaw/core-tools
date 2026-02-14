#!/usr/bin/env python3
"""
CORE SYSTEMS — System Info v1.0
Real-time hardware/software dashboard with export & benchmark.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import psutil
import platform
import socket
import uuid
import json
import time
import os
import subprocess
import threading
import math
from datetime import datetime
from collections import deque

# ── Theme ──────────────────────────────────────────────────────────────
BG = "#0d1117"
BG2 = "#161b22"
BG3 = "#21262d"
FG = "#c9d1d9"
FG_DIM = "#8b949e"
GREEN = "#00ff88"
GREEN_DIM = "#00cc6a"
RED = "#ff6b6b"
YELLOW = "#ffd866"
CYAN = "#79c0ff"
FONT = ("SF Mono", 11) if platform.system() == "Darwin" else ("Consolas", 10)
FONT_SM = (FONT[0], 9)
FONT_LG = (FONT[0], 13, "bold")
FONT_XL = (FONT[0], 18, "bold")

HISTORY_LEN = 60  # seconds of graph history


# ── Helpers ────────────────────────────────────────────────────────────
def safe(fn, default="N/A"):
    try:
        v = fn()
        return v if v is not None else default
    except Exception:
        return default


def fmt_bytes(b):
    if b is None:
        return "N/A"
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if abs(b) < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"


def fmt_freq(mhz):
    if mhz is None or mhz == 0:
        return "N/A"
    if mhz >= 1000:
        return f"{mhz/1000:.2f} GHz"
    return f"{mhz:.0f} MHz"


# ── Data Collectors ────────────────────────────────────────────────────
def get_cpu_info():
    freq = psutil.cpu_freq()
    info = {
        "model": platform.processor() or "Unknown",
        "arch": platform.machine(),
        "cores_physical": psutil.cpu_count(logical=False) or 0,
        "cores_logical": psutil.cpu_count(logical=True) or 0,
        "freq_current": freq.current if freq else 0,
        "freq_max": freq.max if freq else 0,
        "usage_percent": psutil.cpu_percent(interval=0),
        "per_core": psutil.cpu_percent(percpu=True),
    }
    # Temperature
    temps = safe(lambda: psutil.sensors_temperatures(), {})
    if temps:
        for name in ["coretemp", "cpu_thermal", "cpu-thermal", "k10temp"]:
            if name in temps and temps[name]:
                info["temp"] = temps[name][0].current
                break
        if "temp" not in info:
            first = list(temps.values())[0]
            if first:
                info["temp"] = first[0].current
    return info


def get_ram_info():
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    return {
        "total": vm.total,
        "used": vm.used,
        "available": vm.available,
        "percent": vm.percent,
        "swap_total": sw.total,
        "swap_used": sw.used,
        "swap_percent": sw.percent,
    }


def get_disk_info():
    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mount": part.mountpoint,
                "fstype": part.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            })
        except (PermissionError, OSError):
            pass
    # IO counters
    io = safe(lambda: psutil.disk_io_counters(), None)
    return {"partitions": disks, "io": io}


def get_gpu_info():
    gpus = []
    # macOS — system_profiler
    if platform.system() == "Darwin":
        try:
            out = subprocess.check_output(
                ["system_profiler", "SPDisplaysDataType", "-json"],
                timeout=5, text=True
            )
            data = json.loads(out)
            for item in data.get("SPDisplaysDataType", []):
                gpus.append({
                    "name": item.get("sppci_model", "Unknown"),
                    "vram": item.get("spdisplays_vram", "N/A"),
                    "vendor": item.get("sppci_vendor", ""),
                })
        except Exception:
            pass
    # Linux — lspci
    if not gpus and platform.system() == "Linux":
        try:
            out = subprocess.check_output(["lspci"], timeout=5, text=True)
            for line in out.splitlines():
                if "VGA" in line or "3D" in line or "Display" in line:
                    gpus.append({"name": line.split(": ", 1)[-1], "vram": "N/A", "vendor": ""})
        except Exception:
            pass
    # nvidia-smi
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,temperature.gpu,utilization.gpu",
             "--format=csv,noheader,nounits"],
            timeout=5, text=True
        )
        gpus = []
        for line in out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            gpus.append({
                "name": parts[0],
                "vram": f"{parts[1]} MB" if len(parts) > 1 else "N/A",
                "temp": parts[2] if len(parts) > 2 else None,
                "usage": parts[3] if len(parts) > 3 else None,
            })
    except Exception:
        pass
    return gpus or [{"name": "Integrated / Unknown", "vram": "N/A"}]


def get_network_info():
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    nets = []
    for iface, addr_list in addrs.items():
        if iface.startswith("lo") or iface.startswith("veth"):
            continue
        info = {"name": iface, "ip": "", "mac": "", "speed": 0, "up": False}
        for a in addr_list:
            if a.family == socket.AF_INET:
                info["ip"] = a.address
            if a.family == psutil.AF_LINK:
                info["mac"] = a.address
        if iface in stats:
            info["speed"] = stats[iface].speed
            info["up"] = stats[iface].isup
        if info["ip"] or info["up"]:
            nets.append(info)
    return nets


def get_os_info():
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "hostname": socket.gethostname(),
        "python": platform.python_version(),
        "boot_time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_battery_info():
    bat = safe(lambda: psutil.sensors_battery(), None)
    if bat is None:
        return None
    return {
        "percent": bat.percent,
        "plugged": bat.power_plugged,
        "secs_left": bat.secsleft if bat.secsleft != psutil.POWER_TIME_UNLIMITED else -1,
    }


def get_top_processes(sort_by="cpu", n=10):
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = p.info
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    procs.sort(key=lambda x: x.get(key, 0) or 0, reverse=True)
    return procs[:n]


# ── Mini Canvas Graph ──────────────────────────────────────────────────
class MiniGraph(tk.Canvas):
    """Tiny real-time line graph on a Canvas."""

    def __init__(self, parent, width=200, height=50, color=GREEN, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=BG2, highlightthickness=0, **kw)
        self.w = width
        self.h = height
        self.color = color
        self.data = deque([0.0] * HISTORY_LEN, maxlen=HISTORY_LEN)

    def push(self, value):
        self.data.append(max(0, min(100, value)))
        self._redraw()

    def _redraw(self):
        self.delete("all")
        n = len(self.data)
        if n < 2:
            return
        dx = self.w / (n - 1)
        points = []
        for i, v in enumerate(self.data):
            x = i * dx
            y = self.h - (v / 100.0) * (self.h - 4) - 2
            points.append((x, y))
        # Fill
        fill_pts = [(0, self.h)] + points + [(self.w, self.h)]
        flat = [c for p in fill_pts for c in p]
        self.create_polygon(flat, fill=self.color + "18", outline="")
        # Line
        flat_line = [c for p in points for c in p]
        if len(flat_line) >= 4:
            self.create_line(flat_line, fill=self.color, width=1.5, smooth=True)
        # Current value text
        val = self.data[-1]
        self.create_text(self.w - 4, 4, text=f"{val:.0f}%",
                         fill=self.color, font=FONT_SM, anchor="ne")


# ── Benchmark ──────────────────────────────────────────────────────────
def benchmark_cpu():
    """Simple CPU benchmark — compute pi digits."""
    start = time.perf_counter()
    s = 0.0
    for k in range(200000):
        s += (-1) ** k / (2 * k + 1)
    elapsed = time.perf_counter() - start
    score = int(10000 / elapsed)
    return {"time": f"{elapsed:.3f}s", "score": score, "ops": "200k iterations"}


def benchmark_disk():
    """Disk write/read speed test with 64MB file."""
    import tempfile
    size = 64 * 1024 * 1024
    data = os.urandom(size)
    path = os.path.join(tempfile.gettempdir(), "core_bench.tmp")
    # Write
    start = time.perf_counter()
    with open(path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    w_time = time.perf_counter() - start
    # Read
    start = time.perf_counter()
    with open(path, "rb") as f:
        _ = f.read()
    r_time = time.perf_counter() - start
    try:
        os.remove(path)
    except OSError:
        pass
    return {
        "write_speed": fmt_bytes(size / w_time) + "/s",
        "read_speed": fmt_bytes(size / r_time) + "/s",
        "file_size": "64 MB",
    }


# ── Export ─────────────────────────────────────────────────────────────
def collect_report():
    return {
        "timestamp": datetime.now().isoformat(),
        "os": get_os_info(),
        "cpu": get_cpu_info(),
        "ram": get_ram_info(),
        "disks": get_disk_info(),
        "gpu": get_gpu_info(),
        "network": get_network_info(),
        "battery": get_battery_info(),
        "top_processes": get_top_processes(),
    }


def export_json(data, path):
    # Clean non-serializable
    def clean(obj):
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [clean(i) for i in obj]
        if isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        return str(obj)
    with open(path, "w") as f:
        json.dump(clean(data), f, indent=2)


def export_txt(data, path):
    lines = []
    lines.append("=" * 60)
    lines.append("  CORE SYSTEMS — System Info Report")
    lines.append(f"  Generated: {data['timestamp']}")
    lines.append("=" * 60)

    def section(title, items):
        lines.append(f"\n── {title} {'─' * (50 - len(title))}")
        for k, v in items:
            lines.append(f"  {k:<24} {v}")

    o = data["os"]
    section("Operating System", [
        ("System", f"{o['system']} {o['release']}"),
        ("Version", o["version"]),
        ("Hostname", o["hostname"]),
        ("Boot Time", o["boot_time"]),
    ])
    c = data["cpu"]
    section("CPU", [
        ("Model", c["model"]),
        ("Cores", f"{c['cores_physical']}P / {c['cores_logical']}L"),
        ("Frequency", fmt_freq(c["freq_current"])),
        ("Usage", f"{c['usage_percent']}%"),
    ])
    r = data["ram"]
    section("Memory", [
        ("Total", fmt_bytes(r["total"])),
        ("Used", f"{fmt_bytes(r['used'])} ({r['percent']}%)"),
        ("Swap", f"{fmt_bytes(r['swap_used'])} / {fmt_bytes(r['swap_total'])}"),
    ])
    for d in data["disks"]["partitions"]:
        section(f"Disk: {d['mount']}", [
            ("Device", d["device"]),
            ("Type", d["fstype"]),
            ("Size", fmt_bytes(d["total"])),
            ("Used", f"{fmt_bytes(d['used'])} ({d['percent']}%)"),
            ("Free", fmt_bytes(d["free"])),
        ])
    for g in data["gpu"]:
        section("GPU", [
            ("Name", g.get("name", "N/A")),
            ("VRAM", g.get("vram", "N/A")),
        ])
    lines.append("\n" + "=" * 60)
    with open(path, "w") as f:
        f.write("\n".join(lines))


def export_html(data, path):
    c = data["cpu"]
    r = data["ram"]
    o = data["os"]
    rows = ""
    def row(label, val):
        return f"<tr><td style='color:#8b949e;padding:4px 12px'>{label}</td><td style='padding:4px 12px;color:#c9d1d9'>{val}</td></tr>"

    rows += row("OS", f"{o['system']} {o['release']}")
    rows += row("Hostname", o["hostname"])
    rows += row("CPU", c["model"])
    rows += row("Cores", f"{c['cores_physical']}P / {c['cores_logical']}L")
    rows += row("Frequency", fmt_freq(c["freq_current"]))
    rows += row("CPU Usage", f"{c['usage_percent']}%")
    rows += row("RAM", f"{fmt_bytes(r['used'])} / {fmt_bytes(r['total'])} ({r['percent']}%)")
    rows += row("Swap", f"{fmt_bytes(r['swap_used'])} / {fmt_bytes(r['swap_total'])}")
    for d in data["disks"]["partitions"]:
        rows += row(f"Disk {d['mount']}", f"{fmt_bytes(d['used'])} / {fmt_bytes(d['total'])} ({d['percent']}%)")
    for g in data["gpu"]:
        rows += row("GPU", g.get("name", "N/A"))

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>CORE System Info Report</title></head>
<body style="background:#0d1117;color:#c9d1d9;font-family:monospace;padding:40px">
<h1 style="color:#00ff88">⬡ CORE SYSTEMS — System Report</h1>
<p style="color:#8b949e">{data['timestamp']}</p>
<table style="border-collapse:collapse">{rows}</table>
<hr style="border-color:#21262d;margin:20px 0">
<p style="color:#8b949e;font-size:12px">Generated by CORE System Info v1.0</p>
</body></html>"""
    with open(path, "w") as f:
        f.write(html)


# ── Main App ───────────────────────────────────────────────────────────
class SystemInfoApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CORE System Info")
        self.root.configure(bg=BG)
        self.root.geometry("980x720")
        self.root.minsize(800, 600)

        # History for graphs
        self.cpu_history = deque([0.0] * HISTORY_LEN, maxlen=HISTORY_LEN)
        self.ram_history = deque([0.0] * HISTORY_LEN, maxlen=HISTORY_LEN)
        self.net_sent_prev = 0
        self.net_recv_prev = 0

        self._build_ui()
        self._update_loop()
        self.root.mainloop()

    def _build_ui(self):
        # ── Header ──
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(hdr, text="⬡", font=(FONT[0], 24), fg=GREEN, bg=BG).pack(side="left")
        tk.Label(hdr, text=" CORE SYSTEMS", font=FONT_XL, fg=GREEN, bg=BG).pack(side="left")
        tk.Label(hdr, text="  System Info v1.0", font=FONT, fg=FG_DIM, bg=BG).pack(side="left")

        # Buttons
        btn_frame = tk.Frame(hdr, bg=BG)
        btn_frame.pack(side="right")
        for text, cmd in [("Export", self._export), ("Benchmark", self._benchmark), ("Refresh", self._refresh)]:
            b = tk.Button(btn_frame, text=text, command=cmd,
                          bg=BG3, fg=GREEN, activebackground=GREEN_DIM, activeforeground=BG,
                          font=FONT_SM, bd=0, padx=12, pady=4, cursor="hand2")
            b.pack(side="left", padx=3)

        # ── Notebook ──
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG2, foreground=FG_DIM,
                         padding=[14, 6], font=FONT_SM)
        style.map("TNotebook.Tab",
                   background=[("selected", BG3)],
                   foreground=[("selected", GREEN)])

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=12, pady=8)

        # Tabs
        self.tab_overview = self._make_tab("Overview")
        self.tab_cpu = self._make_tab("CPU")
        self.tab_memory = self._make_tab("Memory")
        self.tab_disks = self._make_tab("Disks")
        self.tab_network = self._make_tab("Network")
        self.tab_procs = self._make_tab("Processes")

        self._build_overview()
        self._build_cpu_tab()
        self._build_memory_tab()
        self._build_disk_tab()
        self._build_network_tab()
        self._build_procs_tab()

        # Status bar
        self.status = tk.Label(self.root, text="Ready", font=FONT_SM, fg=FG_DIM, bg=BG, anchor="w")
        self.status.pack(fill="x", padx=16, pady=(0, 8))

    def _make_tab(self, title):
        frame = tk.Frame(self.nb, bg=BG)
        self.nb.add(frame, text=f"  {title}  ")
        return frame

    def _make_card(self, parent, title, row=0, col=0, colspan=1, rowspan=1):
        card = tk.Frame(parent, bg=BG2, highlightbackground=BG3, highlightthickness=1)
        card.grid(row=row, column=col, columnspan=colspan, rowspan=rowspan,
                  padx=4, pady=4, sticky="nsew")
        tk.Label(card, text=title, font=FONT_LG, fg=GREEN, bg=BG2, anchor="w").pack(
            fill="x", padx=10, pady=(8, 4))
        content = tk.Frame(card, bg=BG2)
        content.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        return content

    def _lbl(self, parent, text, fg=FG, font=None):
        l = tk.Label(parent, text=text, fg=fg, bg=BG2, font=font or FONT_SM, anchor="w")
        l.pack(fill="x")
        return l

    # ── Overview Tab ──
    def _build_overview(self):
        tab = self.tab_overview
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        for r in range(3):
            tab.rowconfigure(r, weight=1)

        # OS card
        c = self._make_card(tab, "System", 0, 0)
        self.ov_os = self._lbl(c, "Loading...")

        # CPU card
        c = self._make_card(tab, "CPU", 0, 1)
        self.ov_cpu_lbl = self._lbl(c, "Loading...")
        self.ov_cpu_graph = MiniGraph(c, width=280, height=45)
        self.ov_cpu_graph.pack(fill="x", pady=(4, 0))

        # RAM card
        c = self._make_card(tab, "Memory", 1, 0)
        self.ov_ram_lbl = self._lbl(c, "Loading...")
        self.ov_ram_graph = MiniGraph(c, width=280, height=45, color=CYAN)
        self.ov_ram_graph.pack(fill="x", pady=(4, 0))

        # GPU card
        c = self._make_card(tab, "GPU", 1, 1)
        self.ov_gpu = self._lbl(c, "Loading...")

        # Battery card
        c = self._make_card(tab, "Battery", 2, 0)
        self.ov_bat = self._lbl(c, "Checking...")

        # Network card
        c = self._make_card(tab, "Network", 2, 1)
        self.ov_net = self._lbl(c, "Loading...")

    # ── CPU Tab ──
    def _build_cpu_tab(self):
        tab = self.tab_cpu
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        c = self._make_card(tab, "CPU Details", 0, 0)
        self.cpu_detail = self._lbl(c, "Loading...")

        c = self._make_card(tab, "Per-Core Usage", 1, 0)
        self.cpu_cores_frame = c

    # ── Memory Tab ──
    def _build_memory_tab(self):
        tab = self.tab_memory
        tab.columnconfigure(0, weight=1)
        c = self._make_card(tab, "RAM & Swap", 0, 0)
        self.mem_detail = self._lbl(c, "Loading...")
        self.mem_graph = MiniGraph(c, width=500, height=60, color=CYAN)
        self.mem_graph.pack(fill="x", pady=(6, 0))

    # ── Disk Tab ──
    def _build_disk_tab(self):
        tab = self.tab_disks
        tab.columnconfigure(0, weight=1)
        c = self._make_card(tab, "Storage", 0, 0)
        self.disk_detail = self._lbl(c, "Loading...")

    # ── Network Tab ──
    def _build_network_tab(self):
        tab = self.tab_network
        tab.columnconfigure(0, weight=1)
        c = self._make_card(tab, "Interfaces", 0, 0)
        self.net_detail = self._lbl(c, "Loading...")
        c2 = self._make_card(tab, "Bandwidth", 1, 0)
        self.net_bw = self._lbl(c2, "Measuring...")

    # ── Processes Tab ──
    def _build_procs_tab(self):
        tab = self.tab_procs
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)

        c = self._make_card(tab, "Top Processes (by CPU)", 0, 0)
        self.proc_text = tk.Text(c, bg=BG2, fg=FG, font=FONT_SM,
                                  bd=0, highlightthickness=0, wrap="none")
        self.proc_text.pack(fill="both", expand=True)

    # ── Update Loop ──
    def _update_loop(self):
        try:
            self._refresh_data()
        except Exception as e:
            self.status.config(text=f"Error: {e}")
        self.root.after(2000, self._update_loop)

    def _refresh_data(self):
        now = datetime.now().strftime("%H:%M:%S")

        # CPU
        cpu = get_cpu_info()
        usage = cpu["usage_percent"]
        self.ov_cpu_lbl.config(text=f"{cpu['model']}\n{cpu['cores_physical']}P/{cpu['cores_logical']}L cores  •  {fmt_freq(cpu['freq_current'])}  •  {usage:.0f}%"
                               + (f"  •  {cpu.get('temp', '')}°C" if 'temp' in cpu else ""))
        self.ov_cpu_graph.push(usage)

        self.cpu_detail.config(
            text=f"Model: {cpu['model']}\n"
                 f"Arch: {cpu['arch']}\n"
                 f"Cores: {cpu['cores_physical']} physical / {cpu['cores_logical']} logical\n"
                 f"Frequency: {fmt_freq(cpu['freq_current'])} (max {fmt_freq(cpu['freq_max'])})\n"
                 f"Usage: {usage:.1f}%"
                 + (f"\nTemperature: {cpu['temp']:.0f}°C" if 'temp' in cpu else "")
        )

        # Per-core bars
        for w in self.cpu_cores_frame.winfo_children():
            w.destroy()
        per_core = cpu.get("per_core", [])
        cols = min(8, len(per_core)) if per_core else 1
        for i, pct in enumerate(per_core):
            r, c = divmod(i, cols)
            color = GREEN if pct < 60 else YELLOW if pct < 85 else RED
            lbl = tk.Label(self.cpu_cores_frame, text=f"C{i}: {pct:4.0f}%",
                           fg=color, bg=BG2, font=FONT_SM)
            lbl.grid(row=r, column=c, padx=4, pady=1, sticky="w")

        # RAM
        ram = get_ram_info()
        self.ov_ram_lbl.config(
            text=f"{fmt_bytes(ram['used'])} / {fmt_bytes(ram['total'])} ({ram['percent']}%)\n"
                 f"Swap: {fmt_bytes(ram['swap_used'])} / {fmt_bytes(ram['swap_total'])}"
        )
        self.ov_ram_graph.push(ram["percent"])
        self.mem_detail.config(
            text=f"Total: {fmt_bytes(ram['total'])}\n"
                 f"Used: {fmt_bytes(ram['used'])} ({ram['percent']}%)\n"
                 f"Available: {fmt_bytes(ram['available'])}\n"
                 f"Swap: {fmt_bytes(ram['swap_used'])} / {fmt_bytes(ram['swap_total'])} ({ram['swap_percent']}%)"
        )
        self.mem_graph.push(ram["percent"])

        # GPU (less frequent)
        gpus = get_gpu_info()
        gpu_lines = []
        for g in gpus:
            line = g.get("name", "?")
            if g.get("vram") and g["vram"] != "N/A":
                line += f" — {g['vram']}"
            if g.get("temp"):
                line += f" — {g['temp']}°C"
            gpu_lines.append(line)
        self.ov_gpu.config(text="\n".join(gpu_lines))

        # Battery
        bat = get_battery_info()
        if bat:
            plug = "⚡ Charging" if bat["plugged"] else "🔋 On Battery"
            secs = bat["secs_left"]
            time_left = ""
            if secs and secs > 0:
                h, m = divmod(secs // 60, 60)
                time_left = f" — {int(h)}h {int(m)}m left"
            self.ov_bat.config(text=f"{bat['percent']}%  {plug}{time_left}")
        else:
            self.ov_bat.config(text="No battery detected (desktop)")

        # OS
        osi = get_os_info()
        self.ov_os.config(
            text=f"{osi['system']} {osi['release']}\n"
                 f"Host: {osi['hostname']}\n"
                 f"Boot: {osi['boot_time']}\n"
                 f"Python: {osi['python']}"
        )

        # Disks
        dinfo = get_disk_info()
        lines = []
        for d in dinfo["partitions"]:
            bar_len = 20
            filled = int(d["percent"] / 100 * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            lines.append(f"{d['mount']:<20} [{bar}] {d['percent']:5.1f}%  "
                         f"{fmt_bytes(d['used'])} / {fmt_bytes(d['total'])}  ({d['fstype']})")
        if dinfo["io"]:
            io = dinfo["io"]
            lines.append(f"\nI/O: Read {fmt_bytes(io.read_bytes)} / Write {fmt_bytes(io.write_bytes)}")
        self.disk_detail.config(text="\n".join(lines))

        # Network
        nets = get_network_info()
        lines = []
        for n in nets:
            status = "▲" if n["up"] else "▼"
            speed = f"{n['speed']} Mbps" if n["speed"] else "N/A"
            lines.append(f"{status} {n['name']:<16} IP: {n['ip'] or 'N/A':<16} MAC: {n['mac'] or 'N/A':<18} Speed: {speed}")
        self.net_detail.config(text="\n".join(lines) if lines else "No active interfaces")

        # Bandwidth
        counters = psutil.net_io_counters()
        if self.net_sent_prev:
            sent_rate = (counters.bytes_sent - self.net_sent_prev) / 2
            recv_rate = (counters.bytes_recv - self.net_recv_prev) / 2
            self.net_bw.config(text=f"↑ {fmt_bytes(sent_rate)}/s   ↓ {fmt_bytes(recv_rate)}/s\n"
                                    f"Total sent: {fmt_bytes(counters.bytes_sent)}  •  Total recv: {fmt_bytes(counters.bytes_recv)}")
        self.net_sent_prev = counters.bytes_sent
        self.net_recv_prev = counters.bytes_recv

        # Processes
        procs = get_top_processes()
        self.proc_text.config(state="normal")
        self.proc_text.delete("1.0", "end")
        header = f"{'PID':<8} {'Name':<30} {'CPU%':>6} {'MEM%':>6}\n{'─'*54}\n"
        self.proc_text.insert("end", header)
        for p in procs:
            self.proc_text.insert("end",
                f"{p['pid']:<8} {(p['name'] or '?')[:28]:<30} {(p['cpu_percent'] or 0):>5.1f}% {(p['memory_percent'] or 0):>5.1f}%\n")
        self.proc_text.config(state="disabled")

        self.status.config(text=f"Last update: {now}")

    def _refresh(self):
        self.status.config(text="Refreshing...")
        self._refresh_data()

    def _export(self):
        data = collect_report()
        path = filedialog.asksaveasfilename(
            title="Export Report",
            filetypes=[("JSON", "*.json"), ("HTML", "*.html"), ("Text", "*.txt")],
            defaultextension=".json"
        )
        if not path:
            return
        try:
            if path.endswith(".json"):
                export_json(data, path)
            elif path.endswith(".html"):
                export_html(data, path)
            else:
                export_txt(data, path)
            self.status.config(text=f"Exported to {path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _benchmark(self):
        self.status.config(text="Running benchmark...")
        self.root.update()

        def run():
            cpu_r = benchmark_cpu()
            disk_r = benchmark_disk()
            result = (
                f"── CPU Benchmark ──\n"
                f"  {cpu_r['ops']} in {cpu_r['time']}\n"
                f"  Score: {cpu_r['score']}\n\n"
                f"── Disk Benchmark (64 MB) ──\n"
                f"  Write: {disk_r['write_speed']}\n"
                f"  Read:  {disk_r['read_speed']}"
            )
            self.root.after(0, lambda: (
                messagebox.showinfo("Benchmark Results", result),
                self.status.config(text="Benchmark complete")
            ))

        threading.Thread(target=run, daemon=True).start()


if __name__ == "__main__":
    SystemInfoApp()
