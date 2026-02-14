"""Outlook/Exchange provider using Microsoft Graph API + MSAL."""

from __future__ import annotations

import json
import webbrowser
from datetime import datetime, timezone, timedelta
from typing import Optional

from .base import CalendarProvider, CalendarEvent


class OutlookProvider(CalendarProvider):
    """Microsoft Outlook/Exchange via Graph API."""

    GRAPH_URL = "https://graph.microsoft.com/v1.0"
    # Default public client for desktop apps
    DEFAULT_CLIENT_ID = "YOUR_CLIENT_ID"  # User must register their own app
    SCOPES = ["Calendars.ReadWrite", "User.Read"]

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.client_id = config.get('client_id', self.DEFAULT_CLIENT_ID)
        self.tenant_id = config.get('tenant_id', 'common')
        self.calendar_id = config.get('calendar_id', '')  # Empty = default
        self._token = None
        self._app = None

    def connect(self) -> bool:
        try:
            import msal
            import requests
        except ImportError:
            print("Outlook dependencies not installed. Run: pip install msal requests")
            return False

        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self._app = msal.PublicClientApplication(
            self.client_id, authority=authority
        )

        # Try cached token first
        accounts = self._app.get_accounts()
        if accounts:
            result = self._app.acquire_token_silent(self.SCOPES, account=accounts[0])
            if result and 'access_token' in result:
                self._token = result['access_token']
                self._connected = True
                return True

        # Interactive flow
        try:
            flow = self._app.initiate_device_flow(scopes=self.SCOPES)
            if 'user_code' not in flow:
                print("Failed to initiate device flow")
                return False
            print(f"\nTo sign in, visit: {flow['verification_uri']}")
            print(f"Enter code: {flow['user_code']}\n")
            webbrowser.open(flow['verification_uri'])
            result = self._app.acquire_token_by_device_flow(flow)
            if 'access_token' in result:
                self._token = result['access_token']
                self._connected = True
                return True
            else:
                print(f"Outlook auth failed: {result.get('error_description', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"Outlook OAuth error: {e}")
            return False

    def disconnect(self):
        self._token = None
        self._app = None
        self._connected = False

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self._token}',
            'Content-Type': 'application/json',
        }

    def _calendar_url(self) -> str:
        if self.calendar_id:
            return f"{self.GRAPH_URL}/me/calendars/{self.calendar_id}/events"
        return f"{self.GRAPH_URL}/me/events"

    def fetch_events(self, since: Optional[datetime] = None) -> list[CalendarEvent]:
        if not self._token:
            return []

        import requests

        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=365)

        events = []
        url = self._calendar_url()
        params = {
            '$top': 100,
            '$orderby': 'start/dateTime',
            '$filter': f"start/dateTime ge '{since.strftime('%Y-%m-%dT%H:%M:%S')}'",
        }

        try:
            while url:
                resp = requests.get(url, headers=self._headers(), params=params)
                if resp.status_code != 200:
                    print(f"Outlook API error: {resp.status_code} {resp.text[:200]}")
                    break

                data = resp.json()
                for item in data.get('value', []):
                    ev = self._parse_outlook_event(item)
                    if ev:
                        events.append(ev)

                url = data.get('@odata.nextLink')
                params = {}  # nextLink includes params
        except Exception as e:
            print(f"Error fetching Outlook events: {e}")

        return events

    def push_event(self, event: CalendarEvent) -> bool:
        if not self._token:
            return False

        import requests
        body = self._event_to_outlook(event)

        # Try PATCH (update) first
        try:
            url = f"{self._calendar_url()}/{event.uid}"
            resp = requests.patch(url, headers=self._headers(), json=body)
            if resp.status_code in (200, 204):
                return True
        except Exception:
            pass

        # Create new
        try:
            resp = requests.post(self._calendar_url(), headers=self._headers(), json=body)
            return resp.status_code in (200, 201)
        except Exception as e:
            print(f"Error pushing event to Outlook: {e}")
            return False

    def delete_event(self, uid: str) -> bool:
        if not self._token:
            return False

        import requests
        try:
            url = f"{self._calendar_url()}/{uid}"
            resp = requests.delete(url, headers=self._headers())
            return resp.status_code in (200, 204)
        except Exception as e:
            print(f"Error deleting Outlook event: {e}")
            return False

    def _parse_outlook_event(self, item: dict) -> Optional[CalendarEvent]:
        try:
            start = item.get('start', {})
            end = item.get('end', {})
            all_day = item.get('isAllDay', False)

            dtstart = None
            dtend = None
            if start.get('dateTime'):
                dtstart = datetime.fromisoformat(start['dateTime']).replace(tzinfo=timezone.utc)
            if end.get('dateTime'):
                dtend = datetime.fromisoformat(end['dateTime']).replace(tzinfo=timezone.utc)

            last_mod = None
            if item.get('lastModifiedDateTime'):
                last_mod = datetime.fromisoformat(
                    item['lastModifiedDateTime'].replace('Z', '+00:00')
                )
            created = None
            if item.get('createdDateTime'):
                created = datetime.fromisoformat(
                    item['createdDateTime'].replace('Z', '+00:00')
                )

            return CalendarEvent(
                uid=item.get('id', ''),
                summary=item.get('subject', ''),
                description=item.get('bodyPreview', ''),
                location=item.get('location', {}).get('displayName', ''),
                dtstart=dtstart,
                dtend=dtend,
                all_day=all_day,
                last_modified=last_mod,
                created=created,
                status='CONFIRMED',
                organizer=item.get('organizer', {}).get('emailAddress', {}).get('address', ''),
                attendees=[
                    a.get('emailAddress', {}).get('address', '')
                    for a in item.get('attendees', [])
                ],
            )
        except Exception:
            return None

    @staticmethod
    def _event_to_outlook(event: CalendarEvent) -> dict:
        body: dict = {
            'subject': event.summary,
            'body': {'contentType': 'text', 'content': event.description},
            'isAllDay': event.all_day,
        }
        if event.location:
            body['location'] = {'displayName': event.location}
        if event.dtstart:
            body['start'] = {
                'dateTime': event.dtstart.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': 'UTC',
            }
        if event.dtend:
            body['end'] = {
                'dateTime': event.dtend.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': 'UTC',
            }
        return body
