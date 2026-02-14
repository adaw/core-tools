use reqwest::blocking::Client;
use crate::models::CalendarEvent;
use crate::ics;

/// CalDAV client for fetching calendars
pub struct CalDavClient {
    url: String,
    username: String,
    password: String,
    client: Client,
}

impl CalDavClient {
    pub fn new(url: &str, username: &str, password: &str) -> Self {
        Self {
            url: url.to_string(),
            username: username.to_string(),
            password: password.to_string(),
            client: Client::new(),
        }
    }

    /// Discover calendars via PROPFIND
    pub fn discover_calendars(&self) -> Result<Vec<String>, Box<dyn std::error::Error>> {
        let body = r#"<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:" xmlns:cs="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:displayname/>
    <d:resourcetype/>
  </d:prop>
</d:propfind>"#;

        let response = self.client
            .request(reqwest::Method::from_bytes(b"PROPFIND").unwrap(), &self.url)
            .basic_auth(&self.username, Some(&self.password))
            .header("Depth", "1")
            .header("Content-Type", "application/xml")
            .body(body)
            .send()?;

        let text = response.text()?;
        // Simple href extraction (production would use proper XML parsing)
        let hrefs: Vec<String> = text.split("href>")
            .skip(1)
            .filter_map(|s| s.split('<').next().map(String::from))
            .collect();

        Ok(hrefs)
    }

    /// Fetch events from a calendar via REPORT
    pub fn fetch_events(&self, calendar_path: &str, source_id: &str) -> Result<Vec<CalendarEvent>, Box<dyn std::error::Error>> {
        let url = if calendar_path.starts_with("http") {
            calendar_path.to_string()
        } else {
            format!("{}{}", self.url.trim_end_matches('/'), calendar_path)
        };

        let body = r#"<?xml version="1.0" encoding="utf-8"?>
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:getetag/>
    <c:calendar-data/>
  </d:prop>
  <c:filter>
    <c:comp-filter name="VCALENDAR">
      <c:comp-filter name="VEVENT"/>
    </c:comp-filter>
  </c:filter>
</c:calendar-query>"#;

        let response = self.client
            .request(reqwest::Method::from_bytes(b"REPORT").unwrap(), &url)
            .basic_auth(&self.username, Some(&self.password))
            .header("Depth", "1")
            .header("Content-Type", "application/xml")
            .body(body)
            .send()?;

        let text = response.text()?;
        let mut all_events = Vec::new();

        // Extract calendar-data from response
        for segment in text.split("calendar-data>").skip(1).step_by(2) {
            if let Some(ics_data) = segment.split("</").next() {
                let decoded = ics_data
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                    .replace("&amp;", "&");
                if let Ok(events) = ics::parse_ics(&decoded, source_id) {
                    all_events.extend(events);
                }
            }
        }

        Ok(all_events)
    }

    /// Upload an event to CalDAV server
    pub fn put_event(&self, calendar_path: &str, event: &CalendarEvent) -> Result<(), Box<dyn std::error::Error>> {
        let url = format!("{}{}/{}.ics",
            self.url.trim_end_matches('/'),
            calendar_path,
            event.uid
        );

        let ics_content = format!(
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:{}\r\nSUMMARY:{}\r\nDTSTART:{}\r\n{}{}\r\nEND:VEVENT\r\nEND:VCALENDAR",
            event.uid,
            event.summary,
            event.dtstart,
            event.dtend.as_ref().map(|d| format!("DTEND:{}\r\n", d)).unwrap_or_default(),
            event.description.as_ref().map(|d| format!("DESCRIPTION:{}\r\n", d)).unwrap_or_default(),
        );

        self.client
            .put(&url)
            .basic_auth(&self.username, Some(&self.password))
            .header("Content-Type", "text/calendar")
            .body(ics_content)
            .send()?;

        Ok(())
    }
}
