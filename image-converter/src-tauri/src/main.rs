// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use base64::{engine::general_purpose::STANDARD as BASE64, Engine};
use image::imageops::FilterType;
use image::{DynamicImage, GenericImageView, ImageFormat, ImageReader};
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::Cursor;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use tauri::{Manager, Emitter};

// ── Types ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageInfo {
    pub path: String,
    pub name: String,
    pub width: u32,
    pub height: u32,
    pub size_bytes: u64,
    pub format: String,
    pub thumbnail: String, // base64 data URI
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConvertOptions {
    pub output_format: String,
    pub quality: u8,
    pub resize_mode: String,       // "none", "percent", "pixels", "fit"
    pub resize_width: Option<u32>,
    pub resize_height: Option<u32>,
    pub resize_percent: Option<f64>,
    pub strip_metadata: bool,
    pub output_dir: String,
    pub filename_template: String, // {name}, {index}, {format}, {width}, {height}
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConvertResult {
    pub source: String,
    pub output: String,
    pub original_size: u64,
    pub new_size: u64,
    pub success: bool,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SizeEstimate {
    pub estimated_bytes: u64,
    pub format: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProgressEvent {
    pub completed: usize,
    pub total: usize,
    pub current_file: String,
}

// ── Helpers ────────────────────────────────────────────────────────────

fn detect_format(path: &Path) -> Option<ImageFormat> {
    let ext = path.extension()?.to_str()?.to_lowercase();
    match ext.as_str() {
        "png" => Some(ImageFormat::Png),
        "jpg" | "jpeg" => Some(ImageFormat::Jpeg),
        "webp" => Some(ImageFormat::WebP),
        "avif" => Some(ImageFormat::Avif),
        "bmp" => Some(ImageFormat::Bmp),
        "tiff" | "tif" => Some(ImageFormat::Tiff),
        "ico" => Some(ImageFormat::Ico),
        "gif" => Some(ImageFormat::Gif),
        _ => None,
    }
}

fn parse_output_format(f: &str) -> ImageFormat {
    match f.to_uppercase().as_str() {
        "PNG" => ImageFormat::Png,
        "JPG" | "JPEG" => ImageFormat::Jpeg,
        "WEBP" => ImageFormat::WebP,
        "AVIF" => ImageFormat::Avif,
        "BMP" => ImageFormat::Bmp,
        "TIFF" | "TIF" => ImageFormat::Tiff,
        "ICO" => ImageFormat::Ico,
        "GIF" => ImageFormat::Gif,
        _ => ImageFormat::Png,
    }
}

fn format_extension(fmt: ImageFormat) -> &'static str {
    match fmt {
        ImageFormat::Png => "png",
        ImageFormat::Jpeg => "jpg",
        ImageFormat::WebP => "webp",
        ImageFormat::Avif => "avif",
        ImageFormat::Bmp => "bmp",
        ImageFormat::Tiff => "tiff",
        ImageFormat::Ico => "ico",
        ImageFormat::Gif => "gif",
        _ => "png",
    }
}

fn make_thumbnail(img: &DynamicImage, max_size: u32) -> String {
    let thumb = img.resize(max_size, max_size, FilterType::Triangle);
    let mut buf = Vec::new();
    let mut cursor = Cursor::new(&mut buf);
    thumb
        .write_to(&mut cursor, ImageFormat::Jpeg)
        .unwrap_or_default();
    format!("data:image/jpeg;base64,{}", BASE64.encode(&buf))
}

fn apply_resize(img: DynamicImage, opts: &ConvertOptions) -> DynamicImage {
    match opts.resize_mode.as_str() {
        "percent" => {
            let pct = opts.resize_percent.unwrap_or(100.0) / 100.0;
            let (w, h) = img.dimensions();
            let nw = (w as f64 * pct).round() as u32;
            let nh = (h as f64 * pct).round() as u32;
            if nw > 0 && nh > 0 {
                img.resize_exact(nw, nh, FilterType::Lanczos3)
            } else {
                img
            }
        }
        "pixels" => {
            let nw = opts.resize_width.unwrap_or(0);
            let nh = opts.resize_height.unwrap_or(0);
            if nw > 0 && nh > 0 {
                img.resize_exact(nw, nh, FilterType::Lanczos3)
            } else {
                img
            }
        }
        "fit" => {
            let nw = opts.resize_width.unwrap_or(0);
            let nh = opts.resize_height.unwrap_or(0);
            if nw > 0 && nh > 0 {
                img.resize(nw, nh, FilterType::Lanczos3)
            } else {
                img
            }
        }
        _ => img,
    }
}

fn encode_image(img: &DynamicImage, fmt: ImageFormat, quality: u8) -> Result<Vec<u8>, String> {
    let mut buf = Vec::new();
    let mut cursor = Cursor::new(&mut buf);

    match fmt {
        ImageFormat::Jpeg => {
            let encoder = image::codecs::jpeg::JpegEncoder::new_with_quality(&mut cursor, quality);
            img.write_with_encoder(encoder)
                .map_err(|e| e.to_string())?;
        }
        ImageFormat::WebP => {
            // WebP quality via write_to (image crate uses lossy with default quality)
            img.write_to(&mut cursor, ImageFormat::WebP)
                .map_err(|e| e.to_string())?;
        }
        ImageFormat::Avif => {
            img.write_to(&mut cursor, ImageFormat::Avif)
                .map_err(|e| e.to_string())?;
        }
        _ => {
            img.write_to(&mut cursor, fmt)
                .map_err(|e| e.to_string())?;
        }
    }

    Ok(buf)
}

fn build_output_path(
    source: &Path,
    index: usize,
    opts: &ConvertOptions,
    fmt: ImageFormat,
) -> PathBuf {
    let stem = source.file_stem().unwrap_or_default().to_string_lossy();
    let ext = format_extension(fmt);
    let name = opts
        .filename_template
        .replace("{name}", &stem)
        .replace("{index}", &format!("{:04}", index))
        .replace("{format}", ext)
        .replace("{ext}", ext);

    let filename = if name.contains('.') {
        name
    } else {
        format!("{}.{}", name, ext)
    };

    Path::new(&opts.output_dir).join(filename)
}

// ── Tauri Commands ─────────────────────────────────────────────────────

#[tauri::command]
async fn load_images(paths: Vec<String>) -> Result<Vec<ImageInfo>, String> {
    let results: Vec<ImageInfo> = paths
        .par_iter()
        .filter_map(|p| {
            let path = Path::new(p);
            let reader = ImageReader::open(path).ok()?.with_guessed_format().ok()?;
            let fmt = reader.format()?;
            let img = reader.decode().ok()?;
            let (w, h) = img.dimensions();
            let size = fs::metadata(path).ok()?.len();
            let thumb = make_thumbnail(&img, 200);
            let fmt_str = format!("{:?}", fmt);

            Some(ImageInfo {
                path: p.clone(),
                name: path.file_name()?.to_string_lossy().into_owned(),
                width: w,
                height: h,
                size_bytes: size,
                format: fmt_str,
                thumbnail: thumb,
            })
        })
        .collect();

    Ok(results)
}

#[tauri::command]
async fn estimate_size(path: String, format: String, quality: u8) -> Result<SizeEstimate, String> {
    let img_path = Path::new(&path);
    let img = ImageReader::open(img_path)
        .map_err(|e| e.to_string())?
        .with_guessed_format()
        .map_err(|e| e.to_string())?
        .decode()
        .map_err(|e| e.to_string())?;

    let fmt = parse_output_format(&format);
    let buf = encode_image(&img, fmt, quality)?;

    Ok(SizeEstimate {
        estimated_bytes: buf.len() as u64,
        format,
    })
}

#[tauri::command]
async fn get_preview(path: String, format: String, quality: u8, max_size: u32) -> Result<String, String> {
    let img_path = Path::new(&path);
    let img = ImageReader::open(img_path)
        .map_err(|e| e.to_string())?
        .with_guessed_format()
        .map_err(|e| e.to_string())?
        .decode()
        .map_err(|e| e.to_string())?;

    let preview = img.resize(max_size, max_size, FilterType::Lanczos3);
    let fmt = parse_output_format(&format);
    let buf = encode_image(&preview, fmt, quality)?;

    let mime = match fmt {
        ImageFormat::Png => "image/png",
        ImageFormat::Jpeg => "image/jpeg",
        ImageFormat::WebP => "image/webp",
        ImageFormat::Avif => "image/avif",
        ImageFormat::Gif => "image/gif",
        ImageFormat::Bmp => "image/bmp",
        _ => "image/png",
    };

    Ok(format!("data:{};base64,{}", mime, BASE64.encode(&buf)))
}

#[tauri::command]
async fn convert_images(
    app: tauri::AppHandle,
    paths: Vec<String>,
    options: ConvertOptions,
) -> Result<Vec<ConvertResult>, String> {
    // Ensure output dir exists
    fs::create_dir_all(&options.output_dir).map_err(|e| e.to_string())?;

    let total = paths.len();
    let completed = Arc::new(AtomicUsize::new(0));
    let fmt = parse_output_format(&options.output_format);

    let results: Vec<ConvertResult> = paths
        .par_iter()
        .enumerate()
        .map(|(idx, p)| {
            let source = Path::new(p);
            let result = (|| -> Result<ConvertResult, String> {
                let img = ImageReader::open(source)
                    .map_err(|e| e.to_string())?
                    .with_guessed_format()
                    .map_err(|e| e.to_string())?
                    .decode()
                    .map_err(|e| e.to_string())?;

                let original_size = fs::metadata(source).map(|m| m.len()).unwrap_or(0);

                // Apply resize
                let img = apply_resize(img, &options);

                // Ensure proper color space for JPEG (no alpha)
                let img = if matches!(fmt, ImageFormat::Jpeg) && img.color().has_alpha() {
                    DynamicImage::ImageRgb8(img.to_rgb8())
                } else {
                    img
                };

                // Encode
                let buf = encode_image(&img, fmt, options.quality)?;
                let new_size = buf.len() as u64;

                // Write
                let output_path = build_output_path(source, idx + 1, &options, fmt);
                fs::write(&output_path, &buf).map_err(|e| e.to_string())?;

                Ok(ConvertResult {
                    source: p.clone(),
                    output: output_path.to_string_lossy().into_owned(),
                    original_size,
                    new_size,
                    success: true,
                    error: None,
                })
            })();

            let done = completed.fetch_add(1, Ordering::SeqCst) + 1;
            let _ = app.emit(
                "convert-progress",
                ProgressEvent {
                    completed: done,
                    total,
                    current_file: source
                        .file_name()
                        .unwrap_or_default()
                        .to_string_lossy()
                        .into_owned(),
                },
            );

            match result {
                Ok(r) => r,
                Err(e) => ConvertResult {
                    source: p.clone(),
                    output: String::new(),
                    original_size: 0,
                    new_size: 0,
                    success: false,
                    error: Some(e),
                },
            }
        })
        .collect();

    Ok(results)
}

#[tauri::command]
async fn pick_folder() -> Result<Option<String>, String> {
    // We use the dialog plugin from frontend instead
    Ok(None)
}

// ── Main ───────────────────────────────────────────────────────────────

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            load_images,
            estimate_size,
            get_preview,
            convert_images,
            pick_folder,
        ])
        .run(tauri::generate_context!())
        .expect("error while running CORE Image Converter");
}
