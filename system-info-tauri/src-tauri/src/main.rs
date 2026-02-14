// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod system;

use system::*;

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_overview,
            get_cpu_info,
            get_memory_info,
            get_disk_info,
            get_network_info,
            get_process_list,
            export_report_json,
            export_report_html,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
