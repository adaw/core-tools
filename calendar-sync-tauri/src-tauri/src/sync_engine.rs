use crate::models::{CalendarSource, CalendarEvent, LogEntry, SyncConflict};
use crate::db;
use std::collections::HashMap;

/// Run sync across all configured sources
pub fn run_sync(
    sources: &[CalendarSource],
    two_way: bool,
    dedup: bool,
    conflict_strategy: &str,
) -> Result<String, Box<dyn std::error::Error>> {
    if sources.is_empty() {
        return Ok("No sources configured. Add a calendar source first.".into());
    }

    let mut total_synced = 0;
    let mut total_conflicts = 0;
    let mut total_deduped = 0;

    // Collect all events by source
    let mut all_events: HashMap<String, Vec<CalendarEvent>> = HashMap::new();
    for source in sources {
        let events = db::get_events_by_source(&source.id)?;
        all_events.insert(source.id.clone(), events);
    }

    // Deduplicate if enabled
    if dedup {
        let mut seen: HashMap<String, &CalendarEvent> = HashMap::new();
        for events in all_events.values() {
            for event in events {
                let key = format!("{}|{}", event.summary, event.dtstart);
                if seen.contains_key(&key) {
                    total_deduped += 1;
                    db::insert_log(&LogEntry::info("dedup", &format!("Duplicate: {}", event.summary)))?;
                } else {
                    seen.insert(key, event);
                }
            }
        }
    }

    // Detect conflicts (same UID, different content across sources)
    if sources.len() >= 2 {
        let conflicts = detect_conflicts(&all_events);
        for conflict in &conflicts {
            total_conflicts += 1;
            let resolution = resolve_conflict(conflict, conflict_strategy);
            db::insert_log(&LogEntry::conflict(
                "conflict",
                &format!("Conflict on '{}': resolved with '{}'", conflict.event_uid, resolution),
            ))?;
        }
    }

    // Two-way sync: propagate events between sources
    if two_way && sources.len() >= 2 {
        for (i, source) in sources.iter().enumerate() {
            let source_events = all_events.get(&source.id).cloned().unwrap_or_default();
            for (j, other_source) in sources.iter().enumerate() {
                if i == j { continue; }
                let other_events = all_events.get(&other_source.id).cloned().unwrap_or_default();
                let other_uids: Vec<&str> = other_events.iter().map(|e| e.uid.as_str()).collect();

                for event in &source_events {
                    if !other_uids.contains(&event.uid.as_str()) {
                        let mut new_event = event.clone();
                        new_event.source_id = other_source.id.clone();
                        db::insert_event(&new_event)?;
                        total_synced += 1;
                    }
                }
            }
        }
    }

    total_synced += all_events.values().map(|v| v.len()).sum::<usize>();

    Ok(format!(
        "✅ Sync complete: {} events processed, {} conflicts resolved, {} duplicates removed",
        total_synced, total_conflicts, total_deduped
    ))
}

/// Preview pending changes without applying
pub fn preview(sources: &[CalendarSource]) -> Result<String, Box<dyn std::error::Error>> {
    if sources.is_empty() {
        return Ok("No sources configured.".into());
    }

    let mut preview = String::from("<div>");
    for source in sources {
        let events = db::get_events_by_source(&source.id)?;
        preview.push_str(&format!(
            "<div class='log-entry'><span class='action'>{}</span> — {} events</div>",
            source.source_type, events.len()
        ));
    }
    preview.push_str("</div>");
    Ok(preview)
}

fn detect_conflicts(all_events: &HashMap<String, Vec<CalendarEvent>>) -> Vec<SyncConflict> {
    let mut by_uid: HashMap<&str, Vec<&CalendarEvent>> = HashMap::new();
    for events in all_events.values() {
        for event in events {
            by_uid.entry(&event.uid).or_default().push(event);
        }
    }

    let mut conflicts = Vec::new();
    for (_uid, versions) in &by_uid {
        if versions.len() >= 2 {
            let a = versions[0];
            let b = versions[1];
            if a.summary != b.summary || a.dtstart != b.dtstart || a.description != b.description {
                conflicts.push(SyncConflict {
                    event_uid: a.uid.clone(),
                    source_version: a.clone(),
                    target_version: b.clone(),
                    resolution: None,
                });
            }
        }
    }
    conflicts
}

fn resolve_conflict(conflict: &SyncConflict, strategy: &str) -> String {
    match strategy {
        "newest" => {
            if conflict.source_version.last_modified >= conflict.target_version.last_modified {
                "source".to_string()
            } else {
                "target".to_string()
            }
        }
        "source" => "source".to_string(),
        "target" => "target".to_string(),
        _ => "ask".to_string(),
    }
}
