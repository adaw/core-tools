use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::process::Stdio;
use std::sync::{Arc, Mutex};
use tauri::State;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConversionJob {
    pub id: String,
    pub input_path: String,
    pub output_path: String,
    pub format: String,
    pub quality: String,
    pub progress: f64,
    pub status: String, // "pending", "running", "done", "error", "cancelled"
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConvertRequest {
    pub input_path: String,
    pub output_format: String,
    pub quality: String, // "low", "medium", "high", "lossless"
}

struct AppState {
    jobs: Arc<Mutex<HashMap<String, ConversionJob>>>,
    cancel_flags: Arc<Mutex<HashMap<String, bool>>>,
}

fn get_ffmpeg_args(input: &str, output: &str, format: &str, quality: &str) -> Vec<String> {
    let mut args = vec!["-i".to_string(), input.to_string(), "-y".to_string()];

    let (vb, ab) = match quality {
        "low" => ("1M", "96k"),
        "high" => ("8M", "320k"),
        "lossless" => ("0", "0"),
        _ => ("4M", "192k"), // medium
    };

    let audio_formats = ["mp3", "wav", "flac", "aac", "ogg"];
    let is_audio = audio_formats.contains(&format);

    if is_audio {
        args.push("-vn".to_string());
        match format {
            "mp3" => {
                if quality == "lossless" {
                    args.extend(["-b:a".to_string(), "320k".to_string()]);
                } else {
                    args.extend(["-b:a".to_string(), ab.to_string()]);
                }
            }
            "flac" => {
                args.extend(["-c:a".to_string(), "flac".to_string()]);
            }
            "wav" => {
                args.extend(["-c:a".to_string(), "pcm_s16le".to_string()]);
            }
            "aac" => {
                args.extend(["-c:a".to_string(), "aac".to_string(), "-b:a".to_string(), ab.to_string()]);
            }
            "ogg" => {
                args.extend(["-c:a".to_string(), "libvorbis".to_string(), "-b:a".to_string(), ab.to_string()]);
            }
            _ => {}
        }
    } else {
        match format {
            "mp4" => {
                args.extend(["-c:v".to_string(), "libx264".to_string(), "-b:v".to_string(), vb.to_string()]);
                args.extend(["-c:a".to_string(), "aac".to_string(), "-b:a".to_string(), ab.to_string()]);
            }
            "mkv" => {
                args.extend(["-c:v".to_string(), "libx264".to_string(), "-b:v".to_string(), vb.to_string()]);
                args.extend(["-c:a".to_string(), "aac".to_string(), "-b:a".to_string(), ab.to_string()]);
            }
            "avi" => {
                args.extend(["-c:v".to_string(), "mpeg4".to_string(), "-b:v".to_string(), vb.to_string()]);
                args.extend(["-c:a".to_string(), "mp3".to_string(), "-b:a".to_string(), ab.to_string()]);
            }
            "mov" => {
                args.extend(["-c:v".to_string(), "libx264".to_string(), "-b:v".to_string(), vb.to_string()]);
                args.extend(["-c:a".to_string(), "aac".to_string(), "-b:a".to_string(), ab.to_string()]);
            }
            "webm" => {
                args.extend(["-c:v".to_string(), "libvpx-vp9".to_string(), "-b:v".to_string(), vb.to_string()]);
                args.extend(["-c:a".to_string(), "libopus".to_string(), "-b:a".to_string(), ab.to_string()]);
            }
            _ => {}
        }
    }

    args.push(output.to_string());
    args
}

fn parse_duration(s: &str) -> Option<f64> {
    let re = Regex::new(r"(\d+):(\d+):(\d+)\.(\d+)").ok()?;
    let caps = re.captures(s)?;
    let h: f64 = caps[1].parse().ok()?;
    let m: f64 = caps[2].parse().ok()?;
    let s_val: f64 = caps[3].parse().ok()?;
    let cs: f64 = caps[4].parse().ok()?;
    Some(h * 3600.0 + m * 60.0 + s_val + cs / 100.0)
}

#[tauri::command]
async fn start_conversion(
    request: ConvertRequest,
    state: State<'_, AppState>,
) -> Result<String, String> {
    let job_id = Uuid::new_v4().to_string();

    let ext = &request.output_format;
    let input = &request.input_path;
    let dot_pos = input.rfind('.').unwrap_or(input.len());
    let output_path = format!("{}_converted.{}", &input[..dot_pos], ext);

    let job = ConversionJob {
        id: job_id.clone(),
        input_path: request.input_path.clone(),
        output_path: output_path.clone(),
        format: request.output_format.clone(),
        quality: request.quality.clone(),
        progress: 0.0,
        status: "running".to_string(),
        error: None,
    };

    {
        let mut jobs = state.jobs.lock().unwrap();
        jobs.insert(job_id.clone(), job);
        let mut flags = state.cancel_flags.lock().unwrap();
        flags.insert(job_id.clone(), false);
    }

    let args = get_ffmpeg_args(
        &request.input_path,
        &output_path,
        &request.output_format,
        &request.quality,
    );

    let jid = job_id.clone();
    let jobs_ref = state.jobs.clone();
    let flags_ref = state.cancel_flags.clone();

    tokio::spawn(async move {
        let result = Command::new("ffmpeg")
            .args(&args)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn();

        let mut child = match result {
            Ok(c) => c,
            Err(e) => {
                let mut jobs = jobs_ref.lock().unwrap();
                if let Some(job) = jobs.get_mut(&jid) {
                    job.status = "error".to_string();
                    job.error = Some(format!("Failed to start ffmpeg: {}", e));
                }
                return;
            }
        };

        let stderr = child.stderr.take().unwrap();
        let reader = BufReader::new(stderr);
        let mut lines = reader.lines();
        let mut duration: Option<f64> = None;
        let time_re = Regex::new(r"time=(\d+:\d+:\d+\.\d+)").unwrap();
        let dur_re = Regex::new(r"Duration:\s*(\d+:\d+:\d+\.\d+)").unwrap();

        loop {
            // Check cancel
            let should_cancel = {
                let flags = flags_ref.lock().unwrap();
                flags.get(&jid).copied().unwrap_or(false)
            };
            if should_cancel {
                let _ = child.kill().await;
                let mut jobs = jobs_ref.lock().unwrap();
                if let Some(job) = jobs.get_mut(&jid) {
                    job.status = "cancelled".to_string();
                }
                return;
            }

            match lines.next_line().await {
                Ok(Some(line)) => {
                    if duration.is_none() {
                        if let Some(caps) = dur_re.captures(&line) {
                            duration = parse_duration(&caps[1]);
                        }
                    }
                    if let Some(caps) = time_re.captures(&line) {
                        if let Some(current) = parse_duration(&caps[1]) {
                            if let Some(total) = duration {
                                let pct = (current / total * 100.0).min(100.0);
                                let mut jobs = jobs_ref.lock().unwrap();
                                if let Some(job) = jobs.get_mut(&jid) {
                                    job.progress = pct;
                                }
                            }
                        }
                    }
                }
                Ok(None) => break,
                Err(_) => break,
            }
        }

        let status = child.wait().await;
        let mut jobs = jobs_ref.lock().unwrap();
        if let Some(job) = jobs.get_mut(&jid) {
            if job.status == "cancelled" {
                return;
            }
            match status {
                Ok(s) if s.success() => {
                    job.status = "done".to_string();
                    job.progress = 100.0;
                }
                Ok(s) => {
                    job.status = "error".to_string();
                    job.error = Some(format!("ffmpeg exited with code {}", s.code().unwrap_or(-1)));
                }
                Err(e) => {
                    job.status = "error".to_string();
                    job.error = Some(format!("Process error: {}", e));
                }
            }
        }
    });

    Ok(job_id)
}

#[tauri::command]
async fn get_jobs(state: State<'_, AppState>) -> Result<Vec<ConversionJob>, String> {
    let jobs = state.jobs.lock().unwrap();
    Ok(jobs.values().cloned().collect())
}

#[tauri::command]
async fn cancel_job(job_id: String, state: State<'_, AppState>) -> Result<(), String> {
    let mut flags = state.cancel_flags.lock().unwrap();
    flags.insert(job_id, true);
    Ok(())
}

#[tauri::command]
async fn clear_completed(state: State<'_, AppState>) -> Result<(), String> {
    let mut jobs = state.jobs.lock().unwrap();
    jobs.retain(|_, j| j.status == "running" || j.status == "pending");
    Ok(())
}

#[tauri::command]
fn get_supported_formats() -> Vec<serde_json::Value> {
    serde_json::from_str(
        r#"[
        {"ext":"mp4","label":"MP4","type":"video"},
        {"ext":"mkv","label":"MKV","type":"video"},
        {"ext":"avi","label":"AVI","type":"video"},
        {"ext":"mov","label":"MOV","type":"video"},
        {"ext":"webm","label":"WebM","type":"video"},
        {"ext":"mp3","label":"MP3","type":"audio"},
        {"ext":"wav","label":"WAV","type":"audio"},
        {"ext":"flac","label":"FLAC","type":"audio"},
        {"ext":"aac","label":"AAC","type":"audio"},
        {"ext":"ogg","label":"OGG","type":"audio"}
    ]"#,
    )
    .unwrap()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(AppState {
            jobs: Arc::new(Mutex::new(HashMap::new())),
            cancel_flags: Arc::new(Mutex::new(HashMap::new())),
        })
        .invoke_handler(tauri::generate_handler![
            start_conversion,
            get_jobs,
            cancel_job,
            clear_completed,
            get_supported_formats,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
