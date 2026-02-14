"""Abstract base provider and CalendarEvent data model."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class CalendarEvent:
    """Unified calendar event representation."""
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))
    summary: str = ""
    description: str = ""
    location: str = ""
    dtstart: Optional[datetime] = None
    dtend: Optional[datetime] = None
    all_day: bool = False
    rrule: str = ""
    last_modified: Optional[datetime] = None
    created: Optional[datetime] = None
    status: str = "CONFIRMED"
    organizer: str = ""
    attendees: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    raw_ical: str = ""  # Original iCal component text for lossless roundtrip

    def modified_timestamp(self) -> float:
        """Return last_modified as timestamp, or 0 if unset."""
        if self.last_modified:
            return self.last_modified.timestamp()
        if self.created:
            return self.created.timestamp()
        return 0.0

    def fingerprint(self) -> str:
        """Summary + start time fingerprint for fuzzy dedup."""
        s = (self.summary or "").strip().lower()
        t = self.dtstart.isoformat() if self.dtstart else ""
        return f"{s}|{t}"

    def to_ical_string(self) -> str:
        """Generate an iCal VEVENT string."""
        from icalendar import Calendar, Event, vDatetime
        cal = Calendar()
        cal.add('prodid', '-//CORE SYSTEMS//Calendar Sync//EN')
        cal.add('version', '2.0')
        ev = Event()
        ev.add('uid', self.uid)
        ev.add('summary', self.summary)
        if self.description:
            ev.add('description', self.description)
        if self.location:
            ev.add('location', self.location)
        if self.dtstart:
            if self.all_day:
                ev.add('dtstart', self.dtstart.date())
            else:
                ev.add('dtstart', self.dtstart)
        if self.dtend:
            if self.all_day:
                ev.add('dtend', self.dtend.date())
            else:
                ev.add('dtend', self.dtend)
        now = datetime.now(timezone.utc)
        ev.add('dtstamp', now)
        if self.last_modified:
            ev.add('last-modified', self.last_modified)
        ev.add('status', self.status)
        cal.add_component(ev)
        return cal.to_ical().decode('utf-8')


class CalendarProvider(ABC):
    """Abstract base class for calendar providers."""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self._connected = False

    @property
    def provider_type(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection. Returns True on success."""
        ...

    @abstractmethod
    def disconnect(self):
        """Clean up connection."""
        ...

    @abstractmethod
    def fetch_events(self, since: Optional[datetime] = None) -> list[CalendarEvent]:
        """Fetch events, optionally since a given datetime."""
        ...

    @abstractmethod
    def push_event(self, event: CalendarEvent) -> bool:
        """Push/update a single event. Returns True on success."""
        ...

    @abstractmethod
    def delete_event(self, uid: str) -> bool:
        """Delete event by UID. Returns True on success."""
        ...

    def is_connected(self) -> bool:
        return self._connected

    def __repr__(self):
        return f"<{self.provider_type} '{self.name}'>"
