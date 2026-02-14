#!/usr/bin/env python3
"""
CORE Screen Recorder — Record your screen without watermarks.
Part of CORE SYSTEMS free utility suite.

Features: fullscreen/region/window capture, FPS selection, audio recording,
          MP4/MKV/GIF output, global hotkeys, countdown timer, cursor highlight,
          preview, simple trim, auto-save.
"""

import os
import sys
import time
import json
import threading
import datetime
import tempfile
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path

try:
    import mss
    import mss.tools
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import pyaudio
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

try:
    import wave
    HAS_WAVE = True
except ImportError:
    HAS_WAVE = False

try:
    from pynput import keyboard as pynput_kb
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

try:
    from PIL import Image, ImageTk, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_NAME = "CORE Screen Recorder"
VERSION = "1.0.0"
BG_DARK = "#1a1a2e"
BG_PANEL = "#16213e"
BG_INPUT = "#0f3460"
FG_TEXT = "#e0e0e0"
ACCENT = "#00ff88"
ACCENT_DIM = "#00cc6a"
ACCENT_DARK = "#003d20"
RED = "#ff4444"
YELLOW = "#ffcc00"

DEFAULT_FPS = 30
DEFAULT_FORMAT = "MP4"
DEFAULT_SAVE_DIR = str(Path.home() / "Videos" / "CORE Recordings")

HOTKEY_START_STOP = "<ctrl>+<shift>+r"
HOTKEY_PAUSE = "<ctrl>+<shift>+p"

CONFIG_PATH = Path.home() / ".core-screen-recorder.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config():
    defaults = {
        "fps": DEFAULT_FPS,
        "format": DEFAULT_FORMAT,
        "save_dir": DEFAULT_SAVE_DIR,
        "cursor_highlight": True,
        "countdown": 3,
        "capture_mode": "fullscreen",
        "audio_system": False,
        "audio_mic": False,
        "hotkey_start": HOTKEY_START_STOP,
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                saved = json.load(f)
            defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def generate_filename(ext, save_dir):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(save_dir, f"recording_{ts}.{ext}")


def get_ffmpeg():
    """Find ffmpeg binary."""
    for name in ["ffmpeg"]:
        try:
            subprocess.run([name, "-version"], capture_output=True, check=True)
            return name
        except Exception:
            pass
    # bundled or PATH
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS if hasattr(sys, "_MEIPASS") else os.path.dirname(sys.executable)
        candidate = os.path.join(base, "ffmpeg")
        if sys.platform == "win32":
            candidate += ".exe"
        if os.path.isfile(candidate):
            return candidate
    return None


# ---------------------------------------------------------------------------
# Region Selector Overlay
# ---------------------------------------------------------------------------

class RegionSelector:
    """Transparent overlay to select a screen region."""

    def __init__(self, callback):
        self.callback = callback
        self.root = tk.Toplevel()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.3)
        self.root.configure(bg="black")
        self.root.attributes("-topmost", True)
        self.canvas = tk.Canvas(self.root, cursor="cross", bg="black",
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.start_x = self.start_y = 0
        self.rect = None
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>", lambda e: self.cancel())

    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline=ACCENT, width=2
        )

    def on_drag(self, event):
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y,
                               event.x, event.y)

    def on_release(self, event):
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        self.root.destroy()
        if (x2 - x1) > 10 and (y2 - y1) > 10:
            self.callback({"left": x1, "top": y1,
                           "width": x2 - x1, "height": y2 - y1})
        else:
            self.callback(None)

    def cancel(self):
        self.root.destroy()
        self.callback(None)


# ---------------------------------------------------------------------------
# Audio Recorder Thread
# ---------------------------------------------------------------------------

class AudioRecorder:
    """Records audio from microphone to a WAV file."""

    def __init__(self, output_path, device_index=None):
        self.output_path = output_path
        self.device_index = device_index
        self.recording = False
        self.paused = False
        self.frames = []
        self.thread = None
        self.pa = None
        self.stream = None
        self.sample_rate = 44100
        self.channels = 1
        self.chunk = 1024

    def start(self):
        if not HAS_AUDIO:
            return
        self.recording = True
        self.paused = False
        self.frames = []
        self.thread = threading.Thread(target=self._record, daemon=True)
        self.thread.start()

    def _record(self):
        try:
            self.pa = pyaudio.PyAudio()
            kwargs = {
                "format": pyaudio.paInt16,
                "channels": self.channels,
                "rate": self.sample_rate,
                "input": True,
                "frames_per_buffer": self.chunk,
            }
            if self.device_index is not None:
                kwargs["input_device_index"] = self.device_index
            self.stream = self.pa.open(**kwargs)
            while self.recording:
                if self.paused:
                    time.sleep(0.05)
                    continue
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                self.frames.append(data)
        except Exception:
            pass

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def stop(self):
        self.recording = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
        if self.pa:
            try:
                self.pa.terminate()
            except Exception:
                pass
        # Save WAV
        if self.frames and HAS_WAVE:
            try:
                wf = wave.open(self.output_path, "wb")
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(b"".join(self.frames))
                wf.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Screen Recording Engine
# ---------------------------------------------------------------------------

class RecordingEngine:
    """Captures screen frames using mss and writes with OpenCV."""

    def __init__(self, fps=30, region=None, cursor_highlight=False):
        self.fps = fps
        self.region = region  # dict with left,top,width,height or None for full
        self.cursor_highlight = cursor_highlight
        self.recording = False
        self.paused = False
        self.frames = []
        self.frame_times = []
        self.thread = None
        self._frame_count = 0
        self._start_time = 0

    def start(self):
        self.recording = True
        self.paused = False
        self.frames = []
        self.frame_times = []
        self._frame_count = 0
        self._start_time = time.time()
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _capture_loop(self):
        interval = 1.0 / self.fps
        sct = mss.mss()

        if self.region:
            monitor = self.region
        else:
            monitor = sct.monitors[0]  # all monitors combined

        while self.recording:
            loop_start = time.time()
            if self.paused:
                time.sleep(0.05)
                continue

            img = sct.grab(monitor)
            frame = np.array(img)
            # BGRA -> BGR
            frame = frame[:, :, :3]

            # cursor highlight
            if self.cursor_highlight and HAS_PIL:
                try:
                    import Quartz
                    loc = Quartz.NSEvent.mouseLocation()
                    screen_h = sct.monitors[0]["height"]
                    mx = int(loc.x) - monitor.get("left", 0)
                    my = screen_h - int(loc.y) - monitor.get("top", 0)
                    cv2.circle(frame, (mx, my), 20, (0, 255, 136), 2)
                    cv2.circle(frame, (mx, my), 20, (0, 255, 136, 80), -1)
                except Exception:
                    pass

            self.frames.append(frame)
            self.frame_times.append(time.time())
            self._frame_count += 1

            elapsed = time.time() - loop_start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def stop(self):
        self.recording = False
        if self.thread:
            self.thread.join(timeout=5)

    @property
    def duration(self):
        if self._frame_count > 0 and self.frame_times:
            return self.frame_times[-1] - self.frame_times[0]
        return 0

    def save(self, output_path, fmt="mp4", audio_path=None):
        """Save recorded frames to file. Returns True on success."""
        if not self.frames:
            return False

        h, w = self.frames[0].shape[:2]
        # Make dimensions even (required by most codecs)
        w = w if w % 2 == 0 else w - 1
        h = h if h % 2 == 0 else h - 1

        ext = fmt.lower()

        if ext == "gif":
            return self._save_gif(output_path, w, h)

        # Write raw video first, then mux with ffmpeg if audio
        ffmpeg = get_ffmpeg()

        if ext == "mkv":
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
        else:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        temp_video = output_path if not audio_path else output_path + ".tmp." + ext
        writer = cv2.VideoWriter(temp_video, fourcc, self.fps, (w, h))
        for frame in self.frames:
            f = frame[:h, :w]
            writer.write(f)
        writer.release()

        # Mux audio if available
        if audio_path and os.path.isfile(audio_path) and ffmpeg:
            try:
                cmd = [
                    ffmpeg, "-y",
                    "-i", temp_video,
                    "-i", audio_path,
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-shortest",
                    output_path
                ]
                subprocess.run(cmd, capture_output=True, check=True)
                os.remove(temp_video)
            except Exception:
                # fallback: just rename
                if os.path.exists(temp_video) and not os.path.exists(output_path):
                    os.rename(temp_video, output_path)
        elif temp_video != output_path:
            os.rename(temp_video, output_path)

        return os.path.isfile(output_path)

    def _save_gif(self, output_path, w, h):
        if not HAS_PIL:
            return False
        pil_frames = []
        step = max(1, len(self.frames) // 300)  # cap at 300 frames for GIF
        for i in range(0, len(self.frames), step):
            f = self.frames[i][:h, :w]
            rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
            pil_frames.append(Image.fromarray(rgb))
        if pil_frames:
            duration = int(1000 / self.fps) * step
            pil_frames[0].save(
                output_path, save_all=True, append_images=pil_frames[1:],
                duration=duration, loop=0, optimize=True
            )
            return True
        return False

    def trim(self, start_sec, end_sec):
        """Trim frames in-place."""
        if not self.frame_times:
            return
        t0 = self.frame_times[0]
        new_frames = []
        new_times = []
        for f, t in zip(self.frames, self.frame_times):
            elapsed = t - t0
            if start_sec <= elapsed <= end_sec:
                new_frames.append(f)
                new_times.append(t)
        self.frames = new_frames
        self.frame_times = new_times
        self._frame_count = len(self.frames)


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class ScreenRecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.configure(bg=BG_DARK)
        self.root.minsize(520, 680)
        self.root.resizable(True, True)

        self.cfg = load_config()
        self.engine = None
        self.audio_rec = None
        self.is_recording = False
        self.is_paused = False
        self.selected_region = None
        self.timer_id = None
        self.elapsed = 0
        self.hotkey_listener = None
        self.last_output = None

        self._build_ui()
        self._setup_hotkeys()
        self._check_deps()

    # --- UI ---------------------------------------------------------------

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TFrame", background=BG_DARK)
        style.configure("Panel.TFrame", background=BG_PANEL)
        style.configure("Dark.TLabel", background=BG_DARK, foreground=FG_TEXT,
                         font=("Helvetica", 11))
        style.configure("Title.TLabel", background=BG_DARK, foreground=ACCENT,
                         font=("Helvetica", 20, "bold"))
        style.configure("Sub.TLabel", background=BG_DARK, foreground=ACCENT_DIM,
                         font=("Helvetica", 9))
        style.configure("Status.TLabel", background=BG_PANEL, foreground=FG_TEXT,
                         font=("Helvetica", 10))
        style.configure("Timer.TLabel", background=BG_DARK, foreground=ACCENT,
                         font=("Courier", 36, "bold"))
        style.configure("Accent.TButton", background=ACCENT, foreground=BG_DARK,
                         font=("Helvetica", 12, "bold"), padding=(16, 8))
        style.map("Accent.TButton",
                   background=[("active", ACCENT_DIM), ("disabled", "#555555")])
        style.configure("Red.TButton", background=RED, foreground="white",
                         font=("Helvetica", 11, "bold"), padding=(12, 6))
        style.map("Red.TButton",
                   background=[("active", "#cc3333")])
        style.configure("Dark.TButton", background=BG_INPUT, foreground=FG_TEXT,
                         font=("Helvetica", 10), padding=(10, 5))
        style.map("Dark.TButton",
                   background=[("active", ACCENT_DARK)])
        style.configure("Dark.TCheckbutton", background=BG_DARK, foreground=FG_TEXT,
                         font=("Helvetica", 10))
        style.configure("Dark.TRadiobutton", background=BG_DARK, foreground=FG_TEXT,
                         font=("Helvetica", 10))
        style.configure("Dark.TCombobox", fieldbackground=BG_INPUT,
                         background=BG_INPUT, foreground=FG_TEXT)

        # Header
        header = ttk.Frame(self.root, style="Dark.TFrame")
        header.pack(fill="x", padx=20, pady=(18, 2))
        ttk.Label(header, text="⏺  CORE Screen Recorder", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text=f"v{VERSION} — CORE SYSTEMS • Free & Open Source • No Watermark",
                  style="Sub.TLabel").pack(anchor="w")

        # Timer
        self.timer_label = ttk.Label(self.root, text="00:00:00", style="Timer.TLabel")
        self.timer_label.pack(pady=(14, 6))

        # Capture mode
        mode_frame = ttk.Frame(self.root, style="Dark.TFrame")
        mode_frame.pack(fill="x", padx=20, pady=4)
        ttk.Label(mode_frame, text="Capture Mode:", style="Dark.TLabel").pack(anchor="w")

        self.capture_mode = tk.StringVar(value=self.cfg.get("capture_mode", "fullscreen"))
        modes = [("Fullscreen", "fullscreen"), ("Select Region", "region")]
        mode_row = ttk.Frame(mode_frame, style="Dark.TFrame")
        mode_row.pack(fill="x", pady=2)
        for text, val in modes:
            ttk.Radiobutton(mode_row, text=text, variable=self.capture_mode,
                            value=val, style="Dark.TRadiobutton").pack(side="left", padx=(0, 16))

        # FPS
        fps_frame = ttk.Frame(self.root, style="Dark.TFrame")
        fps_frame.pack(fill="x", padx=20, pady=4)
        ttk.Label(fps_frame, text="FPS:", style="Dark.TLabel").pack(side="left")
        self.fps_var = tk.StringVar(value=str(self.cfg.get("fps", 30)))
        fps_combo = ttk.Combobox(fps_frame, textvariable=self.fps_var,
                                  values=["15", "30", "60"], width=5,
                                  state="readonly", style="Dark.TCombobox")
        fps_combo.pack(side="left", padx=8)

        # Format
        ttk.Label(fps_frame, text="Format:", style="Dark.TLabel").pack(side="left", padx=(16, 0))
        self.fmt_var = tk.StringVar(value=self.cfg.get("format", "MP4"))
        fmt_combo = ttk.Combobox(fps_frame, textvariable=self.fmt_var,
                                  values=["MP4", "MKV", "GIF"], width=5,
                                  state="readonly", style="Dark.TCombobox")
        fmt_combo.pack(side="left", padx=8)

        # Audio
        audio_frame = ttk.Frame(self.root, style="Dark.TFrame")
        audio_frame.pack(fill="x", padx=20, pady=4)
        ttk.Label(audio_frame, text="Audio:", style="Dark.TLabel").pack(anchor="w")
        audio_row = ttk.Frame(audio_frame, style="Dark.TFrame")
        audio_row.pack(fill="x", pady=2)
        self.audio_mic_var = tk.BooleanVar(value=self.cfg.get("audio_mic", False))
        ttk.Checkbutton(audio_row, text="Microphone", variable=self.audio_mic_var,
                         style="Dark.TCheckbutton").pack(side="left", padx=(0, 16))
        self.audio_sys_var = tk.BooleanVar(value=self.cfg.get("audio_system", False))
        ttk.Checkbutton(audio_row, text="System Audio (requires ffmpeg)",
                         variable=self.audio_sys_var,
                         style="Dark.TCheckbutton").pack(side="left")

        # Options
        opt_frame = ttk.Frame(self.root, style="Dark.TFrame")
        opt_frame.pack(fill="x", padx=20, pady=4)
        ttk.Label(opt_frame, text="Options:", style="Dark.TLabel").pack(anchor="w")
        opt_row = ttk.Frame(opt_frame, style="Dark.TFrame")
        opt_row.pack(fill="x", pady=2)

        self.cursor_var = tk.BooleanVar(value=self.cfg.get("cursor_highlight", True))
        ttk.Checkbutton(opt_row, text="Cursor Highlight", variable=self.cursor_var,
                         style="Dark.TCheckbutton").pack(side="left", padx=(0, 16))

        ttk.Label(opt_row, text="Countdown:", style="Dark.TLabel").pack(side="left")
        self.countdown_var = tk.StringVar(value=str(self.cfg.get("countdown", 3)))
        cd_combo = ttk.Combobox(opt_row, textvariable=self.countdown_var,
                                 values=["0", "1", "2", "3", "5"], width=3,
                                 state="readonly", style="Dark.TCombobox")
        cd_combo.pack(side="left", padx=4)

        # Save directory
        dir_frame = ttk.Frame(self.root, style="Dark.TFrame")
        dir_frame.pack(fill="x", padx=20, pady=4)
        ttk.Label(dir_frame, text="Save to:", style="Dark.TLabel").pack(anchor="w")
        dir_row = ttk.Frame(dir_frame, style="Dark.TFrame")
        dir_row.pack(fill="x", pady=2)
        self.dir_var = tk.StringVar(value=self.cfg.get("save_dir", DEFAULT_SAVE_DIR))
        dir_entry = tk.Entry(dir_row, textvariable=self.dir_var, bg=BG_INPUT,
                              fg=FG_TEXT, insertbackground=FG_TEXT,
                              font=("Helvetica", 10), relief="flat", bd=4)
        dir_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(dir_row, text="Browse", style="Dark.TButton",
                    command=self._browse_dir).pack(side="left", padx=(4, 0))

        # Buttons
        btn_frame = ttk.Frame(self.root, style="Dark.TFrame")
        btn_frame.pack(fill="x", padx=20, pady=(16, 4))

        self.record_btn = tk.Button(
            btn_frame, text="⏺  START RECORDING", bg=ACCENT, fg=BG_DARK,
            activebackground=ACCENT_DIM, activeforeground=BG_DARK,
            font=("Helvetica", 14, "bold"), relief="flat", bd=0,
            cursor="hand2", padx=20, pady=10,
            command=self._toggle_recording
        )
        self.record_btn.pack(fill="x", pady=4)

        btn_row2 = ttk.Frame(btn_frame, style="Dark.TFrame")
        btn_row2.pack(fill="x", pady=4)

        self.pause_btn = tk.Button(
            btn_row2, text="⏸ Pause", bg=BG_INPUT, fg=FG_TEXT,
            activebackground=ACCENT_DARK, font=("Helvetica", 11),
            relief="flat", bd=0, padx=12, pady=6,
            command=self._toggle_pause, state="disabled"
        )
        self.pause_btn.pack(side="left", fill="x", expand=True, padx=(0, 2))

        self.trim_btn = tk.Button(
            btn_row2, text="✂ Trim", bg=BG_INPUT, fg=FG_TEXT,
            activebackground=ACCENT_DARK, font=("Helvetica", 11),
            relief="flat", bd=0, padx=12, pady=6,
            command=self._trim_dialog, state="disabled"
        )
        self.trim_btn.pack(side="left", fill="x", expand=True, padx=(2, 2))

        self.open_btn = tk.Button(
            btn_row2, text="📂 Open", bg=BG_INPUT, fg=FG_TEXT,
            activebackground=ACCENT_DARK, font=("Helvetica", 11),
            relief="flat", bd=0, padx=12, pady=6,
            command=self._open_last, state="disabled"
        )
        self.open_btn.pack(side="left", fill="x", expand=True, padx=(2, 0))

        # Status bar
        status_frame = ttk.Frame(self.root, style="Panel.TFrame")
        status_frame.pack(fill="x", side="bottom", padx=0, pady=0)
        self.status_var = tk.StringVar(value="Ready — Press Ctrl+Shift+R to start")
        ttk.Label(status_frame, textvariable=self.status_var,
                  style="Status.TLabel").pack(padx=10, pady=6, anchor="w")

        # Hotkey hint
        hint_frame = ttk.Frame(self.root, style="Dark.TFrame")
        hint_frame.pack(fill="x", padx=20, pady=(4, 8))
        ttk.Label(hint_frame,
                  text="Hotkeys: Ctrl+Shift+R = Start/Stop  •  Ctrl+Shift+P = Pause",
                  style="Sub.TLabel").pack(anchor="w")

    # --- Actions ----------------------------------------------------------

    def _check_deps(self):
        missing = []
        if not HAS_MSS:
            missing.append("mss")
        if not HAS_CV2:
            missing.append("opencv-python")
        if missing:
            self.status_var.set(f"⚠ Missing: {', '.join(missing)} — pip install them")
            self.record_btn.configure(state="disabled")

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.dir_var.get())
        if d:
            self.dir_var.set(d)

    def _save_current_config(self):
        self.cfg.update({
            "fps": int(self.fps_var.get()),
            "format": self.fmt_var.get(),
            "save_dir": self.dir_var.get(),
            "cursor_highlight": self.cursor_var.get(),
            "countdown": int(self.countdown_var.get()),
            "capture_mode": self.capture_mode.get(),
            "audio_mic": self.audio_mic_var.get(),
            "audio_system": self.audio_sys_var.get(),
        })
        save_config(self.cfg)

    def _toggle_recording(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self._save_current_config()

        mode = self.capture_mode.get()
        if mode == "region":
            self.root.iconify()
            time.sleep(0.3)
            RegionSelector(self._on_region_selected)
            return

        self._begin_capture(None)

    def _on_region_selected(self, region):
        self.root.deiconify()
        if region is None:
            self.status_var.set("Region selection cancelled")
            return
        self.selected_region = region
        self._begin_capture(region)

    def _begin_capture(self, region):
        countdown = int(self.countdown_var.get())
        if countdown > 0:
            self._countdown(countdown, region)
        else:
            self._do_start(region)

    def _countdown(self, n, region):
        if n <= 0:
            self._do_start(region)
            return
        self.timer_label.configure(text=f"Starting in {n}...")
        self.status_var.set(f"Countdown: {n}")
        self.root.after(1000, lambda: self._countdown(n - 1, region))

    def _do_start(self, region):
        fps = int(self.fps_var.get())
        self.engine = RecordingEngine(
            fps=fps, region=region,
            cursor_highlight=self.cursor_var.get()
        )

        # Audio
        self.audio_path = None
        if self.audio_mic_var.get() and HAS_AUDIO:
            self.audio_path = tempfile.mktemp(suffix=".wav")
            self.audio_rec = AudioRecorder(self.audio_path)
            self.audio_rec.start()

        self.engine.start()
        self.is_recording = True
        self.is_paused = False
        self.elapsed = 0
        self._update_timer()

        self.record_btn.configure(text="⏹  STOP RECORDING", bg=RED)
        self.pause_btn.configure(state="normal")
        self.trim_btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        self.status_var.set("🔴 Recording...")

    def _stop_recording(self):
        if not self.is_recording:
            return

        self.is_recording = False
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None

        self.status_var.set("Saving...")
        self.root.update()

        self.engine.stop()
        if self.audio_rec:
            self.audio_rec.stop()

        # Save
        fmt = self.fmt_var.get().lower()
        save_dir = self.dir_var.get()
        ensure_dir(save_dir)
        output = generate_filename(fmt, save_dir)

        success = self.engine.save(output, fmt=fmt, audio_path=self.audio_path)

        # Cleanup temp audio
        if self.audio_path and os.path.isfile(self.audio_path):
            try:
                os.remove(self.audio_path)
            except Exception:
                pass

        self.record_btn.configure(text="⏺  START RECORDING", bg=ACCENT)
        self.pause_btn.configure(state="disabled")

        if success:
            self.last_output = output
            size_mb = os.path.getsize(output) / (1024 * 1024)
            frames = len(self.engine.frames) if self.engine else 0
            self.status_var.set(
                f"✅ Saved: {os.path.basename(output)} ({size_mb:.1f} MB, {frames} frames)")
            self.trim_btn.configure(state="normal")
            self.open_btn.configure(state="normal")
        else:
            self.status_var.set("❌ Failed to save recording")

    def _toggle_pause(self):
        if not self.is_recording:
            return
        if self.is_paused:
            self.is_paused = False
            self.engine.resume()
            if self.audio_rec:
                self.audio_rec.resume()
            self.pause_btn.configure(text="⏸ Pause")
            self.status_var.set("🔴 Recording...")
            self._update_timer()
        else:
            self.is_paused = True
            self.engine.pause()
            if self.audio_rec:
                self.audio_rec.pause()
            self.pause_btn.configure(text="▶ Resume")
            self.status_var.set("⏸ Paused")
            if self.timer_id:
                self.root.after_cancel(self.timer_id)

    def _update_timer(self):
        if not self.is_recording or self.is_paused:
            return
        self.elapsed += 1
        h = self.elapsed // 3600
        m = (self.elapsed % 3600) // 60
        s = self.elapsed % 60
        self.timer_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        self.timer_id = self.root.after(1000, self._update_timer)

    def _trim_dialog(self):
        if not self.engine or not self.engine.frames:
            return
        dur = self.engine.duration
        result = simpledialog.askstring(
            "Trim Recording",
            f"Duration: {dur:.1f}s\nEnter trim range (start-end in seconds):\nExample: 2.0-10.5",
            parent=self.root
        )
        if not result:
            return
        try:
            parts = result.split("-")
            start = float(parts[0].strip())
            end = float(parts[1].strip())
        except (ValueError, IndexError):
            messagebox.showerror("Error", "Invalid format. Use: start-end (e.g. 2.0-10.5)")
            return

        self.engine.trim(start, end)

        # Re-save
        fmt = self.fmt_var.get().lower()
        save_dir = self.dir_var.get()
        ensure_dir(save_dir)
        output = generate_filename(fmt, save_dir)
        success = self.engine.save(output, fmt=fmt)
        if success:
            self.last_output = output
            size_mb = os.path.getsize(output) / (1024 * 1024)
            self.status_var.set(f"✅ Trimmed & saved: {os.path.basename(output)} ({size_mb:.1f} MB)")
        else:
            self.status_var.set("❌ Trim save failed")

    def _open_last(self):
        if self.last_output and os.path.isfile(self.last_output):
            if sys.platform == "darwin":
                subprocess.Popen(["open", self.last_output])
            elif sys.platform == "win32":
                os.startfile(self.last_output)
            else:
                subprocess.Popen(["xdg-open", self.last_output])

    # --- Hotkeys ----------------------------------------------------------

    def _setup_hotkeys(self):
        if not HAS_PYNPUT:
            return
        try:
            hotkeys = {
                HOTKEY_START_STOP: lambda: self.root.after(0, self._toggle_recording),
                HOTKEY_PAUSE: lambda: self.root.after(0, self._toggle_pause),
            }
            self.hotkey_listener = pynput_kb.GlobalHotKeys(hotkeys)
            self.hotkey_listener.daemon = True
            self.hotkey_listener.start()
        except Exception:
            pass

    # --- Cleanup ----------------------------------------------------------

    def on_close(self):
        if self.is_recording:
            self._stop_recording()
        self._save_current_config()
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
        self.root.destroy()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    root = tk.Tk()
    app = ScreenRecorderApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)

    # Center window
    root.update_idletasks()
    w, h = 540, 720
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    root.mainloop()


if __name__ == "__main__":
    main()
