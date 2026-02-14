"""Conflict resolution strategies."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from providers.base import CalendarEvent


class ConflictStrategy(Enum):
    KEEP_BOTH = "keep_both"
    NEWER_WINS = "newer_wins"
    SOURCE_WINS = "source_wins"
    TARGET_WINS = "target_wins"
    MANUAL = "manual"


class ConflictResolver:
    """Resolves conflicts between two versions of the same event."""

    def __init__(self, strategy: ConflictStrategy = ConflictStrategy.NEWER_WINS):
        self.strategy = strategy
        self.pending_conflicts: list[tuple[CalendarEvent, CalendarEvent]] = []

    def resolve(
        self,
        source_event: CalendarEvent,
        target_event: CalendarEvent,
    ) -> Optional[CalendarEvent]:
        """
        Resolve conflict between source and target versions.
        Returns the winning event, or None if manual review needed.
        For KEEP_BOTH, returns the source event (target is kept as-is).
        """
        if self.strategy == ConflictStrategy.KEEP_BOTH:
            # Caller should keep target as-is and add source with new UID
            return source_event

        elif self.strategy == ConflictStrategy.NEWER_WINS:
            src_ts = source_event.modified_timestamp()
            tgt_ts = target_event.modified_timestamp()
            if src_ts >= tgt_ts:
                return source_event
            else:
                return target_event

        elif self.strategy == ConflictStrategy.SOURCE_WINS:
            return source_event

        elif self.strategy == ConflictStrategy.TARGET_WINS:
            return target_event

        elif self.strategy == ConflictStrategy.MANUAL:
            self.pending_conflicts.append((source_event, target_event))
            return None

        return source_event

    def has_pending(self) -> bool:
        return len(self.pending_conflicts) > 0

    def get_pending(self) -> list[tuple[CalendarEvent, CalendarEvent]]:
        return list(self.pending_conflicts)

    def resolve_pending(self, index: int, choose_source: bool) -> CalendarEvent:
        """Resolve a pending manual conflict."""
        src, tgt = self.pending_conflicts[index]
        return src if choose_source else tgt

    def clear_pending(self):
        self.pending_conflicts.clear()
