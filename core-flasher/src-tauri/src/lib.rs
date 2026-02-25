mod drives;
mod flasher;

use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Emitter, Manager, State};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DriveInfo {
    pub device: String,
    pub name: String,
    pub size: u64,
    pub size_human: String,
    pub removable: bool,
    pub is_system: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageInfo {
    pub path: String,
    pub name: String,
    pub size: u64,
    pub size_human: String,
    pub format: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FlashProgress {
    pub bytes_written: u64,
    pub total_bytes: u64,
    pub percent: f64,
    pub speed_mbps: f64,
    pub eta_seconds: u64,
    pub phase: String, // "writing", "verifying", "done", "error"
    pub message: String,
}

struct FlashState {
    cancel: Arc<Mutex<bool>>,
}

#[tauri::command]
async fn list_drives() -> Result<Vec<DriveInfo>, String> {
    drives::list_usb_drives().await
}

#[tauri::command]
async fn select_image(path: String) -> Result<ImageInfo, String> {
    let metadata = std::fs::metadata(&path).map_err(|e| e.to_string())?;
    let size = metadata.len();
    let name = std::path::Path::new(&path)
        .file_name()
        .unwrap_or_default()
        .to_string_lossy()
        .to_string();

    let format = match path.rsplit('.').next().unwrap_or("").to_lowercase().as_str() {
        "iso" => "ISO",
        "img" => "IMG",
        "dmg" => "DMG",
        "zip" => "ZIP",
        _ => "Unknown",
    }
    .to_string();

    Ok(ImageInfo {
        path,
        name,
        size,
        size_human: bytesize::ByteSize(size).to_string(),
        format,
    })
}

#[tauri::command]
async fn flash_image(
    app: AppHandle,
    image_path: String,
    device: String,
    verify: bool,
    state: State<'_, FlashState>,
) -> Result<(), String> {
    // Reset cancel flag
    *state.cancel.lock().unwrap() = false;
    let cancel = state.cancel.clone();

    // Validate: never flash to system disk
    let drives = drives::list_usb_drives().await?;
    let target = drives
        .iter()
        .find(|d| d.device == device)
        .ok_or("Drive not found")?;

    if target.is_system {
        return Err("SAFETY: Cannot flash to system disk!".to_string());
    }

    if !target.removable {
        return Err("SAFETY: Target drive is not removable!".to_string());
    }

    let app_clone = app.clone();
    tokio::spawn(async move {
        let result = flasher::flash(&app_clone, &image_path, &device, verify, cancel).await;
        if let Err(e) = result {
            let _ = app_clone.emit(
                "flash-progress",
                FlashProgress {
                    bytes_written: 0,
                    total_bytes: 0,
                    percent: 0.0,
                    speed_mbps: 0.0,
                    eta_seconds: 0,
                    phase: "error".to_string(),
                    message: e,
                },
            );
        }
    });

    Ok(())
}

#[tauri::command]
async fn cancel_flash(state: State<'_, FlashState>) -> Result<(), String> {
    *state.cancel.lock().unwrap() = true;
    Ok(())
}

#[tauri::command]
async fn compute_hash(path: String, algorithm: String) -> Result<String, String> {
    flasher::compute_file_hash(&path, &algorithm).await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .manage(FlashState {
            cancel: Arc::new(Mutex::new(false)),
        })
        .invoke_handler(tauri::generate_handler![
            list_drives,
            select_image,
            flash_image,
            cancel_flash,
            compute_hash,
        ])
        .run(tauri::generate_context!())
        .expect("error while running CORE Flasher");
}
