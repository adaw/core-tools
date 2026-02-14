#!/usr/bin/env python3
"""Calendar Sync — Cross-platform calendar synchronization tool by CORE SYSTEMS."""

import sys
import os

# Ensure the app directory is on the path (for PyInstaller bundles)
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

from app import CalendarSyncApp


def main():
    app = CalendarSyncApp()
    app.mainloop()


if __name__ == "__main__":
    main()
