# ⬡ CORE Batch Renamer

**Bulk file renaming tool with live preview, regex support, and undo.**

Part of [CORE Tools](https://github.com/core-systems/core-tools) — free utilities by CORE SYSTEMS.

![Screenshot](screenshots/preview.png)

---

## Features

- **Find & Replace** — simple text or regex-based search and replace
- **Sequential Numbering** — rename files with auto-incrementing numbers, custom prefix/suffix
- **Date Stamp** — add current date as prefix or suffix in any format
- **Extension Change** — batch change file extensions
- **Case Conversion** — lowercase, UPPERCASE, or Title Case
- **Advanced Regex** — full regex with capture groups and backreferences
- **Live Preview** — see exactly what will change before committing
- **Undo** — instantly reverse the last rename operation
- **Dark Theme** — modern UI with CORE SYSTEMS branding

## Requirements

- Python 3.8+
- No external dependencies (tkinter is included with Python)

## Usage

```bash
# Run directly
python3 renamer.py

# Or make executable
chmod +x renamer.py
./renamer.py
```

1. Click **Add Files** or **Add Folder** to load files
2. Select a rename mode tab (Find & Replace, Numbering, etc.)
3. Configure your rename rule
4. Click **Preview** to see changes
5. Click **RENAME** to execute
6. Use **Undo** if needed

## Build

### macOS (.app bundle)

```bash
chmod +x build.sh
./build.sh
```

Output: `dist/CORE Batch Renamer.app`

### Windows (.exe)

```cmd
build.bat
```

Output: `dist\CORE Batch Renamer.exe`

### Requirements for building

```bash
pip install pyinstaller
```

## Screenshots

| Preview Mode | After Rename |
|---|---|
| ![Preview](screenshots/preview.png) | ![Done](screenshots/done.png) |

> Screenshots are placeholders — will be updated with actual captures.

## License

MIT — free for personal and commercial use.

## Credits

Built by **CORE SYSTEMS** — [core.cz](https://core.cz)
