#[allow(unused_imports)]
use tauri::Manager;
use chrono::Local;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

// ─── Types ───────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileEntry {
    pub path: String,
    pub name: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PreviewItem {
    pub path: String,
    pub old_name: String,
    pub new_name: String,
    pub changed: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RenameResult {
    pub renamed: usize,
    pub errors: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "mode")]
pub enum RenameMode {
    #[serde(rename = "find_replace")]
    FindReplace {
        find: String,
        replace: String,
        use_regex: bool,
    },
    #[serde(rename = "numbering")]
    Numbering {
        prefix: String,
        suffix: String,
        start: usize,
        padding: usize,
    },
    #[serde(rename = "date_stamp")]
    DateStamp {
        format: String,
        position: String,
        separator: String,
    },
    #[serde(rename = "extension")]
    Extension { new_ext: String },
    #[serde(rename = "case_change")]
    CaseChange { case_type: String },
    #[serde(rename = "regex")]
    Regex {
        pattern: String,
        replacement: String,
        apply_to: String,
    },
}

// ─── Rename Logic ────────────────────────────────────────────────────────────

fn apply_rename(filename: &str, mode: &RenameMode, index: usize) -> String {
    let dot_pos = filename.rfind('.');
    let (name, ext) = match dot_pos {
        Some(pos) => (&filename[..pos], &filename[pos..]),
        None => (filename, ""),
    };

    match mode {
        RenameMode::FindReplace {
            find,
            replace,
            use_regex,
        } => {
            if find.is_empty() {
                return filename.to_string();
            }
            if *use_regex {
                match regex::Regex::new(find) {
                    Ok(re) => {
                        let new_name = re.replace_all(name, replace.as_str());
                        format!("{}{}", new_name, ext)
                    }
                    Err(_) => filename.to_string(),
                }
            } else {
                let new_name = name.replace(find.as_str(), replace.as_str());
                format!("{}{}", new_name, ext)
            }
        }
        RenameMode::Numbering {
            prefix,
            suffix,
            start,
            padding,
        } => {
            let num = format!("{:0>width$}", start + index, width = *padding);
            format!("{}{}{}{}", prefix, num, suffix, ext)
        }
        RenameMode::DateStamp {
            format: fmt,
            position,
            separator,
        } => {
            let date_str = Local::now().format(fmt).to_string();
            if position == "prefix" {
                format!("{}{}{}{}", date_str, separator, name, ext)
            } else {
                format!("{}{}{}{}", name, separator, date_str, ext)
            }
        }
        RenameMode::Extension { new_ext } => {
            let ext_with_dot = if new_ext.starts_with('.') {
                new_ext.clone()
            } else {
                format!(".{}", new_ext)
            };
            format!("{}{}", name, ext_with_dot)
        }
        RenameMode::CaseChange { case_type } => {
            let new_name = match case_type.as_str() {
                "upper" => name.to_uppercase(),
                "title" => {
                    let mut result = String::new();
                    let mut capitalize_next = true;
                    for ch in name.chars() {
                        if ch == ' ' || ch == '_' || ch == '-' {
                            capitalize_next = true;
                            result.push(ch);
                        } else if capitalize_next {
                            result.extend(ch.to_uppercase());
                            capitalize_next = false;
                        } else {
                            result.extend(ch.to_lowercase());
                        }
                    }
                    result
                }
                _ => name.to_lowercase(),
            };
            format!("{}{}", new_name, ext)
        }
        RenameMode::Regex {
            pattern,
            replacement,
            apply_to,
        } => {
            if pattern.is_empty() {
                return filename.to_string();
            }
            match regex::Regex::new(pattern) {
                Ok(re) => {
                    if apply_to == "full" {
                        re.replace_all(filename, replacement.as_str()).to_string()
                    } else {
                        let new_name = re.replace_all(name, replacement.as_str());
                        format!("{}{}", new_name, ext)
                    }
                }
                Err(_) => filename.to_string(),
            }
        }
    }
}

// ─── Commands ────────────────────────────────────────────────────────────────

#[tauri::command]
fn list_directory(path: String) -> Result<Vec<FileEntry>, String> {
    let dir = Path::new(&path);
    if !dir.is_dir() {
        return Err(format!("Not a directory: {}", path));
    }
    let mut entries: Vec<FileEntry> = Vec::new();
    let read_dir = fs::read_dir(dir).map_err(|e| e.to_string())?;
    for entry in read_dir {
        let entry = entry.map_err(|e| e.to_string())?;
        let file_path = entry.path();
        if file_path.is_file() {
            if let Some(name) = file_path.file_name().and_then(|n| n.to_str()) {
                entries.push(FileEntry {
                    path: file_path.to_string_lossy().to_string(),
                    name: name.to_string(),
                });
            }
        }
    }
    entries.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()));
    Ok(entries)
}

#[tauri::command]
fn validate_paths(paths: Vec<String>) -> Vec<FileEntry> {
    paths
        .into_iter()
        .filter_map(|p| {
            let path = PathBuf::from(&p);
            if path.is_file() {
                path.file_name()
                    .and_then(|n| n.to_str())
                    .map(|name| FileEntry {
                        path: p,
                        name: name.to_string(),
                    })
            } else {
                None
            }
        })
        .collect()
}

#[tauri::command]
fn preview_rename(files: Vec<FileEntry>, mode: RenameMode) -> Vec<PreviewItem> {
    files
        .iter()
        .enumerate()
        .map(|(i, f)| {
            let new_name = apply_rename(&f.name, &mode, i);
            let changed = new_name != f.name;
            PreviewItem {
                path: f.path.clone(),
                old_name: f.name.clone(),
                new_name,
                changed,
            }
        })
        .collect()
}

#[tauri::command]
fn execute_rename(files: Vec<FileEntry>, mode: RenameMode) -> RenameResult {
    let mut renamed = 0;
    let mut errors = Vec::new();

    let previews: Vec<_> = files
        .iter()
        .enumerate()
        .map(|(i, f)| {
            let new_name = apply_rename(&f.name, &mode, i);
            (f, new_name)
        })
        .collect();

    for (file, new_name) in &previews {
        if file.name == *new_name {
            continue;
        }
        let old_path = PathBuf::from(&file.path);
        let new_path = old_path.parent().unwrap().join(new_name);

        if new_path.exists() && old_path != new_path {
            errors.push(format!("Target exists: {}", new_name));
            continue;
        }
        match fs::rename(&old_path, &new_path) {
            Ok(_) => renamed += 1,
            Err(e) => errors.push(format!("{}: {}", file.name, e)),
        }
    }

    RenameResult { renamed, errors }
}

#[tauri::command]
fn undo_rename(operations: Vec<(String, String)>) -> RenameResult {
    let mut renamed = 0;
    let mut errors = Vec::new();

    for (new_path, old_path) in operations.iter().rev() {
        match fs::rename(new_path, old_path) {
            Ok(_) => renamed += 1,
            Err(e) => errors.push(format!("Undo failed: {}", e)),
        }
    }

    RenameResult { renamed, errors }
}

// ─── App ─────────────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
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
            list_directory,
            validate_paths,
            preview_rename,
            execute_rename,
            undo_rename,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
