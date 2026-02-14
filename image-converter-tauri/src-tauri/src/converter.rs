use base64::{engine::general_purpose::STANDARD as BASE64, Engine};
use image::codecs::bmp::BmpEncoder;
use image::codecs::gif::GifEncoder;
use image::codecs::ico::IcoEncoder;
use image::codecs::jpeg::JpegEncoder;
use image::codecs::png::PngEncoder;
use image::codecs::tiff::TiffEncoder;
use image::{GenericImageView, ImageEncoder, ImageFormat};
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::Cursor;
use std::path::{Path, PathBuf};

#[derive(Debug, Serialize, Deserialize)]
pub struct ImageInfo {
    pub path: String,
    pub filename: String,
    pub width: u32,
    pub height: u32,
    pub format: String,
    pub size_bytes: u64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ConvertOptions {
    pub paths: Vec<String>,
    pub output_dir: String,
    pub format: String,
    pub quality: u8,
    pub resize_width: Option<u32>,
    pub resize_height: Option<u32>,
    pub strip_metadata: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ConvertResult {
    pub source: String,
    pub output: String,
    pub success: bool,
    pub error: Option<String>,
    pub original_size: u64,
    pub new_size: u64,
}

pub fn get_image_info(paths: Vec<PathBuf>) -> Result<Vec<ImageInfo>, String> {
    let results: Vec<ImageInfo> = paths
        .par_iter()
        .filter_map(|p| {
            let meta = fs::metadata(p).ok()?;
            let img = image::open(p).ok()?;
            let (w, h) = img.dimensions();
            let fmt = ImageFormat::from_path(p)
                .map(|f| format!("{:?}", f))
                .unwrap_or_else(|_| "Unknown".into());
            Some(ImageInfo {
                path: p.to_string_lossy().into(),
                filename: p.file_name()?.to_string_lossy().into(),
                width: w,
                height: h,
                format: fmt,
                size_bytes: meta.len(),
            })
        })
        .collect();
    Ok(results)
}

pub fn generate_thumbnail(path: &Path, max_size: u32) -> Result<String, String> {
    let img = image::open(path).map_err(|e| e.to_string())?;
    let thumb = img.thumbnail(max_size, max_size);
    let mut buf = Cursor::new(Vec::new());
    thumb
        .write_to(&mut buf, ImageFormat::Png)
        .map_err(|e| e.to_string())?;
    Ok(format!(
        "data:image/png;base64,{}",
        BASE64.encode(buf.into_inner())
    ))
}

pub fn convert_images(options: ConvertOptions) -> Result<Vec<ConvertResult>, String> {
    fs::create_dir_all(&options.output_dir).map_err(|e| e.to_string())?;

    let results: Vec<ConvertResult> = options
        .paths
        .par_iter()
        .map(|p| convert_single(p, &options))
        .collect();

    Ok(results)
}

fn convert_single(path: &str, options: &ConvertOptions) -> ConvertResult {
    let source_path = PathBuf::from(path);
    let original_size = fs::metadata(&source_path).map(|m| m.len()).unwrap_or(0);

    let stem = source_path
        .file_stem()
        .unwrap_or_default()
        .to_string_lossy();
    let ext = match options.format.to_lowercase().as_str() {
        "jpeg" | "jpg" => "jpg",
        "png" => "png",
        "webp" => "webp",
        "bmp" => "bmp",
        "tiff" | "tif" => "tiff",
        "ico" => "ico",
        "gif" => "gif",
        "avif" => "avif",
        _ => "png",
    };
    let output_path = PathBuf::from(&options.output_dir).join(format!("{}.{}", stem, ext));

    match do_convert(&source_path, &output_path, options) {
        Ok(()) => {
            let new_size = fs::metadata(&output_path).map(|m| m.len()).unwrap_or(0);
            ConvertResult {
                source: path.into(),
                output: output_path.to_string_lossy().into(),
                success: true,
                error: None,
                original_size,
                new_size,
            }
        }
        Err(e) => ConvertResult {
            source: path.into(),
            output: output_path.to_string_lossy().into(),
            success: false,
            error: Some(e),
            original_size,
            new_size: 0,
        },
    }
}

fn do_convert(source: &Path, output: &Path, options: &ConvertOptions) -> Result<(), String> {
    let mut img = image::open(source).map_err(|e| e.to_string())?;

    // Resize if requested
    if let (Some(w), Some(h)) = (options.resize_width, options.resize_height) {
        img = img.resize(w, h, image::imageops::FilterType::Lanczos3);
    } else if let Some(w) = options.resize_width {
        let (ow, oh) = img.dimensions();
        let h = (oh as f64 * w as f64 / ow as f64) as u32;
        img = img.resize_exact(w, h, image::imageops::FilterType::Lanczos3);
    } else if let Some(h) = options.resize_height {
        let (ow, oh) = img.dimensions();
        let w = (ow as f64 * h as f64 / oh as f64) as u32;
        img = img.resize_exact(w, h, image::imageops::FilterType::Lanczos3);
    }

    // Strip metadata = re-encode from raw pixels (which we do anyway)
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    let raw = rgba.as_raw();

    let fmt = options.format.to_lowercase();
    let mut buf = Cursor::new(Vec::new());

    match fmt.as_str() {
        "jpeg" | "jpg" => {
            let enc = JpegEncoder::new_with_quality(&mut buf, options.quality);
            enc.write_image(raw, w, h, image::ExtendedColorType::Rgba8)
                .map_err(|e| e.to_string())?;
        }
        "png" => {
            let enc = PngEncoder::new(&mut buf);
            enc.write_image(raw, w, h, image::ExtendedColorType::Rgba8)
                .map_err(|e| e.to_string())?;
        }
        "webp" => {
            let encoder = webp::Encoder::from_rgba(raw, w, h);
            let mem = if options.quality >= 100 {
                encoder.encode_lossless()
            } else {
                encoder.encode(options.quality as f32)
            };
            fs::write(output, &*mem).map_err(|e| e.to_string())?;
            return Ok(());
        }
        "bmp" => {
            let enc = BmpEncoder::new(&mut buf);
            enc.write_image(raw, w, h, image::ExtendedColorType::Rgba8)
                .map_err(|e| e.to_string())?;
        }
        "tiff" | "tif" => {
            let enc = TiffEncoder::new(&mut buf);
            enc.write_image(raw, w, h, image::ExtendedColorType::Rgba8)
                .map_err(|e| e.to_string())?;
        }
        "ico" => {
            // ICO: resize to 256x256 max
            let ico_img = if w > 256 || h > 256 {
                img.resize(256, 256, image::imageops::FilterType::Lanczos3)
            } else {
                img.clone()
            };
            let ico_rgba = ico_img.to_rgba8();
            let (iw, ih) = ico_rgba.dimensions();
            let enc = IcoEncoder::new(&mut buf);
            enc.write_image(ico_rgba.as_raw(), iw, ih, image::ExtendedColorType::Rgba8)
                .map_err(|e| e.to_string())?;
        }
        "gif" => {
            let mut enc = GifEncoder::new(&mut buf);
            enc.encode(raw, w, h, image::ExtendedColorType::Rgba8)
                .map_err(|e| e.to_string())?;
        }
        _ => return Err(format!("Unsupported format: {}", fmt)),
    }

    fs::write(output, buf.into_inner()).map_err(|e| e.to_string())?;
    Ok(())
}
