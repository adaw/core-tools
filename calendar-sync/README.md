# Calendar Sync

**Cross-platform calendar synchronization tool by CORE SYSTEMS.**

Sync events between Google Calendar, Outlook/Exchange, Apple Calendar, CalDAV servers, and local ICS files — with conflict resolution, duplicate detection, and scheduled auto-sync.

![Python](https://img.shields.io/badge/Python-3.9+-blue) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Features

- **Multi-source sync** — Google Calendar (OAuth), Outlook/Exchange (OAuth), CalDAV (Apple, Nextcloud, etc.), local `.ics` files
- **One-way & two-way sync** — push, pull, or mirror between any two sources
- **Conflict resolution** — keep both, newer wins, or manual review
- **Duplicate detection** — smart matching by UID, summary + time, or fuzzy match
- **Import / Export ICS** — bulk import and export calendar data
- **Scheduled sync** — auto-sync every X minutes in the background
- **Change log** — detailed log of every add, update, and delete
- **Dark theme UI** — modern tkinter interface with CORE SYSTEMS branding

## Screenshots

*Coming soon*

## Requirements

- Python 3.9+
- No system dependencies required (tkinter ships with Python)

### Optional (for calendar providers):

```
pip install -r requirements.txt
```

This installs:
- `google-api-python-client`, `google-auth-oauthlib` — Google Calendar API
- `msal` — Microsoft Outlook/Exchange OAuth
- `caldav` — CalDAV protocol support
- `icalendar` — ICS parsing and generation
- `requests` — HTTP client

## Quick Start

```bash
# Clone
git clone https://github.com/coresystems-dev/core-tools.git
cd core-tools/calendar-sync

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

## Build

### macOS

```bash
chmod +x build.sh
./build.sh
```

Output: `dist/Calendar Sync.app`

### Windows

```bat
build.bat
```

Output: `dist\CalendarSync.exe`

### Requirements for building

```
pip install pyinstaller
```

## Configuration

On first launch, configure your calendar sources in the **Sources** tab:

1. **Google Calendar** — Click "Add Google Calendar", authenticate via OAuth
2. **Outlook/Exchange** — Click "Add Outlook", authenticate via Microsoft OAuth
3. **CalDAV** — Enter server URL, username, and password
4. **Local ICS** — Browse to select `.ics` file(s)

### Sync Settings

- **Direction**: One-way (A→B) or Two-way (A↔B)
- **Conflict Resolution**: Keep both | Newer wins | Manual review
- **Schedule**: Off, or every 5/15/30/60 minutes
- **Duplicate Detection**: UID match, Summary+Time match, or Fuzzy

## Project Structure

```
calendar-sync/
├── main.py              # Entry point
├── app.py               # Main application & UI
├── providers/
│   ├── __init__.py
│   ├── base.py          # Abstract provider interface
│   ├── google_cal.py    # Google Calendar provider
│   ├── outlook.py       # Outlook/Exchange provider
│   ├── caldav_provider.py # CalDAV provider
│   └── ics_file.py      # Local ICS file provider
├── sync/
│   ├── __init__.py
│   ├── engine.py        # Sync engine core
│   ├── conflict.py      # Conflict resolution
│   └── dedup.py         # Duplicate detection
├── ui/
│   ├── __init__.py
│   ├── theme.py         # Dark theme & CORE SYSTEMS styling
│   ├── sources_tab.py   # Sources management UI
│   ├── sync_tab.py      # Sync configuration & execution UI
│   ├── log_tab.py       # Change log viewer
│   └── dialogs.py       # Modal dialogs
├── config.py            # Configuration persistence
├── requirements.txt
├── build.sh
├── build.bat
└── README.md
```

## License

MIT License — free for personal and commercial use.

---

**CORE SYSTEMS** — Free tools, no bullshit.
