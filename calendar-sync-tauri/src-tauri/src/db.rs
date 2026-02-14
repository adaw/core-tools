use rusqlite::{Connection, params};
use std::sync::Mutex;
use std::path::PathBuf;
use once_cell::sync::Lazy;

use crate::models::{CalendarSource, LogEntry, CalendarEvent};

fn db_path() -> PathBuf {
    let mut path = dirs_next().unwrap_or_else(|| PathBuf::from("."));
    path.push("calendar_sync.db");
    path
}

fn dirs_next() -> Option<PathBuf> {
    #[cfg(target_os = "macos")]
    {
        std::env::var("HOME").ok().map(|h| PathBuf::from(h).join("Library/Application Support/com.core-tools.calendar-sync"))
    }
    #[cfg(not(target_os = "macos"))]
    {
        std::env::var("HOME").ok().map(|h| PathBuf::from(h).join(".calendar-sync"))
    }
}

static DB: Lazy<Mutex<Connection>> = Lazy::new(|| {
    let path = db_path();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).ok();
    }
    let conn = Connection::open(&path).expect("Failed to open database");
    Mutex::new(conn)
});

pub fn init() -> Result<(), Box<dyn std::error::Error>> {
    let conn = DB.lock().unwrap();
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            name TEXT NOT NULL,
            config TEXT NOT NULL,
            added_at TEXT NOT NULL,
            url TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            uid TEXT PRIMARY KEY,
            summary TEXT NOT NULL,
            description TEXT,
            dtstart TEXT NOT NULL,
            dtend TEXT,
            location TEXT,
            source_id TEXT NOT NULL,
            last_modified TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS log (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT NOT NULL,
            level TEXT NOT NULL DEFAULT 'info'
        );"
    )?;
    Ok(())
}

pub fn insert_source(source: &CalendarSource) -> Result<(), Box<dyn std::error::Error>> {
    let conn = DB.lock().unwrap();
    conn.execute(
        "INSERT INTO sources (id, source_type, name, config, added_at, url) VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
        params![source.id, source.source_type, source.name, source.config, source.added_at, source.url],
    )?;
    Ok(())
}

pub fn get_sources() -> Result<Vec<CalendarSource>, Box<dyn std::error::Error>> {
    let conn = DB.lock().unwrap();
    let mut stmt = conn.prepare("SELECT id, source_type, name, config, added_at, url FROM sources")?;
    let sources = stmt.query_map([], |row| {
        Ok(CalendarSource {
            id: row.get(0)?,
            source_type: row.get(1)?,
            name: row.get(2)?,
            config: row.get(3)?,
            added_at: row.get(4)?,
            url: row.get(5)?,
        })
    })?.filter_map(|r| r.ok()).collect();
    Ok(sources)
}

pub fn insert_event(event: &CalendarEvent) -> Result<(), Box<dyn std::error::Error>> {
    let conn = DB.lock().unwrap();
    conn.execute(
        "INSERT OR REPLACE INTO events (uid, summary, description, dtstart, dtend, location, source_id, last_modified)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
        params![event.uid, event.summary, event.description, event.dtstart, event.dtend, event.location, event.source_id, event.last_modified],
    )?;
    Ok(())
}

pub fn get_events_by_source(source_id: &str) -> Result<Vec<CalendarEvent>, Box<dyn std::error::Error>> {
    let conn = DB.lock().unwrap();
    let mut stmt = conn.prepare("SELECT uid, summary, description, dtstart, dtend, location, source_id, last_modified FROM events WHERE source_id = ?1")?;
    let events = stmt.query_map(params![source_id], |row| {
        Ok(CalendarEvent {
            uid: row.get(0)?,
            summary: row.get(1)?,
            description: row.get(2)?,
            dtstart: row.get(3)?,
            dtend: row.get(4)?,
            location: row.get(5)?,
            source_id: row.get(6)?,
            last_modified: row.get(7)?,
        })
    })?.filter_map(|r| r.ok()).collect();
    Ok(events)
}

pub fn insert_log(entry: &LogEntry) -> Result<(), Box<dyn std::error::Error>> {
    let conn = DB.lock().unwrap();
    conn.execute(
        "INSERT INTO log (id, timestamp, action, detail, level) VALUES (?1, ?2, ?3, ?4, ?5)",
        params![entry.id, entry.timestamp, entry.action, entry.detail, entry.level],
    )?;
    Ok(())
}

pub fn get_log_entries() -> Result<Vec<LogEntry>, Box<dyn std::error::Error>> {
    let conn = DB.lock().unwrap();
    let mut stmt = conn.prepare("SELECT id, timestamp, action, detail, level FROM log ORDER BY timestamp DESC LIMIT 100")?;
    let entries = stmt.query_map([], |row| {
        Ok(LogEntry {
            id: row.get(0)?,
            timestamp: row.get(1)?,
            action: row.get(2)?,
            detail: row.get(3)?,
            level: row.get(4)?,
        })
    })?.filter_map(|r| r.ok()).collect();
    Ok(entries)
}

pub fn clear_log() -> Result<(), Box<dyn std::error::Error>> {
    let conn = DB.lock().unwrap();
    conn.execute("DELETE FROM log", [])?;
    Ok(())
}
