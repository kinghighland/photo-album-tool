[English](README-en.md)

# Photo Album Deduplication & Supplement Tool

本项目是一个支持图片/视频去重与增补的 Python 工具，提供命令行和图形界面（GUI）两种操作方式，适用于照片/视频批量整理、重复清理、人工筛选等场景。

---

## 功能特性
- **图片/视频去重**：支持常见图片格式（jpg/png/bmp/gif/tiff等）和视频格式（mp4/mov），可按内容、文件名+大小等多重策略去重。
- **增补分析**：自动将补充库中未在主库出现的图片/视频增补到主库，支持批量移动。
- **详细报告**：生成可读性强的去重/增补报告，支持 GUI 浏览、筛选、批量操作。
- **人工筛选**：GUI 支持分组浏览、缩略图预览、勾选保留/删除、批量选择策略。
- **损坏文件检测**：自动检测疑似损坏图片/视频并集中处理。
- **多线程/多进程**：高效处理大批量文件。
- **进度条与日志**：GUI 实时显示进度与详细日志。

---

## 安装依赖

建议使用 Python 3.7+，推荐虚拟环境。

```bash
pip install pillow psutil PyQt5
```

- Windows 下如需视频缩略图功能，请确保已安装 [ffmpeg](https://ffmpeg.org/) 并配置到 PATH。

---

## 命令行用法

### 1. 去重模式

```bash
python main.py <待去重文件夹> --report <报告输出路径> [--hash md5|sha1] [--execute]
```
- 默认只预演（不做实际写入），加 `--execute` 才会真正操作文件。
- 示例：
  ```bash
  python main.py D:/photos --report report.txt --hash md5 --execute
  ```

### 2. 增补模式

```bash
python main.py <主文件夹> <补充文件夹> --report <报告输出路径> [--hash md5|sha1] [--execute]
```
- 示例：
  ```bash
  python main.py D:/photos D:/phone_backup --report supplement_report.txt --execute
  ```

### 3. 帮助

```bash
python main.py --help
```

---

## 图形界面（GUI）用法

### 启动 GUI

```bash
python dedup_gui.py
```

### 主要功能
- 生成去重/增补报告（支持多线程、进度条、日志）
- 加载报告，分组浏览重复图片/视频，缩略图预览
- 勾选保留/删除，支持批量选择策略（保留第一个/最新/最大）
- 一键批量删除、批量移动增补文件
- 损坏文件集中管理
- 日志区自动显示详细统计信息（总数、可删除/增补数、节省空间、损坏数、耗时等）

---

## 常见问题

- **Q: 运行时报 `ModuleNotFoundError: No module named 'PIL'`？**
  - A: 请先运行 `pip install pillow`。
- **Q: 视频缩略图无法显示？**
  - A: 请确保已安装 ffmpeg 并配置到系统 PATH。
- **Q: 多进程报权限错误（Windows）？**
  - A: 建议用管理员权限运行，或避免在系统受限目录操作。
- **Q: 损坏文件如何处理？**
  - A: 工具会自动检测疑似损坏文件并集中到“损坏文件”子文件夹。

---

## 目录结构

```
photo-album-tool/
  |-- main.py           # 命令行入口
  |-- compare.py        # 核心去重/增补逻辑
  |-- dedup_gui.py      # 图形界面入口
  |-- README.md         # 项目说明
  |-- requirements.txt  # 依赖（如有）
  |-- ...
```

---

## 贡献与反馈

如有建议、Bug 反馈或功能需求，欢迎提 Issue 或 PR！