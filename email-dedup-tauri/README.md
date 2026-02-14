# 📧 Email Transfer & Dedup — CORE Tool #6

Tauri 2 desktop app for IMAP email management: connect to any provider, find & remove duplicates, transfer between accounts, and backup to .mbox.

## Features

- **IMAP Connect** — Gmail, Outlook, iCloud, or any generic IMAP server
- **3 Dedup Methods:**
  - Message-ID (exact match)
  - Subject + Date SHA-256 hash
  - Size + Subject fingerprint
- **Email Transfer** — move emails between IMAP accounts
- **Backup** — export any mailbox to standard .mbox format
- **Dry Run** — preview duplicates before deleting
- **Dark UI** — #1a1a2e / #00ff88 theme with account panels and duplicate group preview

## Tech Stack

- **Frontend:** Vanilla HTML/CSS/JS (Tauri webview)
- **Backend:** Rust — `imap` + `native-tls`, `sha2`, `mailparse`, `chrono`
- **Framework:** Tauri 2

## Development

```bash
# Check compilation
cd src-tauri && cargo check

# Run dev
npm install
npm run tauri dev

# Build
npm run tauri build
```

## Security Note

Uses app-specific passwords (Gmail, iCloud) or OAuth tokens. Credentials are never stored — entered per session.
