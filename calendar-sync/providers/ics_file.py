"""Local ICS file provider."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import CalendarProvider, CalendarEvent


def _parse_dt(val) -> Optional[datetime]:
    """Convert icalendar date/datetime to Python datetime."""
    if val is None:
        return None
    dt = val.dt if hasattr(val, 'dt') else val
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    # date only → midnight UTC
    from datetime import time
    return datetime.combine(dt, time.min, tzinfo=timezone.utc)


def _is_all_day(val) -> bool:
    if val is None:
        return False
    dt = val.dt if hasattr(val, 'dt') else val
    return not isinstance(dt, datetime)


class ICSFileProvider(CalendarProvider):
    """Read/write local .ics files."""

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.file_path = Path(config.get('file_path', ''))
        self._events: list[CalendarEvent] = []

    def connect(self) -> bool:
        if not self.file_path.exists():
            # Create empty ICS
            try:
                self.file_path.write_text(
                    "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//CORE SYSTEMS//Calendar Sync//EN\nEND:VCALENDAR\n",
                    encoding='utf-8'
                )
            except OSError:
                return False
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False
        self._events = []

    def fetch_events(self, since: Optional[datetime] = None) -> list[CalendarEvent]:
        try:
            from icalendar import Calendar
        except ImportError:
            return []

        try:
            text = self.file_path.read_text(encoding='utf-8')
        except OSError:
            return []

        cal = Calendar.from_ical(text)
        events = []
        for component in cal.walk():
            if component.name != 'VEVENT':
                continue
            ev = CalendarEvent(
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
                raw_ical=component.to_ical().decode('utf-8', errors='replace'),
            )
            if since and ev.dtstart and ev.dtstart < since:
                continue
            events.append(ev)

        self._events = events
        return events

    def push_event(self, event: CalendarEvent) -> bool:
        try:
            from icalendar import Calendar
        except ImportError:
            return False

        try:
            text = self.file_path.read_text(encoding='utf-8')
            cal = Calendar.from_ical(text)
        except (OSError, ValueError):
            cal = Calendar()
            cal.add('prodid', '-//CORE SYSTEMS//Calendar Sync//EN')
            cal.add('version', '2.0')

        # Remove existing event with same UID
        new_cal = Calendar()
        for key, val in cal.items():
            if key.upper() not in ('BEGIN', 'END'):
                new_cal.add(key, val)

        found = False
        for component in cal.walk():
            if component.name == 'VEVENT':
                if str(component.get('uid', '')) == event.uid:
                    found = True
                    continue  # Skip — we'll add the updated one
                new_cal.add_component(component)
            elif component.name not in ('VCALENDAR',):
                new_cal.add_component(component)

        # Add the event
        from icalendar import Event as IEvent
        new_ev = IEvent()
        new_ev.add('uid', event.uid)
        new_ev.add('summary', event.summary)
        if event.description:
            new_ev.add('description', event.description)
        if event.location:
            new_ev.add('location', event.location)
        if event.dtstart:
            if event.all_day:
                new_ev.add('dtstart', event.dtstart.date())
            else:
                new_ev.add('dtstart', event.dtstart)
        if event.dtend:
            if event.all_day:
                new_ev.add('dtend', event.dtend.date())
            else:
                new_ev.add('dtend', event.dtend)
        new_ev.add('dtstamp', datetime.now(timezone.utc))
        new_ev.add('last-modified', datetime.now(timezone.utc))
        new_ev.add('status', event.status)
        new_cal.add_component(new_ev)

        try:
            # Backup before write
            if self.file_path.exists():
                backup = self.file_path.with_suffix('.ics.bak')
                shutil.copy2(self.file_path, backup)
            self.file_path.write_bytes(new_cal.to_ical())
            return True
        except OSError:
            return False

    def delete_event(self, uid: str) -> bool:
        try:
            from icalendar import Calendar
        except ImportError:
            return False

        try:
            text = self.file_path.read_text(encoding='utf-8')
            cal = Calendar.from_ical(text)
        except (OSError, ValueError):
            return False

        new_cal = Calendar()
        for key, val in cal.items():
            if key.upper() not in ('BEGIN', 'END'):
                new_cal.add(key, val)

        found = False
        for component in cal.walk():
            if component.name == 'VEVENT':
                if str(component.get('uid', '')) == uid:
                    found = True
                    continue
                new_cal.add_component(component)
            elif component.name not in ('VCALENDAR',):
                new_cal.add_component(component)

        if not found:
            return False

        try:
            self.file_path.write_bytes(new_cal.to_ical())
            return True
        except OSError:
            return False
