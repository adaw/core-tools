# 🖥 System Info — CORE Tool #8 (Tauri 2)

Real-time system monitoring dashboard built with Tauri 2 + Rust (`sysinfo` crate).

## Features

- **6 tabs:** Overview, CPU, Memory, Disks, Network, Processes
- **Real-time refresh** every 3s with SVG sparkline charts
- **Dark theme** (#1a1a2e / #00ff88 accent)
- **CPU:** per-core usage, frequency, temperature sensors
- **Memory:** RAM + Swap usage with progress bars
- **Disks:** mount points, filesystem, usage bars
- **Network:** per-interface RX/TX bytes and packets
- **Processes:** top 30 by CPU usage, color-coded
- **Export:** JSON and HTML reports

## Tech Stack

- **Frontend:** Vanilla HTML/CSS/JS, SVG sparklines
- **Backend:** Rust + sysinfo 0.33, chrono
- **Framework:** Tauri 2

## Build

```bash
source "$HOME/.cargo/env"
cd src-tauri && cargo check    # verify
npm install && npm run tauri build  # full build
```

## Structure

```
system-info-tauri/
├── src/
│   └── index.html          # UI (dashboard, tabs, charts)
├── src-tauri/
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   └── src/
│       ├── main.rs          # Tauri app entry
│       └── system.rs        # All Tauri commands (CPU/RAM/disk/net/procs/export)
└── README.md
```
