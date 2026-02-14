"""Dark theme and CORE SYSTEMS branding for tkinter."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


# CORE SYSTEMS color palette
COLORS = {
    'bg': '#1a1a2e',
    'bg_secondary': '#16213e',
    'bg_tertiary': '#0f3460',
    'surface': '#1f2940',
    'surface_hover': '#283550',
    'accent': '#00ff88',
    'accent_dim': '#00cc6a',
    'accent_bg': '#003322',
    'text': '#e0e0e0',
    'text_secondary': '#a0a0b0',
    'text_dim': '#606080',
    'error': '#ff4444',
    'warning': '#ffaa00',
    'success': '#00ff88',
    'border': '#2a3a5e',
    'input_bg': '#0d1b2a',
    'input_border': '#1b2838',
    'scrollbar': '#2a3a5e',
    'tab_active': '#1f2940',
    'tab_inactive': '#0f1a2e',
}

FONTS = {
    'title': ('Segoe UI', 16, 'bold'),
    'heading': ('Segoe UI', 12, 'bold'),
    'body': ('Segoe UI', 10),
    'small': ('Segoe UI', 9),
    'mono': ('Consolas', 10),
    'mono_small': ('Consolas', 9),
}

# macOS font overrides
import sys
if sys.platform == 'darwin':
    FONTS = {
        'title': ('SF Pro Display', 16, 'bold'),
        'heading': ('SF Pro Display', 13, 'bold'),
        'body': ('SF Pro Text', 11),
        'small': ('SF Pro Text', 10),
        'mono': ('SF Mono', 11),
        'mono_small': ('SF Mono', 10),
    }


def apply_theme(root: tk.Tk):
    """Apply CORE SYSTEMS dark theme to the root window."""
    root.configure(bg=COLORS['bg'])
    root.option_add('*Background', COLORS['bg'])
    root.option_add('*Foreground', COLORS['text'])
    root.option_add('*Font', FONTS['body'])

    style = ttk.Style()

    # Try clam theme as base (best for customization)
    try:
        style.theme_use('clam')
    except Exception:
        pass

    # General
    style.configure('.', background=COLORS['bg'], foreground=COLORS['text'],
                     font=FONTS['body'], borderwidth=0)

    # Frame
    style.configure('TFrame', background=COLORS['bg'])
    style.configure('Surface.TFrame', background=COLORS['surface'])
    style.configure('Card.TFrame', background=COLORS['surface'], relief='flat')

    # Label
    style.configure('TLabel', background=COLORS['bg'], foreground=COLORS['text'],
                     font=FONTS['body'])
    style.configure('Title.TLabel', font=FONTS['title'], foreground=COLORS['accent'])
    style.configure('Heading.TLabel', font=FONTS['heading'], foreground=COLORS['text'])
    style.configure('Secondary.TLabel', foreground=COLORS['text_secondary'])
    style.configure('Accent.TLabel', foreground=COLORS['accent'])
    style.configure('Error.TLabel', foreground=COLORS['error'])
    style.configure('Success.TLabel', foreground=COLORS['success'])
    style.configure('Surface.TLabel', background=COLORS['surface'])

    # Button
    style.configure('TButton',
                     background=COLORS['bg_tertiary'],
                     foreground=COLORS['text'],
                     font=FONTS['body'],
                     padding=(12, 6),
                     borderwidth=1,
                     relief='flat')
    style.map('TButton',
              background=[('active', COLORS['surface_hover']),
                          ('pressed', COLORS['accent_bg'])],
              foreground=[('active', COLORS['accent'])])

    style.configure('Accent.TButton',
                     background=COLORS['accent_bg'],
                     foreground=COLORS['accent'],
                     font=FONTS['heading'])
    style.map('Accent.TButton',
              background=[('active', COLORS['accent_dim']),
                          ('pressed', COLORS['accent'])],
              foreground=[('active', COLORS['bg']),
                          ('pressed', COLORS['bg'])])

    style.configure('Danger.TButton',
                     background='#3a1a1a',
                     foreground=COLORS['error'])
    style.map('Danger.TButton',
              background=[('active', '#5a2a2a')])

    # Entry
    style.configure('TEntry',
                     fieldbackground=COLORS['input_bg'],
                     foreground=COLORS['text'],
                     insertcolor=COLORS['accent'],
                     borderwidth=1,
                     relief='solid')

    # Combobox
    style.configure('TCombobox',
                     fieldbackground=COLORS['input_bg'],
                     background=COLORS['bg_tertiary'],
                     foreground=COLORS['text'],
                     arrowcolor=COLORS['accent'],
                     borderwidth=1)
    style.map('TCombobox',
              fieldbackground=[('readonly', COLORS['input_bg'])],
              foreground=[('readonly', COLORS['text'])])

    # Notebook (tabs)
    style.configure('TNotebook', background=COLORS['bg'], borderwidth=0)
    style.configure('TNotebook.Tab',
                     background=COLORS['tab_inactive'],
                     foreground=COLORS['text_secondary'],
                     padding=(16, 8),
                     font=FONTS['body'])
    style.map('TNotebook.Tab',
              background=[('selected', COLORS['tab_active'])],
              foreground=[('selected', COLORS['accent'])])

    # Treeview
    style.configure('Treeview',
                     background=COLORS['surface'],
                     foreground=COLORS['text'],
                     fieldbackground=COLORS['surface'],
                     borderwidth=0,
                     font=FONTS['body'],
                     rowheight=28)
    style.configure('Treeview.Heading',
                     background=COLORS['bg_tertiary'],
                     foreground=COLORS['accent'],
                     font=FONTS['heading'],
                     borderwidth=0)
    style.map('Treeview',
              background=[('selected', COLORS['accent_bg'])],
              foreground=[('selected', COLORS['accent'])])

    # Scrollbar
    style.configure('Vertical.TScrollbar',
                     background=COLORS['bg_secondary'],
                     troughcolor=COLORS['bg'],
                     borderwidth=0,
                     arrowcolor=COLORS['accent'])

    # Checkbutton
    style.configure('TCheckbutton',
                     background=COLORS['bg'],
                     foreground=COLORS['text'],
                     font=FONTS['body'])
    style.map('TCheckbutton',
              background=[('active', COLORS['bg'])],
              foreground=[('active', COLORS['accent'])])

    # Radiobutton
    style.configure('TRadiobutton',
                     background=COLORS['bg'],
                     foreground=COLORS['text'],
                     font=FONTS['body'])
    style.map('TRadiobutton',
              background=[('active', COLORS['bg'])],
              foreground=[('active', COLORS['accent'])])

    # Progressbar
    style.configure('TProgressbar',
                     background=COLORS['accent'],
                     troughcolor=COLORS['bg_secondary'],
                     borderwidth=0)

    # Separator
    style.configure('TSeparator', background=COLORS['border'])

    # LabelFrame
    style.configure('TLabelframe',
                     background=COLORS['bg'],
                     foreground=COLORS['accent'],
                     borderwidth=1,
                     relief='solid')
    style.configure('TLabelframe.Label',
                     background=COLORS['bg'],
                     foreground=COLORS['accent'],
                     font=FONTS['heading'])

    # Spinbox
    style.configure('TSpinbox',
                     fieldbackground=COLORS['input_bg'],
                     foreground=COLORS['text'],
                     arrowcolor=COLORS['accent'],
                     borderwidth=1)

    return style


def create_separator(parent, orient='horizontal', **kwargs) -> ttk.Separator:
    sep = ttk.Separator(parent, orient=orient)
    sep.pack(fill='x' if orient == 'horizontal' else 'y', **kwargs)
    return sep


def branded_header(parent) -> ttk.Frame:
    """Create CORE SYSTEMS branded header."""
    frame = ttk.Frame(parent, style='Surface.TFrame')

    title = ttk.Label(frame, text="◆ CALENDAR SYNC", style='Title.TLabel')
    title.configure(background=COLORS['surface'])
    title.pack(side='left', padx=16, pady=12)

    subtitle = ttk.Label(frame, text="CORE SYSTEMS", style='Secondary.TLabel')
    subtitle.configure(background=COLORS['surface'], font=FONTS['small'])
    subtitle.pack(side='right', padx=16, pady=12)

    return frame
