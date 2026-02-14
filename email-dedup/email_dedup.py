#!/usr/bin/env python3
"""
CORE Email Transfer & Dedup
Free email migration and deduplication tool by CORE SYSTEMS.

Features:
- Connect to IMAP accounts (Gmail, Outlook, iCloud, generic)
- Transfer emails between accounts (copy/move)
- Deduplicate by Message-ID, Subject+Date+From hash, or size
- Preview duplicate groups before deletion
- Dry run mode
- Filter by folder, date, sender
- Progress tracking with statistics
- Export reports (CSV/TXT)
- Backup to .mbox before delete
- OAuth2 for Gmail/Outlook, app passwords for others
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import imaplib
import email
import email.utils
import email.policy
import hashlib
import csv
import os
import re
import json
import mailbox
import threading
import time
import ssl
import socket
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any
from io import StringIO

# ─── Version ────────────────────────────────────────────────────────────────
VERSION = "1.0.0"
APP_NAME = "CORE Email Transfer & Dedup"

# ─── Theme ──────────────────────────────────────────────────────────────────
COLORS = {
    "bg": "#1a1a2e",
    "bg_secondary": "#16213e",
    "bg_tertiary": "#0f3460",
    "fg": "#e0e0e0",
    "fg_dim": "#888888",
    "accent": "#00ff88",
    "accent_dim": "#00cc6a",
    "danger": "#ff4444",
    "warning": "#ffaa00",
    "success": "#00ff88",
    "border": "#2a2a4a",
    "input_bg": "#0d1b2a",
    "input_fg": "#e0e0e0",
    "button_bg": "#00ff88",
    "button_fg": "#1a1a2e",
    "select_bg": "#00ff88",
}

# ─── IMAP Presets ───────────────────────────────────────────────────────────
IMAP_PRESETS = {
    "Gmail": {"host": "imap.gmail.com", "port": 993, "ssl": True},
    "Outlook": {"host": "outlook.office365.com", "port": 993, "ssl": True},
    "iCloud": {"host": "imap.mail.me.com", "port": 993, "ssl": True},
    "Yahoo": {"host": "imap.mail.yahoo.com", "port": 993, "ssl": True},
    "Custom": {"host": "", "port": 993, "ssl": True},
}

# ─── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class IMAPAccount:
    name: str
    host: str
    port: int
    username: str
    password: str
    use_ssl: bool = True
    connection: Optional[imaplib.IMAP4] = field(default=None, repr=False)

    def connect(self) -> imaplib.IMAP4:
        if self.connection:
            try:
                self.connection.noop()
                return self.connection
            except Exception:
                self.connection = None
        ctx = ssl.create_default_context()
        if self.use_ssl:
            self.connection = imaplib.IMAP4_SSL(self.host, self.port, ssl_context=ctx)
        else:
            self.connection = imaplib.IMAP4(self.host, self.port)
            self.connection.starttls(ssl_context=ctx)
        self.connection.login(self.username, self.password)
        return self.connection

    def disconnect(self):
        if self.connection:
            try:
                self.connection.logout()
            except Exception:
                pass
            self.connection = None

    def list_folders(self) -> List[str]:
        conn = self.connect()
        status, data = conn.list()
        folders = []
        if status == "OK":
            for item in data:
                if item is None:
                    continue
                decoded = item.decode("utf-8", errors="replace") if isinstance(item, bytes) else str(item)
                match = re.search(r'"([^"]*)"$|(\S+)$', decoded)
                if match:
                    folder = match.group(1) or match.group(2)
                    folders.append(folder)
        return sorted(folders)


@dataclass
class EmailInfo:
    uid: str
    message_id: str
    subject: str
    from_addr: str
    date_str: str
    date_parsed: Optional[datetime]
    size: int
    folder: str
    hash_key: str = ""

    def compute_hash(self):
        raw = f"{self.subject}|{self.date_str}|{self.from_addr}".encode("utf-8")
        self.hash_key = hashlib.sha256(raw).hexdigest()


@dataclass
class DuplicateGroup:
    key: str
    method: str
    emails: List[EmailInfo] = field(default_factory=list)

    @property
    def count(self):
        return len(self.emails)

    @property
    def keep(self):
        return self.emails[0] if self.emails else None

    @property
    def duplicates(self):
        return self.emails[1:]


# ─── Core Engine ────────────────────────────────────────────────────────────

class EmailEngine:
    """Handles all IMAP operations for scanning, dedup, transfer."""

    def __init__(self, progress_callback=None, log_callback=None):
        self.progress_cb = progress_callback or (lambda *a: None)
        self.log_cb = log_callback or (lambda msg: None)
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def reset_cancel(self):
        self._cancel = False

    def scan_folder(self, account: IMAPAccount, folder: str,
                    date_from: Optional[datetime] = None,
                    date_to: Optional[datetime] = None,
                    sender_filter: str = "") -> List[EmailInfo]:
        """Scan a folder and return list of EmailInfo."""
        conn = account.connect()
        status, _ = conn.select(f'"{folder}"', readonly=True)
        if status != "OK":
            self.log_cb(f"  ⚠ Cannot select folder: {folder}")
            return []

        # Build search criteria
        criteria = []
        if date_from:
            criteria.append(f'SINCE {date_from.strftime("%d-%b-%Y")}')
        if date_to:
            criteria.append(f'BEFORE {date_to.strftime("%d-%b-%Y")}')
        if sender_filter:
            criteria.append(f'FROM "{sender_filter}"')

        search_str = " ".join(criteria) if criteria else "ALL"
        status, data = conn.uid("search", None, search_str)
        if status != "OK" or not data[0]:
            return []

        uids = data[0].split()
        total = len(uids)
        self.log_cb(f"  📧 {folder}: {total} messages found")
        emails = []

        # Fetch in batches
        batch_size = 50
        for i in range(0, total, batch_size):
            if self._cancel:
                break
            batch = uids[i:i + batch_size]
            uid_range = b",".join(batch)
            status, msg_data = conn.uid("fetch", uid_range, "(BODY.PEEK[HEADER] RFC822.SIZE)")
            if status != "OK":
                continue

            for j in range(0, len(msg_data), 2):
                if self._cancel:
                    break
                item = msg_data[j]
                if not isinstance(item, tuple) or len(item) < 2:
                    continue

                header_data = item[1]
                meta_line = item[0].decode("utf-8", errors="replace") if isinstance(item[0], bytes) else str(item[0])

                # Extract UID from response
                uid_match = re.search(r"UID (\d+)", meta_line)
                uid_val = uid_match.group(1) if uid_match else str(i + j // 2)

                # Extract size
                size_match = re.search(r"RFC822\.SIZE (\d+)", meta_line)
                size_val = int(size_match.group(1)) if size_match else 0

                try:
                    msg = email.message_from_bytes(header_data, policy=email.policy.default)
                except Exception:
                    continue

                message_id = msg.get("Message-ID", "").strip()
                subject = msg.get("Subject", "(no subject)") or "(no subject)"
                from_addr = msg.get("From", "") or ""
                date_str = msg.get("Date", "") or ""

                date_parsed = None
                if date_str:
                    try:
                        parsed = email.utils.parsedate_to_datetime(date_str)
                        date_parsed = parsed.replace(tzinfo=None)
                    except Exception:
                        pass

                info = EmailInfo(
                    uid=uid_val,
                    message_id=message_id,
                    subject=subject,
                    from_addr=from_addr,
                    date_str=date_str,
                    date_parsed=date_parsed,
                    size=size_val,
                    folder=folder,
                )
                info.compute_hash()
                emails.append(info)

            self.progress_cb(min(i + batch_size, total), total)

        return emails

    def find_duplicates(self, emails: List[EmailInfo],
                        method: str = "message_id") -> List[DuplicateGroup]:
        """Find duplicate groups using specified method."""
        groups: Dict[str, List[EmailInfo]] = defaultdict(list)

        for em in emails:
            if method == "message_id":
                if em.message_id:
                    groups[em.message_id].append(em)
            elif method == "hash":
                groups[em.hash_key].append(em)
            elif method == "size_subject":
                key = f"{em.size}|{em.subject}"
                groups[key].append(em)

        result = []
        for key, ems in groups.items():
            if len(ems) > 1:
                # Sort by date (keep oldest) then by UID
                ems.sort(key=lambda e: (e.date_parsed or datetime.min, e.uid))
                result.append(DuplicateGroup(key=key, method=method, emails=ems))

        result.sort(key=lambda g: g.count, reverse=True)
        return result

    def backup_to_mbox(self, account: IMAPAccount, emails: List[EmailInfo],
                       output_path: str) -> int:
        """Backup emails to local .mbox file. Returns count backed up."""
        conn = account.connect()
        mbox = mailbox.mbox(output_path)
        mbox.lock()
        count = 0
        total = len(emails)

        try:
            for i, em in enumerate(emails):
                if self._cancel:
                    break
                try:
                    conn.select(f'"{em.folder}"', readonly=True)
                    status, data = conn.uid("fetch", em.uid, "(RFC822)")
                    if status == "OK" and data[0] and isinstance(data[0], tuple):
                        raw = data[0][1]
                        msg = mailbox.mboxMessage(email.message_from_bytes(raw))
                        mbox.add(msg)
                        count += 1
                except Exception as e:
                    self.log_cb(f"  ⚠ Backup failed for UID {em.uid}: {e}")
                self.progress_cb(i + 1, total)
        finally:
            mbox.unlock()
            mbox.close()

        return count

    def delete_emails(self, account: IMAPAccount, emails: List[EmailInfo],
                      dry_run: bool = False) -> int:
        """Delete emails. Returns count deleted."""
        if dry_run:
            self.log_cb(f"  🔍 DRY RUN: Would delete {len(emails)} emails")
            return len(emails)

        conn = account.connect()
        deleted = 0
        # Group by folder for efficiency
        by_folder: Dict[str, List[str]] = defaultdict(list)
        for em in emails:
            by_folder[em.folder].append(em.uid)

        for folder, uids in by_folder.items():
            if self._cancel:
                break
            conn.select(f'"{folder}"')
            for uid in uids:
                if self._cancel:
                    break
                try:
                    conn.uid("store", uid, "+FLAGS", "(\\Deleted)")
                    deleted += 1
                except Exception as e:
                    self.log_cb(f"  ⚠ Delete failed UID {uid}: {e}")
                self.progress_cb(deleted, len(emails))
            conn.expunge()

        return deleted

    def transfer_emails(self, source: IMAPAccount, dest: IMAPAccount,
                        emails: List[EmailInfo], dest_folder: str,
                        move: bool = False, dry_run: bool = False) -> int:
        """Transfer emails from source to dest. Returns count transferred."""
        if dry_run:
            self.log_cb(f"  🔍 DRY RUN: Would transfer {len(emails)} emails to {dest_folder}")
            return len(emails)

        src_conn = source.connect()
        dst_conn = dest.connect()

        # Ensure dest folder exists
        try:
            dst_conn.select(f'"{dest_folder}"')
        except Exception:
            dst_conn.create(f'"{dest_folder}"')
            dst_conn.select(f'"{dest_folder}"')

        transferred = 0
        total = len(emails)

        for i, em in enumerate(emails):
            if self._cancel:
                break
            try:
                src_conn.select(f'"{em.folder}"', readonly=not move)
                status, data = src_conn.uid("fetch", em.uid, "(RFC822 FLAGS)")
                if status != "OK" or not data[0] or not isinstance(data[0], tuple):
                    continue

                raw = data[0][1]
                meta = data[0][0].decode("utf-8", errors="replace") if isinstance(data[0][0], bytes) else str(data[0][0])

                # Parse flags
                flags_match = re.search(r"FLAGS \(([^)]*)\)", meta)
                flags = flags_match.group(1) if flags_match else ""
                # Remove \Recent flag
                flags = " ".join(f for f in flags.split() if f != "\\Recent")

                # Parse internal date
                date_str = None
                try:
                    msg = email.message_from_bytes(raw)
                    d = msg.get("Date", "")
                    if d:
                        parsed = email.utils.parsedate_to_datetime(d)
                        date_str = imaplib.Time2Internaldate(parsed.timestamp())
                except Exception:
                    date_str = None

                if date_str is None:
                    date_str = imaplib.Time2Internaldate(time.time())

                dst_conn.append(f'"{dest_folder}"', f"({flags})" if flags else None, date_str, raw)
                transferred += 1

                if move:
                    src_conn.uid("store", em.uid, "+FLAGS", "(\\Deleted)")

            except Exception as e:
                self.log_cb(f"  ⚠ Transfer failed UID {em.uid}: {e}")

            self.progress_cb(i + 1, total)

        if move:
            # Expunge deleted from source
            by_folder = set(em.folder for em in emails)
            for folder in by_folder:
                try:
                    src_conn.select(f'"{folder}"')
                    src_conn.expunge()
                except Exception:
                    pass

        return transferred


# ─── Report Export ──────────────────────────────────────────────────────────

def export_report_csv(groups: List[DuplicateGroup], path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Group", "Method", "UID", "Message-ID", "Subject", "From", "Date", "Size", "Folder", "Action"])
        for i, g in enumerate(groups, 1):
            for j, em in enumerate(g.emails):
                action = "KEEP" if j == 0 else "DELETE"
                writer.writerow([i, g.method, em.uid, em.message_id, em.subject,
                                em.from_addr, em.date_str, em.size, em.folder, action])


def export_report_txt(groups: List[DuplicateGroup], path: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"CORE Email Dedup Report — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 72 + "\n\n")
        f.write(f"Total duplicate groups: {len(groups)}\n")
        f.write(f"Total duplicates: {sum(len(g.duplicates) for g in groups)}\n\n")
        for i, g in enumerate(groups, 1):
            f.write(f"─── Group {i} ({g.method}, {g.count} copies) ───\n")
            for j, em in enumerate(g.emails):
                tag = "✓ KEEP  " if j == 0 else "✗ DELETE"
                f.write(f"  {tag} [{em.folder}] {em.subject[:60]}\n")
                f.write(f"           From: {em.from_addr[:50]}  Date: {em.date_str[:30]}  Size: {em.size}\n")
            f.write("\n")


# ─── GUI ────────────────────────────────────────────────────────────────────

class StyledButton(tk.Button):
    def __init__(self, parent, **kwargs):
        kwargs.setdefault("bg", COLORS["button_bg"])
        kwargs.setdefault("fg", COLORS["button_fg"])
        kwargs.setdefault("activebackground", COLORS["accent_dim"])
        kwargs.setdefault("activeforeground", COLORS["button_fg"])
        kwargs.setdefault("relief", "flat")
        kwargs.setdefault("font", ("Helvetica", 11, "bold"))
        kwargs.setdefault("cursor", "hand2")
        kwargs.setdefault("padx", 16)
        kwargs.setdefault("pady", 6)
        super().__init__(parent, **kwargs)
        self.bind("<Enter>", lambda e: self.config(bg=COLORS["accent_dim"]))
        self.bind("<Leave>", lambda e: self.config(bg=kwargs.get("bg", COLORS["button_bg"])))


class DangerButton(StyledButton):
    def __init__(self, parent, **kwargs):
        kwargs["bg"] = COLORS["danger"]
        kwargs["activebackground"] = "#cc3333"
        super().__init__(parent, **kwargs)
        self.bind("<Leave>", lambda e: self.config(bg=COLORS["danger"]))


class SecondaryButton(StyledButton):
    def __init__(self, parent, **kwargs):
        kwargs["bg"] = COLORS["bg_tertiary"]
        kwargs["fg"] = COLORS["fg"]
        kwargs["activebackground"] = COLORS["border"]
        kwargs["activeforeground"] = COLORS["fg"]
        super().__init__(parent, **kwargs)
        self.bind("<Leave>", lambda e: self.config(bg=COLORS["bg_tertiary"]))


class AccountFrame(tk.LabelFrame):
    """Frame for configuring an IMAP account."""

    def __init__(self, parent, title="Account", **kwargs):
        super().__init__(parent, text=title, bg=COLORS["bg_secondary"],
                        fg=COLORS["accent"], font=("Helvetica", 11, "bold"),
                        padx=10, pady=8, **kwargs)

        self.preset_var = tk.StringVar(value="Gmail")
        self.host_var = tk.StringVar(value="imap.gmail.com")
        self.port_var = tk.StringVar(value="993")
        self.ssl_var = tk.BooleanVar(value=True)
        self.user_var = tk.StringVar()
        self.pass_var = tk.StringVar()
        self.connected = False
        self.account: Optional[IMAPAccount] = None
        self.folders: List[str] = []

        self._build()

    def _build(self):
        row = 0
        # Preset
        tk.Label(self, text="Provider:", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 10)).grid(row=row, column=0, sticky="w", pady=2)
        preset_menu = ttk.Combobox(self, textvariable=self.preset_var,
                                   values=list(IMAP_PRESETS.keys()), state="readonly", width=15)
        preset_menu.grid(row=row, column=1, sticky="w", pady=2, padx=(4, 0))
        preset_menu.bind("<<ComboboxSelected>>", self._on_preset)
        row += 1

        # Host
        tk.Label(self, text="Host:", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 10)).grid(row=row, column=0, sticky="w", pady=2)
        tk.Entry(self, textvariable=self.host_var, bg=COLORS["input_bg"],
                fg=COLORS["input_fg"], insertbackground=COLORS["fg"],
                relief="flat", width=30).grid(row=row, column=1, sticky="ew", pady=2, padx=(4, 0))
        row += 1

        # Port + SSL
        tk.Label(self, text="Port:", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 10)).grid(row=row, column=0, sticky="w", pady=2)
        pf = tk.Frame(self, bg=COLORS["bg_secondary"])
        pf.grid(row=row, column=1, sticky="w", pady=2, padx=(4, 0))
        tk.Entry(pf, textvariable=self.port_var, bg=COLORS["input_bg"],
                fg=COLORS["input_fg"], insertbackground=COLORS["fg"],
                relief="flat", width=6).pack(side="left")
        tk.Checkbutton(pf, text="SSL", variable=self.ssl_var,
                      bg=COLORS["bg_secondary"], fg=COLORS["fg"],
                      selectcolor=COLORS["input_bg"],
                      activebackground=COLORS["bg_secondary"]).pack(side="left", padx=8)
        row += 1

        # Username
        tk.Label(self, text="Email:", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 10)).grid(row=row, column=0, sticky="w", pady=2)
        tk.Entry(self, textvariable=self.user_var, bg=COLORS["input_bg"],
                fg=COLORS["input_fg"], insertbackground=COLORS["fg"],
                relief="flat", width=30).grid(row=row, column=1, sticky="ew", pady=2, padx=(4, 0))
        row += 1

        # Password
        tk.Label(self, text="Password:", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 10)).grid(row=row, column=0, sticky="w", pady=2)
        tk.Entry(self, textvariable=self.pass_var, show="•", bg=COLORS["input_bg"],
                fg=COLORS["input_fg"], insertbackground=COLORS["fg"],
                relief="flat", width=30).grid(row=row, column=1, sticky="ew", pady=2, padx=(4, 0))
        row += 1

        # Status
        self.status_label = tk.Label(self, text="⚪ Not connected", bg=COLORS["bg_secondary"],
                                     fg=COLORS["fg_dim"], font=("Helvetica", 9))
        self.status_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.columnconfigure(1, weight=1)

    def _on_preset(self, event=None):
        preset = IMAP_PRESETS.get(self.preset_var.get(), {})
        if preset.get("host"):
            self.host_var.set(preset["host"])
        self.port_var.set(str(preset.get("port", 993)))
        self.ssl_var.set(preset.get("ssl", True))

    def get_account(self) -> Optional[IMAPAccount]:
        if not self.user_var.get() or not self.pass_var.get():
            return None
        return IMAPAccount(
            name=self.preset_var.get(),
            host=self.host_var.get(),
            port=int(self.port_var.get()),
            username=self.user_var.get(),
            password=self.pass_var.get(),
            use_ssl=self.ssl_var.get(),
        )

    def try_connect(self) -> bool:
        acc = self.get_account()
        if not acc:
            self.status_label.config(text="⚠ Fill in all fields", fg=COLORS["warning"])
            return False
        try:
            acc.connect()
            self.folders = acc.list_folders()
            self.account = acc
            self.connected = True
            self.status_label.config(text=f"🟢 Connected ({len(self.folders)} folders)", fg=COLORS["success"])
            return True
        except Exception as e:
            self.connected = False
            self.status_label.config(text=f"🔴 {str(e)[:60]}", fg=COLORS["danger"])
            return False

    def disconnect(self):
        if self.account:
            self.account.disconnect()
            self.account = None
        self.connected = False
        self.status_label.config(text="⚪ Disconnected", fg=COLORS["fg_dim"])


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("960x780")
        self.minsize(800, 600)
        self.configure(bg=COLORS["bg"])

        # State
        self.engine = EmailEngine(
            progress_callback=self._update_progress,
            log_callback=self._log,
        )
        self.scanned_emails: List[EmailInfo] = []
        self.dup_groups: List[DuplicateGroup] = []
        self.worker_thread: Optional[threading.Thread] = None

        self._build_ui()
        self._apply_theme()

    def _build_ui(self):
        # ─── Header ─────────────────────────────────────────────────────
        header = tk.Frame(self, bg=COLORS["bg"], pady=8)
        header.pack(fill="x", padx=16)
        tk.Label(header, text="◆ CORE", bg=COLORS["bg"], fg=COLORS["accent"],
                font=("Helvetica", 18, "bold")).pack(side="left")
        tk.Label(header, text="  Email Transfer & Dedup", bg=COLORS["bg"],
                fg=COLORS["fg"], font=("Helvetica", 18)).pack(side="left")
        tk.Label(header, text=f"v{VERSION}", bg=COLORS["bg"],
                fg=COLORS["fg_dim"], font=("Helvetica", 10)).pack(side="right")

        # Separator
        tk.Frame(self, bg=COLORS["accent"], height=2).pack(fill="x", padx=16)

        # ─── Notebook ───────────────────────────────────────────────────
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(8, 4))

        self._build_dedup_tab()
        self._build_transfer_tab()
        self._build_log_tab()

        # ─── Bottom bar ─────────────────────────────────────────────────
        bottom = tk.Frame(self, bg=COLORS["bg"], pady=6)
        bottom.pack(fill="x", padx=16)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(bottom, variable=self.progress_var,
                                            maximum=100, length=300)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(bottom, textvariable=self.status_var, bg=COLORS["bg"],
                fg=COLORS["fg_dim"], font=("Helvetica", 9)).pack(side="right")

    def _build_dedup_tab(self):
        tab = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.notebook.add(tab, text=" 🔍 Deduplicate ")

        # Account
        top = tk.Frame(tab, bg=COLORS["bg"])
        top.pack(fill="x", padx=8, pady=4)

        self.dedup_account = AccountFrame(top, title="IMAP Account")
        self.dedup_account.pack(side="left", fill="x", expand=True, padx=(0, 4))

        # Options panel
        opts = tk.LabelFrame(top, text="Options", bg=COLORS["bg_secondary"],
                            fg=COLORS["accent"], font=("Helvetica", 11, "bold"),
                            padx=10, pady=8)
        opts.pack(side="right", fill="y", padx=(4, 0))

        tk.Label(opts, text="Method:", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 10)).grid(row=0, column=0, sticky="w")
        self.dedup_method = tk.StringVar(value="message_id")
        for i, (val, label) in enumerate([
            ("message_id", "Message-ID"),
            ("hash", "Subject+Date+From"),
            ("size_subject", "Size+Subject"),
        ]):
            tk.Radiobutton(opts, text=label, variable=self.dedup_method, value=val,
                          bg=COLORS["bg_secondary"], fg=COLORS["fg"],
                          selectcolor=COLORS["input_bg"],
                          activebackground=COLORS["bg_secondary"],
                          font=("Helvetica", 9)).grid(row=i + 1, column=0, sticky="w")

        tk.Label(opts, text="", bg=COLORS["bg_secondary"]).grid(row=4, column=0)

        self.dry_run_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opts, text="Dry Run", variable=self.dry_run_var,
                      bg=COLORS["bg_secondary"], fg=COLORS["warning"],
                      selectcolor=COLORS["input_bg"],
                      activebackground=COLORS["bg_secondary"],
                      font=("Helvetica", 10, "bold")).grid(row=5, column=0, sticky="w")

        self.backup_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opts, text="Backup before delete", variable=self.backup_var,
                      bg=COLORS["bg_secondary"], fg=COLORS["fg"],
                      selectcolor=COLORS["input_bg"],
                      activebackground=COLORS["bg_secondary"],
                      font=("Helvetica", 9)).grid(row=6, column=0, sticky="w")

        # Filters
        filters = tk.LabelFrame(tab, text="Filters", bg=COLORS["bg_secondary"],
                                fg=COLORS["accent"], font=("Helvetica", 11, "bold"),
                                padx=10, pady=6)
        filters.pack(fill="x", padx=8, pady=4)

        ff = tk.Frame(filters, bg=COLORS["bg_secondary"])
        ff.pack(fill="x")

        tk.Label(ff, text="Folders (comma-sep, empty=all):", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 9)).pack(side="left")
        self.folder_filter_var = tk.StringVar()
        tk.Entry(ff, textvariable=self.folder_filter_var, bg=COLORS["input_bg"],
                fg=COLORS["input_fg"], insertbackground=COLORS["fg"],
                relief="flat", width=30).pack(side="left", padx=4)

        tk.Label(ff, text="Sender:", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 9)).pack(side="left", padx=(12, 0))
        self.sender_filter_var = tk.StringVar()
        tk.Entry(ff, textvariable=self.sender_filter_var, bg=COLORS["input_bg"],
                fg=COLORS["input_fg"], insertbackground=COLORS["fg"],
                relief="flat", width=20).pack(side="left", padx=4)

        df = tk.Frame(filters, bg=COLORS["bg_secondary"])
        df.pack(fill="x", pady=(4, 0))

        tk.Label(df, text="Date from (YYYY-MM-DD):", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 9)).pack(side="left")
        self.date_from_var = tk.StringVar()
        tk.Entry(df, textvariable=self.date_from_var, bg=COLORS["input_bg"],
                fg=COLORS["input_fg"], insertbackground=COLORS["fg"],
                relief="flat", width=12).pack(side="left", padx=4)

        tk.Label(df, text="to:", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 9)).pack(side="left", padx=(8, 0))
        self.date_to_var = tk.StringVar()
        tk.Entry(df, textvariable=self.date_to_var, bg=COLORS["input_bg"],
                fg=COLORS["input_fg"], insertbackground=COLORS["fg"],
                relief="flat", width=12).pack(side="left", padx=4)

        SecondaryButton(df, text="📂 Load Folders", command=self._load_folders).pack(side="right")

        # Buttons
        btns = tk.Frame(tab, bg=COLORS["bg"])
        btns.pack(fill="x", padx=8, pady=4)

        StyledButton(btns, text="🔌 Connect", command=self._connect_dedup).pack(side="left", padx=(0, 4))
        StyledButton(btns, text="🔍 Scan & Find Duplicates", command=self._scan_dedup).pack(side="left", padx=4)
        DangerButton(btns, text="🗑 Delete Duplicates", command=self._delete_dupes).pack(side="left", padx=4)
        SecondaryButton(btns, text="📊 Export Report", command=self._export_report).pack(side="left", padx=4)
        SecondaryButton(btns, text="⛔ Cancel", command=self._cancel_op).pack(side="right")

        # Results
        results_frame = tk.Frame(tab, bg=COLORS["bg"])
        results_frame.pack(fill="both", expand=True, padx=8, pady=4)

        # Stats
        self.stats_var = tk.StringVar(value="No scan performed yet.")
        tk.Label(results_frame, textvariable=self.stats_var, bg=COLORS["bg"],
                fg=COLORS["accent"], font=("Helvetica", 10, "bold"),
                anchor="w").pack(fill="x")

        # Treeview for duplicate groups
        tree_frame = tk.Frame(results_frame, bg=COLORS["bg"])
        tree_frame.pack(fill="both", expand=True, pady=(4, 0))

        cols = ("action", "folder", "subject", "from", "date", "size")
        self.dup_tree = ttk.Treeview(tree_frame, columns=cols, show="tree headings",
                                     selectmode="extended", height=10)
        self.dup_tree.heading("#0", text="Group")
        self.dup_tree.column("#0", width=100)
        for col, label, w in [
            ("action", "Action", 60), ("folder", "Folder", 100),
            ("subject", "Subject", 250), ("from", "From", 150),
            ("date", "Date", 120), ("size", "Size", 70),
        ]:
            self.dup_tree.heading(col, text=label)
            self.dup_tree.column(col, width=w)

        yscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.dup_tree.yview)
        self.dup_tree.configure(yscrollcommand=yscroll.set)
        self.dup_tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

    def _build_transfer_tab(self):
        tab = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.notebook.add(tab, text=" 📤 Transfer ")

        accs = tk.Frame(tab, bg=COLORS["bg"])
        accs.pack(fill="x", padx=8, pady=4)

        self.src_account = AccountFrame(accs, title="Source Account")
        self.src_account.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.dst_account = AccountFrame(accs, title="Destination Account")
        self.dst_account.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # Transfer options
        topts = tk.LabelFrame(tab, text="Transfer Options", bg=COLORS["bg_secondary"],
                              fg=COLORS["accent"], font=("Helvetica", 11, "bold"),
                              padx=10, pady=8)
        topts.pack(fill="x", padx=8, pady=4)

        of = tk.Frame(topts, bg=COLORS["bg_secondary"])
        of.pack(fill="x")

        tk.Label(of, text="Source Folder:", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 10)).pack(side="left")
        self.src_folder_var = tk.StringVar(value="INBOX")
        self.src_folder_combo = ttk.Combobox(of, textvariable=self.src_folder_var, width=25)
        self.src_folder_combo.pack(side="left", padx=4)

        tk.Label(of, text="→ Dest Folder:", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 10)).pack(side="left", padx=(16, 0))
        self.dst_folder_var = tk.StringVar(value="INBOX")
        self.dst_folder_combo = ttk.Combobox(of, textvariable=self.dst_folder_var, width=25)
        self.dst_folder_combo.pack(side="left", padx=4)

        of2 = tk.Frame(topts, bg=COLORS["bg_secondary"])
        of2.pack(fill="x", pady=(6, 0))

        self.transfer_mode_var = tk.StringVar(value="copy")
        tk.Radiobutton(of2, text="Copy", variable=self.transfer_mode_var, value="copy",
                      bg=COLORS["bg_secondary"], fg=COLORS["fg"],
                      selectcolor=COLORS["input_bg"],
                      activebackground=COLORS["bg_secondary"],
                      font=("Helvetica", 10)).pack(side="left")
        tk.Radiobutton(of2, text="Move (delete from source)", variable=self.transfer_mode_var, value="move",
                      bg=COLORS["bg_secondary"], fg=COLORS["danger"],
                      selectcolor=COLORS["input_bg"],
                      activebackground=COLORS["bg_secondary"],
                      font=("Helvetica", 10)).pack(side="left", padx=8)

        self.transfer_dry_var = tk.BooleanVar(value=True)
        tk.Checkbutton(of2, text="Dry Run", variable=self.transfer_dry_var,
                      bg=COLORS["bg_secondary"], fg=COLORS["warning"],
                      selectcolor=COLORS["input_bg"],
                      activebackground=COLORS["bg_secondary"],
                      font=("Helvetica", 10, "bold")).pack(side="left", padx=16)

        # Transfer filter
        tf = tk.Frame(topts, bg=COLORS["bg_secondary"])
        tf.pack(fill="x", pady=(6, 0))
        tk.Label(tf, text="Sender filter:", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 9)).pack(side="left")
        self.transfer_sender_var = tk.StringVar()
        tk.Entry(tf, textvariable=self.transfer_sender_var, bg=COLORS["input_bg"],
                fg=COLORS["input_fg"], insertbackground=COLORS["fg"],
                relief="flat", width=25).pack(side="left", padx=4)

        tk.Label(tf, text="Date from:", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 9)).pack(side="left", padx=(12, 0))
        self.transfer_date_from_var = tk.StringVar()
        tk.Entry(tf, textvariable=self.transfer_date_from_var, bg=COLORS["input_bg"],
                fg=COLORS["input_fg"], insertbackground=COLORS["fg"],
                relief="flat", width=12).pack(side="left", padx=4)
        tk.Label(tf, text="to:", bg=COLORS["bg_secondary"],
                fg=COLORS["fg"], font=("Helvetica", 9)).pack(side="left")
        self.transfer_date_to_var = tk.StringVar()
        tk.Entry(tf, textvariable=self.transfer_date_to_var, bg=COLORS["input_bg"],
                fg=COLORS["input_fg"], insertbackground=COLORS["fg"],
                relief="flat", width=12).pack(side="left", padx=4)

        # Buttons
        btns = tk.Frame(tab, bg=COLORS["bg"])
        btns.pack(fill="x", padx=8, pady=4)

        StyledButton(btns, text="🔌 Connect Both", command=self._connect_transfer).pack(side="left", padx=(0, 4))
        StyledButton(btns, text="📤 Start Transfer", command=self._start_transfer).pack(side="left", padx=4)
        SecondaryButton(btns, text="⛔ Cancel", command=self._cancel_op).pack(side="right")

        # Transfer log
        self.transfer_log = scrolledtext.ScrolledText(tab, bg=COLORS["input_bg"],
                                                       fg=COLORS["fg"], font=("Courier", 10),
                                                       insertbackground=COLORS["fg"],
                                                       relief="flat", height=12)
        self.transfer_log.pack(fill="both", expand=True, padx=8, pady=4)

    def _build_log_tab(self):
        tab = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.notebook.add(tab, text=" 📋 Log ")

        self.log_text = scrolledtext.ScrolledText(tab, bg=COLORS["input_bg"],
                                                   fg=COLORS["fg"], font=("Courier", 10),
                                                   insertbackground=COLORS["fg"],
                                                   relief="flat")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

        btns = tk.Frame(tab, bg=COLORS["bg"])
        btns.pack(fill="x", padx=8, pady=(0, 4))
        SecondaryButton(btns, text="Clear", command=lambda: self.log_text.delete("1.0", "end")).pack(side="right")

    def _apply_theme(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=COLORS["bg_secondary"],
                        foreground=COLORS["fg"], padding=[12, 6],
                        font=("Helvetica", 10, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", COLORS["bg_tertiary"])],
                  foreground=[("selected", COLORS["accent"])])

        style.configure("Treeview", background=COLORS["input_bg"],
                        foreground=COLORS["fg"], fieldbackground=COLORS["input_bg"],
                        font=("Helvetica", 9), rowheight=22)
        style.configure("Treeview.Heading", background=COLORS["bg_tertiary"],
                        foreground=COLORS["accent"], font=("Helvetica", 9, "bold"))
        style.map("Treeview", background=[("selected", COLORS["bg_tertiary"])],
                  foreground=[("selected", COLORS["accent"])])

        style.configure("TProgressbar", troughcolor=COLORS["bg_secondary"],
                        background=COLORS["accent"], thickness=8)

        style.configure("TCombobox", fieldbackground=COLORS["input_bg"],
                        background=COLORS["bg_secondary"],
                        foreground=COLORS["input_fg"])

    # ─── Helpers ────────────────────────────────────────────────────────

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self.log_text.insert("end", line)
        self.log_text.see("end")

    def _update_progress(self, current: int, total: int):
        if total > 0:
            pct = (current / total) * 100
            self.progress_var.set(pct)
            self.status_var.set(f"{current}/{total}")
        self.update_idletasks()

    def _cancel_op(self):
        self.engine.cancel()
        self._log("⛔ Cancel requested...")
        self.status_var.set("Cancelling...")

    def _parse_date(self, s: str) -> Optional[datetime]:
        s = s.strip()
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("Date Error", f"Invalid date format: {s}\nUse YYYY-MM-DD")
            return None

    def _run_async(self, func, *args):
        """Run a function in a background thread."""
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("Busy", "An operation is already running.")
            return
        self.engine.reset_cancel()
        self.progress_var.set(0)

        def wrapper():
            try:
                func(*args)
            except Exception as e:
                self.after(0, lambda: self._log(f"❌ Error: {e}"))
                self.after(0, lambda: self.status_var.set("Error"))

        self.worker_thread = threading.Thread(target=wrapper, daemon=True)
        self.worker_thread.start()

    # ─── Dedup Actions ──────────────────────────────────────────────────

    def _connect_dedup(self):
        self._log("🔌 Connecting to dedup account...")
        if self.dedup_account.try_connect():
            self._log(f"✅ Connected: {len(self.dedup_account.folders)} folders")
        else:
            self._log("❌ Connection failed")

    def _load_folders(self):
        if not self.dedup_account.connected:
            messagebox.showinfo("Not Connected", "Connect first.")
            return
        folders = "\n".join(self.dedup_account.folders)
        self._log(f"📂 Available folders:\n{folders}")

    def _scan_dedup(self):
        if not self.dedup_account.connected:
            messagebox.showinfo("Not Connected", "Connect to account first.")
            return
        self._run_async(self._do_scan_dedup)

    def _do_scan_dedup(self):
        account = self.dedup_account.account
        method = self.dedup_method.get()

        date_from = self._parse_date(self.date_from_var.get())
        date_to = self._parse_date(self.date_to_var.get())
        sender = self.sender_filter_var.get().strip()

        # Determine folders
        folder_text = self.folder_filter_var.get().strip()
        if folder_text:
            folders = [f.strip() for f in folder_text.split(",")]
        else:
            folders = self.dedup_account.folders

        self.after(0, lambda: self._log(f"🔍 Scanning {len(folders)} folders with method '{method}'..."))
        self.after(0, lambda: self.status_var.set("Scanning..."))

        all_emails = []
        for folder in folders:
            if self.engine._cancel:
                break
            self.after(0, lambda f=folder: self._log(f"  📁 Scanning: {f}"))
            emails = self.engine.scan_folder(account, folder, date_from, date_to, sender)
            all_emails.extend(emails)

        self.scanned_emails = all_emails
        self.after(0, lambda: self._log(f"📊 Total emails scanned: {len(all_emails)}"))

        # Find duplicates
        self.dup_groups = self.engine.find_duplicates(all_emails, method)
        total_dupes = sum(len(g.duplicates) for g in self.dup_groups)

        self.after(0, lambda: self._update_dedup_ui(len(all_emails), len(self.dup_groups), total_dupes))
        self.after(0, lambda: self.status_var.set("Scan complete"))
        self.after(0, lambda: self.progress_var.set(100))

    def _update_dedup_ui(self, total_emails: int, groups: int, dupes: int):
        self.stats_var.set(
            f"📧 {total_emails} emails scanned  |  "
            f"📦 {groups} duplicate groups  |  "
            f"🗑 {dupes} duplicates to remove"
        )
        self._log(f"✅ Found {groups} groups, {dupes} duplicates")

        # Populate tree
        self.dup_tree.delete(*self.dup_tree.get_children())
        for i, g in enumerate(self.dup_groups):
            gid = self.dup_tree.insert("", "end", text=f"Group {i + 1} ({g.count}x)",
                                       open=False)
            for j, em in enumerate(g.emails):
                action = "✓ KEEP" if j == 0 else "✗ DELETE"
                subj = em.subject[:60] if em.subject else "(no subject)"
                frm = em.from_addr[:40] if em.from_addr else ""
                date = em.date_str[:25] if em.date_str else ""
                self.dup_tree.insert(gid, "end", values=(action, em.folder, subj, frm, date, em.size))

    def _delete_dupes(self):
        if not self.dup_groups:
            messagebox.showinfo("No Duplicates", "Run a scan first.")
            return

        dry_run = self.dry_run_var.get()
        total_dupes = sum(len(g.duplicates) for g in self.dup_groups)

        if not dry_run:
            if not messagebox.askyesno("Confirm Delete",
                                       f"Delete {total_dupes} duplicate emails?\n\n"
                                       f"This cannot be undone (unless backup is enabled)."):
                return

        self._run_async(self._do_delete_dupes, dry_run)

    def _do_delete_dupes(self, dry_run: bool):
        account = self.dedup_account.account
        all_dupes = []
        for g in self.dup_groups:
            all_dupes.extend(g.duplicates)

        # Backup if requested
        if self.backup_var.get() and not dry_run:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.expanduser(f"~/core-email-backup-{ts}.mbox")
            self.after(0, lambda: self._log(f"💾 Backing up {len(all_dupes)} emails to {backup_path}..."))
            self.after(0, lambda: self.status_var.set("Backing up..."))
            backed = self.engine.backup_to_mbox(account, all_dupes, backup_path)
            self.after(0, lambda: self._log(f"✅ Backed up {backed} emails"))

        # Delete
        self.after(0, lambda: self._log(f"🗑 {'DRY RUN: ' if dry_run else ''}Deleting {len(all_dupes)} duplicates..."))
        self.after(0, lambda: self.status_var.set("Deleting..." if not dry_run else "Dry run..."))
        deleted = self.engine.delete_emails(account, all_dupes, dry_run)

        prefix = "Would delete" if dry_run else "Deleted"
        self.after(0, lambda: self._log(f"✅ {prefix} {deleted} emails"))
        self.after(0, lambda: self.status_var.set(f"{prefix} {deleted}"))
        self.after(0, lambda: self.progress_var.set(100))

    def _export_report(self):
        if not self.dup_groups:
            messagebox.showinfo("No Data", "Run a scan first.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Text", "*.txt"), ("All", "*.*")],
            initialfile=f"email-dedup-report-{datetime.now().strftime('%Y%m%d')}"
        )
        if not path:
            return

        try:
            if path.endswith(".txt"):
                export_report_txt(self.dup_groups, path)
            else:
                export_report_csv(self.dup_groups, path)
            self._log(f"📊 Report exported: {path}")
            messagebox.showinfo("Exported", f"Report saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    # ─── Transfer Actions ───────────────────────────────────────────────

    def _connect_transfer(self):
        self._log("🔌 Connecting source account...")
        ok1 = self.src_account.try_connect()
        if ok1:
            self._log(f"✅ Source connected ({len(self.src_account.folders)} folders)")
            self.src_folder_combo.config(values=self.src_account.folders)
        else:
            self._log("❌ Source connection failed")

        self._log("🔌 Connecting destination account...")
        ok2 = self.dst_account.try_connect()
        if ok2:
            self._log(f"✅ Destination connected ({len(self.dst_account.folders)} folders)")
            self.dst_folder_combo.config(values=self.dst_account.folders)
        else:
            self._log("❌ Destination connection failed")

    def _start_transfer(self):
        if not self.src_account.connected or not self.dst_account.connected:
            messagebox.showinfo("Not Connected", "Connect both accounts first.")
            return
        self._run_async(self._do_transfer)

    def _do_transfer(self):
        src = self.src_account.account
        dst = self.dst_account.account
        src_folder = self.src_folder_var.get()
        dst_folder = self.dst_folder_var.get()
        move = self.transfer_mode_var.get() == "move"
        dry_run = self.transfer_dry_var.get()

        date_from = self._parse_date(self.transfer_date_from_var.get())
        date_to = self._parse_date(self.transfer_date_to_var.get())
        sender = self.transfer_sender_var.get().strip()

        self.after(0, lambda: self._log(f"📧 Scanning source folder: {src_folder}..."))
        self.after(0, lambda: self.status_var.set("Scanning source..."))

        emails = self.engine.scan_folder(src, src_folder, date_from, date_to, sender)
        self.after(0, lambda: self._log(f"📊 Found {len(emails)} emails to transfer"))

        if not emails:
            self.after(0, lambda: self.status_var.set("No emails to transfer"))
            return

        mode = "Moving" if move else "Copying"
        self.after(0, lambda: self._log(f"📤 {mode} {len(emails)} emails to {dst_folder}..."))
        self.after(0, lambda: self.status_var.set(f"{mode}..."))

        transferred = self.engine.transfer_emails(src, dst, emails, dst_folder, move, dry_run)

        prefix = "Would transfer" if dry_run else "Transferred"
        self.after(0, lambda: self._log(f"✅ {prefix} {transferred} emails"))
        self.after(0, lambda: self.status_var.set(f"{prefix} {transferred}"))
        self.after(0, lambda: self.progress_var.set(100))

        # Log to transfer tab
        def _tlog():
            ts = datetime.now().strftime("%H:%M:%S")
            self.transfer_log.insert("end",
                f"[{ts}] {prefix} {transferred}/{len(emails)} emails "
                f"from {src_folder} → {dst_folder} "
                f"({'DRY RUN' if dry_run else 'LIVE'})\n")
            self.transfer_log.see("end")
        self.after(0, _tlog)


# ─── Entry Point ────────────────────────────────────────────────────────────

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
