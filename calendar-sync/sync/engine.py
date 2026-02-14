"""Core sync engine — orchestrates synchronization between two providers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Callable

from providers.base import CalendarProvider, CalendarEvent
from .conflict import ConflictResolver, ConflictStrategy
from .dedup import DedupStrategy, find_match


class SyncDirection(Enum):
    ONE_WAY = "one_way"       # Source → Target
    TWO_WAY = "two_way"       # Source ↔ Target


@dataclass
class SyncChange:
    """Record of a single sync change."""
    action: str          # "added", "updated", "deleted", "skipped", "conflict"
    event_summary: str
    source_name: str
    target_name: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: str = ""

    def to_dict(self) -> dict:
        return {
            'action': self.action,
            'event_summary': self.event_summary,
            'source': self.source_name,
            'target': self.target_name,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details,
        }


@dataclass
class SyncResult:
    """Result of a sync operation."""
    added: int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0
    conflicts: int = 0
    errors: list[str] = field(default_factory=list)
    changes: list[SyncChange] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.added + self.updated + self.deleted

    def summary(self) -> str:
        parts = []
        if self.added:
            parts.append(f"{self.added} added")
        if self.updated:
            parts.append(f"{self.updated} updated")
        if self.deleted:
            parts.append(f"{self.deleted} deleted")
        if self.skipped:
            parts.append(f"{self.skipped} skipped")
        if self.conflicts:
            parts.append(f"{self.conflicts} conflicts")
        if self.errors:
            parts.append(f"{len(self.errors)} errors")
        return ", ".join(parts) if parts else "No changes"


class SyncEngine:
    """Orchestrates sync between two calendar providers."""

    def __init__(
        self,
        source: CalendarProvider,
        target: CalendarProvider,
        direction: SyncDirection = SyncDirection.TWO_WAY,
        conflict_strategy: ConflictStrategy = ConflictStrategy.NEWER_WINS,
        dedup_strategy: DedupStrategy = DedupStrategy.UID,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        self.source = source
        self.target = target
        self.direction = direction
        self.resolver = ConflictResolver(conflict_strategy)
        self.dedup = dedup_strategy
        self._progress = progress_callback or (lambda msg: None)

    def sync(self, since: Optional[datetime] = None) -> SyncResult:
        """Execute synchronization. Returns SyncResult."""
        result = SyncResult()

        self._progress(f"Fetching events from {self.source.name}...")
        source_events = self.source.fetch_events(since)
        self._progress(f"Found {len(source_events)} events in {self.source.name}")

        self._progress(f"Fetching events from {self.target.name}...")
        target_events = self.target.fetch_events(since)
        self._progress(f"Found {len(target_events)} events in {self.target.name}")

        # Source → Target
        self._sync_direction(
            source_events, target_events,
            self.source, self.target,
            result
        )

        # Target → Source (two-way only)
        if self.direction == SyncDirection.TWO_WAY:
            self._progress("Syncing reverse direction...")
            self._sync_direction(
                target_events, source_events,
                self.target, self.source,
                result
            )

        self._progress(f"Sync complete: {result.summary()}")
        return result

    def _sync_direction(
        self,
        from_events: list[CalendarEvent],
        to_events: list[CalendarEvent],
        from_provider: CalendarProvider,
        to_provider: CalendarProvider,
        result: SyncResult,
    ):
        for src_ev in from_events:
            match = find_match(src_ev, to_events, self.dedup)

            if match is None:
                # New event — push to target
                self._progress(f"Adding: {src_ev.summary}")
                if to_provider.push_event(src_ev):
                    result.added += 1
                    result.changes.append(SyncChange(
                        action="added",
                        event_summary=src_ev.summary,
                        source_name=from_provider.name,
                        target_name=to_provider.name,
                    ))
                else:
                    result.errors.append(f"Failed to add: {src_ev.summary}")
            else:
                # Exists — check for conflict
                if self._events_differ(src_ev, match):
                    winner = self.resolver.resolve(src_ev, match)
                    if winner is None:
                        # Manual review
                        result.conflicts += 1
                        result.changes.append(SyncChange(
                            action="conflict",
                            event_summary=src_ev.summary,
                            source_name=from_provider.name,
                            target_name=to_provider.name,
                            details="Awaiting manual resolution",
                        ))
                    elif winner is src_ev:
                        # Update target with source version
                        winner_copy = CalendarEvent(
                            uid=match.uid,  # Keep target UID
                            summary=winner.summary,
                            description=winner.description,
                            location=winner.location,
                            dtstart=winner.dtstart,
                            dtend=winner.dtend,
                            all_day=winner.all_day,
                            last_modified=winner.last_modified,
                            created=winner.created,
                            status=winner.status,
                        )
                        if to_provider.push_event(winner_copy):
                            result.updated += 1
                            result.changes.append(SyncChange(
                                action="updated",
                                event_summary=src_ev.summary,
                                source_name=from_provider.name,
                                target_name=to_provider.name,
                            ))
                        else:
                            result.errors.append(f"Failed to update: {src_ev.summary}")
                    else:
                        # Target wins — skip
                        result.skipped += 1
                else:
                    result.skipped += 1

    @staticmethod
    def _events_differ(a: CalendarEvent, b: CalendarEvent) -> bool:
        """Check if two events have meaningful differences."""
        return (
            a.summary != b.summary
            or a.description != b.description
            or a.location != b.location
            or a.dtstart != b.dtstart
            or a.dtend != b.dtend
            or a.all_day != b.all_day
            or a.status != b.status
        )
