"""Duplicate detection for calendar events."""

from __future__ import annotations

from enum import Enum
from difflib import SequenceMatcher
from typing import Optional

from providers.base import CalendarEvent


class DedupStrategy(Enum):
    UID = "uid"
    SUMMARY_TIME = "summary_time"
    FUZZY = "fuzzy"


def events_match(a: CalendarEvent, b: CalendarEvent, strategy: DedupStrategy) -> bool:
    """Check if two events are duplicates according to the given strategy."""
    if strategy == DedupStrategy.UID:
        return bool(a.uid and b.uid and a.uid == b.uid)
    elif strategy == DedupStrategy.SUMMARY_TIME:
        return a.fingerprint() == b.fingerprint()
    elif strategy == DedupStrategy.FUZZY:
        # UID match is always a hit
        if a.uid and b.uid and a.uid == b.uid:
            return True
        # Fuzzy: similar summary + close start time
        s1 = (a.summary or "").strip().lower()
        s2 = (b.summary or "").strip().lower()
        ratio = SequenceMatcher(None, s1, s2).ratio()
        if ratio < 0.8:
            return False
        # Times must be within 1 hour
        if a.dtstart and b.dtstart:
            delta = abs((a.dtstart - b.dtstart).total_seconds())
            return delta < 3600
        return ratio > 0.95
    return False


def find_duplicates(
    events: list[CalendarEvent],
    strategy: DedupStrategy = DedupStrategy.UID,
) -> list[tuple[int, int]]:
    """Find duplicate pairs in a list of events. Returns index pairs."""
    pairs = []
    for i in range(len(events)):
        for j in range(i + 1, len(events)):
            if events_match(events[i], events[j], strategy):
                pairs.append((i, j))
    return pairs


def find_match(
    event: CalendarEvent,
    candidates: list[CalendarEvent],
    strategy: DedupStrategy,
) -> Optional[CalendarEvent]:
    """Find a matching event in candidates list."""
    for c in candidates:
        if events_match(event, c, strategy):
            return c
    return None
