use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use tauri::Manager;
use tempfile::TempDir;

// ─── Types ───────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OcrResult {
    pub file: String,
    pub text: String,
    pub confidence: f64,
    pub language: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConversionResult {
    pub success: bool,
    pub output_path: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatchProgress {
    pub current: usize,
    pub total: usize,
    pub current_file: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileInfo {
    pub path: String,
    pub name: String,
    pub size: u64,
    pub file_type: String,
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

fn detect_file_type(path: &str) -> String {
    let ext = Path::new(path)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();
    match ext.as_str() {
        "pdf" => "pdf".to_string(),
        "doc" | "docx" => "docx".to_string(),
        "png" | "jpg" | "jpeg" | "tiff" | "tif" | "bmp" | "gif" | "webp" => "image".to_string(),
        "txt" => "text".to_string(),
        _ => "unknown".to_string(),
    }
}

fn find_tesseract() -> String {
    // Try common paths
    for path in &[
        "/usr/local/bin/tesseract",
        "/opt/homebrew/bin/tesseract",
        "/usr/bin/tesseract",
    ] {
        if Path::new(path).exists() {
            return path.to_string();
        }
    }
    "tesseract".to_string() // fallback to PATH
}

fn find_tool(name: &str) -> String {
    for prefix in &["/usr/local/bin/", "/opt/homebrew/bin/", "/usr/bin/"] {
        let full = format!("{}{}", prefix, name);
        if Path::new(&full).exists() {
            return full;
        }
    }
    name.to_string()
}

// ─── Commands ────────────────────────────────────────────────────────────────

#[tauri::command]
fn check_dependencies() -> Result<serde_json::Value, String> {
    let tesseract = Command::new(find_tesseract())
        .arg("--version")
        .output();
    let tesseract_ok = tesseract.is_ok() && tesseract.unwrap().status.success();

    let pdftotext = Command::new(find_tool("pdftotext"))
        .arg("-v")
        .output();
    let pdftotext_ok = pdftotext.is_ok();

    let libreoffice = Command::new(find_tool("soffice"))
        .arg("--version")
        .output();
    let libreoffice_ok = libreoffice.is_ok() && libreoffice.unwrap().status.success();

    Ok(serde_json::json!({
        "tesseract": tesseract_ok,
        "poppler": pdftotext_ok,
        "libreoffice": libreoffice_ok,
    }))
}

#[tauri::command]
fn get_tesseract_languages() -> Result<Vec<String>, String> {
    let output = Command::new(find_tesseract())
        .arg("--list-langs")
        .output()
        .map_err(|e| format!("Failed to run tesseract: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let langs: Vec<String> = stdout
        .lines()
        .skip(1) // skip header line
        .map(|l| l.trim().to_string())
        .filter(|l| !l.is_empty())
        .collect();

    Ok(langs)
}

#[tauri::command]
fn validate_files(paths: Vec<String>) -> Vec<FileInfo> {
    paths
        .into_iter()
        .filter_map(|p| {
            let path = PathBuf::from(&p);
            if path.is_file() {
                let meta = fs::metadata(&path).ok()?;
                let name = path.file_name()?.to_str()?.to_string();
                Some(FileInfo {
                    path: p,
                    name,
                    size: meta.len(),
                    file_type: detect_file_type(&path.to_string_lossy()),
                })
            } else {
                None
            }
        })
        .collect()
}

#[tauri::command]
fn ocr_image(path: String, language: String) -> Result<OcrResult, String> {
    let tesseract = find_tesseract();
    let tmp_dir = TempDir::new().map_err(|e| e.to_string())?;
    let output_base = tmp_dir.path().join("ocr_output");

    let output = Command::new(&tesseract)
        .arg(&path)
        .arg(output_base.to_str().unwrap())
        .arg("-l")
        .arg(&language)
        .arg("--psm")
        .arg("3")
        .arg("--oem")
        .arg("1")
        .output()
        .map_err(|e| format!("Tesseract failed: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Tesseract error: {}", stderr));
    }

    let text_file = format!("{}.txt", output_base.to_str().unwrap());
    let text = fs::read_to_string(&text_file)
        .map_err(|e| format!("Failed to read OCR output: {}", e))?;

    // Get confidence via tsv output
    let tsv_output = Command::new(&tesseract)
        .arg(&path)
        .arg("stdout")
        .arg("-l")
        .arg(&language)
        .arg("--psm")
        .arg("3")
        .arg("tsv")
        .output();

    let confidence = if let Ok(tsv) = tsv_output {
        let tsv_text = String::from_utf8_lossy(&tsv.stdout);
        let confs: Vec<f64> = tsv_text
            .lines()
            .skip(1)
            .filter_map(|line| {
                let cols: Vec<&str> = line.split('\t').collect();
                if cols.len() >= 12 {
                    cols[10].parse::<f64>().ok().filter(|&c| c >= 0.0)
                } else {
                    None
                }
            })
            .collect();
        if confs.is_empty() {
            0.0
        } else {
            confs.iter().sum::<f64>() / confs.len() as f64
        }
    } else {
        0.0
    };

    let file_name = Path::new(&path)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("unknown")
        .to_string();

    Ok(OcrResult {
        file: file_name,
        text,
        confidence,
        language,
    })
}

#[tauri::command]
fn pdf_to_text(path: String) -> Result<String, String> {
    let output = Command::new(find_tool("pdftotext"))
        .arg("-layout")
        .arg(&path)
        .arg("-")
        .output()
        .map_err(|e| format!("pdftotext failed: {}", e))?;

    if !output.status.success() {
        return Err(format!(
            "pdftotext error: {}",
            String::from_utf8_lossy(&output.stderr)
        ));
    }

    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

#[tauri::command]
fn pdf_to_images(path: String) -> Result<Vec<String>, String> {
    let tmp_dir = TempDir::new().map_err(|e| e.to_string())?;
    let tmp_path = tmp_dir.into_path(); // persist so images remain

    let output_prefix = tmp_path.join("page");

    let output = Command::new(find_tool("pdftoppm"))
        .arg("-png")
        .arg("-r")
        .arg("300")
        .arg(&path)
        .arg(output_prefix.to_str().unwrap())
        .output()
        .map_err(|e| format!("pdftoppm failed: {}", e))?;

    if !output.status.success() {
        return Err(format!(
            "pdftoppm error: {}",
            String::from_utf8_lossy(&output.stderr)
        ));
    }

    let mut images: Vec<String> = fs::read_dir(&tmp_path)
        .map_err(|e| e.to_string())?
        .filter_map(|e| e.ok())
        .map(|e| e.path().to_string_lossy().to_string())
        .filter(|p| p.ends_with(".png"))
        .collect();

    images.sort();
    Ok(images)
}

#[tauri::command]
fn pdf_to_docx(pdf_path: String, output_path: String) -> Result<ConversionResult, String> {
    // Strategy: extract text with pdftotext, then create a simple DOCX
    // For image-based PDFs, we use OCR first
    let text = pdf_to_text(pdf_path.clone()).unwrap_or_default();

    if text.trim().is_empty() {
        return Err("PDF appears to be image-based. Use OCR mode for this PDF.".to_string());
    }

    // Use LibreOffice for the conversion if available, or create simple text-based docx
    // First try: convert PDF directly with LibreOffice
    let output_dir = Path::new(&output_path)
        .parent()
        .unwrap_or(Path::new("."))
        .to_string_lossy()
        .to_string();

    let result = Command::new(find_tool("soffice"))
        .arg("--headless")
        .arg("--convert-to")
        .arg("docx")
        .arg("--outdir")
        .arg(&output_dir)
        .arg(&pdf_path)
        .output();

    match result {
        Ok(out) if out.status.success() => {
            // LibreOffice creates the file with same name but .docx extension
            let pdf_stem = Path::new(&pdf_path)
                .file_stem()
                .unwrap()
                .to_str()
                .unwrap();
            let created = format!("{}/{}.docx", output_dir, pdf_stem);

            // Rename if needed
            if created != output_path {
                let _ = fs::rename(&created, &output_path);
            }

            Ok(ConversionResult {
                success: true,
                output_path: output_path.clone(),
                message: "PDF converted to DOCX successfully".to_string(),
            })
        }
        _ => Err("LibreOffice conversion failed. Ensure LibreOffice is installed.".to_string()),
    }
}

#[tauri::command]
fn docx_to_pdf(docx_path: String, output_path: String) -> Result<ConversionResult, String> {
    let output_dir = Path::new(&output_path)
        .parent()
        .unwrap_or(Path::new("."))
        .to_string_lossy()
        .to_string();

    let result = Command::new(find_tool("soffice"))
        .arg("--headless")
        .arg("--convert-to")
        .arg("pdf")
        .arg("--outdir")
        .arg(&output_dir)
        .arg(&docx_path)
        .output()
        .map_err(|e| format!("LibreOffice failed: {}", e))?;

    if !result.status.success() {
        return Err(format!(
            "Conversion failed: {}",
            String::from_utf8_lossy(&result.stderr)
        ));
    }

    let docx_stem = Path::new(&docx_path)
        .file_stem()
        .unwrap()
        .to_str()
        .unwrap();
    let created = format!("{}/{}.pdf", output_dir, docx_stem);

    if created != output_path {
        let _ = fs::rename(&created, &output_path);
    }

    Ok(ConversionResult {
        success: true,
        output_path: output_path.clone(),
        message: "DOCX converted to PDF successfully".to_string(),
    })
}

#[tauri::command]
fn images_to_pdf(image_paths: Vec<String>, output_path: String) -> Result<ConversionResult, String> {
    // Use ImageMagick convert or img2pdf
    let result = Command::new(find_tool("img2pdf"))
        .args(&image_paths)
        .arg("-o")
        .arg(&output_path)
        .output();

    match result {
        Ok(out) if out.status.success() => Ok(ConversionResult {
            success: true,
            output_path: output_path.clone(),
            message: format!("{} images merged into PDF", image_paths.len()),
        }),
        _ => {
            // Fallback: try ImageMagick
            let mut args = image_paths.clone();
            args.push(output_path.clone());
            let result2 = Command::new(find_tool("magick"))
                .args(&args)
                .output()
                .map_err(|e| format!("Neither img2pdf nor ImageMagick available: {}", e))?;

            if result2.status.success() {
                Ok(ConversionResult {
                    success: true,
                    output_path,
                    message: format!("{} images merged into PDF (ImageMagick)", image_paths.len()),
                })
            } else {
                Err("Failed to create PDF from images".to_string())
            }
        }
    }
}

#[tauri::command]
fn save_text_to_file(text: String, output_path: String) -> Result<ConversionResult, String> {
    fs::write(&output_path, &text).map_err(|e| e.to_string())?;
    Ok(ConversionResult {
        success: true,
        output_path: output_path.clone(),
        message: "Text saved successfully".to_string(),
    })
}

#[tauri::command]
fn read_file_base64(path: String) -> Result<String, String> {
    let data = fs::read(&path).map_err(|e| e.to_string())?;
    Ok(base64::Engine::encode(
        &base64::engine::general_purpose::STANDARD,
        &data,
    ))
}

// ─── App ─────────────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            check_dependencies,
            get_tesseract_languages,
            validate_files,
            ocr_image,
            pdf_to_text,
            pdf_to_images,
            pdf_to_docx,
            docx_to_pdf,
            images_to_pdf,
            save_text_to_file,
            read_file_base64,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
