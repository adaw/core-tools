use rusqlite::{Connection, params};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::Mutex;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClipItem {
    pub id: String,
    pub content: String,
    pub category: String,       // text | link | code | image
    pub pinned: bool,
    pub favorite: bool,
    pub timestamp: String,       // ISO 8601
    pub preview: String,         // truncated preview
}

pub struct Database {
    conn: Mutex<Connection>,
}

impl Database {
    pub fn new() -> Result<Self, String> {
        let path = Self::db_path();
        std::fs::create_dir_all(path.parent().unwrap()).map_err(|e| e.to_string())?;
        let conn = Connection::open(&path).map_err(|e| e.to_string())?;

        conn.execute_batch("
            PRAGMA journal_mode = WAL;
            PRAGMA synchronous = NORMAL;
            PRAGMA cache_size = -8000;
            CREATE TABLE IF NOT EXISTS clips (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'text',
                pinned INTEGER NOT NULL DEFAULT 0,
                favorite INTEGER NOT NULL DEFAULT 0,
                timestamp TEXT NOT NULL,
                preview TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_clips_timestamp ON clips(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_clips_category ON clips(category);
            CREATE INDEX IF NOT EXISTS idx_clips_pinned ON clips(pinned);
            CREATE INDEX IF NOT EXISTS idx_clips_content ON clips(content);
        ").map_err(|e| e.to_string())?;

        Ok(Self { conn: Mutex::new(conn) })
    }

    fn db_path() -> PathBuf {
        let base = if cfg!(target_os = "macos") {
            dirs_next().unwrap_or_else(|| PathBuf::from("."))
        } else {
            PathBuf::from(".")
        };
        base.join("history.db")
    }

    pub fn add(&self, content: &str) -> Result<Option<ClipItem>, String> {
        let content = content.trim();
        if content.is_empty() { return Ok(None); }

        let conn = self.conn.lock().map_err(|e| e.to_string())?;

        // Check for duplicate
        let existing: Option<String> = conn.query_row(
            "SELECT id FROM clips WHERE content = ?1 LIMIT 1",
            params![content],
            |row| row.get(0),
        ).ok();

        if let Some(id) = existing {
            // Update timestamp to move to top
            let now = chrono::Utc::now().to_rfc3339();
            conn.execute(
                "UPDATE clips SET timestamp = ?1 WHERE id = ?2",
                params![now, id],
            ).map_err(|e| e.to_string())?;
            return self.get_by_id_conn(&conn, &id);
        }

        let id = uuid::Uuid::new_v4().to_string();
        let category = categorize(content);
        let preview = make_preview(content);
        let now = chrono::Utc::now().to_rfc3339();

        conn.execute(
            "INSERT INTO clips (id, content, category, pinned, favorite, timestamp, preview)
             VALUES (?1, ?2, ?3, 0, 0, ?4, ?5)",
            params![id, content, category, now, preview],
        ).map_err(|e| e.to_string())?;

        // Auto-cleanup: keep max 2000 unpinned items
        conn.execute(
            "DELETE FROM clips WHERE pinned = 0 AND id NOT IN (
                SELECT id FROM clips WHERE pinned = 0 ORDER BY timestamp DESC LIMIT 2000
            )", [],
        ).map_err(|e| e.to_string())?;

        self.get_by_id_conn(&conn, &id)
    }

    fn get_by_id_conn(&self, conn: &Connection, id: &str) -> Result<Option<ClipItem>, String> {
        conn.query_row(
            "SELECT id, content, category, pinned, favorite, timestamp, preview FROM clips WHERE id = ?1",
            params![id],
            |row| Ok(ClipItem {
                id: row.get(0)?,
                content: row.get(1)?,
                category: row.get(2)?,
                pinned: row.get::<_, i32>(3)? != 0,
                favorite: row.get::<_, i32>(4)? != 0,
                timestamp: row.get(5)?,
                preview: row.get(6)?,
            }),
        ).map(Some).map_err(|e| e.to_string())
    }

    pub fn search(&self, query: &str, category: &str, limit: usize, offset: usize) -> Result<Vec<ClipItem>, String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;

        let (sql, use_query) = match (query.is_empty(), category == "all") {
            (true, true) => (
                "SELECT id, content, category, pinned, favorite, timestamp, preview FROM clips ORDER BY pinned DESC, timestamp DESC LIMIT ?1 OFFSET ?2".to_string(),
                false
            ),
            (true, false) => (
                format!("SELECT id, content, category, pinned, favorite, timestamp, preview FROM clips WHERE category = '{}' ORDER BY pinned DESC, timestamp DESC LIMIT ?1 OFFSET ?2", category),
                false
            ),
            (false, true) => (
                "SELECT id, content, category, pinned, favorite, timestamp, preview FROM clips WHERE content LIKE '%' || ?3 || '%' ORDER BY pinned DESC, timestamp DESC LIMIT ?1 OFFSET ?2".to_string(),
                true
            ),
            (false, false) => (
                format!("SELECT id, content, category, pinned, favorite, timestamp, preview FROM clips WHERE category = '{}' AND content LIKE '%' || ?3 || '%' ORDER BY pinned DESC, timestamp DESC LIMIT ?1 OFFSET ?2", category),
                true
            ),
        };

        let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
        let rows = if use_query {
            stmt.query_map(params![limit as i64, offset as i64, query], |row| {
                Ok(ClipItem {
                    id: row.get(0)?,
                    content: row.get(1)?,
                    category: row.get(2)?,
                    pinned: row.get::<_, i32>(3)? != 0,
                    favorite: row.get::<_, i32>(4)? != 0,
                    timestamp: row.get(5)?,
                    preview: row.get(6)?,
                })
            }).map_err(|e| e.to_string())?
        } else {
            stmt.query_map(params![limit as i64, offset as i64], |row| {
                Ok(ClipItem {
                    id: row.get(0)?,
                    content: row.get(1)?,
                    category: row.get(2)?,
                    pinned: row.get::<_, i32>(3)? != 0,
                    favorite: row.get::<_, i32>(4)? != 0,
                    timestamp: row.get(5)?,
                    preview: row.get(6)?,
                })
            }).map_err(|e| e.to_string())?
        };

        let mut items = Vec::new();
        for row in rows {
            items.push(row.map_err(|e| e.to_string())?);
        }
        Ok(items)
    }

    pub fn count(&self, query: &str, category: &str) -> Result<usize, String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        let (sql, use_query) = match (query.is_empty(), category == "all") {
            (true, true) => ("SELECT COUNT(*) FROM clips".to_string(), false),
            (true, false) => (format!("SELECT COUNT(*) FROM clips WHERE category = '{}'", category), false),
            (false, true) => ("SELECT COUNT(*) FROM clips WHERE content LIKE '%' || ?1 || '%'".to_string(), true),
            (false, false) => (format!("SELECT COUNT(*) FROM clips WHERE category = '{}' AND content LIKE '%' || ?1 || '%'", category), true),
        };
        let count: i64 = if use_query {
            conn.query_row(&sql, params![query], |r| r.get(0))
        } else {
            conn.query_row(&sql, [], |r| r.get(0))
        }.map_err(|e| e.to_string())?;
        Ok(count as usize)
    }

    pub fn delete(&self, id: &str) -> Result<(), String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        conn.execute("DELETE FROM clips WHERE id = ?1", params![id]).map_err(|e| e.to_string())?;
        Ok(())
    }

    pub fn toggle_pin(&self, id: &str) -> Result<bool, String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        conn.execute("UPDATE clips SET pinned = 1 - pinned WHERE id = ?1", params![id]).map_err(|e| e.to_string())?;
        let pinned: i32 = conn.query_row("SELECT pinned FROM clips WHERE id = ?1", params![id], |r| r.get(0)).map_err(|e| e.to_string())?;
        Ok(pinned != 0)
    }

    pub fn toggle_favorite(&self, id: &str) -> Result<bool, String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        conn.execute("UPDATE clips SET favorite = 1 - favorite WHERE id = ?1", params![id]).map_err(|e| e.to_string())?;
        let fav: i32 = conn.query_row("SELECT favorite FROM clips WHERE id = ?1", params![id], |r| r.get(0)).map_err(|e| e.to_string())?;
        Ok(fav != 0)
    }

    pub fn clear_unpinned(&self) -> Result<usize, String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        let count = conn.execute("DELETE FROM clips WHERE pinned = 0", []).map_err(|e| e.to_string())?;
        Ok(count)
    }

    pub fn export_json(&self) -> Result<String, String> {
        let items = self.search("", "all", 100000, 0)?;
        serde_json::to_string_pretty(&items).map_err(|e| e.to_string())
    }

    pub fn export_csv(&self) -> Result<String, String> {
        let items = self.search("", "all", 100000, 0)?;
        let mut wtr = csv::Writer::from_writer(Vec::new());
        wtr.write_record(&["id", "content", "category", "pinned", "favorite", "timestamp"]).map_err(|e| e.to_string())?;
        for item in &items {
            wtr.write_record(&[
                &item.id, &item.content, &item.category,
                &item.pinned.to_string(), &item.favorite.to_string(), &item.timestamp,
            ]).map_err(|e| e.to_string())?;
        }
        let data = wtr.into_inner().map_err(|e| e.to_string())?;
        String::from_utf8(data).map_err(|e| e.to_string())
    }

    pub fn cleanup_old(&self, days: i64) -> Result<usize, String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        let cutoff = (chrono::Utc::now() - chrono::Duration::days(days)).to_rfc3339();
        let count = conn.execute(
            "DELETE FROM clips WHERE pinned = 0 AND timestamp < ?1",
            params![cutoff],
        ).map_err(|e| e.to_string())?;
        Ok(count)
    }
}

fn dirs_next() -> Option<PathBuf> {
    #[cfg(target_os = "macos")]
    {
        std::env::var("HOME").ok().map(|h| PathBuf::from(h).join("Library/Application Support/CORE Clipboard Manager"))
    }
    #[cfg(target_os = "linux")]
    {
        std::env::var("HOME").ok().map(|h| PathBuf::from(h).join(".config/core-clipboard-manager"))
    }
    #[cfg(target_os = "windows")]
    {
        std::env::var("APPDATA").ok().map(|a| PathBuf::from(a).join("CORE Clipboard Manager"))
    }
}

fn categorize(text: &str) -> String {
    let trimmed = text.trim();
    // URL detection
    if trimmed.starts_with("http://") || trimmed.starts_with("https://") {
        if !trimmed.contains('\n') && !trimmed.contains(' ') {
            return "link".to_string();
        }
    }
    // Code detection: contains common code patterns
    let code_indicators = ["{", "}", "fn ", "def ", "class ", "import ", "const ", "let ", "var ",
                           "function ", "=>", "->", "pub ", "#include", "#!/", "SELECT ", "CREATE "];
    let line_count = trimmed.lines().count();
    let code_score: usize = code_indicators.iter()
        .filter(|&&ind| trimmed.contains(ind))
        .count();
    if line_count >= 3 && code_score >= 2 {
        return "code".to_string();
    }
    // Image data
    if trimmed.starts_with("data:image/") || trimmed.starts_with("iVBOR") || trimmed.starts_with("/9j/") {
        return "image".to_string();
    }
    "text".to_string()
}

fn make_preview(text: &str) -> String {
    let lines: Vec<&str> = text.lines().take(4).collect();
    let mut preview = lines.join("\n");
    if preview.len() > 300 {
        preview.truncate(300);
        preview.push_str("…");
    } else if text.lines().count() > 4 {
        preview.push_str("\n…");
    }
    preview
}
