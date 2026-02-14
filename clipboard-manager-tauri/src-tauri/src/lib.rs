mod db;

use arboard::Clipboard;
use db::{ClipEntry, Database};
use serde::Serialize;
use tauri::Emitter;
use sha2::{Digest, Sha256};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{AppHandle, Manager, State};

struct AppState {
    db: Mutex<Database>,
}

#[derive(Serialize)]
struct Stats {
    total: usize,
    pinned: usize,
    text: usize,
    link: usize,
    code: usize,
    image: usize,
}

fn detect_category(content: &str) -> String {
    let trimmed = content.trim();
    if trimmed.starts_with("http://") || trimmed.starts_with("https://") {
        "link".into()
    } else if trimmed.contains("fn ") || trimmed.contains("function ")
        || trimmed.contains("def ") || trimmed.contains("class ")
        || trimmed.contains("import ") || trimmed.contains("const ")
        || trimmed.contains("let ") || trimmed.contains("var ")
        || trimmed.contains("{") && trimmed.contains("}")
    {
        "code".into()
    } else {
        "text".into()
    }
}

fn content_hash(content: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(content.as_bytes());
    hex::encode(hasher.finalize())
}

#[tauri::command]
fn get_entries(
    state: State<AppState>,
    query: Option<String>,
    category: Option<String>,
    pinned_only: bool,
    limit: Option<usize>,
    offset: Option<usize>,
) -> Result<Vec<ClipEntry>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.get_entries(
        query.as_deref(),
        category.as_deref(),
        pinned_only,
        limit.unwrap_or(100),
        offset.unwrap_or(0),
    )
    .map_err(|e| e.to_string())
}

#[tauri::command]
fn toggle_pin(state: State<AppState>, id: i64) -> Result<bool, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.toggle_pin(id).map_err(|e| e.to_string())
}

#[tauri::command]
fn delete_entry(state: State<AppState>, id: i64) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.delete(id).map_err(|e| e.to_string())
}

#[tauri::command]
fn clear_all(state: State<AppState>) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.clear_all().map_err(|e| e.to_string())
}

#[tauri::command]
fn get_stats(state: State<AppState>) -> Result<Stats, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let all = db.get_entries(None, None, false, 100_000, 0).map_err(|e| e.to_string())?;
    let pinned = all.iter().filter(|e| e.pinned).count();
    let text = all.iter().filter(|e| e.category == "text").count();
    let link = all.iter().filter(|e| e.category == "link").count();
    let code = all.iter().filter(|e| e.category == "code").count();
    let image = all.iter().filter(|e| e.category == "image").count();
    Ok(Stats { total: all.len(), pinned, text, link, code, image })
}

#[tauri::command]
fn export_entries(
    state: State<AppState>,
    format: String,
) -> Result<String, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let entries = db.get_entries(None, None, false, 100_000, 0).map_err(|e| e.to_string())?;

    match format.as_str() {
        "json" => serde_json::to_string_pretty(&entries).map_err(|e| e.to_string()),
        "txt" => {
            let lines: Vec<String> = entries
                .iter()
                .map(|e| format!("[{}] [{}] {}", e.created_at, e.category, e.content))
                .collect();
            Ok(lines.join("\n"))
        }
        _ => Err("Unsupported format. Use 'json' or 'txt'.".into()),
    }
}

#[tauri::command]
fn copy_to_clipboard(content: String) -> Result<(), String> {
    let mut clip = Clipboard::new().map_err(|e| e.to_string())?;
    clip.set_text(&content).map_err(|e| e.to_string())
}

fn start_clipboard_monitor(app: AppHandle) {
    std::thread::spawn(move || {
        let mut last_hash = String::new();
        loop {
            std::thread::sleep(Duration::from_millis(500));
            let text = {
                let Ok(mut clip) = Clipboard::new() else { continue };
                match clip.get_text() {
                    Ok(t) if !t.trim().is_empty() => t,
                    _ => continue,
                }
            };
            let hash = content_hash(&text);
            if hash == last_hash {
                continue;
            }
            last_hash = hash;
            let category = detect_category(&text);
            let state = app.state::<AppState>();
            if let Ok(db) = state.db.lock() {
                let _ = db.insert(&text, &category);
                let _ = db.enforce_limit(1000);
            }
            let _ = app.emit("clipboard-updated", ());
        }
    });
}

pub fn run() {
    let db = Database::new().expect("Failed to initialize database");

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(AppState { db: Mutex::new(db) })
        .invoke_handler(tauri::generate_handler![
            get_entries,
            toggle_pin,
            delete_entry,
            clear_all,
            get_stats,
            export_entries,
            copy_to_clipboard,
        ])
        .setup(|app| {
            start_clipboard_monitor(app.handle().clone());
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
