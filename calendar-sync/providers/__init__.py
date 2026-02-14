"""Calendar providers for Calendar Sync."""

from .base import CalendarProvider, CalendarEvent
from .ics_file import ICSFileProvider
from .google_cal import GoogleCalendarProvider
from .outlook import OutlookProvider
from .caldav_provider import CalDAVProvider

PROVIDER_TYPES = {
    'ics_file': ICSFileProvider,
    'google': GoogleCalendarProvider,
    'outlook': OutlookProvider,
    'caldav': CalDAVProvider,
}

__all__ = [
    'CalendarProvider', 'CalendarEvent', 'PROVIDER_TYPES',
    'ICSFileProvider', 'GoogleCalendarProvider', 'OutlookProvider', 'CalDAVProvider',
]
