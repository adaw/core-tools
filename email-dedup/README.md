# ◆ CORE Email Transfer & Dedup

**Free email migration and deduplication tool by CORE SYSTEMS.**

![Python](https://img.shields.io/badge/Python-3.8+-blue) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

### 🔍 Deduplication
- **Three detection methods:** Message-ID, Subject+Date+From hash, Size+Subject
- Preview duplicate groups before deletion
- Dry run mode — see what would be deleted without touching anything
- Backup to `.mbox` before deleting
- Export dedup reports (CSV/TXT)

### 📤 Email Transfer
- One-way copy or move between any two IMAP accounts
- Filter by folder, date range, sender
- Preserves flags and dates
- Dry run mode for safe preview

### 📧 Account Support
- **Gmail** (app password)
- **Outlook / Office 365** (app password)
- **iCloud** (app password)
- **Yahoo** and any generic IMAP server

### 🎨 UI
- Dark theme with CORE SYSTEMS branding (green #00ff88 accents)
- Progress bar with real-time statistics
- Threaded operations — UI stays responsive
- Zero external dependencies (pure tkinter)

## Quick Start

```bash
# Run directly
python3 email_dedup.py

# Or install & run
pip install -e .
core-email-dedup
```

## App Passwords

Most providers require **app-specific passwords** (not your regular password):

| Provider | How to get app password |
|----------|------------------------|
| **Gmail** | [Google Account → Security → App passwords](https://myaccount.google.com/apppasswords) |
| **Outlook** | [Microsoft Account → Security → App passwords](https://account.microsoft.com/security) |
| **iCloud** | [Apple ID → Sign-In and Security → App-Specific Passwords](https://appleid.apple.com/) |
| **Yahoo** | [Yahoo Account → Security → App password](https://login.yahoo.com/account/security) |

## Build

### macOS

```bash
chmod +x build.sh
./build.sh
# Output: dist/CORE Email Dedup.app
```

### Windows

```bat
build.bat
REM Output: dist\CORE Email Dedup.exe
```

### Manual Build

```bash
pip install pyinstaller
pyinstaller --onefile --windowed \
  --name "CORE Email Dedup" \
  --icon icon.ico \
  email_dedup.py
```

## Usage

### Deduplication Workflow

1. **Connect** to your IMAP account (select provider, enter credentials)
2. **Configure filters** (optional): folders, date range, sender
3. **Select detection method**: Message-ID (most accurate), Subject+Date+From, or Size+Subject
4. **Enable Dry Run** (recommended for first scan)
5. Click **Scan & Find Duplicates**
6. Review duplicate groups in the tree view
7. Optionally **Export Report** (CSV/TXT)
8. Disable Dry Run and click **Delete Duplicates** (with backup enabled)

### Transfer Workflow

1. **Connect** source and destination accounts
2. Select source and destination **folders**
3. Choose **Copy** or **Move** mode
4. Apply **filters** if needed (sender, date range)
5. Enable **Dry Run** for preview
6. Click **Start Transfer**

## Project Structure

```
email-dedup/
├── email_dedup.py    # Main application (single file, zero deps)
├── build.sh          # macOS build script
├── build.bat         # Windows build script
├── setup.py          # pip install support
└── README.md
```

## Requirements

- Python 3.8+
- No external dependencies (stdlib only: tkinter, imaplib, email, hashlib)
- PyInstaller for building standalone executables

## License

MIT — Free for personal and commercial use.

---

**◆ CORE SYSTEMS** — Free tools, no bullshit.
