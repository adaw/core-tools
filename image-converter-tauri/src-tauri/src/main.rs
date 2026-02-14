// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod converter;

use converter::{ConvertOptions, ConvertResult, ImageInfo};
use std::path::PathBuf;

#[tauri::command]
fn get_image_info(paths: Vec<String>) -> Result<Vec<ImageInfo>, String> {
    converter::get_image_info(
        paths.iter().map(PathBuf::from).collect()
    )
}

#[tauri::command]
fn generate_thumbnail(path: String, max_size: u32) -> Result<String, String> {
    converter::generate_thumbnail(&PathBuf::from(path), max_size)
}

#[tauri::command]
fn convert_images(options: ConvertOptions) -> Result<Vec<ConvertResult>, String> {
    converter::convert_images(options)
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![
            get_image_info,
            generate_thumbnail,
            convert_images,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
