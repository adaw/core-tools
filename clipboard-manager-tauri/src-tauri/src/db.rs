use rusqlite::{params, Connection, Result};
use serde::Serialize;

#[derive(Debug, Serialize, Clone)]
pub struct ClipEntry {
    pub id: i64,
    pub content: String,
    pub category: String,
    pub pinned: bool,
    pub created_at: String,
}

pub struct Database {
    conn: Connection,
}

impl Database {
    pub fn new() -> Result<Self> {
        let data_dir = dirs_next().unwrap_or_else(|| std::path::PathBuf::from("."));
        std::fs::create_dir_all(&data_dir).ok();
        let db_path = data_dir.join("clipboard_history.db");
        let conn = Connection::open(db_path)?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'text',
                pinned INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_category ON entries(category);
            CREATE INDEX IF NOT EXISTS idx_pinned ON entries(pinned);
            CREATE INDEX IF NOT EXISTS idx_created ON entries(created_at DESC);",
        )?;
        Ok(Self { conn })
    }

    pub fn insert(&self, content: &str, category: &str) -> Result<i64> {
        // Avoid duplicate of most recent entry
        let last: Option<String> = self
            .conn
            .query_row(
                "SELECT content FROM entries ORDER BY id DESC LIMIT 1",
                [],
                |row| row.get(0),
            )
            .ok();
        if last.as_deref() == Some(content) {
            return Ok(0);
        }
        self.conn.execute(
            "INSERT INTO entries (content, category) VALUES (?1, ?2)",
            params![content, category],
        )?;
        Ok(self.conn.last_insert_rowid())
    }

    pub fn get_entries(
        &self,
        query: Option<&str>,
        category: Option<&str>,
        pinned_only: bool,
        limit: usize,
        offset: usize,
    ) -> Result<Vec<ClipEntry>> {
        let mut sql = String::from("SELECT id, content, category, pinned, created_at FROM entries WHERE 1=1");
        let mut param_values: Vec<Box<dyn rusqlite::types::ToSql>> = Vec::new();

        if let Some(q) = query {
            if !q.is_empty() {
                sql.push_str(" AND content LIKE ?");
                param_values.push(Box::new(format!("%{}%", q)));
            }
        }
        if let Some(cat) = category {
            if !cat.is_empty() && cat != "all" {
                sql.push_str(" AND category = ?");
                param_values.push(Box::new(cat.to_string()));
            }
        }
        if pinned_only {
            sql.push_str(" AND pinned = 1");
        }
        sql.push_str(" ORDER BY pinned DESC, id DESC LIMIT ? OFFSET ?");
        param_values.push(Box::new(limit as i64));
        param_values.push(Box::new(offset as i64));

        let params_ref: Vec<&dyn rusqlite::types::ToSql> = param_values.iter().map(|p| p.as_ref()).collect();
        let mut stmt = self.conn.prepare(&sql)?;
        let entries = stmt
            .query_map(params_ref.as_slice(), |row| {
                Ok(ClipEntry {
                    id: row.get(0)?,
                    content: row.get(1)?,
                    category: row.get(2)?,
                    pinned: row.get::<_, i32>(3)? != 0,
                    created_at: row.get(4)?,
                })
            })?
            .collect::<Result<Vec<_>>>()?;
        Ok(entries)
    }

    pub fn toggle_pin(&self, id: i64) -> Result<bool> {
        self.conn.execute(
            "UPDATE entries SET pinned = CASE WHEN pinned = 0 THEN 1 ELSE 0 END WHERE id = ?1",
            params![id],
        )?;
        let pinned: bool = self.conn.query_row(
            "SELECT pinned FROM entries WHERE id = ?1",
            params![id],
            |row| row.get::<_, i32>(0).map(|v| v != 0),
        )?;
        Ok(pinned)
    }

    pub fn delete(&self, id: i64) -> Result<()> {
        self.conn.execute("DELETE FROM entries WHERE id = ?1", params![id])?;
        Ok(())
    }

    pub fn clear_all(&self) -> Result<()> {
        self.conn.execute("DELETE FROM entries WHERE pinned = 0", [])?;
        Ok(())
    }

    pub fn enforce_limit(&self, max: usize) -> Result<()> {
        self.conn.execute(
            "DELETE FROM entries WHERE pinned = 0 AND id NOT IN (SELECT id FROM entries ORDER BY pinned DESC, id DESC LIMIT ?1)",
            params![max as i64],
        )?;
        Ok(())
    }
}

fn dirs_next() -> Option<std::path::PathBuf> {
    std::env::var("HOME")
        .ok()
        .map(|h| std::path::PathBuf::from(h).join(".local").join("share").join("clipboard-manager"))
}
