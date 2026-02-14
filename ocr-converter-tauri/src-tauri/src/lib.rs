use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct OcrResult {
    pub text: String,
    pub confidence: f32,
    pub source_file: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PdfTextResult {
    pub text: String,
    pub page_count: usize,
    pub source_file: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct BatchResult {
    pub results: Vec<OcrResult>,
    pub total_files: usize,
    pub successful: usize,
    pub failed: usize,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ConversionResult {
    pub output_path: String,
    pub success: bool,
    pub message: String,
}

/// Perform OCR on an image file using Tesseract
#[tauri::command]
fn ocr_image(file_path: String, language: String) -> Result<OcrResult, String> {
    let lang = if language.is_empty() { "eng" } else { &language };

    let mut tess = tesseract::Tesseract::new(None, Some(lang))
        .map_err(|e| format!("Failed to init Tesseract: {}", e))?
        .set_image(&file_path)
        .map_err(|e| format!("Failed to set image: {}", e))?;

    let confidence = tess.mean_text_conf();

    let text = tess
        .get_text()
        .map_err(|e| format!("OCR failed: {}", e))?;

    Ok(OcrResult {
        text,
        confidence: confidence as f32,
        source_file: file_path,
    })
}

/// Extract text from a PDF file
#[tauri::command]
fn pdf_to_text(file_path: String) -> Result<PdfTextResult, String> {
    let doc = lopdf::Document::load(&file_path)
        .map_err(|e| format!("Failed to load PDF: {}", e))?;

    let page_count = doc.get_pages().len();
    let mut all_text = String::new();

    for page_num in 1..=page_count as u32 {
        if let Ok(text) = doc.extract_text(&[page_num]) {
            all_text.push_str(&text);
            all_text.push('\n');
        }
    }

    Ok(PdfTextResult {
        text: all_text,
        page_count,
        source_file: file_path,
    })
}

/// Convert an image to a PDF using printpdf 0.8
#[tauri::command]
fn image_to_pdf(file_path: String, output_path: String) -> Result<ConversionResult, String> {
    let img = image::open(&file_path)
        .map_err(|e| format!("Failed to open image: {}", e))?;

    let (width, height) = (img.width() as usize, img.height() as usize);
    let dpi = 150.0_f32;
    let pt_width = (width as f32 / dpi) * 72.0;
    let pt_height = (height as f32 / dpi) * 72.0;

    let rgb_img = img.to_rgb8();
    let raw_pixels = rgb_img.into_raw();

    let raw_image = printpdf::RawImage {
        pixels: printpdf::RawImageData::U8(raw_pixels),
        width,
        height,
        data_format: printpdf::RawImageFormat::RGB8,
        tag: Vec::new(),
    };

    let mut doc = printpdf::PdfDocument::new("Converted Image");
    let image_id = doc.add_image(&raw_image);

    let page = printpdf::PdfPage::new(
        printpdf::Mm(pt_width * 25.4 / 72.0),
        printpdf::Mm(pt_height * 25.4 / 72.0),
        vec![printpdf::Op::UseXobject {
            id: image_id,
            transform: printpdf::XObjectTransform {
                dpi: Some(dpi),
                ..Default::default()
            },
        }],
    );

    doc.with_pages(vec![page]);

    let output = if output_path.is_empty() {
        let p = Path::new(&file_path);
        p.with_extension("pdf").to_string_lossy().to_string()
    } else {
        output_path
    };

    let bytes = doc.save(&printpdf::PdfSaveOptions::default(), &mut Vec::new());
    std::fs::write(&output, &bytes)
        .map_err(|e| format!("Failed to write PDF: {}", e))?;

    Ok(ConversionResult {
        output_path: output,
        success: true,
        message: "Image converted to PDF successfully".to_string(),
    })
}

/// Batch OCR on multiple image files
#[tauri::command]
fn batch_ocr(file_paths: Vec<String>, language: String) -> BatchResult {
    let total = file_paths.len();
    let mut results = Vec::new();
    let mut successful = 0usize;
    let mut failed = 0usize;

    for path in file_paths {
        match ocr_image(path.clone(), language.clone()) {
            Ok(result) => {
                successful += 1;
                results.push(result);
            }
            Err(err) => {
                failed += 1;
                results.push(OcrResult {
                    text: format!("Error: {}", err),
                    confidence: 0.0,
                    source_file: path,
                });
            }
        }
    }

    BatchResult {
        results,
        total_files: total,
        successful,
        failed,
    }
}

/// Get available Tesseract languages
#[tauri::command]
fn get_available_languages() -> Result<Vec<String>, String> {
    Ok(vec![
        "eng".into(), "ces".into(), "deu".into(),
        "fra".into(), "spa".into(), "ita".into(),
        "pol".into(), "rus".into(), "chi_sim".into(),
        "jpn".into(), "kor".into(), "ara".into(),
    ])
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            ocr_image,
            pdf_to_text,
            image_to_pdf,
            batch_ocr,
            get_available_languages,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
