use serde::{Deserialize, Serialize};
use chrono::Utc;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CalendarSource {
    pub id: String,
    pub source_type: String,
    pub name: String,
    pub config: String,
    pub added_at: String,
    pub url: Option<String>,
}

impl CalendarSource {
    pub fn new(source_type: &str, config: &str) -> Self {
        let url = serde_json::from_str::<serde_json::Value>(config)
            .ok()
            .and_then(|v| v.get("url").and_then(|u| u.as_str().map(String::from)));
        Self {
            id: Uuid::new_v4().to_string(),
            source_type: source_type.to_string(),
            name: source_type.to_string(),
            config: config.to_string(),
            added_at: Utc::now().format("%Y-%m-%d %H:%M:%S").to_string(),
            url,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CalendarEvent {
    pub uid: String,
    pub summary: String,
    pub description: Option<String>,
    pub dtstart: String,
    pub dtend: Option<String>,
    pub location: Option<String>,
    pub source_id: String,
    pub last_modified: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogEntry {
    pub id: String,
    pub timestamp: String,
    pub action: String,
    pub detail: String,
    pub level: String,
}

impl LogEntry {
    pub fn info(action: &str, detail: &str) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            timestamp: Utc::now().format("%Y-%m-%d %H:%M:%S").to_string(),
            action: action.to_string(),
            detail: detail.to_string(),
            level: "info".to_string(),
        }
    }

    pub fn conflict(action: &str, detail: &str) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            timestamp: Utc::now().format("%Y-%m-%d %H:%M:%S").to_string(),
            action: action.to_string(),
            detail: detail.to_string(),
            level: "conflict".to_string(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncConflict {
    pub event_uid: String,
    pub source_version: CalendarEvent,
    pub target_version: CalendarEvent,
    pub resolution: Option<String>,
}
