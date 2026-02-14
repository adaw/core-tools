// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use chrono::Local;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use tauri::State;

// ── State ──────────────────────────────────────────────────────────────────

struct AppState {
    undo_stack: Mutex<Vec<Vec<RenameRecord>>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct RenameRecord {
    old_path: String,
    new_path: String,
}

// ── Types ──────────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(tag = "mode")]
enum RenameMode {
    #[serde(rename = "find_replace")]
    FindReplace { find: String, replace: String },
    #[serde(rename = "numbering")]
    Numbering {
        prefix: String,
        start: u32,
        padding: u32,
    },
    #[serde(rename = "date")]
    Date { format: String, position: String },
    #[serde(rename = "extension")]
    Extension { new_ext: String },
    #[serde(rename = "case")]
    Case { case_type: String },
    #[serde(rename = "regex")]
    RegexMode { pattern: String, replacement: String },
}

#[derive(Debug, Serialize)]
struct PreviewItem {
    original: String,
    renamed: String,
    changed: bool,
}

#[derive(Debug, Serialize)]
struct RenameResult {
    success: u32,
    failed: u32,
    errors: Vec<String>,
}

// ── Helpers ────────────────────────────────────────────────────────────────

fn apply_rename(name: &str, mode: &RenameMode, index: usize) -> String {
    let path = Path::new(name);
    let stem = path.file_stem().unwrap_or_default().to_string_lossy();
    let ext = path.extension().map(|e| e.to_string_lossy().to_string());

    let new_stem = match mode {
        RenameMode::FindReplace { find, replace } => stem.replace(find.as_str(), replace.as_str()),
        RenameMode::Numbering {
            prefix,
            start,
            padding,
        } => {
            let num = *start + index as u32;
            format!("{}{:0>width$}", prefix, num, width = *padding as usize)
        }
        RenameMode::Date { format, position } => {
            let date_str = Local::now().format(format.as_str()).to_string();
            match position.as_str() {
                "prefix" => format!("{}_{}", date_str, stem),
                "suffix" => format!("{}_{}", stem, date_str),
                _ => format!("{}_{}", date_str, stem),
            }
        }
        RenameMode::Extension { new_ext } => {
            let clean = new_ext.trim_start_matches('.');
            return format!("{}.{}", stem, clean);
        }
        RenameMode::Case { case_type } => match case_type.as_str() {
            "lower" => stem.to_lowercase(),
            "upper" => stem.to_uppercase(),
            "title" => stem
                .split(|c: char| c == '_' || c == '-' || c == ' ')
                .map(|w| {
                    let mut c = w.chars();
                    match c.next() {
                        None => String::new(),
                        Some(f) => f.to_uppercase().to_string() + &c.as_str().to_lowercase(),
                    }
                })
                .collect::<Vec<_>>()
                .join(" "),
            "snake" => stem
                .replace(|c: char| c == ' ' || c == '-', "_")
                .to_lowercase(),
            "kebab" => stem
                .replace(|c: char| c == ' ' || c == '_', "-")
                .to_lowercase(),
            _ => stem.to_string(),
        },
        RenameMode::RegexMode {
            pattern,
            replacement,
        } => {
            if let Ok(re) = Regex::new(pattern) {
                re.replace_all(&stem, replacement.as_str()).to_string()
            } else {
                stem.to_string()
            }
        }
    };

    match (mode, &ext) {
        (RenameMode::Extension { .. }, _) => new_stem,
        (_, Some(e)) => format!("{}.{}", new_stem, e),
        (_, None) => new_stem,
    }
}

// ── Commands ───────────────────────────────────────────────────────────────

#[tauri::command]
fn list_files(directory: String) -> Result<Vec<String>, String> {
    let path = PathBuf::from(&directory);
    if !path.is_dir() {
        return Err("Not a valid directory".into());
    }
    let mut files: Vec<String> = fs::read_dir(&path)
        .map_err(|e| e.to_string())?
        .filter_map(|entry| {
            let entry = entry.ok()?;
            if entry.file_type().ok()?.is_file() {
                Some(entry.file_name().to_string_lossy().to_string())
            } else {
                None
            }
        })
        .collect();
    files.sort();
    Ok(files)
}

#[tauri::command]
fn preview_rename(files: Vec<String>, mode_json: String) -> Result<Vec<PreviewItem>, String> {
    let mode: RenameMode = serde_json::from_str(&mode_json).map_err(|e| e.to_string())?;
    Ok(files
        .iter()
        .enumerate()
        .map(|(i, f)| {
            let renamed = apply_rename(f, &mode, i);
            let changed = &renamed != f;
            PreviewItem {
                original: f.clone(),
                renamed,
                changed,
            }
        })
        .collect())
}

#[tauri::command]
fn execute_rename(
    directory: String,
    files: Vec<String>,
    mode_json: String,
    state: State<AppState>,
) -> Result<RenameResult, String> {
    let mode: RenameMode = serde_json::from_str(&mode_json).map_err(|e| e.to_string())?;
    let dir = PathBuf::from(&directory);

    let mut success = 0u32;
    let mut failed = 0u32;
    let mut errors = Vec::new();
    let mut records = Vec::new();

    // Check for conflicts first
    let mut targets: HashMap<String, String> = HashMap::new();
    for (i, f) in files.iter().enumerate() {
        let new_name = apply_rename(f, &mode, i);
        if let Some(existing) = targets.get(&new_name) {
            return Err(format!(
                "Conflict: '{}' and '{}' would both become '{}'",
                existing, f, new_name
            ));
        }
        targets.insert(new_name, f.clone());
    }

    for (i, f) in files.iter().enumerate() {
        let new_name = apply_rename(f, &mode, i);
        if new_name == *f {
            continue;
        }
        let old_path = dir.join(f);
        let new_path = dir.join(&new_name);

        match fs::rename(&old_path, &new_path) {
            Ok(_) => {
                success += 1;
                records.push(RenameRecord {
                    old_path: old_path.to_string_lossy().to_string(),
                    new_path: new_path.to_string_lossy().to_string(),
                });
            }
            Err(e) => {
                failed += 1;
                errors.push(format!("{}: {}", f, e));
            }
        }
    }

    if !records.is_empty() {
        state.undo_stack.lock().unwrap().push(records);
    }

    Ok(RenameResult {
        success,
        failed,
        errors,
    })
}

#[tauri::command]
fn undo_rename(state: State<AppState>) -> Result<u32, String> {
    let mut stack = state.undo_stack.lock().unwrap();
    let records = stack.pop().ok_or("Nothing to undo")?;
    let mut count = 0u32;
    for rec in records.iter().rev() {
        if let Err(e) = fs::rename(&rec.new_path, &rec.old_path) {
            return Err(format!("Undo failed at {}: {}", rec.new_path, e));
        }
        count += 1;
    }
    Ok(count)
}

#[tauri::command]
fn get_undo_count(state: State<AppState>) -> usize {
    state.undo_stack.lock().unwrap().len()
}

fn main() {
    tauri::Builder::default()
        .manage(AppState {
            undo_stack: Mutex::new(Vec::new()),
        })
        .invoke_handler(tauri::generate_handler![
            list_files,
            preview_rename,
            execute_rename,
            undo_rename,
            get_undo_count,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
