use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::Stdio;
use tokio::io::AsyncReadExt;
use tokio::process::Command;
use tauri::{Manager, Emitter};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BookMetadata {
    pub title: Option<String>,
    pub author: Option<String>,
    pub language: Option<String>,
    pub publisher: Option<String>,
    pub description: Option<String>,
    pub isbn: Option<String>,
    pub tags: Option<String>,
    pub series: Option<String>,
    pub series_index: Option<String>,
    pub cover_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConversionJob {
    pub id: String,
    pub input_path: String,
    pub output_format: String,
    pub output_dir: String,
    pub options: ConversionOptions,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConversionOptions {
    pub margin_top: Option<f64>,
    pub margin_bottom: Option<f64>,
    pub margin_left: Option<f64>,
    pub margin_right: Option<f64>,
    pub font_size: Option<f64>,
    pub line_height: Option<f64>,
    pub page_size: Option<String>,  // a4, letter, etc for PDF
    pub embed_font_family: Option<String>,
    pub no_images: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConversionProgress {
    pub job_id: String,
    pub file_name: String,
    pub progress: f64, // 0-100
    pub status: String, // "converting", "done", "error"
    pub message: Option<String>,
}

#[tauri::command]
async fn check_calibre() -> Result<bool, String> {
    let output = Command::new("ebook-convert")
        .arg("--version")
        .output()
        .await;
    Ok(output.is_ok())
}

#[tauri::command]
async fn get_metadata(file_path: String) -> Result<BookMetadata, String> {
    let output = Command::new("ebook-meta")
        .arg(&file_path)
        .output()
        .await
        .map_err(|e| format!("Failed to run ebook-meta: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let mut meta = BookMetadata {
        title: None, author: None, language: None, publisher: None,
        description: None, isbn: None, tags: None, series: None,
        series_index: None, cover_path: None,
    };

    for line in stdout.lines() {
        let line = line.trim();
        if let Some((key, val)) = line.split_once(':') {
            let key = key.trim().to_lowercase();
            let val = val.trim().to_string();
            if val.is_empty() { continue; }
            match key.as_str() {
                "title" => meta.title = Some(val),
                "author(s)" | "authors" | "author" => meta.author = Some(val),
                "language" | "languages" => meta.language = Some(val),
                "publisher" => meta.publisher = Some(val),
                "comments" | "description" => meta.description = Some(val),
                "isbn" => meta.isbn = Some(val),
                "tags" => meta.tags = Some(val),
                "series" => meta.series = Some(val),
                "series index" => meta.series_index = Some(val),
                _ => {}
            }
        }
    }

    Ok(meta)
}

#[tauri::command]
async fn set_metadata(file_path: String, metadata: BookMetadata) -> Result<(), String> {
    let mut args: Vec<String> = vec![file_path];

    if let Some(ref t) = metadata.title { args.extend(["--title".into(), t.clone()]); }
    if let Some(ref a) = metadata.author { args.extend(["--authors".into(), a.clone()]); }
    if let Some(ref l) = metadata.language { args.extend(["--language".into(), l.clone()]); }
    if let Some(ref p) = metadata.publisher { args.extend(["--publisher".into(), p.clone()]); }
    if let Some(ref d) = metadata.description { args.extend(["--comments".into(), d.clone()]); }
    if let Some(ref i) = metadata.isbn { args.extend(["--isbn".into(), i.clone()]); }
    if let Some(ref t) = metadata.tags { args.extend(["--tags".into(), t.clone()]); }
    if let Some(ref s) = metadata.series { args.extend(["--series".into(), s.clone()]); }
    if let Some(ref si) = metadata.series_index { args.extend(["--index".into(), si.clone()]); }
    if let Some(ref c) = metadata.cover_path { args.extend(["--cover".into(), c.clone()]); }

    let output = Command::new("ebook-meta")
        .args(&args)
        .output()
        .await
        .map_err(|e| format!("Failed to run ebook-meta: {}", e))?;

    if output.status.success() {
        Ok(())
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}

#[tauri::command]
async fn extract_cover(file_path: String, output_path: String) -> Result<String, String> {
    let output = Command::new("ebook-meta")
        .args(&[&file_path, "--get-cover", &output_path])
        .output()
        .await
        .map_err(|e| format!("Failed: {}", e))?;

    if output.status.success() {
        Ok(output_path)
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}

#[tauri::command]
async fn get_cover_base64(file_path: String) -> Result<Option<String>, String> {
    let tmp = std::env::temp_dir().join(format!("ebook_cover_{}.jpg", uuid::Uuid::new_v4()));
    let tmp_str = tmp.to_string_lossy().to_string();

    let output = Command::new("ebook-meta")
        .args(&[&file_path, "--get-cover", &tmp_str])
        .output()
        .await
        .map_err(|e| format!("Failed: {}", e))?;

    if output.status.success() && tmp.exists() {
        let data = tokio::fs::read(&tmp).await.map_err(|e| e.to_string())?;
        let _ = tokio::fs::remove_file(&tmp).await;
        use base64::Engine;
        Ok(Some(base64::engine::general_purpose::STANDARD.encode(&data)))
    } else {
        Ok(None)
    }
}

#[tauri::command]
async fn convert_ebook(
    app: tauri::AppHandle,
    job: ConversionJob,
) -> Result<String, String> {
    let input = PathBuf::from(&job.input_path);
    let file_stem = input.file_stem()
        .ok_or("Invalid input file")?
        .to_string_lossy()
        .to_string();

    let output_path = PathBuf::from(&job.output_dir)
        .join(format!("{}.{}", file_stem, job.output_format));
    let output_str = output_path.to_string_lossy().to_string();

    let mut args: Vec<String> = vec![
        job.input_path.clone(),
        output_str.clone(),
    ];

    let opts = &job.options;
    if let Some(v) = opts.margin_top { args.extend(["--margin-top".into(), v.to_string()]); }
    if let Some(v) = opts.margin_bottom { args.extend(["--margin-bottom".into(), v.to_string()]); }
    if let Some(v) = opts.margin_left { args.extend(["--margin-left".into(), v.to_string()]); }
    if let Some(v) = opts.margin_right { args.extend(["--margin-right".into(), v.to_string()]); }
    if let Some(v) = opts.font_size { args.extend(["--base-font-size".into(), v.to_string()]); }
    if let Some(v) = opts.line_height { args.extend(["--line-height".into(), v.to_string()]); }
    if let Some(ref v) = opts.page_size { args.extend(["--paper-size".into(), v.clone()]); }
    if let Some(ref v) = opts.embed_font_family { args.extend(["--embed-font-family".into(), v.clone()]); }
    if opts.no_images == Some(true) { args.push("--no-images".into()); }

    // Emit start
    let _ = app.emit("conversion-progress", ConversionProgress {
        job_id: job.id.clone(),
        file_name: file_stem.clone(),
        progress: 0.0,
        status: "converting".into(),
        message: Some("Starting conversion...".into()),
    });

    let mut child = Command::new("ebook-convert")
        .args(&args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start ebook-convert: {}", e))?;

    // Read stderr for progress
    let stderr = child.stderr.take();
    let stdout = child.stdout.take();
    let job_id = job.id.clone();
    let file_name = file_stem.clone();
    let app_clone = app.clone();

    if let Some(mut stderr) = stderr {
        let jid = job_id.clone();
        let fname = file_name.clone();
        let app2 = app_clone.clone();
        tokio::spawn(async move {
            let mut buf = [0u8; 1024];
            let mut accumulated = String::new();
            loop {
                match stderr.read(&mut buf).await {
                    Ok(0) => break,
                    Ok(n) => {
                        accumulated.push_str(&String::from_utf8_lossy(&buf[..n]));
                        // Parse progress percentage from calibre output
                        let pct = parse_progress(&accumulated);
                        let _ = app2.emit("conversion-progress", ConversionProgress {
                            job_id: jid.clone(),
                            file_name: fname.clone(),
                            progress: pct,
                            status: "converting".into(),
                            message: None,
                        });
                    }
                    Err(_) => break,
                }
            }
        });
    }

    // Also drain stdout
    if let Some(mut stdout) = stdout {
        tokio::spawn(async move {
            let mut buf = [0u8; 1024];
            loop {
                match stdout.read(&mut buf).await {
                    Ok(0) | Err(_) => break,
                    _ => {}
                }
            }
        });
    }

    let status = child.wait().await.map_err(|e| e.to_string())?;

    if status.success() {
        let _ = app.emit("conversion-progress", ConversionProgress {
            job_id: job.id,
            file_name,
            progress: 100.0,
            status: "done".into(),
            message: Some(output_str.clone()),
        });
        Ok(output_str)
    } else {
        let _ = app.emit("conversion-progress", ConversionProgress {
            job_id: job.id,
            file_name,
            progress: 0.0,
            status: "error".into(),
            message: Some("Conversion failed".into()),
        });
        Err("Conversion failed".into())
    }
}

fn parse_progress(text: &str) -> f64 {
    // Calibre outputs lines like "33% Converting input..."
    let mut best = 0.0f64;
    for line in text.lines() {
        let trimmed = line.trim();
        if let Some(pos) = trimmed.find('%') {
            if let Ok(num) = trimmed[..pos].trim().parse::<f64>() {
                if num > best && num <= 100.0 { best = num; }
            }
        }
    }
    best
}

#[tauri::command]
async fn get_toc(file_path: String) -> Result<String, String> {
    // Use ebook-convert to dump TOC
    let output = Command::new("ebook-convert")
        .args(&[&file_path, "/dev/null", "--dump-toc"])
        .output()
        .await;

    // Alternative: try ebook-meta
    let meta_output = Command::new("ebook-meta")
        .args(&[&file_path, "--get-cover", "/dev/null"])
        .output()
        .await;

    // Just return raw metadata which includes TOC info
    let output = Command::new("ebook-meta")
        .arg(&file_path)
        .output()
        .await
        .map_err(|e| e.to_string())?;

    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

#[tauri::command]
fn get_supported_formats() -> Vec<String> {
    vec![
        "epub".into(), "mobi".into(), "pdf".into(), "azw3".into(),
        "fb2".into(), "txt".into(), "html".into(), "docx".into(),
        "rtf".into(), "odt".into(), "lit".into(), "pdb".into(),
        "cbz".into(), "cbr".into(),
    ]
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            check_calibre,
            get_metadata,
            set_metadata,
            extract_cover,
            get_cover_base64,
            convert_ebook,
            get_toc,
            get_supported_formats,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
