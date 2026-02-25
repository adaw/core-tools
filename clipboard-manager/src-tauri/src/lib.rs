mod db;

use db::{ClipItem, Database};
use std::sync::Arc;
use tauri::{Manager, State};
use tokio::sync::Mutex as TokioMutex;
use arboard::Clipboard;

struct AppState {
    db: Database,
    last_clipboard: TokioMutex<String>,
    monitoring: TokioMutex<bool>,
}

// ── Tauri Commands ──────────────────────────────────────────────────────────

#[tauri::command]
async fn get_items(
    state: State<'_, Arc<AppState>>,
    query: String,
    category: String,
    limit: usize,
    offset: usize,
) -> Result<Vec<ClipItem>, String> {
    state.db.search(&query, &category, limit, offset)
}

#[tauri::command]
async fn get_count(
    state: State<'_, Arc<AppState>>,
    query: String,
    category: String,
) -> Result<usize, String> {
    state.db.count(&query, &category)
}

#[tauri::command]
async fn add_item(state: State<'_, Arc<AppState>>, content: String) -> Result<Option<ClipItem>, String> {
    state.db.add(&content)
}

#[tauri::command]
async fn delete_item(state: State<'_, Arc<AppState>>, id: String) -> Result<(), String> {
    state.db.delete(&id)
}

#[tauri::command]
async fn toggle_pin(state: State<'_, Arc<AppState>>, id: String) -> Result<bool, String> {
    state.db.toggle_pin(&id)
}

#[tauri::command]
async fn toggle_favorite(state: State<'_, Arc<AppState>>, id: String) -> Result<bool, String> {
    state.db.toggle_favorite(&id)
}

#[tauri::command]
async fn clear_unpinned(state: State<'_, Arc<AppState>>) -> Result<usize, String> {
    state.db.clear_unpinned()
}

#[tauri::command]
async fn export_data(state: State<'_, Arc<AppState>>, format: String) -> Result<String, String> {
    match format.as_str() {
        "csv" => state.db.export_csv(),
        _ => state.db.export_json(),
    }
}

#[tauri::command]
async fn cleanup_old(state: State<'_, Arc<AppState>>, days: i64) -> Result<usize, String> {
    state.db.cleanup_old(days)
}

#[tauri::command]
async fn copy_to_clipboard(state: State<'_, Arc<AppState>>, content: String) -> Result<(), String> {
    // Update last_clipboard to avoid re-detecting
    {
        let mut last = state.last_clipboard.lock().await;
        *last = content.clone();
    }
    let mut clip = Clipboard::new().map_err(|e| e.to_string())?;
    clip.set_text(&content).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
async fn set_monitoring(state: State<'_, Arc<AppState>>, enabled: bool) -> Result<(), String> {
    let mut m = state.monitoring.lock().await;
    *m = enabled;
    Ok(())
}

#[tauri::command]
async fn get_monitoring(state: State<'_, Arc<AppState>>) -> Result<bool, String> {
    let m = state.monitoring.lock().await;
    Ok(*m)
}

// ── Clipboard Monitoring ────────────────────────────────────────────────────

fn start_clipboard_monitor(app: tauri::AppHandle, state: Arc<AppState>) {
    std::thread::spawn(move || {
        let mut clipboard = match Clipboard::new() {
            Ok(c) => c,
            Err(_) => return,
        };

        loop {
            std::thread::sleep(std::time::Duration::from_millis(500));

            let monitoring = {
                let rt = tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
                rt.block_on(async { *state.monitoring.lock().await })
            };

            if !monitoring { continue; }

            let current = match clipboard.get_text() {
                Ok(t) => t,
                Err(_) => continue,
            };

            if current.trim().is_empty() { continue; }

            let is_new = {
                let rt = tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
                rt.block_on(async {
                    let mut last = state.last_clipboard.lock().await;
                    if *last == current {
                        false
                    } else {
                        *last = current.clone();
                        true
                    }
                })
            };

            if is_new {
                if let Ok(Some(_)) = state.db.add(&current) {
                    let _ = app.emit("clipboard-changed", ());
                }
            }
        }
    });
}

// ── App Setup ───────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let db = Database::new().expect("Failed to initialize database");
    let state = Arc::new(AppState {
        db,
        last_clipboard: TokioMutex::new(String::new()),
        monitoring: TokioMutex::new(true),
    });

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(state.clone())
        .setup(move |app| {
            let handle = app.handle().clone();
            start_clipboard_monitor(handle, state.clone());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_items,
            get_count,
            add_item,
            delete_item,
            toggle_pin,
            toggle_favorite,
            clear_unpinned,
            export_data,
            cleanup_old,
            copy_to_clipboard,
            set_monitoring,
            get_monitoring,
        ])
        .run(tauri::generate_context!())
        .expect("error while running CORE Clipboard Manager");
}
