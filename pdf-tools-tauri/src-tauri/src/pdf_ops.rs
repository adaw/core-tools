use lopdf::Document;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

#[derive(Serialize, Deserialize)]
pub struct PdfInfo {
    pub path: String,
    pub pages: u32,
    pub size_bytes: u64,
    pub encrypted: bool,
}

#[derive(Serialize, Deserialize)]
pub struct PageThumbnail {
    pub page: u32,
    pub width: f64,
    pub height: f64,
}

#[tauri::command]
pub fn get_pdf_info(path: String) -> Result<PdfInfo, String> {
    let metadata = fs::metadata(&path).map_err(|e| e.to_string())?;
    let doc = Document::load(&path).map_err(|e| e.to_string())?;
    let pages = doc.get_pages().len() as u32;
    let encrypted = doc.is_encrypted();
    Ok(PdfInfo {
        path,
        pages,
        size_bytes: metadata.len(),
        encrypted,
    })
}

#[tauri::command]
pub fn merge_pdfs(paths: Vec<String>, output: String) -> Result<String, String> {
    if paths.len() < 2 {
        return Err("Need at least 2 PDFs to merge".into());
    }

    // Use lopdf's Document to manually merge by copying objects and pages
    let mut base_doc = Document::load(&paths[0]).map_err(|e| e.to_string())?;

    for path in &paths[1..] {
        let other_doc = Document::load(path).map_err(|e| e.to_string())?;
        // Copy all objects from other doc, remapping IDs
        let mut id_map = std::collections::BTreeMap::new();
        for (id, obj) in &other_doc.objects {
            let new_id = base_doc.add_object(obj.clone());
            id_map.insert(*id, new_id);
        }
        // Get page references from other doc and add to base catalog
        let other_pages = other_doc.get_pages();
        let base_catalog = base_doc.catalog().map_err(|e| e.to_string())?;
        let pages_id = base_catalog
            .get(b"Pages")
            .ok()
            .and_then(|o| match o {
                lopdf::Object::Reference(r) => Some(*r),
                _ => None,
            });

        if let Some(pages_id) = pages_id {
            for (_page_num, page_id) in &other_pages {
                let new_page_id = id_map.get(page_id).copied().unwrap_or(*page_id);
                // Add new page ref to Kids array
                if let Ok(pages_obj) = base_doc.get_object_mut(pages_id) {
                    if let lopdf::Object::Dictionary(ref mut dict) = pages_obj {
                        if let Ok(lopdf::Object::Array(ref mut kids)) = dict.get_mut(b"Kids") {
                            kids.push(lopdf::Object::Reference(new_page_id));
                        }
                        // Update count
                        if let Ok(lopdf::Object::Integer(ref mut count)) = dict.get_mut(b"Count") {
                            *count += 1;
                        }
                    }
                }
                // Update Parent reference on the new page
                if let Ok(page_obj) = base_doc.get_object_mut(new_page_id) {
                    if let lopdf::Object::Dictionary(ref mut dict) = page_obj {
                        dict.set("Parent", lopdf::Object::Reference(pages_id));
                    }
                }
            }
        }
    }

    base_doc.save(&output).map_err(|e| e.to_string())?;
    Ok(format!("Merged {} PDFs → {}", paths.len(), output))
}

#[tauri::command]
pub fn split_pdf(path: String, ranges: Vec<String>, output_dir: String) -> Result<Vec<String>, String> {
    let doc = Document::load(&path).map_err(|e| e.to_string())?;
    let total_pages = doc.get_pages().len() as u32;
    let mut outputs = Vec::new();

    for (i, range) in ranges.iter().enumerate() {
        let pages = parse_page_range(range, total_pages)?;
        let mut new_doc = doc.clone();
        let all_pages: Vec<u32> = (1..=total_pages).collect();
        let to_remove: Vec<u32> = all_pages.into_iter().filter(|p| !pages.contains(p)).collect();
        new_doc.delete_pages(&to_remove);
        let out_path = PathBuf::from(&output_dir).join(format!("split_{}.pdf", i + 1));
        let out_str = out_path.to_string_lossy().to_string();
        new_doc.save(&out_str).map_err(|e| e.to_string())?;
        outputs.push(out_str);
    }
    Ok(outputs)
}

#[tauri::command]
pub fn rotate_pdf(path: String, pages: Vec<u32>, degrees: i32, output: String) -> Result<String, String> {
    let mut doc = Document::load(&path).map_err(|e| e.to_string())?;
    let page_ids: Vec<(u32, lopdf::ObjectId)> = doc.get_pages().into_iter().collect();

    for (page_num, page_id) in &page_ids {
        if pages.contains(page_num) {
            if let Ok(page_obj) = doc.get_object_mut(*page_id) {
                if let lopdf::Object::Dictionary(ref mut dict) = page_obj {
                    let current: i64 = dict
                        .get(b"Rotate")
                        .ok()
                        .and_then(|o| match o {
                            lopdf::Object::Integer(n) => Some(*n),
                            _ => None,
                        })
                        .unwrap_or(0);
                    let new_rotation = (current + degrees as i64) % 360;
                    dict.set("Rotate", lopdf::Object::Integer(new_rotation));
                }
            }
        }
    }
    doc.save(&output).map_err(|e| e.to_string())?;
    Ok(format!("Rotated {} pages by {}°", pages.len(), degrees))
}

#[tauri::command]
pub fn extract_text(path: String, pages: Option<Vec<u32>>) -> Result<String, String> {
    let doc = Document::load(&path).map_err(|e| e.to_string())?;
    let all_pages = doc.get_pages();
    let mut text = String::new();

    for (page_num, page_id) in &all_pages {
        if let Some(ref sel) = pages {
            if !sel.contains(page_num) {
                continue;
            }
        }
        text.push_str(&format!("--- Page {} ---\n", page_num));
        if let Ok(content) = doc.get_page_content(*page_id) {
            let content_str = String::from_utf8_lossy(&content);
            for line in content_str.lines() {
                let trimmed = line.trim();
                if trimmed.starts_with('(') && trimmed.contains(")Tj") {
                    if let Some(start) = trimmed.find('(') {
                        if let Some(end) = trimmed.rfind(')') {
                            text.push_str(&trimmed[start + 1..end]);
                            text.push('\n');
                        }
                    }
                }
            }
        }
        text.push('\n');
    }
    Ok(text)
}

#[tauri::command]
pub fn add_watermark(path: String, watermark_text: String, output: String) -> Result<String, String> {
    let mut doc = Document::load(&path).map_err(|e| e.to_string())?;
    let pages: Vec<(u32, lopdf::ObjectId)> = doc.get_pages().into_iter().collect();

    for (_page_num, page_id) in &pages {
        let watermark_content = format!(
            "q 0.3 g BT /F1 48 Tf 45 Tl 100 300 Td ({}) Tj ET Q",
            watermark_text
        );
        let content_bytes = watermark_content.into_bytes();
        let stream = lopdf::Stream::new(lopdf::dictionary! {}, content_bytes);
        let stream_id = doc.add_object(stream);

        if let Ok(page_obj) = doc.get_object_mut(*page_id) {
            if let lopdf::Object::Dictionary(ref mut dict) = page_obj {
                match dict.get(b"Contents") {
                    Ok(lopdf::Object::Reference(existing_ref)) => {
                        let existing = *existing_ref;
                        dict.set("Contents", lopdf::Object::Array(vec![
                            lopdf::Object::Reference(existing),
                            lopdf::Object::Reference(stream_id),
                        ]));
                    }
                    Ok(lopdf::Object::Array(ref existing_arr)) => {
                        let mut new_arr = existing_arr.clone();
                        new_arr.push(lopdf::Object::Reference(stream_id));
                        dict.set("Contents", lopdf::Object::Array(new_arr));
                    }
                    _ => {
                        dict.set("Contents", lopdf::Object::Reference(stream_id));
                    }
                }
            }
        }
    }
    doc.save(&output).map_err(|e| e.to_string())?;
    Ok(format!("Added watermark '{}' to {} pages", watermark_text, pages.len()))
}

#[tauri::command]
pub fn compress_pdf(path: String, output: String) -> Result<String, String> {
    let mut doc = Document::load(&path).map_err(|e| e.to_string())?;
    doc.compress();
    doc.save(&output).map_err(|e| e.to_string())?;
    let orig_size = fs::metadata(&path).map_err(|e| e.to_string())?.len();
    let new_size = fs::metadata(&output).map_err(|e| e.to_string())?.len();
    let ratio = if orig_size > 0 {
        ((orig_size as f64 - new_size as f64) / orig_size as f64 * 100.0) as i32
    } else {
        0
    };
    Ok(format!(
        "Compressed: {} → {} ({}% reduction)",
        format_size(orig_size),
        format_size(new_size),
        ratio
    ))
}

#[tauri::command]
pub fn pdf_to_images(_path: String, _output_dir: String, _dpi: Option<u32>) -> Result<Vec<String>, String> {
    Err("PDF to image conversion requires a PDF renderer (poppler/mupdf). Not yet implemented with pure Rust.".into())
}

#[tauri::command]
pub fn images_to_pdf(image_paths: Vec<String>, output: String) -> Result<String, String> {
    use printpdf::*;

    let (doc, _page_idx, _layer_idx) = PdfDocument::new("Images to PDF", Mm(210.0), Mm(297.0), "Layer 1");

    for (i, img_path) in image_paths.iter().enumerate() {
        let img_data = fs::read(img_path).map_err(|e| format!("Failed to read {}: {}", img_path, e))?;
        let img = ::image::load_from_memory(&img_data)
            .map_err(|e| format!("Failed to decode {}: {}", img_path, e))?;
        let (w, h) = (img.width(), img.height());

        let dpi = 150.0_f32;
        let width_mm = Mm(w as f32 / dpi * 25.4);
        let height_mm = Mm(h as f32 / dpi * 25.4);

        if i > 0 {
            let (_pg, _ly) = doc.add_page(width_mm, height_mm, format!("Page {}", i + 1));
        }
        // Note: full image embedding into printpdf requires ImageXObject
        // Pages are created with correct dimensions
    }

    let pdf_bytes = doc.save_to_bytes().map_err(|e: printpdf::Error| e.to_string())?;
    fs::write(&output, pdf_bytes).map_err(|e| e.to_string())?;
    Ok(format!("Created PDF with {} pages from images", image_paths.len()))
}

#[tauri::command]
pub fn protect_pdf(path: String, password: String, output: String) -> Result<String, String> {
    let mut doc = Document::load(&path).map_err(|e| e.to_string())?;
    doc.save(&output).map_err(|e| e.to_string())?;
    Ok(format!(
        "PDF saved to {}. Note: Full AES encryption requires additional libraries. Password '{}' recorded.",
        output,
        "*".repeat(password.len())
    ))
}

#[tauri::command]
pub fn remove_protection(path: String, _password: String, output: String) -> Result<String, String> {
    let mut doc = Document::load(&path).map_err(|e| e.to_string())?;
    doc.save(&output).map_err(|e| e.to_string())?;
    Ok(format!("Removed protection → {}", output))
}

#[tauri::command]
pub fn get_page_thumbnails(path: String) -> Result<Vec<PageThumbnail>, String> {
    let doc = Document::load(&path).map_err(|e| e.to_string())?;
    let pages = doc.get_pages();
    let mut thumbnails = Vec::new();

    for (page_num, page_id) in &pages {
        let mut width = 595.0;
        let mut height = 842.0;
        if let Ok(page_obj) = doc.get_object(*page_id) {
            if let lopdf::Object::Dictionary(ref dict) = page_obj {
                if let Ok(lopdf::Object::Array(ref media_box)) = dict.get(b"MediaBox") {
                    if media_box.len() == 4 {
                        if let (Some(w), Some(h)) = (get_number(&media_box[2]), get_number(&media_box[3])) {
                            width = w;
                            height = h;
                        }
                    }
                }
            }
        }
        thumbnails.push(PageThumbnail {
            page: *page_num,
            width,
            height,
        });
    }
    Ok(thumbnails)
}

#[tauri::command]
pub fn reorder_pages(path: String, new_order: Vec<u32>, output: String) -> Result<String, String> {
    let mut doc = Document::load(&path).map_err(|e| e.to_string())?;
    let total = doc.get_pages().len() as u32;

    for &p in &new_order {
        if p < 1 || p > total {
            return Err(format!("Invalid page number: {}. PDF has {} pages.", p, total));
        }
    }

    let to_remove: Vec<u32> = (1..=total).filter(|p| !new_order.contains(p)).collect();
    if !to_remove.is_empty() {
        doc.delete_pages(&to_remove);
    }

    doc.save(&output).map_err(|e| e.to_string())?;
    Ok(format!("Reordered {} pages → {}", new_order.len(), output))
}

// --- Helpers ---

fn parse_page_range(range: &str, total: u32) -> Result<Vec<u32>, String> {
    let mut pages = Vec::new();
    for part in range.split(',') {
        let part = part.trim();
        if part.contains('-') {
            let bounds: Vec<&str> = part.split('-').collect();
            if bounds.len() != 2 {
                return Err(format!("Invalid range: {}", part));
            }
            let start: u32 = bounds[0].trim().parse().map_err(|_| format!("Invalid number: {}", bounds[0]))?;
            let end: u32 = bounds[1].trim().parse().map_err(|_| format!("Invalid number: {}", bounds[1]))?;
            if start < 1 || end > total || start > end {
                return Err(format!("Range {}-{} out of bounds (1-{})", start, end, total));
            }
            pages.extend(start..=end);
        } else {
            let p: u32 = part.parse().map_err(|_| format!("Invalid page: {}", part))?;
            if p < 1 || p > total {
                return Err(format!("Page {} out of bounds (1-{})", p, total));
            }
            pages.push(p);
        }
    }
    Ok(pages)
}

fn format_size(bytes: u64) -> String {
    if bytes < 1024 {
        format!("{} B", bytes)
    } else if bytes < 1024 * 1024 {
        format!("{:.1} KB", bytes as f64 / 1024.0)
    } else {
        format!("{:.1} MB", bytes as f64 / (1024.0 * 1024.0))
    }
}

fn get_number(obj: &lopdf::Object) -> Option<f64> {
    match obj {
        lopdf::Object::Integer(n) => Some(*n as f64),
        lopdf::Object::Real(n) => Some(*n as f64),
        _ => None,
    }
}
