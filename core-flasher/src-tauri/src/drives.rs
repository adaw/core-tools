use crate::DriveInfo;

#[cfg(target_os = "macos")]
pub async fn list_usb_drives() -> Result<Vec<DriveInfo>, String> {
    let output = tokio::process::Command::new("diskutil")
        .args(["list", "-plist", "external", "physical"])
        .output()
        .await
        .map_err(|e| format!("Failed to run diskutil: {}", e))?;

    if !output.status.success() {
        // No external drives found is not an error
        return Ok(vec![]);
    }

    let plist_data = String::from_utf8_lossy(&output.stdout);
    let mut drives = Vec::new();

    // Parse diskutil output to find external USB drives
    // Use diskutil info for each disk found
    let list_output = tokio::process::Command::new("diskutil")
        .args(["list", "external", "physical"])
        .output()
        .await
        .map_err(|e| format!("Failed to run diskutil: {}", e))?;

    let list_text = String::from_utf8_lossy(&list_output.stdout);

    for line in list_text.lines() {
        if line.starts_with("/dev/disk") {
            let device = line.split_whitespace().next().unwrap_or("").to_string();
            if device.is_empty() {
                continue;
            }

            // Get detailed info for this disk
            let info_output = tokio::process::Command::new("diskutil")
                .args(["info", &device])
                .output()
                .await
                .map_err(|e| format!("diskutil info failed: {}", e))?;

            let info_text = String::from_utf8_lossy(&info_output.stdout);
            let mut name = String::from("USB Drive");
            let mut size: u64 = 0;
            let mut removable = false;
            let mut is_system = false;

            for info_line in info_text.lines() {
                let info_line = info_line.trim();
                if info_line.starts_with("Media Name:") {
                    name = info_line
                        .split(':')
                        .nth(1)
                        .unwrap_or("USB Drive")
                        .trim()
                        .to_string();
                } else if info_line.starts_with("Disk Size:") {
                    // Parse "Disk Size: 31.0 GB (31016378368 Bytes)"
                    if let Some(bytes_part) = info_line.split('(').nth(1) {
                        if let Some(num) = bytes_part.split_whitespace().next() {
                            size = num.parse().unwrap_or(0);
                        }
                    }
                } else if info_line.starts_with("Removable Media:") {
                    removable = info_line.contains("Removable");
                } else if info_line.starts_with("Virtual:") {
                    // Virtual disks might be system-related
                    if info_line.contains("Yes") {
                        is_system = true;
                    }
                } else if info_line.starts_with("Internal:") {
                    if info_line.contains("Yes") {
                        is_system = true;
                    }
                }
            }

            // SAFETY: Mark internal drives as system - NEVER allow flashing
            // diskutil "external physical" should only return external drives,
            // but double-check
            if device == "/dev/disk0" || device == "/dev/disk1" {
                is_system = true;
            }

            // Always consider removable for external drives
            if !is_system {
                removable = true;
            }

            drives.push(DriveInfo {
                device: device.clone(),
                name,
                size,
                size_human: bytesize::ByteSize(size).to_string(),
                removable,
                is_system,
            });
        }
    }

    // Filter out system drives entirely
    Ok(drives.into_iter().filter(|d| !d.is_system).collect())
}

#[cfg(target_os = "linux")]
pub async fn list_usb_drives() -> Result<Vec<DriveInfo>, String> {
    let output = tokio::process::Command::new("lsblk")
        .args(["-J", "-b", "-o", "NAME,SIZE,RM,TYPE,MOUNTPOINT,LABEL,TRAN"])
        .output()
        .await
        .map_err(|e| format!("Failed to run lsblk: {}", e))?;

    let text = String::from_utf8_lossy(&output.stdout);
    let parsed: serde_json::Value = serde_json::from_str(&text).map_err(|e| e.to_string())?;

    let mut drives = Vec::new();

    if let Some(devices) = parsed["blockdevices"].as_array() {
        for dev in devices {
            let dtype = dev["type"].as_str().unwrap_or("");
            if dtype != "disk" {
                continue;
            }

            let name = dev["name"].as_str().unwrap_or("");
            let size = dev["size"].as_u64().unwrap_or(0);
            let removable = dev["rm"].as_bool().unwrap_or(false)
                || dev["rm"].as_str() == Some("1")
                || dev["rm"].as_u64() == Some(1);
            let tran = dev["tran"].as_str().unwrap_or("");
            let label = dev["label"].as_str().unwrap_or(name);

            // Only USB drives
            let is_usb = tran == "usb" || removable;
            let device_path = format!("/dev/{}", name);

            // System disk detection
            let mut is_system = false;
            if let Some(children) = dev["children"].as_array() {
                for child in children {
                    let mp = child["mountpoint"].as_str().unwrap_or("");
                    if mp == "/" || mp == "/boot" || mp == "/home" || mp.starts_with("/boot/") {
                        is_system = true;
                    }
                }
            }

            if is_usb && !is_system {
                drives.push(DriveInfo {
                    device: device_path,
                    name: label.to_string(),
                    size,
                    size_human: bytesize::ByteSize(size).to_string(),
                    removable,
                    is_system: false,
                });
            }
        }
    }

    Ok(drives)
}

#[cfg(target_os = "windows")]
pub async fn list_usb_drives() -> Result<Vec<DriveInfo>, String> {
    let output = tokio::process::Command::new("powershell")
        .args([
            "-Command",
            "Get-Disk | Where-Object { $_.BusType -eq 'USB' } | Select-Object Number, FriendlyName, Size, IsSystem | ConvertTo-Json",
        ])
        .output()
        .await
        .map_err(|e| format!("Failed to run PowerShell: {}", e))?;

    let text = String::from_utf8_lossy(&output.stdout);
    let parsed: serde_json::Value = serde_json::from_str(&text).unwrap_or(serde_json::Value::Null);

    let mut drives = Vec::new();
    let disks = if parsed.is_array() {
        parsed.as_array().unwrap().clone()
    } else if parsed.is_object() {
        vec![parsed]
    } else {
        vec![]
    };

    for disk in disks {
        let num = disk["Number"].as_u64().unwrap_or(0);
        let name = disk["FriendlyName"]
            .as_str()
            .unwrap_or("USB Drive")
            .to_string();
        let size = disk["Size"].as_u64().unwrap_or(0);
        let is_system = disk["IsSystem"].as_bool().unwrap_or(false);

        if !is_system {
            drives.push(DriveInfo {
                device: format!("\\\\.\\PhysicalDrive{}", num),
                name,
                size,
                size_human: bytesize::ByteSize(size).to_string(),
                removable: true,
                is_system: false,
            });
        }
    }

    Ok(drives)
}
