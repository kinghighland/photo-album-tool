[中文说明](README.md)

# Photo Album Deduplication & Supplement Tool

This project is a Python tool for deduplicating and supplementing photo/video collections. It provides both command-line and graphical user interface (GUI) modes, suitable for batch organization, duplicate cleaning, and manual review of photos and videos.

---

## Features
- **Photo/Video Deduplication**: Supports common image formats (jpg/png/bmp/gif/tiff, etc.) and video formats (mp4/mov). Deduplication by content, filename+size, and more.
- **Supplement Analysis**: Automatically supplements photos/videos from a secondary folder to the main library if not already present. Supports batch move.
- **Detailed Reports**: Generates readable deduplication/supplement reports, viewable and actionable in the GUI.
- **Manual Review**: GUI supports group browsing, thumbnail preview, selective keep/delete, and batch selection strategies.
- **Corrupted File Detection**: Automatically detects and centralizes suspected corrupted photos/videos.
- **Multithreading/Multiprocessing**: Efficiently handles large numbers of files.
- **Progress Bar & Logging**: GUI displays real-time progress and detailed logs.

---

## Installation

Python 3.7+ is recommended. Use a virtual environment if possible.

```bash
pip install pillow psutil PyQt5
```

- For video thumbnail support on Windows, ensure [ffmpeg](https://ffmpeg.org/) is installed and added to your PATH.

---

## Command-Line Usage

### 1. Deduplication Mode

```bash
python main.py <target_folder> --report <report_output_path> [--hash md5|sha1] [--execute]
```
- By default, runs in dry-run mode (no actual file changes). Add `--execute` to perform real operations.
- Example:
  ```bash
  python main.py D:/photos --report report.txt --hash md5 --execute
  ```

### 2. Supplement Mode

```bash
python main.py <main_folder> <supplement_folder> --report <report_output_path> [--hash md5|sha1] [--execute]
```
- Example:
  ```bash
  python main.py D:/photos D:/phone_backup --report supplement_report.txt --execute
  ```

### 3. Help

```bash
python main.py --help
```

---

## Graphical User Interface (GUI)

### Launch GUI

```bash
python dedup_gui.py
```

### Main Features
- Generate deduplication/supplement reports (with multithreading, progress bar, and logs)
- Load reports, browse duplicate photo/video groups, thumbnail preview
- Select keep/delete, batch selection strategies (keep first/newest/largest)
- One-click batch delete, batch move of supplement files
- Centralized management of corrupted files
- Log area automatically displays detailed statistics (totals, deletable/supplementable counts, space savings, corrupted count, elapsed time, etc.)

---

## FAQ

- **Q: `ModuleNotFoundError: No module named 'PIL'`?**
  - A: Run `pip install pillow` first.
- **Q: Video thumbnails not showing?**
  - A: Make sure ffmpeg is installed and in your system PATH.
- **Q: Multiprocessing permission errors (Windows)?**
  - A: Try running as administrator, or avoid operating in system-protected folders.
- **Q: How are corrupted files handled?**
  - A: The tool automatically detects and moves suspected corrupted files to a 'Corrupted Files' subfolder.

---

## Directory Structure

```
photo-album-tool/
  |-- main.py           # Command-line entry
  |-- compare.py        # Core deduplication/supplement logic
  |-- dedup_gui.py      # GUI entry
  |-- README.md         # Project documentation
  |-- requirements.txt  # Dependencies (if present)
  |-- ...
```

---

## Contributing & Feedback

Suggestions, bug reports, and feature requests are welcome! Please open an issue or pull request.