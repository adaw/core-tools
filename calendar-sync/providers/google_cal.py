"""Google Calendar provider using OAuth2."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from .base import CalendarProvider, CalendarEvent


class GoogleCalendarProvider(CalendarProvider):
    """Google Calendar API provider."""

    SCOPES = ['https://www.googleapis.com/auth/calendar']

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.credentials_file = config.get('credentials_file', '')
        self.calendar_id = config.get('calendar_id', 'primary')
        self._service = None
        self._creds = None

    def connect(self) -> bool:
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError:
            print("Google Calendar dependencies not installed. Run: pip install google-api-python-client google-auth-oauthlib")
            return False

        from config import get_config_dir
        token_file = get_config_dir() / 'google_token.json'

        creds = None
        if token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(token_file), self.SCOPES)
            except Exception:
                pass

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None

            if not creds:
                if not self.credentials_file or not os.path.exists(self.credentials_file):
                    print("Google credentials file not found. Download from Google Cloud Console.")
                    return False
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"Google OAuth failed: {e}")
                    return False

            # Save token
            try:
                token_file.write_text(creds.to_json(), encoding='utf-8')
            except OSError:
                pass

        try:
            self._service = build('calendar', 'v3', credentials=creds)
            self._creds = creds
            self._connected = True
            return True
        except Exception as e:
            print(f"Failed to build Google Calendar service: {e}")
            return False

    def disconnect(self):
        self._service = None
        self._creds = None
        self._connected = False

    def fetch_events(self, since: Optional[datetime] = None) -> list[CalendarEvent]:
        if not self._service:
            return []

        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=365)

        events = []
        page_token = None

        try:
            while True:
                result = self._service.events().list(
                    calendarId=self.calendar_id,
                    timeMin=since.isoformat(),
                    maxResults=250,
                    singleEvents=True,
                    orderBy='startTime',
                    pageToken=page_token,
                ).execute()

                for item in result.get('items', []):
                    ev = self._parse_google_event(item)
                    if ev:
                        events.append(ev)

                page_token = result.get('nextPageToken')
                if not page_token:
                    break
        except Exception as e:
            print(f"Error fetching Google events: {e}")

        return events

    def push_event(self, event: CalendarEvent) -> bool:
        if not self._service:
            return False

        body = self._event_to_google(event)

        try:
            # Try update first
            self._service.events().update(
                calendarId=self.calendar_id,
                eventId=self._safe_event_id(event.uid),
                body=body,
            ).execute()
            return True
        except Exception:
            pass

        try:
            self._service.events().insert(
                calendarId=self.calendar_id,
                body=body,
            ).execute()
            return True
        except Exception as e:
            print(f"Error pushing event to Google: {e}")
            return False

    def delete_event(self, uid: str) -> bool:
        if not self._service:
            return False
        try:
            self._service.events().delete(
                calendarId=self.calendar_id,
                eventId=self._safe_event_id(uid),
            ).execute()
            return True
        except Exception as e:
            print(f"Error deleting Google event: {e}")
            return False

    @staticmethod
    def _safe_event_id(uid: str) -> str:
        """Google event IDs must be lowercase alphanumeric."""
        return uid.replace('-', '').replace('_', '').lower()[:1024]

    def _parse_google_event(self, item: dict) -> Optional[CalendarEvent]:
        try:
            start = item.get('start', {})
            end = item.get('end', {})
            all_day = 'date' in start

            dtstart = None
            dtend = None
            if all_day:
                dtstart = datetime.fromisoformat(start['date']).replace(tzinfo=timezone.utc)
                dtend = datetime.fromisoformat(end.get('date', start['date'])).replace(tzinfo=timezone.utc)
            else:
                raw = start.get('dateTime', '')
                if raw:
                    dtstart = datetime.fromisoformat(raw)
                raw = end.get('dateTime', '')
                if raw:
                    dtend = datetime.fromisoformat(raw)

            updated = item.get('updated')
            last_mod = None
            if updated:
                last_mod = datetime.fromisoformat(updated.replace('Z', '+00:00'))

            created = None
            cr = item.get('created')
            if cr:
                created = datetime.fromisoformat(cr.replace('Z', '+00:00'))

            return CalendarEvent(
                uid=item.get('id', ''),
                summary=item.get('summary', ''),
                description=item.get('description', ''),
                location=item.get('location', ''),
                dtstart=dtstart,
                dtend=dtend,
                all_day=all_day,
                last_modified=last_mod,
                created=created,
                status=item.get('status', 'confirmed').upper(),
                organizer=item.get('organizer', {}).get('email', ''),
                attendees=[a.get('email', '') for a in item.get('attendees', [])],
            )
        except Exception:
            return None

    @staticmethod
    def _event_to_google(event: CalendarEvent) -> dict:
        body: dict = {
            'summary': event.summary,
            'description': event.description,
            'location': event.location,
            'status': event.status.lower(),
        }
        if event.all_day:
            if event.dtstart:
                body['start'] = {'date': event.dtstart.strftime('%Y-%m-%d')}
            if event.dtend:
                body['end'] = {'date': event.dtend.strftime('%Y-%m-%d')}
        else:
            if event.dtstart:
                body['start'] = {'dateTime': event.dtstart.isoformat()}
            if event.dtend:
                body['end'] = {'dateTime': event.dtend.isoformat()}
        return body
