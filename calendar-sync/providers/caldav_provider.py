"""CalDAV provider — works with Apple Calendar, Nextcloud, Radicale, etc."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from .base import CalendarProvider, CalendarEvent


class CalDAVProvider(CalendarProvider):
    """Generic CalDAV provider."""

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.url = config.get('url', '')
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        self.calendar_name = config.get('calendar_name', '')
        self._client = None
        self._calendar = None

    def connect(self) -> bool:
        try:
            import caldav
        except ImportError:
            print("CalDAV dependency not installed. Run: pip install caldav")
            return False

        try:
            self._client = caldav.DAVClient(
                url=self.url,
                username=self.username,
                password=self.password,
            )
            principal = self._client.principal()
            calendars = principal.calendars()

            if not calendars:
                print("No calendars found on CalDAV server")
                return False

            if self.calendar_name:
                for cal in calendars:
                    if cal.name == self.calendar_name:
                        self._calendar = cal
                        break
                if not self._calendar:
                    print(f"Calendar '{self.calendar_name}' not found. Available: {[c.name for c in calendars]}")
                    return False
            else:
                self._calendar = calendars[0]

            self._connected = True
            return True
        except Exception as e:
            print(f"CalDAV connection failed: {e}")
            return False

    def disconnect(self):
        self._client = None
        self._calendar = None
        self._connected = False

    def fetch_events(self, since: Optional[datetime] = None) -> list[CalendarEvent]:
        if not self._calendar:
            return []

        try:
            from icalendar import Calendar as ICalendar
        except ImportError:
            return []

        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=365)
        end = datetime.now(timezone.utc) + timedelta(days=365)

        events = []
        try:
            results = self._calendar.date_search(start=since, end=end, expand=False)
            for caldav_event in results:
                try:
                    ical_data = caldav_event.data
                    if not ical_data:
                        continue
                    cal = ICalendar.from_ical(ical_data)
                    for component in cal.walk():
                        if component.name == 'VEVENT':
                            ev = self._parse_vevent(component, ical_data)
                            if ev:
                                events.append(ev)
                except Exception:
                    continue
        except Exception as e:
            print(f"Error fetching CalDAV events: {e}")

        return events

    def push_event(self, event: CalendarEvent) -> bool:
        if not self._calendar:
            return False

        ical_str = event.to_ical_string()
        try:
            # Try to find existing event and update
            try:
                existing = self._calendar.event_by_uid(event.uid)
                existing.data = ical_str
                existing.save()
                return True
            except Exception:
                pass

            # Create new
            self._calendar.save_event(ical_str)
            return True
        except Exception as e:
            print(f"Error pushing CalDAV event: {e}")
            return False

    def delete_event(self, uid: str) -> bool:
        if not self._calendar:
            return False
        try:
            existing = self._calendar.event_by_uid(uid)
            existing.delete()
            return True
        except Exception as e:
            print(f"Error deleting CalDAV event: {e}")
            return False

    @staticmethod
    def _parse_vevent(component, raw_ical: str = "") -> Optional[CalendarEvent]:
        from providers.ics_file import _parse_dt, _is_all_day

        try:
            return CalendarEvent(
                uid=str(component.get('uid', '')),
                summary=str(component.get('summary', '')),
                description=str(component.get('description', '')),
                location=str(component.get('location', '')),
                dtstart=_parse_dt(component.get('dtstart')),
                dtend=_parse_dt(component.get('dtend')),
                all_day=_is_all_day(component.get('dtstart')),
                last_modified=_parse_dt(component.get('last-modified')),
                created=_parse_dt(component.get('created')),
                status=str(component.get('status', 'CONFIRMED')),
                raw_ical=raw_ical if isinstance(raw_ical, str) else '',
            )
        except Exception:
            return None
