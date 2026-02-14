"""Configuration persistence for Calendar Sync."""

import json
import os
from pathlib import Path
from typing import Any


def get_config_dir() -> Path:
    """Get platform-appropriate config directory."""
    if os.name == 'nt':
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    config_dir = base / 'CoreSystems' / 'CalendarSync'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


import sys


class Config:
    """Manages application configuration."""

    def __init__(self):
        self.config_dir = get_config_dir()
        self.config_file = self.config_dir / 'config.json'
        self.data: dict[str, Any] = self._load()

    def _load(self) -> dict:
        if self.config_file.exists():
            try:
                return json.loads(self.config_file.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, OSError):
                return self._defaults()
        return self._defaults()

    def _defaults(self) -> dict:
        return {
            'sources': [],
            'sync_pairs': [],
            'schedule_minutes': 0,
            'conflict_resolution': 'newer_wins',
            'dedup_strategy': 'uid',
            'window_geometry': '1100x750',
            'log_entries': [],
        }

    def save(self):
        try:
            self.config_file.write_text(
                json.dumps(self.data, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
        except OSError as e:
            print(f"Failed to save config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        self.data[key] = value
        self.save()

    def add_source(self, source: dict):
        sources = self.data.setdefault('sources', [])
        sources.append(source)
        self.save()

    def remove_source(self, index: int):
        sources = self.data.get('sources', [])
        if 0 <= index < len(sources):
            sources.pop(index)
            self.save()

    def add_log_entry(self, entry: dict):
        logs = self.data.setdefault('log_entries', [])
        logs.append(entry)
        # Keep last 1000 entries
        if len(logs) > 1000:
            self.data['log_entries'] = logs[-1000:]
        self.save()

    def clear_logs(self):
        self.data['log_entries'] = []
        self.save()
