use icalendar::{Calendar, Component, EventLike};
use crate::models::CalendarEvent;
use chrono::Utc;

/// Parse ICS content string into CalendarEvents
pub fn parse_ics(content: &str, source_id: &str) -> Result<Vec<CalendarEvent>, Box<dyn std::error::Error>> {
    let calendar: Calendar = content.parse().map_err(|e: String| e)?;
    let mut events = Vec::new();

    for component in calendar.components {
        if let Some(event) = component.as_event() {
            let uid = event.get_uid().unwrap_or("unknown").to_string();
            let summary = event.get_summary().unwrap_or("(no title)").to_string();
            let description = event.get_description().map(String::from);
            let location = event.get_location().map(String::from);

            let dtstart = event.property_value("DTSTART")
                .unwrap_or("unknown")
                .to_string();
            let dtend = event.property_value("DTEND")
                .map(String::from);
            let last_modified = event.property_value("LAST-MODIFIED")
                .map(String::from)
                .unwrap_or_else(|| Utc::now().format("%Y%m%dT%H%M%SZ").to_string());

            events.push(CalendarEvent {
                uid,
                summary,
                description,
                dtstart,
                dtend,
                location,
                source_id: source_id.to_string(),
                last_modified,
            });
        }
    }

    Ok(events)
}

/// Read and parse an ICS file
pub fn parse_ics_file(path: &str, source_id: &str) -> Result<Vec<CalendarEvent>, Box<dyn std::error::Error>> {
    let content = std::fs::read_to_string(path)?;
    parse_ics(&content, source_id)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_simple_ics() {
        let ics = r#"BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:test-123
SUMMARY:Test Event
DTSTART:20240101T100000Z
DTEND:20240101T110000Z
END:VEVENT
END:VCALENDAR"#;

        let events = parse_ics(ics, "test-source").unwrap();
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].summary, "Test Event");
    }
}
