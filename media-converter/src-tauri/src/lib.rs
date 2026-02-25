use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::process::Stdio;
use std::sync::Arc;
use tauri::{AppHandle, Emitter, Manager, State};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use tokio::sync::Mutex;
use uuid::Uuid;
use regex::Regex;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConvertRequest {
    pub file_path: String,
    pub output_dir: String,
    pub format: String,
    pub quality: String,
    pub codec: Option<String>,
    pub bitrate: Option<String>,
    pub resolution: Option<String>,
    pub sample_rate: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct FileInfo {
    pub path: String,
    pub name: String,
    pub size: u64,
    pub duration: f64,
    pub format: String,
    pub is_video: bool,
    pub codec: String,
    pub resolution: String,
    pub bitrate: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProgressEvent {
    pub job_id: String,
    pub file_name: String,
    pub progress: f64,
    pub status: String, // "converting", "done", "error", "cancelled"
    pub message: String,
}

struct AppState {
    jobs: Mutex<HashMap<String, tokio::sync::watch::Sender<bool>>>,
}

#[tauri::command]
async fn check_ffmpeg() -> Result<String, String> {
    let output = std::process::Command::new("ffmpeg")
        .arg("-version")
        .output();
    match output {
        Ok(o) => {
            let version = String::from_utf8_lossy(&o.stdout);
            let first_line = version.lines().next().unwrap_or("ffmpeg found");
            Ok(first_line.to_string())
        }
        Err(_) => Err("FFmpeg not found in PATH".to_string()),
    }
}

#[tauri::command]
async fn probe_file(path: String) -> Result<FileInfo, String> {
    let output = std::process::Command::new("ffprobe")
        .args([
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            &path,
        ])
        .output()
        .map_err(|e| format!("ffprobe error: {}", e))?;

    let json: serde_json::Value =
        serde_json::from_slice(&output.stdout).map_err(|e| format!("Parse error: {}", e))?;

    let format_info = &json["format"];
    let streams = json["streams"].as_array().ok_or("No streams")?;

    let video_stream = streams.iter().find(|s| s["codec_type"] == "video");
    let audio_stream = streams.iter().find(|s| s["codec_type"] == "audio");
    let is_video = video_stream.is_some();

    let duration = format_info["duration"]
        .as_str()
        .and_then(|d| d.parse::<f64>().ok())
        .unwrap_or(0.0);

    let file_name = std::path::Path::new(&path)
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_default();

    let size = format_info["size"]
        .as_str()
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(0);

    let codec = if is_video {
        video_stream.unwrap()["codec_name"]
            .as_str()
            .unwrap_or("unknown")
            .to_string()
    } else {
        audio_stream
            .map(|s| s["codec_name"].as_str().unwrap_or("unknown"))
            .unwrap_or("unknown")
            .to_string()
    };

    let resolution = if is_video {
        let vs = video_stream.unwrap();
        format!(
            "{}x{}",
            vs["width"].as_u64().unwrap_or(0),
            vs["height"].as_u64().unwrap_or(0)
        )
    } else {
        String::new()
    };

    let bitrate = format_info["bit_rate"]
        .as_str()
        .and_then(|b| b.parse::<u64>().ok())
        .map(|b| format!("{} kbps", b / 1000))
        .unwrap_or_default();

    let fmt = format_info["format_name"]
        .as_str()
        .unwrap_or("unknown")
        .to_string();

    Ok(FileInfo {
        path,
        name: file_name,
        size,
        duration,
        format: fmt,
        is_video,
        codec,
        resolution,
        bitrate,
    })
}

#[tauri::command]
async fn select_output_dir() -> Result<String, String> {
    // Use rfd for native folder dialog
    let result = rfd_pick_folder().await;
    result.ok_or("No folder selected".to_string())
}

async fn rfd_pick_folder() -> Option<String> {
    // Fallback: use a simple approach via tauri dialog plugin
    // Actually we handle this from frontend via tauri-plugin-dialog
    None
}

#[tauri::command]
async fn convert_file(
    app: AppHandle,
    state: State<'_, AppState>,
    request: ConvertRequest,
) -> Result<String, String> {
    let job_id = Uuid::new_v4().to_string();
    let (cancel_tx, cancel_rx) = tokio::sync::watch::channel(false);

    {
        let mut jobs = state.jobs.lock().await;
        jobs.insert(job_id.clone(), cancel_tx);
    }

    let job_id_clone = job_id.clone();
    let app_clone = app.clone();

    tokio::spawn(async move {
        run_conversion(app_clone, job_id_clone, request, cancel_rx).await;
    });

    Ok(job_id)
}

#[tauri::command]
async fn cancel_job(state: State<'_, AppState>, job_id: String) -> Result<(), String> {
    let jobs = state.jobs.lock().await;
    if let Some(tx) = jobs.get(&job_id) {
        let _ = tx.send(true);
        Ok(())
    } else {
        Err("Job not found".to_string())
    }
}

async fn run_conversion(
    app: AppHandle,
    job_id: String,
    request: ConvertRequest,
    mut cancel_rx: tokio::sync::watch::Receiver<bool>,
) {
    let src = PathBuf::from(&request.file_path);
    let file_name = src
        .file_stem()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or("output".to_string());
    let display_name = src
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or("file".to_string());

    let out_path = PathBuf::from(&request.output_dir)
        .join(format!("{}.{}", file_name, request.format.to_lowercase()));

    // Get duration for progress
    let duration = get_duration(&request.file_path).await.unwrap_or(0.0);

    let mut args: Vec<String> = vec![
        "-i".to_string(),
        request.file_path.clone(),
        "-y".to_string(),
        "-progress".to_string(),
        "pipe:1".to_string(),
    ];

    let video_formats = ["mp4", "mkv", "avi", "mov", "webm"];
    let audio_formats = ["mp3", "wav", "flac", "aac", "ogg"];
    let fmt = request.format.to_lowercase();
    let is_video_output = video_formats.contains(&fmt.as_str());
    let _is_audio_output = audio_formats.contains(&fmt.as_str());

    // Quality presets
    match request.quality.as_str() {
        "high" => {
            if is_video_output {
                args.extend(["-crf".to_string(), "18".to_string()]);
            } else {
                args.extend(["-q:a".to_string(), "0".to_string()]);
            }
        }
        "medium" => {
            if is_video_output {
                args.extend(["-crf".to_string(), "23".to_string()]);
            } else {
                args.extend(["-q:a".to_string(), "4".to_string()]);
            }
        }
        "low" => {
            if is_video_output {
                args.extend(["-crf".to_string(), "28".to_string()]);
            } else {
                args.extend(["-q:a".to_string(), "8".to_string()]);
            }
        }
        _ => {}
    }

    // Codec override
    if let Some(codec) = &request.codec {
        if !codec.is_empty() {
            if is_video_output {
                args.extend(["-c:v".to_string(), codec.clone()]);
            } else {
                args.extend(["-c:a".to_string(), codec.clone()]);
            }
        }
    }

    // Bitrate override
    if let Some(bitrate) = &request.bitrate {
        if !bitrate.is_empty() {
            if is_video_output {
                args.extend(["-b:v".to_string(), bitrate.clone()]);
            } else {
                args.extend(["-b:a".to_string(), bitrate.clone()]);
            }
        }
    }

    // Resolution override
    if let Some(res) = &request.resolution {
        if !res.is_empty() && is_video_output {
            args.extend(["-vf".to_string(), format!("scale={}", res.replace('x', ":"))]);
        }
    }

    // Sample rate override (audio)
    if let Some(sr) = &request.sample_rate {
        if !sr.is_empty() {
            args.extend(["-ar".to_string(), sr.clone()]);
        }
    }

    // Format-specific defaults
    match fmt.as_str() {
        "webm" => {
            if request.codec.is_none() || request.codec.as_deref() == Some("") {
                args.extend(["-c:v".to_string(), "libvpx-vp9".to_string()]);
                args.extend(["-c:a".to_string(), "libopus".to_string()]);
            }
        }
        "ogg" => {
            if request.codec.is_none() || request.codec.as_deref() == Some("") {
                args.extend(["-c:a".to_string(), "libvorbis".to_string()]);
            }
        }
        "aac" => {
            if request.codec.is_none() || request.codec.as_deref() == Some("") {
                args.extend(["-c:a".to_string(), "aac".to_string()]);
            }
        }
        _ => {}
    }

    // Audio-only extraction from video
    if !is_video_output {
        args.extend(["-vn".to_string()]);
    }

    args.push(out_path.to_string_lossy().to_string());

    emit_progress(&app, &job_id, &display_name, 0.0, "converting", "Starting...");

    let mut child = match Command::new("ffmpeg")
        .args(&args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            emit_progress(&app, &job_id, &display_name, 0.0, "error", &format!("Failed to start ffmpeg: {}", e));
            return;
        }
    };

    let stdout = child.stdout.take().unwrap();
    let mut reader = BufReader::new(stdout).lines();

    let time_re = Regex::new(r"out_time_us=(\d+)").unwrap();

    loop {
        tokio::select! {
            line = reader.next_line() => {
                match line {
                    Ok(Some(l)) => {
                        if let Some(caps) = time_re.captures(&l) {
                            if let Ok(us) = caps[1].parse::<f64>() {
                                let secs = us / 1_000_000.0;
                                let pct = if duration > 0.0 {
                                    (secs / duration * 100.0).min(99.9)
                                } else {
                                    0.0
                                };
                                emit_progress(&app, &job_id, &display_name, pct, "converting",
                                    &format!("{:.1}%", pct));
                            }
                        }
                    }
                    Ok(None) => break,
                    Err(_) => break,
                }
            }
            _ = cancel_rx.changed() => {
                if *cancel_rx.borrow() {
                    let _ = child.kill().await;
                    let _ = tokio::fs::remove_file(&out_path).await;
                    emit_progress(&app, &job_id, &display_name, 0.0, "cancelled", "Cancelled");
                    return;
                }
            }
        }
    }

    let status = child.wait().await;
    match status {
        Ok(s) if s.success() => {
            emit_progress(&app, &job_id, &display_name, 100.0, "done", "Complete!");
        }
        Ok(s) => {
            emit_progress(&app, &job_id, &display_name, 0.0, "error",
                &format!("FFmpeg exited with code {}", s.code().unwrap_or(-1)));
        }
        Err(e) => {
            emit_progress(&app, &job_id, &display_name, 0.0, "error", &format!("Error: {}", e));
        }
    }
}

fn emit_progress(app: &AppHandle, job_id: &str, file_name: &str, progress: f64, status: &str, message: &str) {
    let _ = app.emit("conversion-progress", ProgressEvent {
        job_id: job_id.to_string(),
        file_name: file_name.to_string(),
        progress,
        status: status.to_string(),
        message: message.to_string(),
    });
}

async fn get_duration(path: &str) -> Option<f64> {
    let output = std::process::Command::new("ffprobe")
        .args([
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            path,
        ])
        .output()
        .ok()?;
    let s = String::from_utf8_lossy(&output.stdout);
    s.trim().parse::<f64>().ok()
}

#[tauri::command]
async fn get_thumbnail(path: String) -> Result<String, String> {
    let tmp = std::env::temp_dir().join(format!("core_thumb_{}.jpg", Uuid::new_v4()));
    let status = std::process::Command::new("ffmpeg")
        .args([
            "-i", &path,
            "-ss", "00:00:01",
            "-vframes", "1",
            "-vf", "scale=200:-1",
            "-y",
            &tmp.to_string_lossy(),
        ])
        .output()
        .map_err(|e| e.to_string())?;

    if !status.status.success() {
        return Err("Failed to generate thumbnail".to_string());
    }

    let bytes = std::fs::read(&tmp).map_err(|e| e.to_string())?;
    let _ = std::fs::remove_file(&tmp);
    let b64 = base64_encode(&bytes);
    Ok(format!("data:image/jpeg;base64,{}", b64))
}

fn base64_encode(data: &[u8]) -> String {
    const CHARS: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut result = String::new();
    for chunk in data.chunks(3) {
        let b0 = chunk[0] as u32;
        let b1 = if chunk.len() > 1 { chunk[1] as u32 } else { 0 };
        let b2 = if chunk.len() > 2 { chunk[2] as u32 } else { 0 };
        let triple = (b0 << 16) | (b1 << 8) | b2;
        result.push(CHARS[((triple >> 18) & 0x3F) as usize] as char);
        result.push(CHARS[((triple >> 12) & 0x3F) as usize] as char);
        if chunk.len() > 1 {
            result.push(CHARS[((triple >> 6) & 0x3F) as usize] as char);
        } else {
            result.push('=');
        }
        if chunk.len() > 2 {
            result.push(CHARS[(triple & 0x3F) as usize] as char);
        } else {
            result.push('=');
        }
    }
    result
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .manage(AppState {
            jobs: Mutex::new(HashMap::new()),
        })
        .invoke_handler(tauri::generate_handler![
            check_ffmpeg,
            probe_file,
            convert_file,
            cancel_job,
            get_thumbnail,
            select_output_dir,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
