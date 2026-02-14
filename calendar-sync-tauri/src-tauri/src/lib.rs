mod db;
mod caldav;
mod ics;
mod sync_engine;
mod models;

use models::{CalendarSource, LogEntry};
// Tauri commands

#[tauri::command]
async fn add_source(source_type: String, config: String) -> Result<String, String> {
    let source = CalendarSource::new(&source_type, &config);
    db::insert_source(&source).map_err(|e| e.to_string())?;
    Ok(format!("Added {} source", source_type))
}

#[tauri::command]
async fn add_caldav_source(url: String, username: String, password: String) -> Result<String, String> {
    let config = serde_json::json!({
        "url": url,
        "username": username,
        "password": password,
    }).to_string();
    let source = CalendarSource::new("caldav", &config);
    db::insert_source(&source).map_err(|e| e.to_string())?;
    Ok("CalDAV source added".into())
}

#[tauri::command]
async fn import_ics_file() -> Result<String, String> {
    // In real usage, tauri-plugin-dialog would open a file picker
    Ok("ICS import: use file dialog to select .ics file".into())
}

#[tauri::command]
async fn list_sources() -> Result<Vec<CalendarSource>, String> {
    db::get_sources().map_err(|e| e.to_string())
}

#[tauri::command]
async fn sync_now(two_way: bool, dedup: bool, conflict_strategy: String) -> Result<String, String> {
    let sources = db::get_sources().map_err(|e| e.to_string())?;
    let result = sync_engine::run_sync(&sources, two_way, dedup, &conflict_strategy)
        .map_err(|e| e.to_string())?;
    db::insert_log(&LogEntry::info("sync", &result)).map_err(|e| e.to_string())?;
    Ok(result)
}

#[tauri::command]
async fn preview_sync() -> Result<String, String> {
    let sources = db::get_sources().map_err(|e| e.to_string())?;
    sync_engine::preview(&sources).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_log() -> Result<Vec<LogEntry>, String> {
    db::get_log_entries().map_err(|e| e.to_string())
}

#[tauri::command]
async fn clear_log() -> Result<(), String> {
    db::clear_log().map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Initialize database
    db::init().expect("Failed to initialize database");

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![
            add_source,
            add_caldav_source,
            import_ics_file,
            list_sources,
            sync_now,
            preview_sync,
            get_log,
            clear_log,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
