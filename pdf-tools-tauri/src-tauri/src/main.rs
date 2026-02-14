#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod pdf_ops;

use pdf_ops::*;

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_pdf_info,
            merge_pdfs,
            split_pdf,
            rotate_pdf,
            extract_text,
            add_watermark,
            compress_pdf,
            pdf_to_images,
            images_to_pdf,
            protect_pdf,
            remove_protection,
            get_page_thumbnails,
            reorder_pages,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
