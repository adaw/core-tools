# ⬡ CORE System Info

**CORE Tool #8** — Real-time hardware & software dashboard.

![Python](https://img.shields.io/badge/Python-3.8+-00ff88?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-macOS%20|%20Windows%20|%20Linux-00ff88?style=flat-square)

## Features

- **CPU** — Model, frequency, cores, temperature, real-time usage graph
- **RAM** — Total, used, available, swap, real-time graph
- **Disks** — Partitions, usage bars, I/O counters
- **GPU** — Detection via system_profiler / lspci / nvidia-smi
- **Network** — Interfaces, IPs, MACs, speed, live bandwidth monitor
- **Battery** — Charge level, plugged status, time remaining
- **OS Info** — System, hostname, boot time
- **Processes** — Top 10 by CPU/RAM usage, auto-refreshing
- **Export** — JSON, HTML, or TXT reports
- **Benchmark** — Quick CPU & disk speed test

## Quick Start

```bash
pip install psutil
python system_info.py
```

## Build Standalone

### macOS
```bash
./build.sh
# → dist/CORE System Info.app
```

### Windows
```batch
build.bat
REM → dist\CORE System Info.exe
```

## Requirements

- Python 3.8+
- `psutil` >= 5.9.0
- `tkinter` (included with Python)
- `pyinstaller` (for builds only)

## UI

Dark theme with CORE SYSTEMS branding (#00ff88 green). Real-time graphs update every 2 seconds. Tabbed interface: Overview, CPU, Memory, Disks, Network, Processes.

## License

MIT — CORE SYSTEMS
