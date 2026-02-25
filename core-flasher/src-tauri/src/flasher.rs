use crate::FlashProgress;
use md5::Md5;
use sha2::{Digest, Sha256};
use std::io::{Read, Seek, SeekFrom, Write};
use std::sync::{Arc, Mutex};
use std::time::Instant;
use tauri::{AppHandle, Emitter};

const BUFFER_SIZE: usize = 4 * 1024 * 1024; // 4MB buffer

pub async fn flash(
    app: &AppHandle,
    image_path: &str,
    device: &str,
    verify: bool,
    cancel: Arc<Mutex<bool>>,
) -> Result<(), String> {
    let image_path = image_path.to_string();
    let device = device.to_string();
    let app = app.clone();

    // Handle ZIP extraction
    let actual_path = if image_path.to_lowercase().ends_with(".zip") {
        emit_progress(&app, 0, 0, 0.0, 0.0, 0, "extracting", "Extracting ZIP...");
        extract_zip(&image_path).await?
    } else {
        image_path.clone()
    };

    // Unmount the drive first (macOS)
    #[cfg(target_os = "macos")]
    {
        emit_progress(&app, 0, 0, 0.0, 0.0, 0, "preparing", "Unmounting drive...");
        let _ = tokio::process::Command::new("diskutil")
            .args(["unmountDisk", &device])
            .output()
            .await;
    }

    // Get file size
    let file_size = std::fs::metadata(&actual_path)
        .map_err(|e| format!("Cannot read image: {}", e))?
        .len();

    // Open source and target
    let mut source =
        std::fs::File::open(&actual_path).map_err(|e| format!("Cannot open image: {}", e))?;

    // On macOS/Linux, we need raw device access
    let raw_device = if cfg!(target_os = "macos") {
        device.replace("/dev/disk", "/dev/rdisk")
    } else {
        device.clone()
    };

    let mut target = std::fs::OpenOptions::new()
        .write(true)
        .open(&raw_device)
        .map_err(|e| {
            format!(
                "Cannot open device {} — run with sudo or grant disk access: {}",
                raw_device, e
            )
        })?;

    // Write phase
    let mut buffer = vec![0u8; BUFFER_SIZE];
    let mut bytes_written: u64 = 0;
    let start = Instant::now();

    loop {
        if *cancel.lock().unwrap() {
            emit_progress(
                &app,
                bytes_written,
                file_size,
                0.0,
                0.0,
                0,
                "error",
                "Cancelled by user",
            );
            return Err("Flash cancelled".to_string());
        }

        let n = source
            .read(&mut buffer)
            .map_err(|e| format!("Read error: {}", e))?;
        if n == 0 {
            break;
        }

        target
            .write_all(&buffer[..n])
            .map_err(|e| format!("Write error: {}", e))?;

        bytes_written += n as u64;
        let elapsed = start.elapsed().as_secs_f64();
        let speed = if elapsed > 0.0 {
            bytes_written as f64 / elapsed / 1_048_576.0
        } else {
            0.0
        };
        let percent = (bytes_written as f64 / file_size as f64) * 100.0;
        let eta = if speed > 0.0 {
            ((file_size - bytes_written) as f64 / (speed * 1_048_576.0)) as u64
        } else {
            0
        };

        emit_progress(
            &app,
            bytes_written,
            file_size,
            percent,
            speed,
            eta,
            "writing",
            &format!("Writing... {:.1}%", percent),
        );
    }

    // Sync
    target
        .flush()
        .map_err(|e| format!("Flush error: {}", e))?;
    drop(target);

    // Verify phase
    if verify {
        emit_progress(
            &app,
            0,
            file_size,
            0.0,
            0.0,
            0,
            "verifying",
            "Verifying write...",
        );

        source.seek(SeekFrom::Start(0)).map_err(|e| e.to_string())?;
        let mut target_read = std::fs::File::open(&raw_device).map_err(|e| {
            format!("Cannot open device for verification: {}", e)
        })?;

        let mut src_buf = vec![0u8; BUFFER_SIZE];
        let mut tgt_buf = vec![0u8; BUFFER_SIZE];
        let mut verified: u64 = 0;
        let verify_start = Instant::now();

        loop {
            if *cancel.lock().unwrap() {
                return Err("Verification cancelled".to_string());
            }

            let n1 = source
                .read(&mut src_buf)
                .map_err(|e| format!("Read error: {}", e))?;
            if n1 == 0 {
                break;
            }

            let n2 = target_read
                .read(&mut tgt_buf[..n1])
                .map_err(|e| format!("Device read error: {}", e))?;

            if n1 != n2 || src_buf[..n1] != tgt_buf[..n2] {
                return Err(format!(
                    "Verification FAILED at byte offset {}",
                    verified
                ));
            }

            verified += n1 as u64;
            let elapsed = verify_start.elapsed().as_secs_f64();
            let speed = if elapsed > 0.0 {
                verified as f64 / elapsed / 1_048_576.0
            } else {
                0.0
            };
            let percent = (verified as f64 / file_size as f64) * 100.0;

            emit_progress(
                &app,
                verified,
                file_size,
                percent,
                speed,
                0,
                "verifying",
                &format!("Verifying... {:.1}%", percent),
            );
        }
    }

    emit_progress(
        &app,
        file_size,
        file_size,
        100.0,
        0.0,
        0,
        "done",
        "Flash complete!",
    );

    Ok(())
}

fn emit_progress(
    app: &AppHandle,
    bytes_written: u64,
    total_bytes: u64,
    percent: f64,
    speed_mbps: f64,
    eta_seconds: u64,
    phase: &str,
    message: &str,
) {
    let _ = app.emit(
        "flash-progress",
        FlashProgress {
            bytes_written,
            total_bytes,
            percent,
            speed_mbps,
            eta_seconds,
            phase: phase.to_string(),
            message: message.to_string(),
        },
    );
}

async fn extract_zip(zip_path: &str) -> Result<String, String> {
    let file = std::fs::File::open(zip_path).map_err(|e| format!("Cannot open ZIP: {}", e))?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| format!("Invalid ZIP: {}", e))?;

    // Find the first ISO/IMG/DMG in the archive
    let mut target_name = None;
    for i in 0..archive.len() {
        let entry = archive.by_index(i).map_err(|e| e.to_string())?;
        let name = entry.name().to_lowercase();
        if name.ends_with(".iso") || name.ends_with(".img") || name.ends_with(".dmg") {
            target_name = Some(i);
            break;
        }
    }

    let idx = target_name.ok_or("No ISO/IMG/DMG found in ZIP")?;
    let mut entry = archive.by_index(idx).map_err(|e| e.to_string())?;

    let tmp_dir = std::env::temp_dir().join("core-flasher");
    std::fs::create_dir_all(&tmp_dir).map_err(|e| e.to_string())?;

    let out_path = tmp_dir.join(entry.name().split('/').last().unwrap_or("image.img"));
    let mut out_file = std::fs::File::create(&out_path).map_err(|e| e.to_string())?;
    std::io::copy(&mut entry, &mut out_file).map_err(|e| e.to_string())?;

    Ok(out_path.to_string_lossy().to_string())
}

pub async fn compute_file_hash(path: &str, algorithm: &str) -> Result<String, String> {
    let mut file = std::fs::File::open(path).map_err(|e| format!("Cannot open file: {}", e))?;
    let mut buffer = vec![0u8; BUFFER_SIZE];

    match algorithm.to_lowercase().as_str() {
        "sha256" => {
            let mut hasher = Sha256::new();
            loop {
                let n = file.read(&mut buffer).map_err(|e| e.to_string())?;
                if n == 0 {
                    break;
                }
                hasher.update(&buffer[..n]);
            }
            Ok(format!("{:x}", hasher.finalize()))
        }
        "md5" => {
            let mut hasher = Md5::new();
            loop {
                let n = file.read(&mut buffer).map_err(|e| e.to_string())?;
                if n == 0 {
                    break;
                }
                hasher.update(&buffer[..n]);
            }
            Ok(format!("{:x}", hasher.finalize()))
        }
        _ => Err(format!("Unsupported algorithm: {}", algorithm)),
    }
}
