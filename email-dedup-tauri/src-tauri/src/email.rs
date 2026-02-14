use imap::Session;
use mailparse::parse_mail;
use native_tls::{TlsConnector, TlsStream};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::io::Write;
use std::net::TcpStream;
use std::path::PathBuf;

// ── Types ──────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImapAccount {
    pub label: String,
    pub host: String,
    pub port: u16,
    pub username: String,
    pub password: String,
    pub provider: String, // gmail | outlook | icloud | generic
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MailboxInfo {
    pub name: String,
    pub message_count: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmailHeader {
    pub uid: u32,
    pub message_id: String,
    pub subject: String,
    pub from: String,
    pub date: String,
    pub size: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DuplicateGroup {
    pub key: String,
    pub method: String,
    pub emails: Vec<EmailHeader>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DedupResult {
    pub total_scanned: usize,
    pub duplicate_groups: Vec<DuplicateGroup>,
    pub total_duplicates: usize,
    pub dry_run: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransferProgress {
    pub transferred: usize,
    pub total: usize,
    pub current_subject: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransferResult {
    pub transferred: usize,
    pub failed: usize,
    pub errors: Vec<String>,
}

// ── IMAP Connection ────────────────────────────────────────────────────────

pub fn imap_defaults(provider: &str) -> (&'static str, u16) {
    match provider {
        "gmail" => ("imap.gmail.com", 993),
        "outlook" => ("outlook.office365.com", 993),
        "icloud" => ("imap.mail.me.com", 993),
        _ => ("", 993),
    }
}

pub fn connect(account: &ImapAccount) -> Result<Session<TlsStream<TcpStream>>, String> {
    let tls = TlsConnector::builder()
        .build()
        .map_err(|e| format!("TLS error: {e}"))?;

    let client = imap::connect(
        (account.host.as_str(), account.port),
        &account.host,
        &tls,
    )
    .map_err(|e| format!("Connection error: {e}"))?;

    let session = client
        .login(&account.username, &account.password)
        .map_err(|e| format!("Login failed: {:?}", e.0))?;

    Ok(session)
}

// ── Mailbox Listing ────────────────────────────────────────────────────────

pub fn list_mailboxes(session: &mut Session<TlsStream<TcpStream>>) -> Result<Vec<MailboxInfo>, String> {
    let names = session
        .list(None, Some("*"))
        .map_err(|e| format!("List error: {e}"))?;

    let mut mailboxes = Vec::new();
    for name in names.iter() {
        let mbox_name = name.name().to_string();
        let count = match session.select(&mbox_name) {
            Ok(mb) => mb.exists,
            Err(_) => 0,
        };
        mailboxes.push(MailboxInfo {
            name: mbox_name,
            message_count: count,
        });
    }

    Ok(mailboxes)
}

// ── Fetch Headers ──────────────────────────────────────────────────────────

pub fn fetch_headers(
    session: &mut Session<TlsStream<TcpStream>>,
    mailbox: &str,
) -> Result<Vec<EmailHeader>, String> {
    let mb = session
        .select(mailbox)
        .map_err(|e| format!("Select error: {e}"))?;

    if mb.exists == 0 {
        return Ok(Vec::new());
    }

    let range = format!("1:{}", mb.exists);
    let messages = session
        .fetch(&range, "(UID RFC822.SIZE BODY.PEEK[HEADER.FIELDS (MESSAGE-ID SUBJECT FROM DATE)])")
        .map_err(|e| format!("Fetch error: {e}"))?;

    let mut headers = Vec::new();
    for msg in messages.iter() {
        let uid = msg.uid.unwrap_or(0);
        let size = msg.size.unwrap_or(0);
        let header_bytes = msg
            .header()
            .or_else(|| msg.body())
            .unwrap_or_default();

        let parsed = parse_mail(header_bytes).unwrap_or_else(|_| {
            parse_mail(b"").unwrap()
        });

        let get_hdr = |name: &str| -> String {
            parsed
                .headers
                .iter()
                .find(|h| h.get_key().eq_ignore_ascii_case(name))
                .map(|h| h.get_value())
                .unwrap_or_default()
        };

        headers.push(EmailHeader {
            uid,
            message_id: get_hdr("Message-ID"),
            subject: get_hdr("Subject"),
            from: get_hdr("From"),
            date: get_hdr("Date"),
            size,
        });
    }

    Ok(headers)
}

// ── Dedup Methods ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DedupMethod {
    MessageId,
    SubjectDateHash,
    SizeSubject,
}

fn dedup_key(email: &EmailHeader, method: &DedupMethod) -> Option<String> {
    match method {
        DedupMethod::MessageId => {
            let mid = email.message_id.trim().to_string();
            if mid.is_empty() {
                None
            } else {
                Some(mid)
            }
        }
        DedupMethod::SubjectDateHash => {
            let input = format!("{}|{}", email.subject.trim(), email.date.trim());
            if input == "|" {
                return None;
            }
            let mut hasher = Sha256::new();
            hasher.update(input.as_bytes());
            Some(format!("{:x}", hasher.finalize()))
        }
        DedupMethod::SizeSubject => {
            let input = format!("{}|{}", email.size, email.subject.trim());
            if email.subject.trim().is_empty() {
                return None;
            }
            Some(input)
        }
    }
}

pub fn find_duplicates(headers: &[EmailHeader], method: DedupMethod) -> DedupResult {
    let method_name = match &method {
        DedupMethod::MessageId => "Message-ID",
        DedupMethod::SubjectDateHash => "Subject+Date Hash",
        DedupMethod::SizeSubject => "Size+Subject",
    };

    let mut groups: HashMap<String, Vec<EmailHeader>> = HashMap::new();

    for email in headers {
        if let Some(key) = dedup_key(email, &method) {
            groups.entry(key).or_default().push(email.clone());
        }
    }

    let duplicate_groups: Vec<DuplicateGroup> = groups
        .into_iter()
        .filter(|(_, emails)| emails.len() > 1)
        .map(|(key, emails)| DuplicateGroup {
            key,
            method: method_name.to_string(),
            emails,
        })
        .collect();

    let total_duplicates: usize = duplicate_groups
        .iter()
        .map(|g| g.emails.len() - 1) // keep one, rest are dupes
        .sum();

    DedupResult {
        total_scanned: headers.len(),
        duplicate_groups,
        total_duplicates,
        dry_run: true,
    }
}

// ── Delete Duplicates ──────────────────────────────────────────────────────

pub fn delete_duplicates(
    session: &mut Session<TlsStream<TcpStream>>,
    mailbox: &str,
    groups: &[DuplicateGroup],
    dry_run: bool,
) -> Result<usize, String> {
    if dry_run {
        let count: usize = groups.iter().map(|g| g.emails.len() - 1).sum();
        return Ok(count);
    }

    session
        .select(mailbox)
        .map_err(|e| format!("Select error: {e}"))?;

    let mut deleted = 0;
    for group in groups {
        // Keep first, delete rest
        for email in group.emails.iter().skip(1) {
            let uid_str = format!("{}", email.uid);
            if session.uid_store(&uid_str, "+FLAGS (\\Deleted)").is_ok() {
                deleted += 1;
            }
        }
    }

    session.expunge().map_err(|e| format!("Expunge error: {e}"))?;
    Ok(deleted)
}

// ── Transfer Emails ────────────────────────────────────────────────────────

pub fn transfer_emails(
    src_session: &mut Session<TlsStream<TcpStream>>,
    dst_session: &mut Session<TlsStream<TcpStream>>,
    src_mailbox: &str,
    dst_mailbox: &str,
) -> Result<TransferResult, String> {
    let mb = src_session
        .select(src_mailbox)
        .map_err(|e| format!("Source select error: {e}"))?;

    if mb.exists == 0 {
        return Ok(TransferResult {
            transferred: 0,
            failed: 0,
            errors: vec![],
        });
    }

    let range = format!("1:{}", mb.exists);
    let messages = src_session
        .fetch(&range, "(UID RFC822)")
        .map_err(|e| format!("Fetch error: {e}"))?;

    let mut transferred = 0;
    let mut failed = 0;
    let mut errors = Vec::new();

    for msg in messages.iter() {
        let body = match msg.body() {
            Some(b) => b,
            None => {
                failed += 1;
                errors.push(format!("UID {}: no body", msg.uid.unwrap_or(0)));
                continue;
            }
        };

        match dst_session.append(dst_mailbox, body) {
            Ok(_) => transferred += 1,
            Err(e) => {
                failed += 1;
                errors.push(format!("UID {}: {e}", msg.uid.unwrap_or(0)));
            }
        }
    }

    Ok(TransferResult {
        transferred,
        failed,
        errors,
    })
}

// ── Backup to .mbox ───────────────────────────────────────────────────────

pub fn backup_to_mbox(
    session: &mut Session<TlsStream<TcpStream>>,
    mailbox: &str,
    output_path: &PathBuf,
) -> Result<usize, String> {
    let mb = session
        .select(mailbox)
        .map_err(|e| format!("Select error: {e}"))?;

    if mb.exists == 0 {
        return Ok(0);
    }

    let range = format!("1:{}", mb.exists);
    let messages = session
        .fetch(&range, "(UID RFC822)")
        .map_err(|e| format!("Fetch error: {e}"))?;

    let mut file = std::fs::File::create(output_path)
        .map_err(|e| format!("File create error: {e}"))?;

    let mut count = 0;
    for msg in messages.iter() {
        if let Some(body) = msg.body() {
            // mbox format: "From " line separator
            writeln!(file, "From - {}", chrono::Utc::now().to_rfc2822())
                .map_err(|e| format!("Write error: {e}"))?;
            file.write_all(body)
                .map_err(|e| format!("Write error: {e}"))?;
            writeln!(file).map_err(|e| format!("Write error: {e}"))?;
            count += 1;
        }
    }

    Ok(count)
}
