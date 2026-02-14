# 📅 Calendar Sync — CORE Tool #5

Tauri 2 desktop app for calendar synchronization across multiple providers.

## Features

- **Multi-source support:** Google Calendar, Outlook, CalDAV, ICS file import
- **Two-way sync** between any configured sources
- **Conflict resolution:** newest wins, source/target priority, or manual
- **Deduplication** of identical events across calendars
- **Auto-schedule** sync at configurable intervals
- **Change log** with full history in SQLite

## Tech Stack

- **Frontend:** Vanilla JS + Vite, dark theme (#1a1a2e / #00ff88)
- **Backend:** Rust + Tauri 2
- **CalDAV:** reqwest-based PROPFIND/REPORT/PUT client
- **ICS parsing:** icalendar crate
- **Storage:** SQLite via rusqlite (bundled)
- **UI:** Tab-based (Sources / Sync / Log)

## Development

```bash
npm install
cd src-tauri && cargo check
npm run tauri dev
```

## Build

```bash
npm run tauri build
```

## Architecture

```
src/                  # Frontend (HTML/CSS/JS)
src-tauri/
  src/
    main.rs           # Entry point
    lib.rs            # Tauri commands
    models.rs         # Data structures
    db.rs             # SQLite operations
    ics.rs            # ICS/iCalendar parsing
    caldav.rs         # CalDAV client
    sync_engine.rs    # Sync logic, conflict resolution, dedup
```

## Part of [CORE Tools](https://github.com/AdrianHorzworker/core-tools)
