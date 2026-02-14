// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod email;

use email::{
    DedupMethod, DedupResult, DuplicateGroup, EmailHeader, ImapAccount, MailboxInfo,
    TransferResult,
};
use std::path::PathBuf;

// ── Tauri Commands ─────────────────────────────────────────────────────────

#[tauri::command]
fn get_provider_defaults(provider: String) -> (String, u16) {
    let (host, port) = email::imap_defaults(&provider);
    (host.to_string(), port)
}

#[tauri::command]
fn test_connection(account: ImapAccount) -> Result<Vec<MailboxInfo>, String> {
    let mut session = email::connect(&account)?;
    let mailboxes = email::list_mailboxes(&mut session)?;
    let _ = session.logout();
    Ok(mailboxes)
}

#[tauri::command]
fn fetch_headers(account: ImapAccount, mailbox: String) -> Result<Vec<EmailHeader>, String> {
    let mut session = email::connect(&account)?;
    let headers = email::fetch_headers(&mut session, &mailbox)?;
    let _ = session.logout();
    Ok(headers)
}

#[tauri::command]
fn find_duplicates(
    account: ImapAccount,
    mailbox: String,
    method: String,
) -> Result<DedupResult, String> {
    let mut session = email::connect(&account)?;
    let headers = email::fetch_headers(&mut session, &mailbox)?;
    let _ = session.logout();

    let dedup_method = match method.as_str() {
        "message-id" => DedupMethod::MessageId,
        "subject-date" => DedupMethod::SubjectDateHash,
        "size-subject" => DedupMethod::SizeSubject,
        _ => return Err(format!("Unknown method: {method}")),
    };

    Ok(email::find_duplicates(&headers, dedup_method))
}

#[tauri::command]
fn delete_duplicates(
    account: ImapAccount,
    mailbox: String,
    groups: Vec<DuplicateGroup>,
    dry_run: bool,
) -> Result<usize, String> {
    let mut session = email::connect(&account)?;
    let result = email::delete_duplicates(&mut session, &mailbox, &groups, dry_run)?;
    let _ = session.logout();
    Ok(result)
}

#[tauri::command]
fn transfer_emails(
    src_account: ImapAccount,
    dst_account: ImapAccount,
    src_mailbox: String,
    dst_mailbox: String,
) -> Result<TransferResult, String> {
    let mut src_session = email::connect(&src_account)?;
    let mut dst_session = email::connect(&dst_account)?;
    let result = email::transfer_emails(
        &mut src_session,
        &mut dst_session,
        &src_mailbox,
        &dst_mailbox,
    )?;
    let _ = src_session.logout();
    let _ = dst_session.logout();
    Ok(result)
}

#[tauri::command]
fn backup_mbox(
    account: ImapAccount,
    mailbox: String,
    output_path: String,
) -> Result<usize, String> {
    let mut session = email::connect(&account)?;
    let path = PathBuf::from(output_path);
    let count = email::backup_to_mbox(&mut session, &mailbox, &path)?;
    let _ = session.logout();
    Ok(count)
}

// ── Main ───────────────────────────────────────────────────────────────────

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_provider_defaults,
            test_connection,
            fetch_headers,
            find_duplicates,
            delete_duplicates,
            transfer_emails,
            backup_mbox,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
