use serde::{Deserialize, Serialize};
use std::path::Path;
use std::process::Command;

// ─── Types ───────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AudioFileInfo {
    pub path: String,
    pub name: String,
    pub format: String,
    pub duration: f64,
    pub bitrate: u32,
    pub sample_rate: u32,
    pub channels: u32,
    pub size: u64,
    pub title: String,
    pub artist: String,
    pub album: String,
    pub year: String,
    pub genre: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConvertOptions {
    pub input_path: String,
    pub output_path: String,
    pub format: String,
    pub bitrate: Option<String>,
    pub sample_rate: Option<u32>,
    pub channels: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EditOptions {
    pub input_path: String,
    pub output_path: String,
    pub operation: String,
    pub start_time: Option<f64>,
    pub end_time: Option<f64>,
    pub fade_duration: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetadataUpdate {
    pub path: String,
    pub title: Option<String>,
    pub artist: Option<String>,
    pub album: Option<String>,
    pub year: Option<String>,
    pub genre: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WaveformData {
    pub peaks: Vec<f32>,
    pub duration: f64,
    pub sample_rate: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpResult {
    pub success: bool,
    pub message: String,
    pub output_path: Option<String>,
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

fn find_ffmpeg() -> String {
    // Try common paths
    for path in &["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"] {
        if Path::new(path).exists() {
            return path.to_string();
        }
    }
    "ffmpeg".to_string()
}

fn find_ffprobe() -> String {
    for path in &["/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe", "/usr/bin/ffprobe"] {
        if Path::new(path).exists() {
            return path.to_string();
        }
    }
    "ffprobe".to_string()
}

// ─── Commands ────────────────────────────────────────────────────────────────

#[tauri::command]
fn probe_file(path: String) -> Result<AudioFileInfo, String> {
    let ffprobe = find_ffprobe();
    let output = Command::new(&ffprobe)
        .args([
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            &path,
        ])
        .output()
        .map_err(|e| format!("ffprobe error: {}", e))?;

    if !output.status.success() {
        return Err(format!("ffprobe failed: {}", String::from_utf8_lossy(&output.stderr)));
    }

    let json: serde_json::Value = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("JSON parse error: {}", e))?;

    let format = &json["format"];
    let stream = json["streams"].as_array()
        .and_then(|s| s.iter().find(|s| s["codec_type"] == "audio"))
        .ok_or("No audio stream found")?;

    let filename = Path::new(&path)
        .file_name()
        .unwrap_or_default()
        .to_string_lossy()
        .to_string();

    let tags = &format["tags"];

    Ok(AudioFileInfo {
        path: path.clone(),
        name: filename,
        format: format["format_name"].as_str().unwrap_or("unknown").to_string(),
        duration: format["duration"].as_str().unwrap_or("0").parse().unwrap_or(0.0),
        bitrate: format["bit_rate"].as_str().unwrap_or("0").parse().unwrap_or(0),
        sample_rate: stream["sample_rate"].as_str().unwrap_or("0").parse().unwrap_or(0),
        channels: stream["channels"].as_u64().unwrap_or(0) as u32,
        size: format["size"].as_str().unwrap_or("0").parse().unwrap_or(0),
        title: tags["title"].as_str().or(tags["TITLE"].as_str()).unwrap_or("").to_string(),
        artist: tags["artist"].as_str().or(tags["ARTIST"].as_str()).unwrap_or("").to_string(),
        album: tags["album"].as_str().or(tags["ALBUM"].as_str()).unwrap_or("").to_string(),
        year: tags["date"].as_str().or(tags["DATE"].as_str()).or(tags["year"].as_str()).unwrap_or("").to_string(),
        genre: tags["genre"].as_str().or(tags["GENRE"].as_str()).unwrap_or("").to_string(),
    })
}

#[tauri::command]
fn convert_audio(opts: ConvertOptions) -> Result<OpResult, String> {
    let ffmpeg = find_ffmpeg();
    let mut args = vec![
        "-y".to_string(),
        "-i".to_string(),
        opts.input_path.clone(),
    ];

    if let Some(br) = &opts.bitrate {
        args.push("-b:a".to_string());
        args.push(br.clone());
    }
    if let Some(sr) = opts.sample_rate {
        args.push("-ar".to_string());
        args.push(sr.to_string());
    }
    if let Some(ch) = opts.channels {
        args.push("-ac".to_string());
        args.push(ch.to_string());
    }
    args.push(opts.output_path.clone());

    let output = Command::new(&ffmpeg)
        .args(&args)
        .output()
        .map_err(|e| format!("ffmpeg error: {}", e))?;

    if output.status.success() {
        Ok(OpResult {
            success: true,
            message: "Conversion complete".to_string(),
            output_path: Some(opts.output_path),
        })
    } else {
        Ok(OpResult {
            success: false,
            message: String::from_utf8_lossy(&output.stderr).to_string(),
            output_path: None,
        })
    }
}

#[tauri::command]
fn edit_audio(opts: EditOptions) -> Result<OpResult, String> {
    let ffmpeg = find_ffmpeg();
    let mut args = vec!["-y".to_string(), "-i".to_string(), opts.input_path.clone()];

    match opts.operation.as_str() {
        "trim" => {
            if let Some(start) = opts.start_time {
                args.push("-ss".to_string());
                args.push(format!("{}", start));
            }
            if let Some(end) = opts.end_time {
                args.push("-to".to_string());
                args.push(format!("{}", end));
            }
            args.push("-c".to_string());
            args.push("copy".to_string());
        }
        "fade_in" => {
            let dur = opts.fade_duration.unwrap_or(2.0);
            args.push("-af".to_string());
            args.push(format!("afade=t=in:d={}", dur));
        }
        "fade_out" => {
            let dur = opts.fade_duration.unwrap_or(2.0);
            let start = opts.start_time.unwrap_or(0.0);
            args.push("-af".to_string());
            args.push(format!("afade=t=out:st={}:d={}", start, dur));
        }
        "normalize" => {
            args.push("-af".to_string());
            args.push("loudnorm=I=-16:LRA=11:TP=-1.5".to_string());
        }
        "split_silence" => {
            args.push("-af".to_string());
            args.push("silencedetect=noise=-30dB:d=1".to_string());
            args.push("-f".to_string());
            args.push("null".to_string());
            args.push("-".to_string());

            let output = Command::new(&ffmpeg)
                .args(&args)
                .output()
                .map_err(|e| format!("ffmpeg error: {}", e))?;

            return Ok(OpResult {
                success: output.status.success(),
                message: String::from_utf8_lossy(&output.stderr).to_string(),
                output_path: None,
            });
        }
        _ => return Err(format!("Unknown operation: {}", opts.operation)),
    }

    args.push(opts.output_path.clone());

    let output = Command::new(&ffmpeg)
        .args(&args)
        .output()
        .map_err(|e| format!("ffmpeg error: {}", e))?;

    Ok(OpResult {
        success: output.status.success(),
        message: if output.status.success() {
            "Edit complete".to_string()
        } else {
            String::from_utf8_lossy(&output.stderr).to_string()
        },
        output_path: if output.status.success() { Some(opts.output_path) } else { None },
    })
}

#[tauri::command]
fn merge_audio(input_paths: Vec<String>, output_path: String) -> Result<OpResult, String> {
    let ffmpeg = find_ffmpeg();

    // Create concat file content
    let list_content: String = input_paths
        .iter()
        .map(|p| format!("file '{}'", p.replace("'", "'\\''")))
        .collect::<Vec<_>>()
        .join("\n");

    let tmp_list = format!("{}.txt", &output_path);
    std::fs::write(&tmp_list, &list_content)
        .map_err(|e| format!("Failed to write concat list: {}", e))?;

    let output = Command::new(&ffmpeg)
        .args(["-y", "-f", "concat", "-safe", "0", "-i", &tmp_list, "-c", "copy", &output_path])
        .output()
        .map_err(|e| format!("ffmpeg error: {}", e))?;

    let _ = std::fs::remove_file(&tmp_list);

    Ok(OpResult {
        success: output.status.success(),
        message: if output.status.success() {
            "Merge complete".to_string()
        } else {
            String::from_utf8_lossy(&output.stderr).to_string()
        },
        output_path: if output.status.success() { Some(output_path) } else { None },
    })
}

#[tauri::command]
fn update_metadata(meta: MetadataUpdate) -> Result<OpResult, String> {
    let ffmpeg = find_ffmpeg();
    let ext = Path::new(&meta.path)
        .extension()
        .unwrap_or_default()
        .to_string_lossy()
        .to_string();
    let tmp_out = format!("{}_meta_tmp.{}", &meta.path, &ext);

    let mut args = vec!["-y".to_string(), "-i".to_string(), meta.path.clone()];

    if let Some(v) = &meta.title { args.extend(["-metadata".to_string(), format!("title={}", v)]); }
    if let Some(v) = &meta.artist { args.extend(["-metadata".to_string(), format!("artist={}", v)]); }
    if let Some(v) = &meta.album { args.extend(["-metadata".to_string(), format!("album={}", v)]); }
    if let Some(v) = &meta.year { args.extend(["-metadata".to_string(), format!("date={}", v)]); }
    if let Some(v) = &meta.genre { args.extend(["-metadata".to_string(), format!("genre={}", v)]); }

    args.extend(["-c".to_string(), "copy".to_string(), tmp_out.clone()]);

    let output = Command::new(&ffmpeg)
        .args(&args)
        .output()
        .map_err(|e| format!("ffmpeg error: {}", e))?;

    if output.status.success() {
        std::fs::rename(&tmp_out, &meta.path)
            .map_err(|e| format!("Failed to replace file: {}", e))?;
        Ok(OpResult {
            success: true,
            message: "Metadata updated".to_string(),
            output_path: Some(meta.path),
        })
    } else {
        let _ = std::fs::remove_file(&tmp_out);
        Ok(OpResult {
            success: false,
            message: String::from_utf8_lossy(&output.stderr).to_string(),
            output_path: None,
        })
    }
}

#[tauri::command]
fn get_waveform_data(path: String, num_peaks: u32) -> Result<WaveformData, String> {
    let ffprobe = find_ffprobe();
    let ffmpeg = find_ffmpeg();

    // Get duration
    let probe_out = Command::new(&ffprobe)
        .args(["-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", &path])
        .output()
        .map_err(|e| format!("ffprobe error: {}", e))?;

    let duration: f64 = String::from_utf8_lossy(&probe_out.stdout)
        .trim()
        .parse()
        .unwrap_or(0.0);

    // Extract raw PCM peaks using ffmpeg
    let output = Command::new(&ffmpeg)
        .args([
            "-i", &path,
            "-ac", "1",
            "-filter:a", &format!("aresample=8000,aformat=sample_fmts=s16", ),
            "-f", "s16le",
            "-"
        ])
        .output()
        .map_err(|e| format!("ffmpeg waveform error: {}", e))?;

    if !output.status.success() {
        return Err(format!("FFmpeg waveform extraction failed"));
    }

    let samples: Vec<i16> = output.stdout
        .chunks_exact(2)
        .map(|c| i16::from_le_bytes([c[0], c[1]]))
        .collect();

    let chunk_size = (samples.len() / num_peaks as usize).max(1);
    let peaks: Vec<f32> = samples
        .chunks(chunk_size)
        .take(num_peaks as usize)
        .map(|chunk| {
            let max = chunk.iter().map(|s| s.unsigned_abs() as f32).fold(0.0f32, f32::max);
            max / 32768.0
        })
        .collect();

    Ok(WaveformData {
        peaks,
        duration,
        sample_rate: 8000,
    })
}

// ─── App ─────────────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            probe_file,
            convert_audio,
            edit_audio,
            merge_audio,
            update_metadata,
            get_waveform_data,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
