use serde::{Deserialize, Serialize};
use sysinfo::{Components, Disks, Networks, System};
// (removed unused imports)

// ── Data structures ──────────────────────────────────────────────

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Overview {
    pub hostname: String,
    pub os_name: String,
    pub os_version: String,
    pub kernel_version: String,
    pub cpu_brand: String,
    pub cpu_cores: usize,
    pub total_memory_mb: u64,
    pub used_memory_mb: u64,
    pub total_swap_mb: u64,
    pub used_swap_mb: u64,
    pub uptime_seconds: u64,
    pub cpu_usage_percent: f32,
    pub load_avg: [f64; 3],
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CpuCore {
    pub name: String,
    pub usage_percent: f32,
    pub frequency_mhz: u64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CpuInfo {
    pub brand: String,
    pub physical_cores: usize,
    pub logical_cores: usize,
    pub global_usage: f32,
    pub cores: Vec<CpuCore>,
    pub temperatures: Vec<TempSensor>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TempSensor {
    pub label: String,
    pub temperature_c: f32,
    pub max_c: f32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MemoryInfo {
    pub total_mb: u64,
    pub used_mb: u64,
    pub available_mb: u64,
    pub usage_percent: f64,
    pub swap_total_mb: u64,
    pub swap_used_mb: u64,
    pub swap_usage_percent: f64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DiskEntry {
    pub name: String,
    pub mount_point: String,
    pub fs_type: String,
    pub total_gb: f64,
    pub used_gb: f64,
    pub available_gb: f64,
    pub usage_percent: f64,
    pub is_removable: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct NetworkInterface {
    pub name: String,
    pub received_bytes: u64,
    pub transmitted_bytes: u64,
    pub received_packets: u64,
    pub transmitted_packets: u64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ProcessEntry {
    pub pid: u32,
    pub name: String,
    pub cpu_percent: f32,
    pub memory_mb: u64,
    pub status: String,
}

// ── Tauri Commands ───────────────────────────────────────────────

#[tauri::command]
pub fn get_overview() -> Overview {
    let mut sys = System::new_all();
    sys.refresh_all();
    std::thread::sleep(std::time::Duration::from_millis(200));
    sys.refresh_cpu_all();

    let cpus = sys.cpus();
    let load = System::load_average();

    Overview {
        hostname: System::host_name().unwrap_or_default(),
        os_name: System::name().unwrap_or_default(),
        os_version: System::os_version().unwrap_or_default(),
        kernel_version: System::kernel_version().unwrap_or_default(),
        cpu_brand: cpus.first().map(|c| c.brand().to_string()).unwrap_or_default(),
        cpu_cores: cpus.len(),
        total_memory_mb: sys.total_memory() / 1_048_576,
        used_memory_mb: sys.used_memory() / 1_048_576,
        total_swap_mb: sys.total_swap() / 1_048_576,
        used_swap_mb: sys.used_swap() / 1_048_576,
        uptime_seconds: System::uptime(),
        cpu_usage_percent: sys.global_cpu_usage(),
        load_avg: [load.one, load.five, load.fifteen],
    }
}

#[tauri::command]
pub fn get_cpu_info() -> CpuInfo {
    let mut sys = System::new_all();
    sys.refresh_all();
    std::thread::sleep(std::time::Duration::from_millis(200));
    sys.refresh_cpu_all();

    let cpus = sys.cpus();
    let components = Components::new_with_refreshed_list();

    CpuInfo {
        brand: cpus.first().map(|c| c.brand().to_string()).unwrap_or_default(),
        physical_cores: sys.physical_core_count().unwrap_or(0),
        logical_cores: cpus.len(),
        global_usage: sys.global_cpu_usage(),
        cores: cpus
            .iter()
            .map(|c| CpuCore {
                name: c.name().to_string(),
                usage_percent: c.cpu_usage(),
                frequency_mhz: c.frequency(),
            })
            .collect(),
        temperatures: components
            .iter()
            .map(|comp| TempSensor {
                label: comp.label().to_string(),
                temperature_c: comp.temperature().unwrap_or(0.0),
                max_c: comp.max().unwrap_or(0.0),
            })
            .collect(),
    }
}

#[tauri::command]
pub fn get_memory_info() -> MemoryInfo {
    let mut sys = System::new_all();
    sys.refresh_memory();

    let total = sys.total_memory();
    let used = sys.used_memory();
    let swap_total = sys.total_swap();
    let swap_used = sys.used_swap();

    MemoryInfo {
        total_mb: total / 1_048_576,
        used_mb: used / 1_048_576,
        available_mb: sys.available_memory() / 1_048_576,
        usage_percent: if total > 0 { (used as f64 / total as f64) * 100.0 } else { 0.0 },
        swap_total_mb: swap_total / 1_048_576,
        swap_used_mb: swap_used / 1_048_576,
        swap_usage_percent: if swap_total > 0 { (swap_used as f64 / swap_total as f64) * 100.0 } else { 0.0 },
    }
}

#[tauri::command]
pub fn get_disk_info() -> Vec<DiskEntry> {
    let disks = Disks::new_with_refreshed_list();

    disks
        .iter()
        .map(|d| {
            let total = d.total_space();
            let available = d.available_space();
            let used = total.saturating_sub(available);
            DiskEntry {
                name: d.name().to_string_lossy().to_string(),
                mount_point: d.mount_point().to_string_lossy().to_string(),
                fs_type: d.file_system().to_string_lossy().to_string(),
                total_gb: total as f64 / 1_073_741_824.0,
                used_gb: used as f64 / 1_073_741_824.0,
                available_gb: available as f64 / 1_073_741_824.0,
                usage_percent: if total > 0 { (used as f64 / total as f64) * 100.0 } else { 0.0 },
                is_removable: d.is_removable(),
            }
        })
        .collect()
}

#[tauri::command]
pub fn get_network_info() -> Vec<NetworkInterface> {
    let networks = Networks::new_with_refreshed_list();

    networks
        .iter()
        .map(|(name, data)| NetworkInterface {
            name: name.clone(),
            received_bytes: data.total_received(),
            transmitted_bytes: data.total_transmitted(),
            received_packets: data.total_packets_received(),
            transmitted_packets: data.total_packets_transmitted(),
        })
        .collect()
}

#[tauri::command]
pub fn get_process_list() -> Vec<ProcessEntry> {
    let mut sys = System::new_all();
    sys.refresh_all();
    std::thread::sleep(std::time::Duration::from_millis(200));
    sys.refresh_all();

    let mut procs: Vec<ProcessEntry> = sys
        .processes()
        .iter()
        .map(|(pid, proc_)| ProcessEntry {
            pid: pid.as_u32(),
            name: proc_.name().to_string_lossy().to_string(),
            cpu_percent: proc_.cpu_usage(),
            memory_mb: proc_.memory() / 1_048_576,
            status: format!("{:?}", proc_.status()),
        })
        .collect();

    procs.sort_by(|a, b| b.cpu_percent.partial_cmp(&a.cpu_percent).unwrap_or(std::cmp::Ordering::Equal));
    procs.truncate(50);
    procs
}

#[tauri::command]
pub fn export_report_json() -> Result<String, String> {
    let overview = get_overview();
    let cpu = get_cpu_info();
    let memory = get_memory_info();
    let disks = get_disk_info();
    let network = get_network_info();
    let processes = get_process_list();

    let report = serde_json::json!({
        "timestamp": chrono::Local::now().to_rfc3339(),
        "overview": overview,
        "cpu": cpu,
        "memory": memory,
        "disks": disks,
        "network": network,
        "processes": processes,
    });

    serde_json::to_string_pretty(&report).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn export_report_html() -> Result<String, String> {
    let overview = get_overview();
    let _cpu = get_cpu_info();
    let memory = get_memory_info();
    let disks = get_disk_info();

    let html = format!(r#"<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>System Info Report</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 2rem; }}
h1 {{ color: #00ff88; }} h2 {{ color: #00ff88; border-bottom: 1px solid #333; padding-bottom: 0.5rem; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ padding: 8px 12px; border: 1px solid #333; text-align: left; }}
th {{ background: #16213e; color: #00ff88; }}
.bar {{ background: #333; border-radius: 4px; overflow: hidden; height: 20px; }}
.bar-fill {{ background: #00ff88; height: 100%; }}
</style>
</head>
<body>
<h1>🖥 System Info Report</h1>
<p>Generated: {timestamp}</p>

<h2>Overview</h2>
<table>
<tr><th>Hostname</th><td>{hostname}</td></tr>
<tr><th>OS</th><td>{os} {os_ver}</td></tr>
<tr><th>CPU</th><td>{cpu_brand} ({cores} cores)</td></tr>
<tr><th>Memory</th><td>{used_mem} / {total_mem} MB</td></tr>
<tr><th>Uptime</th><td>{uptime}s</td></tr>
</table>

<h2>CPU ({cpu_usage:.1}%)</h2>
<div class="bar"><div class="bar-fill" style="width:{cpu_usage}%"></div></div>

<h2>Memory ({mem_pct:.1}%)</h2>
<div class="bar"><div class="bar-fill" style="width:{mem_pct}%"></div></div>

<h2>Disks</h2>
<table>
<tr><th>Mount</th><th>Total GB</th><th>Used GB</th><th>Usage</th></tr>
{disk_rows}
</table>
</body></html>"#,
        timestamp = chrono::Local::now().format("%Y-%m-%d %H:%M:%S"),
        hostname = overview.hostname,
        os = overview.os_name,
        os_ver = overview.os_version,
        cpu_brand = overview.cpu_brand,
        cores = overview.cpu_cores,
        used_mem = overview.used_memory_mb,
        total_mem = overview.total_memory_mb,
        uptime = overview.uptime_seconds,
        cpu_usage = overview.cpu_usage_percent,
        mem_pct = memory.usage_percent,
        disk_rows = disks.iter().map(|d| format!(
            "<tr><td>{}</td><td>{:.1}</td><td>{:.1}</td><td>{:.1}%</td></tr>",
            d.mount_point, d.total_gb, d.used_gb, d.usage_percent
        )).collect::<Vec<_>>().join("\n"),
    );

    Ok(html)
}
