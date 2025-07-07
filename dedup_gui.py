import sys
import os
import subprocess

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget, QListWidgetItem,
    QFileDialog, QCheckBox, QMessageBox, QScrollArea, QGroupBox, QDialog, QComboBox, QTabWidget, QLineEdit, QFrame,
    QTextEdit, QProgressBar, QInputDialog, QMenu, QSplitter
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPalette, QColor
from PIL import Image, UnidentifiedImageError
Image.MAX_IMAGE_PIXELS = 1400000000  # 例如允许4.2亿像素图片

import re
import threading
import traceback
import importlib.util
import tempfile
import time
import logging

# 在文件开头添加全局变量
FFMPEG_AVAILABLE = None

# 添加logger定义
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('photo_tool.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)  # 新增logger定义

from compare import find_duplicates, supplement_images #, collect_images, collect_videos 这两个函数包含多进程代码，在GUI环境中会导致pickle错误


def check_ffmpeg_available():
    """检查系统是否安装了ffmpeg"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL, 
            timeout=5,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False
    

THUMBNAIL_DIR = '.thumbnails'
os.makedirs(THUMBNAIL_DIR, exist_ok=True)
# 动态导入 compare.py 的 find_duplicates
spec = importlib.util.spec_from_file_location("compare", "compare.py")
compare = importlib.util.module_from_spec(spec)
sys.modules["compare"] = compare
spec.loader.exec_module(compare)

def get_video_thumbnail(video_path, width=240, height=180):
    """
    改进的视频缩略图生成，包含ffmpeg检查
    """
    global FFMPEG_AVAILABLE
    
    # 懒加载检查ffmpeg
    if FFMPEG_AVAILABLE is None:
        FFMPEG_AVAILABLE = check_ffmpeg_available()
        if not FFMPEG_AVAILABLE:
            logger.warning("未检测到ffmpeg，视频缩略图功能将不可用")
    
    # 如果ffmpeg不可用，返回空的QPixmap
    if not FFMPEG_AVAILABLE:
        return QPixmap()
    
    if not os.path.exists(video_path):
        return QPixmap()
    
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        thumb_path = tmp.name
    
    try:
        cmd = [
            'ffmpeg', '-y', '-i', video_path, '-ss', '00:00:01.000', '-vframes', '1',
            '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease', 
            thumb_path
        ]
        
        result = subprocess.run(
            cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL, 
            timeout=10,  # 添加10秒超时
            check=True
        )
        
        if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            pix = QPixmap(thumb_path)
        else:
            pix = QPixmap()
            
    except subprocess.TimeoutExpired:
        logger.warning(f"生成视频缩略图超时: {video_path}")
        pix = QPixmap()
    except subprocess.CalledProcessError:
        logger.warning(f"ffmpeg处理视频失败: {video_path}")
        pix = QPixmap()
    except Exception as e:
        logger.warning(f"生成视频缩略图时发生错误: {video_path}, 错误: {e}")
        pix = QPixmap()
    finally:
        # 确保临时文件被删除
        try:
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
        except OSError:
            pass
    
    return pix

class ReportThread(QThread):
    log_signal = pyqtSignal(str)
    done_signal = pyqtSignal(str)
    data_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)

    def __init__(self, folder, report_path, hash_method, lang):
        super().__init__()
        self.folder = folder
        self.report_path = report_path
        self.hash_method = hash_method
        self.lang = lang
        self._is_cancelled = False

    def run(self):
        try:
            import compare
            compare.LANG = self.lang
            self.log_signal.emit(tr('start_dedup'))
            
            def log_cb(msg):
                if not self._is_cancelled:
                    self.log_signal.emit(msg)
            
            def prog_cb(val):
                if not self._is_cancelled:
                    self.progress = val
            
            result = compare.find_duplicates(
                self.folder, 
                self.report_path, 
                self.hash_method, 
                dry_run=False, 
                log_callback=log_cb, 
                progress_callback=prog_cb
            )
            
            if not self._is_cancelled:
                self.data_signal.emit(result)
                self.log_signal.emit(tr('dedup_done', path=self.report_path))
                self.done_signal.emit(self.report_path)
                
        except KeyboardInterrupt:
            self.log_signal.emit("Task canceled by user")
        except Exception as e:
            tb = traceback.format_exc()
            error_msg = f"Task failed: {str(e)}"
            self.log_signal.emit(error_msg)
            self.error_signal.emit(f"{error_msg}\n\nDetailed Error:\n{tb}")
    
    def cancel(self):
        self._is_cancelled = True

class SupplementReportThread(QThread):
    log_signal = pyqtSignal(str)
    done_signal = pyqtSignal(str)
    data_signal = pyqtSignal(object)
    def __init__(self, main_folder, supplement_folder, report_path, hash_method, lang, dry_run=True):
        super().__init__()
        self.main_folder = main_folder
        self.supplement_folder = supplement_folder
        self.report_path = report_path
        self.hash_method = hash_method
        self.dry_run = dry_run
        self.lang = lang
    def run(self):
        try:
            import compare
            compare.LANG = self.lang
            self.log_signal.emit(tr('start_supp'))
            def log_cb(msg):
                self.log_signal.emit(msg)
            def prog_cb(val):
                self.progress = val
            result = compare.supplement_images(self.main_folder, self.supplement_folder, self.report_path, self.hash_method, dry_run=self.dry_run, log_callback=log_cb, progress_callback=prog_cb)
            self.data_signal.emit(result)
            self.log_signal.emit(tr('supp_done', path=self.report_path))
            self.done_signal.emit(self.report_path)
        except Exception as e:
            tb = traceback.format_exc()
            self.log_signal.emit(tr('error', err=e, tb=tb))
class ClickableLabel(QLabel):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet('border: 2px solid #aaa; border-radius: 6px; background: #f8f8f8;')
    def enterEvent(self, event):
        self.setStyleSheet('border: 2px solid #0078d7; border-radius: 6px; background: #f0f8ff;')
    def leaveEvent(self, event):
        self.setStyleSheet('border: 2px solid #aaa; border-radius: 6px; background: #f8f8f8;')
    def mousePressEvent(self, event):
        if os.path.exists(self.path):
            dlg = QDialog(self)
            dlg.setWindowTitle(os.path.basename(self.path))
            vbox = QVBoxLayout(dlg)
            img_label = QLabel()
            pix = QPixmap(self.path)
            if not pix.isNull():
                # 限制最大显示尺寸
                screen = QApplication.primaryScreen().availableGeometry()
                maxw, maxh = int(screen.width() * 0.8), int(screen.height() * 0.8)
                pix = pix.scaled(maxw, maxh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                img_label.setPixmap(pix)
            else:
                img_label.setText('无法加载图片')
            vbox.addWidget(img_label)
            dlg.resize( min(pix.width()+40, 1200), min(pix.height()+80, 900) )
            dlg.exec_()

class DedupGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('照片去重报告处理工具')
        self.resize(1100, 750)
        self.report_path = None
        self.img_groups = []
        self.vid_groups = []
        self.current_img_group = 0
        self.current_vid_group = 0
        self.img_checked = {}
        self.vid_checked = {}
        self.supplement_img_files = []
        self.supplement_vid_files = []
        self.supplement_img_target_dir = None
        self.supplement_vid_target_dir = None
        self._last_report_start_time = None
        self._last_report_end_time = None
        self._last_supp_main_count = None
        self._last_supp_supp_count = None
        self._last_supp_corrupt_img = 0
        self._last_supp_corrupt_vid = 0
        self.corrupt_img_files = []
        self._last_dedup_result = None
        self._last_supp_result = None
        
        # 添加新的实例变量
        self.img_group_details = {}
        self.vid_group_details = {}
        self.supplement_img_details = []
        self.supplement_vid_details = []
        self.skipped_img_details = []
        self.skipped_vid_details = []
        
        # 新增：存储文件夹信息的变量
        self.folder_info_messages = []
        
        self.init_ui()

    def init_ui(self):
        # 使用QSplitter来实现可调整的布局
        main_layout = QVBoxLayout(self)
        
        # 语言切换区
        lang_layout = QHBoxLayout()
        self.lang_label = QLabel(tr('choose_language'))
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(['中文', 'English'])
        self.combo_lang.setCurrentIndex(0 if LANG == 'zh' else 1)
        self.combo_lang.currentIndexChanged.connect(self.on_language_changed)
        lang_layout.addWidget(self.lang_label)
        lang_layout.addWidget(self.combo_lang)
        lang_layout.addStretch()
        main_layout.addLayout(lang_layout)
        
        # 顶部操作区
        btn_layout = QHBoxLayout()
        self.btn_generate_report = QPushButton(tr('generate_report'))
        self.btn_generate_report.clicked.connect(self.generate_report_dialog)
        self.btn_generate_supp_report = QPushButton(tr('generate_supp_report'))
        self.btn_generate_supp_report.clicked.connect(self.generate_supp_report_dialog)
        self.btn_load = QPushButton(tr('load_report'))
        self.btn_load.clicked.connect(self.load_report)
        self.btn_delete = QPushButton(tr('delete'))
        self.btn_delete.clicked.connect(self.delete_files)
        self.btn_select_all = QPushButton(tr('select_all'))
        self.btn_select_all.clicked.connect(self.select_all_groups)
        self.btn_unselect_all = QPushButton(tr('unselect_all'))
        self.btn_unselect_all.clicked.connect(self.unselect_all_groups)
        self.combo_strategy = QComboBox()
        self.combo_strategy.addItems([tr('keep_first'), tr('keep_newest'), tr('keep_largest')])
        self.combo_strategy.currentIndexChanged.connect(self.apply_strategy)
        self.batch_select_label = QLabel(tr('batch_select'))
        btn_layout.addWidget(self.btn_generate_report)
        btn_layout.addWidget(self.btn_generate_supp_report)
        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_unselect_all)
        btn_layout.addWidget(self.batch_select_label)
        btn_layout.addWidget(self.combo_strategy)
        main_layout.addLayout(btn_layout)

        # 创建主要的可调整布局分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 上部分：主要内容区域（TabWidget + 进度条）
        upper_widget = QWidget()
        upper_layout = QVBoxLayout(upper_widget)
        
        # 进度条
        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(0)
        self.progress.hide()
        upper_layout.addWidget(self.progress)
        
        # TabWidget
        self.tabs = QTabWidget()
        # 图片Tab
        img_tab = QWidget()
        img_layout = QHBoxLayout(img_tab)
        self.group_list = QListWidget()
        self.group_list.currentRowChanged.connect(self.on_group_changed)
        img_layout.addWidget(self.group_list, 2)
        right = QVBoxLayout()
        # 本组全选/全不选
        group_btn_layout = QHBoxLayout()
        self.btn_group_select_all = QPushButton(tr('select_all'))
        self.btn_group_select_all.clicked.connect(self.select_all_current_group)
        self.btn_group_unselect_all = QPushButton(tr('unselect_all'))
        self.btn_group_unselect_all.clicked.connect(self.unselect_all_current_group)
        group_btn_layout.addWidget(self.btn_group_select_all)
        group_btn_layout.addWidget(self.btn_group_unselect_all)
        right.addLayout(group_btn_layout)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.img_group = QGroupBox(tr('img_tab'))
        self.img_layout = QVBoxLayout()
        self.img_group.setLayout(self.img_layout)
        self.scroll.setWidget(self.img_group)
        right.addWidget(self.scroll, 8)
        img_layout.addLayout(right, 8)
        self.tabs.addTab(img_tab, tr('img_tab'))
        
        # 视频Tab
        vid_tab = QWidget()
        vid_layout = QHBoxLayout(vid_tab)
        self.vid_group_list = QListWidget()
        self.vid_group_list.currentRowChanged.connect(self.on_vid_group_changed)
        vid_layout.addWidget(self.vid_group_list, 2)
        vid_right = QVBoxLayout()
        # 本组全选/全不选
        vid_group_btn_layout = QHBoxLayout()
        self.btn_vid_group_select_all = QPushButton(tr('select_all'))
        self.btn_vid_group_select_all.clicked.connect(self.select_all_current_vid_group)
        self.btn_vid_group_unselect_all = QPushButton(tr('unselect_all'))
        self.btn_vid_group_unselect_all.clicked.connect(self.unselect_all_current_vid_group)
        vid_group_btn_layout.addWidget(self.btn_vid_group_select_all)
        vid_group_btn_layout.addWidget(self.btn_vid_group_unselect_all)
        vid_right.addLayout(vid_group_btn_layout)
        self.vid_scroll = QScrollArea()
        self.vid_scroll.setWidgetResizable(True)
        self.vid_group_box = QGroupBox(tr('vid_tab'))
        self.vid_layout = QVBoxLayout()
        self.vid_group_box.setLayout(self.vid_layout)
        self.vid_scroll.setWidget(self.vid_group_box)
        vid_right.addWidget(self.vid_scroll, 8)
        vid_layout.addLayout(vid_right, 8)
        self.tabs.addTab(vid_tab, tr('vid_tab'))
        
        # 增补结果Tab
        self.supplement_tab = QWidget()
        supp_layout = QVBoxLayout(self.supplement_tab)
        self.supp_img_label = QLabel()
        supp_layout.addWidget(self.supp_img_label)
        self.supplement_img_list = QListWidget()
        supp_layout.addWidget(self.supplement_img_list, 4)
        self.btn_move_img_supp = QPushButton(tr('move_supp_img'))
        self.btn_move_img_supp.clicked.connect(lambda: self.move_supplement_files('img'))
        supp_layout.addWidget(self.btn_move_img_supp)
        self.supp_vid_label = QLabel()
        supp_layout.addWidget(self.supp_vid_label)
        self.supplement_vid_list = QListWidget()
        supp_layout.addWidget(self.supplement_vid_list, 2)
        self.btn_move_vid_supp = QPushButton(tr('move_supp_vid'))
        self.btn_move_vid_supp.clicked.connect(lambda: self.move_supplement_files('vid'))
        supp_layout.addWidget(self.btn_move_vid_supp)
        self.tabs.addTab(self.supplement_tab, tr('supp_tab'))
        upper_layout.addWidget(self.tabs)
        
        # 下部分：日志输出区
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        # 移除固定高度限制，让用户可以通过拖动调整
        # self.log_box.setMaximumHeight(120)  # 删除这行
        
        # 将上下部分添加到分割器
        splitter.addWidget(upper_widget)
        splitter.addWidget(self.log_box)
        
        # 设置分割器的初始比例 (上部分占80%，日志区占20%)
        splitter.setSizes([600, 150])
        splitter.setStretchFactor(0, 1)  # 上部分可伸缩
        splitter.setStretchFactor(1, 0)  # 日志区固定比例
        
        # 将分割器添加到主布局
        main_layout.addWidget(splitter)
        
        # 检查系统依赖
        self.check_system_dependencies()
           
        import compare
        compare.LANG = LANG

    def check_system_dependencies(self):
        if not check_ffmpeg_available():
            print("⚠️ ffmpeg 不可用，视频缩略图功能受限")
            self.log_box.append("⚠️ 警告: 未检测到ffmpeg，视频缩略图功能将不可用")
            self.log_box.append("   建议安装ffmpeg以获得完整功能")
        else:
           print("✅ ffmpeg 可用，视频功能正常")
 
    def apply_strategy(self):
        strategy = self.combo_strategy.currentText()
        for i, group in enumerate(self.img_groups):
            if not group:
                self.img_checked[i] = set()
                continue
            if strategy == tr('keep_first'):
                self.img_checked[i] = {group[0]}
            elif strategy == tr('keep_newest'):
                newest = max(group, key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0)
                self.img_checked[i] = {newest}
            elif strategy == tr('keep_largest'):
                largest = max(group, key=lambda p: os.path.getsize(p) if os.path.exists(p) else 0)
                self.img_checked[i] = {largest}
        self.show_group(self.current_img_group)

    def load_report(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('select_report'), '', tr('text_files'))
        if not path:
            return
        # 加载报告时也清除之前的结果
        self.clear_interface()
        
        self.report_path = path
        # 检查是否为增补报告
        with open(path, 'r', encoding='utf-8') as f:
            first_lines = [f.readline() for _ in range(5)]
        if any(tr('supplement_report') in line for line in first_lines):
            self.show_supplement_report(path)
            self.tabs.setCurrentWidget(self.supplement_tab)
            return
        # 否则为去重报告
        self.img_groups, self.vid_groups = self.parse_report(path)
        self.img_checked = {i: {group[0]} if group else set() for i, group in enumerate(self.img_groups)}
        self.vid_checked = {i: {group[0]} if group else set() for i, group in enumerate(self.vid_groups)}
        self.group_list.clear()
        for i, group in enumerate(self.img_groups):
            self.group_list.addItem(f"{tr('group')}{i+1} ({len(group)})")
        if self.img_groups:
            self.group_list.setCurrentRow(0)
        self.vid_group_list.clear()
        for i, group in enumerate(self.vid_groups):
            self.vid_group_list.addItem(f"{tr('video_group')}{i+1} ({len(group)})")
        if self.vid_groups:
            self.vid_group_list.setCurrentRow(0)
        self.combo_strategy.setCurrentIndex(0)
        self.tabs.setCurrentIndex(0)

    def parse_report(self, path):
        img_groups = []
        vid_groups = []
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        group = []
        mode = None  # 'img' or 'vid'
        
        for line in lines:
            l = line.strip()
            
            # 匹配图片重复组的开始
            if re.match(r'重复图片组\d+|Duplicate Image Group \d+', l):
                if group and mode == 'img':
                    img_groups.append(group)
                if group and mode == 'vid':
                    vid_groups.append(group)
                group = []
                mode = 'img'
                continue
                
            # 匹配视频重复组的开始  
            elif re.match(r'视频重复组\d+|Duplicate Video Group \d+', l):
                if group and mode == 'img':
                    img_groups.append(group)
                if group and mode == 'vid':
                    vid_groups.append(group)
                group = []
                mode = 'vid'
                continue
                
            # 跳过标题行、统计行、空行等
            elif (l.startswith('去重图片报告') or l.startswith('Deduplication Report') or
                l.startswith('共检测到') or l.startswith('duplicate') or
                l.startswith('未发现') or l.startswith('No duplicate') or
                not l):
                continue
                
            # 处理文件路径行（以4个空格开头）on_report_done 
            elif line.startswith('    ') and mode:
                file_path = l
                if file_path:  # 确保不是空行
                    group.append(file_path)
        
        # 处理最后一组
        if group:
            if mode == 'img':
                img_groups.append(group)
            elif mode == 'vid':
                vid_groups.append(group)
        
        return img_groups, vid_groups

    def on_group_changed(self, idx):
        if idx < 0 or idx >= len(self.img_groups):
            return
        self.current_img_group = idx
        self.show_group(idx)

    def show_group(self, idx):
        self.corrupt_img_files = []
        for i in reversed(range(self.img_layout.count())):
            w = self.img_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        
        group = self.img_groups[idx]
        for path in group:
            row = QHBoxLayout()
            label = ClickableLabel(path)
            is_corrupt = False
            
            if os.path.exists(path):
                # 使用改进的图片验证方法
                try:
                    with Image.open(path) as img:
                        img.load()  # 使用load()代替verify()
                        # 验证成功，显示缩略图
                        pix = QPixmap(path)
                        if not pix.isNull():
                            pix = pix.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            label.setPixmap(pix)
                        else:
                            label.setText(tr('no_thumbnail'))
                except (IOError, OSError, UnidentifiedImageError):
                    is_corrupt = True
                    self.corrupt_img_files.append(path)
                    label.setText(tr('corrupted'))
                    label.setStyleSheet('color: red; font-weight: bold;')
                except Exception as e:
                    logger.warning(f"验证图片时发生错误: {path}, 错误: {e}")
                    is_corrupt = True
                    self.corrupt_img_files.append(path)
                    label.setText(tr('corrupted'))
                    label.setStyleSheet('color: red; font-weight: bold;')
            else:
                label.setText(tr('file_not_found'))
            row.addWidget(label)
            frame = QFrame()
            frame.setFrameShape(QFrame.VLine)
            frame.setFrameShadow(QFrame.Sunken)
            row.addWidget(frame)
            path_label = QLabel(path)
            path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row.addWidget(path_label, 2)
            cb = QCheckBox(tr('keep'))
            cb.setChecked(path in self.img_checked[idx])
            cb.stateChanged.connect(lambda state, p=path: self.on_check_changed(idx, p, state))
            row.addWidget(cb)
            row_widget = QWidget()
            row_widget.setLayout(row)
            if is_corrupt:
                row_widget.setStyleSheet('background: #ffeaea; border: 1px solid #ff8888; border-radius: 8px;')
            else:
                row_widget.setStyleSheet('background: #f9f9f9; margin-bottom: 6px; border-radius: 8px;')
            self.img_layout.addWidget(row_widget)
        # 更新统计区损坏图片数
        self.log_dedup_stats()

    def on_check_changed(self, group_idx, path, state):
        if state == Qt.Checked:
            self.img_checked[group_idx].add(path)
        else:
            self.img_checked[group_idx].discard(path)

    # 视频Tab相关
    def on_vid_group_changed(self, idx):
        if idx < 0 or idx >= len(self.vid_groups):
            return
        self.current_vid_group = idx
        self.show_vid_group(idx)

    def show_vid_group(self, idx):
        for i in reversed(range(self.vid_layout.count())):
            w = self.vid_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        group = self.vid_groups[idx]
        for path in group:
            row = QHBoxLayout()
            # 视频缩略图
            thumb = get_video_thumbnail(path)
            thumb_label = QLabel()
            if thumb and not thumb.isNull():
                pix = thumb
                pix = pix.scaled(160, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                thumb_label.setPixmap(pix)
                thumb_label.setCursor(Qt.PointingHandCursor)
                def show_big_thumb(p=path):
                    dlg = QDialog(self)
                    dlg.setWindowTitle(os.path.basename(p))
                    vbox = QVBoxLayout(dlg)
                    img_label = QLabel()
                    # 生成大尺寸缩略图
                    big_thumb = get_video_thumbnail(p, width=800, height=600)
                    if big_thumb and not big_thumb.isNull():
                        screen = QApplication.primaryScreen().availableGeometry()
                        maxw, maxh = int(screen.width() * 0.8), int(screen.height() * 0.8)
                        big_thumb = big_thumb.scaled(maxw, maxh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        img_label.setPixmap(big_thumb)
                    else:
                        img_label.setText('无法加载缩略图')
                    vbox.addWidget(img_label)
                    dlg.resize( min(big_thumb.width()+40 if big_thumb else 600, 1200), min(big_thumb.height()+80 if big_thumb else 400, 900) )
                    dlg.exec_()
                thumb_label.mousePressEvent = lambda e, f=show_big_thumb: f()
            else:
                thumb_label.setText('无缩略图')
            row.addWidget(thumb_label)
            # 只显示文件名、路径、大小
            name = os.path.basename(path)
            size = os.path.getsize(path) if os.path.exists(path) else 0
            name_label = QLabel(name)
            row.addWidget(name_label)
            size_label = QLabel(f'{size/1024/1024:.2f} MB')
            row.addWidget(size_label)
            path_label = QLabel(path)
            path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row.addWidget(path_label, 2)
            cb = QCheckBox(tr('keep'))
            cb.setChecked(path in self.vid_checked[idx])
            cb.stateChanged.connect(lambda state, p=path: self.on_vid_check_changed(idx, p, state))
            row.addWidget(cb)
            row_widget = QWidget()
            row_widget.setLayout(row)
            row_widget.setStyleSheet('background: #f9f9f9; margin-bottom: 6px; border-radius: 8px;')
            self.vid_layout.addWidget(row_widget)

    def on_vid_check_changed(self, group_idx, path, state):
        if state == Qt.Checked:
            self.vid_checked[group_idx].add(path)
        else:
            self.vid_checked[group_idx].discard(path)

    def select_all_groups(self):
        tab = self.tabs.currentIndex()
        if tab == 0:
            if not self.img_groups:
                return
            for i, group in enumerate(self.img_groups):
                self.img_checked[i] = set(group)
            self.show_group(self.current_img_group)
        else:
            if not self.vid_groups:
                return
            for i, group in enumerate(self.vid_groups):
                self.vid_checked[i] = set(group)
            self.show_vid_group(self.current_vid_group)

    def unselect_all_groups(self):
        tab = self.tabs.currentIndex()
        if tab == 0:
            if not self.img_groups:
                return
            for i in self.img_checked:
                self.img_checked[i] = set()
            self.show_group(self.current_img_group)
        else:
            if not self.vid_groups:
                return
            for i in self.vid_checked:
                self.vid_checked[i] = set()
            self.show_vid_group(self.current_vid_group)

    def select_all_current_group(self):
        idx = self.current_img_group
        if not self.img_groups or not (0 <= idx < len(self.img_groups)):
            return
        self.img_checked[idx] = set(self.img_groups[idx])
        self.show_group(idx)

    def unselect_all_current_group(self):
        idx = self.current_img_group
        if not self.img_groups or not (0 <= idx < len(self.img_groups)):
            return
        self.img_checked[idx] = set()
        self.show_group(idx)

    def select_all_current_vid_group(self):
        idx = self.current_vid_group
        if not self.vid_groups or not (0 <= idx < len(self.vid_groups)):
            return
        self.vid_checked[idx] = set(self.vid_groups[idx])
        self.show_vid_group(idx)

    def unselect_all_current_vid_group(self):
        idx = self.current_vid_group
        if not self.vid_groups or not (0 <= idx < len(self.vid_groups)):
            return
        self.vid_checked[idx] = set()
        self.show_vid_group(idx)

    def delete_files(self):
        delete_list = []
        for idx, group in enumerate(self.img_groups):
            for path in group:
                if path not in self.img_checked[idx]:
                    delete_list.append(path)
        for idx, group in enumerate(self.vid_groups):
            for path in group:
                if path not in self.vid_checked[idx]:
                    delete_list.append(path)
        if not delete_list:
            QMessageBox.information(self, tr('delete'), tr('no_files_to_delete'))
            return
        reply = QMessageBox.question(self, tr('confirm_delete'), f'{tr("confirm_delete_msg")} {len(delete_list)} {tr("files")}?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        failed = []
        for path in delete_list:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                failed.append((path, str(e)))
        if not failed:
            QMessageBox.information(self, tr('delete_complete'), f'{tr("delete_complete_msg")} {len(delete_list)} {tr("files")}.')
        else:
            QMessageBox.warning(self, tr('partial_delete_failed'), f'{tr("partial_delete_failed_msg")} {len(failed)} {tr("files")} {tr("delete_failed")}.\\n' + '\\n'.join(f[0] for f in failed))
        self.load_report()

    def show_supplement_report(self, path, from_data=False):
        if from_data and self._last_supp_result:
            self._update_supplement_ui()
            return
        # 兼容老报告文件
        self.corrupt_img_files = []
        self.supplement_img_list.clear()
        self.supplement_vid_list.clear()
        self.supplement_img_files = []
        self.supplement_vid_files = []
        self.supplement_img_target_dir = None
        self.supplement_vid_target_dir = None
        self._last_supp_corrupt_img = 0
        self._last_supp_corrupt_vid = 0
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        mode = None
        for line in lines:
            l = line.rstrip('\\r\\n')
            # 宽松匹配"成功增补...图片到:"或英文
            if re.search(r'(成功增补|Supplemented)\\s*\\d+.*(图片|images).*到:|to:', l):
                mode = 'img'
                m = re.search(r'(到:|to:)\\s*(.+)$', l)
                if m:
                    self.supplement_img_target_dir = m.group(2).strip()
                continue
            if re.search(r'(成功增补|Supplemented)\\s*\\d+.*(视频|videos).*到:|to:', l):
                mode = 'vid'
                m = re.search(r'(到:|to:)\\s*(.+)$', l)
                if m:
                    self.supplement_vid_target_dir = m.group(2).strip()
                continue
            if l.startswith(tr('already_exists')) or l.strip() == '' or l.startswith(tr('dry_run')) or l.startswith(tr('supp_img_report')):
                mode = None
                continue
            if tr('corrupted_files') in l and mode == 'img':
                self._last_supp_corrupt_img += 1
                continue
            if tr('corrupted_files') in l and mode == 'vid':
                self._last_supp_corrupt_vid += 1
                continue
            if re.search(r'[A-Za-z]:[\\\\//]', l):
                if mode == 'img':
                    self.supplement_img_files.append(l.strip())
                elif mode == 'vid':
                    self.supplement_vid_files.append(l.strip())
        # 图片缩略图列表
        for f in self.supplement_img_files:
            item_widget = QWidget()
            hbox = QHBoxLayout(item_widget)
            is_corrupt = False
            try:
                with Image.open(f) as im:
                    im.verify()
                thumb = QPixmap(f)
            except Exception:
                is_corrupt = True
                self.corrupt_img_files.append(f)
                thumb = None
            if thumb and not thumb.isNull():
                pix = thumb.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                thumb_label = QLabel()
                thumb_label.setPixmap(pix)
                thumb_label.setCursor(Qt.PointingHandCursor)
                def show_big_thumb(p=f):
                    dlg = QDialog(self)
                    dlg.setWindowTitle(os.path.basename(p))
                    vbox = QVBoxLayout(dlg)
                    img_label = QLabel()
                    pix2 = QPixmap(p)
                    if not pix2.isNull():
                        screen = QApplication.primaryScreen().availableGeometry()
                        maxw, maxh = int(screen.width() * 0.8), int(screen.height() * 0.8)
                        pix2 = pix2.scaled(maxw, maxh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        img_label.setPixmap(pix2)
                    else:
                        img_label.setText(tr('no_thumbnail'))
                    vbox.addWidget(img_label)
                    dlg.resize( min(pix2.width()+40 if pix2 else 600, 1200), min(pix2.height()+80 if pix2 else 400, 900) )
                    dlg.exec_()
                thumb_label.mousePressEvent = lambda e, f=show_big_thumb: f()
                hbox.addWidget(thumb_label)
            else:
                l = QLabel(tr('corrupted')) if is_corrupt else QLabel(tr('no_thumbnail'))
                l.setStyleSheet('color: red; font-weight: bold;' if is_corrupt else '')
                hbox.addWidget(l)
            hbox.addWidget(QLabel(f))
            item_widget.setLayout(hbox)
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            if is_corrupt:
                list_item.setBackground(Qt.red)
            self.supplement_img_list.addItem(list_item)
            self.supplement_img_list.setItemWidget(list_item, item_widget)
        # 视频缩略图列表
        self.supplement_vid_list.clear()
        for f in self.supplement_vid_files:
            item_widget = QWidget()
            hbox = QHBoxLayout(item_widget)
            thumb = get_video_thumbnail(f)
            if thumb and not thumb.isNull():
                pix = thumb.scaled(80, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                thumb_label = QLabel()
                thumb_label.setPixmap(pix)
                thumb_label.setCursor(Qt.PointingHandCursor)
                def show_big_thumb(p=f):
                    dlg = QDialog(self)
                    dlg.setWindowTitle(os.path.basename(p))
                    vbox = QVBoxLayout(dlg)
                    img_label = QLabel()
                    big_thumb = get_video_thumbnail(p, width=800, height=600)
                    if big_thumb and not big_thumb.isNull():
                        screen = QApplication.primaryScreen().availableGeometry()
                        maxw, maxh = int(screen.width() * 0.8), int(screen.height() * 0.8)
                        big_thumb = big_thumb.scaled(maxw, maxh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        img_label.setPixmap(big_thumb)
                    else:
                        img_label.setText('无法加载缩略图')
                    vbox.addWidget(img_label)
                    dlg.resize( min(big_thumb.width()+40 if big_thumb else 600, 1200), min(big_thumb.height()+80 if big_thumb else 400, 900) )
                    dlg.exec_()
                thumb_label.mousePressEvent = lambda e, f=show_big_thumb: f()
                hbox.addWidget(thumb_label)
            else:
                hbox.addWidget(QLabel(tr('no_thumbnail')))
            hbox.addWidget(QLabel(f))
            item_widget.setLayout(hbox)
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            self.supplement_vid_list.addItem(list_item)
            self.supplement_vid_list.setItemWidget(list_item, item_widget)
        # 动态刷新统计标签
        self.supp_img_label.setText(tr('supp_img', count=len(self.supplement_img_files)) + ' 张')
        self.supp_vid_label.setText(tr('supp_vid', count=len(self.supplement_vid_files)) + ' 个')
        # 更新统计区损坏图片数
        self.log_supplement_stats()

    def move_supplement_files(self, which):
        if which == 'img':
            files = self.supplement_img_files
            label = tr('img')
            target_dir = self.supplement_img_target_dir
        else:
            files = self.supplement_vid_files
            label = tr('vid')
            target_dir = self.supplement_vid_target_dir
        if not files:
            QMessageBox.information(self, tr('batch_move'), f'{tr("no_files_to_move")} {label}.')
            return
        if not target_dir:
            QMessageBox.warning(self, tr('batch_move'), f'{tr("target_dir_not_found")} {label}.')
            return
        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.warning(self, tr('batch_move'), f'{tr("target_dir_create_fail")}\\n{target_dir}\\n{e}')
                return
        # 新增：损坏文件集中到一个子文件夹
        corrupt_dir = os.path.join(target_dir, tr('corrupted_files'))
        if not os.path.exists(corrupt_dir):
            os.makedirs(corrupt_dir, exist_ok=True)
        failed = []
        corrupt = []
        for f in files:
            try:
                if os.path.exists(f):
                    is_corrupt = False
                    if which == 'img':
                        #from PIL import Image
                        #Image.MAX_IMAGE_PIXELS = 200000000  # 例如允许2亿像素图片
                        try:
                            with Image.open(f) as im:
                                im.verify()
                        except Exception:
                            is_corrupt = True
                    elif which == 'vid':
                        # 简单判断：文件过小或ffmpeg无法读取
                        try:
                            import subprocess
                            result = subprocess.run([
                                'ffmpeg', '-v', 'error', '-i', f, '-f', 'null', '-'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                            if result.returncode != 0:
                                is_corrupt = True
                        except Exception:
                            is_corrupt = True
                    base = os.path.basename(f)
                    if is_corrupt:
                        target = os.path.join(corrupt_dir, base)
                        corrupt.append(f)
                    else:
                        target = os.path.join(target_dir, base)
                    count = 1
                    while os.path.exists(target):
                        name, ext = os.path.splitext(base)
                        target = os.path.join(os.path.dirname(target), f"{name}_{count}{ext}")
                        count += 1
                    os.rename(f, target)
            except Exception as e:
                failed.append((f, str(e)))
        msg = f'{tr("move_success")} {len(files)-len(failed)} {label} {tr("to")}\\n{target_dir}'
        if corrupt:
            msg += f'\\n{tr("move_corrupt")} {len(corrupt)} {tr("corrupted_files")} {tr("to")}: {corrupt_dir}'
        if not failed:
            QMessageBox.information(self, tr('batch_move'), msg)
        else:
            QMessageBox.warning(self, tr('partial_move_failed'), f'{tr("partial_move_failed_msg")} {len(failed)} {label} {tr("move_failed")}.\\n' + '\\n'.join(f[0] for f in failed))

    def clear_interface(self): 
        """清除界面上所有任务结果显示"""
        # 清除数据变量
        self.img_groups = []
        self.vid_groups = []
        self.current_img_group = 0
        self.current_vid_group = 0
        self.img_checked = {}
        self.vid_checked = {}
        self.supplement_img_files = []
        self.supplement_vid_files = []
        self.supplement_img_target_dir = None
        self.supplement_vid_target_dir = None
        self.corrupt_img_files = []
        self._last_dedup_result = None
        self._last_supp_result = None
        
        # 清除详细信息数据
        self.img_group_details = {}
        self.vid_group_details = {}
        self.supplement_img_details = []
        self.supplement_vid_details = []
        self.skipped_img_details = []
        self.skipped_vid_details = []
        
        # 清除统计相关变量
        self._last_supp_main_count = None
        self._last_supp_supp_count = None
        self._last_supp_corrupt_img = 0
        self._last_supp_corrupt_vid = 0
        
        # 清除图片重复组列表
        self.group_list.clear()
        
        # 清除视频重复组列表
        self.vid_group_list.clear()
        
        # 清除图片显示区域
        for i in reversed(range(self.img_layout.count())):
            w = self.img_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        
        # 清除视频显示区域
        for i in reversed(range(self.vid_layout.count())):
            w = self.vid_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        
        # 清除增补图片列表
        self.supplement_img_list.clear()
        
        # 清除增补视频列表
        self.supplement_vid_list.clear()
        
        # 重置增补标签
        self.supp_img_label.setText(tr('supp_img', count=0) + ' 张')
        self.supp_vid_label.setText(tr('supp_vid', count=0) + ' 个')
        
        # 重置策略选择
        self.combo_strategy.setCurrentIndex(0)
        
        # 切换到第一个页签
        self.tabs.setCurrentIndex(0)

    def generate_report_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, tr('select_target_folder'))
        if not folder:
            return
        
        # 清除界面上的上次任务结果
        self.clear_interface()

        # 清空之前的文件夹信息和日志
        self.folder_info_messages = []
        self.log_box.clear()
        
        # 添加并保存文件夹信息
        folder_msg = f'{tr("selected_target_folder")}: {folder}'
        self.folder_info_messages.append(folder_msg)
        self.log_box.append(folder_msg)
        
        report_path, _ = QFileDialog.getSaveFileName(self, tr('save_report_as'), 'report.txt', tr('text_files'))
        if not report_path:
            return
        hash_method = 'md5'
        self.progress.show()
        self._last_report_start_time = time.time()
        self.thread = ReportThread(folder, report_path, hash_method, LANG)
        self.thread.data_signal.connect(self.on_dedup_data)
        self.thread.done_signal.connect(self.on_report_done)
        self.thread.error_signal.connect(self.on_thread_error)  
        self.thread.start()

    def on_thread_error(self, error_msg):
        """处理线程执行错误"""
        self.progress.hide()
        QMessageBox.critical(self, "Execuation Error", error_msg)
        self.log_box.append("❌ Execuation Failed")
        
    def generate_supp_report_dialog(self):
        main_folder = QFileDialog.getExistingDirectory(self, tr('select_main_folder'))
        if not main_folder:
            return
        
        # 清除界面上的上次任务结果
        self.clear_interface()
        
        # 清空之前的文件夹信息和日志
        self.folder_info_messages = []
        self.log_box.clear()
        
        # 添加并保存主文件夹信息
        main_msg = f'{tr("selected_main_folder")}: {main_folder}'
        self.folder_info_messages.append(main_msg)
        self.log_box.append(main_msg)
        
        supplement_folder = QFileDialog.getExistingDirectory(self, tr('select_supp_folder'))
        if not supplement_folder:
            return
        
        # 添加并保存补充文件夹信息
        supp_msg = f'{tr("selected_supp_folder")}: {supplement_folder}'
        self.folder_info_messages.append(supp_msg)
        self.log_box.append(supp_msg)
        
        if os.path.abspath(main_folder) == os.path.abspath(supplement_folder):
            QMessageBox.warning(self, tr('param_error'), tr('main_supp_same'))
            return
        report_path, _ = QFileDialog.getSaveFileName(self, tr('save_supp_report_as'), 'supplement_report.txt', tr('text_files'))
        if not report_path:
            return
        hash_method = 'md5'
        self.progress.show()
        self._last_report_start_time = time.time()
        self.supp_thread = SupplementReportThread(main_folder, supplement_folder, report_path, hash_method, LANG, dry_run=True)
        self.supp_thread.data_signal.connect(self.on_supp_data)
        self.supp_thread.done_signal.connect(self.on_report_done)
        self.supp_thread.start()

    def on_report_done(self, report_path):
        self.progress.hide()
        self._last_report_end_time = time.time()
        self.log_box.append(f'{tr("report_done")}')
        # 注释掉这行，因为数据已经通过on_dedup_data处理了
        # self.load_report_path(report_path)

    def load_report_path(self, path):
        self.report_path = path
        # 检查是否为增补报告
        with open(path, 'r', encoding='utf-8') as f:
            first_lines = [f.readline() for _ in range(10)]
        if any(line.strip() in ('增补图片报告', 'Supplement Report') or '增补' in line or 'Supplement' in line for line in first_lines):
            # 解析主/补库扫描数
            main_count, supp_count = None, None
            for line in first_lines:
                if '主库共扫描' in line or 'Main scanned' in line:
                    m = re.search(r'(主库共扫描|Main scanned)\\D*(\\d+)', line)
                    if m:
                        main_count = int(m.group(2))
                if '补充库共扫描' in line or 'Supplement scanned' in line:
                    m = re.search(r'(补充库共扫描|Supplement scanned)\\D*(\\d+)', line)
                    if m:
                        supp_count = int(m.group(2))
            self._last_supp_main_count = main_count
            self._last_supp_supp_count = supp_count
            self.show_supplement_report(path)
            self.tabs.setCurrentWidget(self.supplement_tab)
            self.log_supplement_stats()
            return
        self.img_groups, self.vid_groups = self.parse_report(path)
        self.img_checked = {i: {group[0]} if group else set() for i, group in enumerate(self.img_groups)}
        self.vid_checked = {i: {group[0]} if group else set() for i, group in enumerate(self.vid_groups)}
        self.group_list.clear()
        for i, group in enumerate(self.img_groups):
            self.group_list.addItem(f"{tr('group')}{i+1} ({len(group)})")
        if self.img_groups:
            self.group_list.setCurrentRow(0)
        self.vid_group_list.clear()
        for i, group in enumerate(self.vid_groups):
            self.vid_group_list.addItem(f"{tr('video_group')}{i+1} ({len(group)})")
        if self.vid_groups:
            self.vid_group_list.setCurrentRow(0)
        self.combo_strategy.setCurrentIndex(0)
        self.tabs.setCurrentIndex(0)
        self.log_dedup_stats()

    def on_dedup_data(self, result):
        """处理去重数据"""
        self._last_dedup_result = result
        
        # 转换数据格式供GUI使用
        self.img_groups = []
        self.img_group_details = {}
        for group_idx, group in enumerate(result.get('img_groups', [])):
            # 提取路径列表供现有GUI逻辑使用
            paths = [file_info['path'] for file_info in group]
            self.img_groups.append(paths)
            # 存储完整的文件信息
            self.img_group_details[group_idx] = group
        
        self.vid_groups = []
        self.vid_group_details = {}
        for group_idx, group in enumerate(result.get('vid_groups', [])):
            paths = [file_info['path'] for file_info in group]
            self.vid_groups.append(paths)
            self.vid_group_details[group_idx] = group
        
        # 存储损坏文件列表
        self.corrupt_img_files = result.get('corrupt_files', [])
        
        # 初始化选择状态
        self.img_checked = {i: {group[0]} if group else set() for i, group in enumerate(self.img_groups)}
        self.vid_checked = {i: {group[0]} if group else set() for i, group in enumerate(self.vid_groups)}
        
        # 更新UI
        self._update_group_lists()
        self._update_progress(result.get('progress', 1.0))
        self._update_log(result.get('log', []))
        self._update_dedup_stats(result.get('stats', {}))
        
        # 显示当前组
        self.tabs.setCurrentIndex(0)
        if self.img_groups:
            self.group_list.setCurrentRow(0)
            self.show_group(0)
        if self.vid_groups:
            self.vid_group_list.setCurrentRow(0)
            self.show_vid_group(0)

    def on_supp_data(self, result):
        """处理增补数据"""
        self._last_supp_result = result
        
        # 提取文件路径供现有GUI使用
        self.supplement_img_files = [img['path'] for img in result.get('added_images', [])]
        self.supplement_vid_files = [vid['path'] for vid in result.get('added_videos', [])]
        
        # 存储完整信息
        self.supplement_img_details = result.get('added_images', [])
        self.supplement_vid_details = result.get('added_videos', [])
        self.skipped_img_details = result.get('skipped_images', [])
        self.skipped_vid_details = result.get('skipped_videos', [])
        
        # 目标目录
        target_dirs = result.get('target_dirs', {})
        self.supplement_img_target_dir = target_dirs.get('supplement_dir')
        self.supplement_vid_target_dir = target_dirs.get('mp4_dir')
        
        # 损坏文件
        self.corrupt_img_files = result.get('corrupt_files', [])
        
        # 更新UI
        self._update_supplement_ui()
        self._update_progress(result.get('progress', 1.0))
        self._update_log(result.get('log', []))
        self._update_supplement_stats(result.get('stats', {}))
        
        # 切换到增补tab
        self.tabs.setCurrentWidget(self.supplement_tab)

    def _update_group_lists(self):
        """更新分组列表"""
        self.group_list.clear()
        for i, group in enumerate(self.img_groups):
            self.group_list.addItem(f"{tr('group')}{i+1} ({len(group)})")
        
        self.vid_group_list.clear()
        for i, group in enumerate(self.vid_groups):
            self.vid_group_list.addItem(f"{tr('video_group')}{i+1} ({len(group)})")
        
        if self.img_groups:
            self.group_list.setCurrentRow(0)
        if self.vid_groups:
            self.vid_group_list.setCurrentRow(0)

    def _update_progress(self, progress):
        """更新进度条"""
        self.progress.setMaximum(100)
        self.progress.setValue(int(progress * 100))
        if progress >= 1.0:
            self.progress.hide()

    def _update_log(self, log_messages):
        """更新日志显示，只显示关键进展信息，同时保留文件夹信息"""
        # 先保存文件夹信息，然后清空日志
        folder_info = self.folder_info_messages.copy()
        self.log_box.clear()
        
        # 重新添加文件夹信息
        for msg in folder_info:
            self.log_box.append(msg)
        
        # 如果有文件夹信息，添加一个分隔符
        if folder_info:
            self.log_box.append("─" * 50)
        
        # 定义要显示的关键信息模式
        key_patterns = [
            # 任务开始/完成
            r'正在扫描|Scanning|发现.*文件|Found.*files',
            r'正在分析|Analyzing|分析完成|Analysis complete',
            r'去重完成|报告已保存|Deduplication complete|Report saved',
            r'报告生成完成|Report generation complete',
            
            # 统计信息
            r'统计.*去重|stat.*dedup|总扫描|Total scanned',
            
            # 错误和警告
            r'错误|Error|警告|Warning|失败|Failed',
            
            # 任务状态
            r'开始.*任务|Starting.*task|完成.*任务|Completed.*task'
        ]
        
        for msg in log_messages:
            # 检查是否是关键信息
            should_display = False
            for pattern in key_patterns:
                if re.search(pattern, msg, re.IGNORECASE):
                    should_display = True
                    break
            
            if should_display:
                self.log_box.append(msg)

    def _update_dedup_stats(self, stats):
        """更新去重统计信息"""
        self._last_report_end_time = time.time()
        # 这里可以添加更详细的统计信息显示
        self.log_dedup_stats(from_data=True)

    def _update_supplement_ui(self):
        """更新增补界面"""
        self.supplement_img_list.clear()
        for file_info in self.supplement_img_details:
            item_widget = QWidget()
            hbox = QHBoxLayout(item_widget)
            
            is_corrupt = file_info.get('is_corrupt', False)
            
            if not is_corrupt:
                try:
                    thumb = QPixmap(file_info['path'])
                    if not thumb.isNull():
                        pix = thumb.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        thumb_label = QLabel()
                        thumb_label.setPixmap(pix)
                        thumb_label.setCursor(Qt.PointingHandCursor)
                        
                        def show_big_thumb(p=file_info['path']):
                            dlg = QDialog(self)
                            dlg.setWindowTitle(os.path.basename(p))
                            vbox = QVBoxLayout(dlg)
                            img_label = QLabel()
                            pix2 = QPixmap(p)
                            if not pix2.isNull():
                                screen = QApplication.primaryScreen().availableGeometry()
                                maxw, maxh = int(screen.width() * 0.8), int(screen.height() * 0.8)
                                pix2 = pix2.scaled(maxw, maxh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                img_label.setPixmap(pix2)
                            else:
                                img_label.setText(tr('no_thumbnail'))
                            vbox.addWidget(img_label)
                            dlg.resize( min(pix2.width()+40 if pix2 else 600, 1200), min(pix2.height()+80 if pix2 else 400, 900) )
                            dlg.exec_()
                        
                        thumb_label.mousePressEvent = lambda e, f=show_big_thumb: f()
                        hbox.addWidget(thumb_label)
                    else:
                        raise Exception("Cannot load thumbnail")
                except Exception:
                    l = QLabel(tr('no_thumbnail'))
                    hbox.addWidget(l)
            else:
                l = QLabel(tr('corrupted'))
                l.setStyleSheet('color: red; font-weight: bold;')
                hbox.addWidget(l)
            
            hbox.addWidget(QLabel(file_info['path']))
            item_widget.setLayout(hbox)
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            if is_corrupt:
                list_item.setBackground(Qt.red)
            self.supplement_img_list.addItem(list_item)
            self.supplement_img_list.setItemWidget(list_item, item_widget)
        
        # 处理视频
        self.supplement_vid_list.clear()
        for file_info in self.supplement_vid_details:
            item_widget = QWidget()
            hbox = QHBoxLayout(item_widget)
            
            thumb = get_video_thumbnail(file_info['path'])
            if thumb and not thumb.isNull():
                pix = thumb.scaled(80, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                thumb_label = QLabel()
                thumb_label.setPixmap(pix)
                thumb_label.setCursor(Qt.PointingHandCursor)
                
                def show_big_thumb(p=file_info['path']):
                    dlg = QDialog(self)
                    dlg.setWindowTitle(os.path.basename(p))
                    vbox = QVBoxLayout(dlg)
                    img_label = QLabel()
                    big_thumb = get_video_thumbnail(p, width=800, height=600)
                    if big_thumb and not big_thumb.isNull():
                        screen = QApplication.primaryScreen().availableGeometry()
                        maxw, maxh = int(screen.width() * 0.8), int(screen.height() * 0.8)
                        big_thumb = big_thumb.scaled(maxw, maxh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        img_label.setPixmap(big_thumb)
                    else:
                        img_label.setText('无法加载缩略图')
                    vbox.addWidget(img_label)
                    dlg.resize( min(big_thumb.width()+40 if big_thumb else 600, 1200), min(big_thumb.height()+80 if big_thumb else 400, 900) )
                    dlg.exec_()
                
                thumb_label.mousePressEvent = lambda e, f=show_big_thumb: f()
                hbox.addWidget(thumb_label)
            else:
                hbox.addWidget(QLabel(tr('no_thumbnail')))
            
            hbox.addWidget(QLabel(file_info['path']))
            item_widget.setLayout(hbox)
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            self.supplement_vid_list.addItem(list_item)
            self.supplement_vid_list.setItemWidget(list_item, item_widget)
        
        # 更新标签
        self.supp_img_label.setText(tr('supp_img', count=len(self.supplement_img_files)) + ' 张')
        self.supp_vid_label.setText(tr('supp_vid', count=len(self.supplement_vid_files)) + ' 个')
    
    def _update_supplement_stats(self, stats):
        """更新增补统计信息"""
        self._last_report_end_time = time.time()
        # 更新统计计数器
        self._last_supp_main_count = stats.get('main_scanned')
        self._last_supp_supp_count = stats.get('supplement_scanned')
        self._last_supp_corrupt_img = stats.get('corrupt_files_count', 0)
        self._last_supp_corrupt_vid = 0  # 视频损坏检测在这个版本中暂不实现
        self.log_supplement_stats(from_data=True)

    def log_dedup_stats(self, from_data=False):
        if from_data and self._last_dedup_result:
            stats = self._last_dedup_result.get('stats', {})
            
            # 直接从stats获取扫描总数，不再调用collect_images
            img_scanned = stats.get('total_images_scanned', 0)
            vid_scanned = stats.get('total_videos_scanned', 0)
            
            # 计算可删除的文件数
            img_del = sum(len(g)-1 for g in self.img_groups if len(g)>1)
            vid_del = sum(len(g)-1 for g in self.vid_groups if len(g)>1)
            
            # 计算可删除文件的大小
            img_del_size = 0
            img_corrupt = len(self.corrupt_img_files)
            for group_idx, group in enumerate(self.img_groups):
                if group_idx in self.img_group_details:
                    for file_info in self.img_group_details[group_idx][1:]:  # 跳过第一个文件
                        img_del_size += file_info.get('size', 0)
            
            vid_del_size = 0
            vid_corrupt = 0
            for group_idx, group in enumerate(self.vid_groups):
                if group_idx in self.vid_group_details:
                    for file_info in self.vid_group_details[group_idx][1:]:  # 跳过第一个文件
                        vid_del_size += file_info.get('size', 0)
                    for file_info in self.vid_group_details[group_idx]:
                        if not os.path.exists(file_info['path']):
                            vid_corrupt += 1
            
            elapsed = None
            if self._last_report_start_time and self._last_report_end_time:
                elapsed = self._last_report_end_time - self._last_report_start_time
            
            msg = f"{tr('stat_dedup')}"
            msg += f"\n  {tr('img_total', count=img_scanned)}, {tr('img_del', count=img_del)}, {tr('img_save', size=img_del_size/1024/1024)}, {tr('img_corrupt', count=img_corrupt)}"
            msg += f"\n  {tr('vid_total', count=vid_scanned)}, {tr('vid_del', count=vid_del)}, {tr('vid_save', size=vid_del_size/1024/1024)}, {tr('vid_corrupt', count=vid_corrupt)}"
            if elapsed:
                msg += f"\n  {tr('elapsed', sec=elapsed)}"
            self.log_box.append(msg)
            return
        
        # 统计去重报告（从文件解析的情况）
        img_total = sum(len(g) for g in self.img_groups)
        vid_total = sum(len(g) for g in self.vid_groups)
        img_del = sum(len(g)-1 for g in self.img_groups if len(g)>1)
        vid_del = sum(len(g)-1 for g in self.vid_groups if len(g)>1)
        img_del_size = 0
        img_corrupt = 0
        for g in self.img_groups:
            for p in g[1:]:
                try:
                    img_del_size += os.path.getsize(p)
                except Exception:
                    pass
            for p in g:
                if not os.path.exists(p):
                    img_corrupt += 1
                else:
                    try:
                        #from PIL import Image
                        #Image.MAX_IMAGE_PIXELS = 200000000  # 例如允许2亿像素图片
                        with Image.open(p) as im:
                            im.verify()
                    except Exception:
                        img_corrupt += 1
        vid_del_size = 0
        vid_corrupt = 0
        for g in self.vid_groups:
            for p in g[1:]:
                try:
                    vid_del_size += os.path.getsize(p)
                except Exception:
                    pass
            for p in g:
                if not os.path.exists(p):
                    vid_corrupt += 1
        elapsed = None
        if self._last_report_start_time and self._last_report_end_time:
            elapsed = self._last_report_end_time - self._last_report_start_time
        msg = f"{tr('stat_dedup')}"
        msg += f"\n  {tr('img_total', count=img_total)}, {tr('img_del', count=img_del)}, {tr('img_save', size=img_del_size/1024/1024)}, {tr('img_corrupt', count=img_corrupt)}"
        msg += f"\n  {tr('vid_total', count=vid_total)}, {tr('vid_del', count=vid_del)}, {tr('vid_save', size=vid_del_size/1024/1024)}, {tr('vid_corrupt', count=vid_corrupt)}"
        if elapsed:
            msg += f"\n  {tr('elapsed', sec=elapsed)}"
        self.log_box.append(msg)

    def log_supplement_stats(self, from_data=False):
        if from_data and self._last_supp_result:
            stats = self._last_supp_result.get('stats', {})
            img_count = len(self.supplement_img_files)
            vid_count = len(self.supplement_vid_files)
            
            img_size = sum(img.get('size', 0) for img in self.supplement_img_details)
            vid_size = sum(vid.get('size', 0) for vid in self.supplement_vid_details)
            
            elapsed = None
            if self._last_report_start_time and self._last_report_end_time:
                elapsed = self._last_report_end_time - self._last_report_start_time
            msg = f"{tr('stat_supp')}"
            if self._last_supp_main_count is not None:
                msg += f"\n  {tr('main_scanned', count=self._last_supp_main_count)}"
            if self._last_supp_supp_count is not None:
                msg += f"\n  {tr('supp_scanned', count=self._last_supp_supp_count)}"
            msg += f"\n  {tr('supp_img', count=img_count)} 张, {tr('supp_img_save', size=img_size/1024/1024)}, {tr('supp_img_corrupt', count=self._last_supp_corrupt_img)}"
            msg += f"\n  {tr('supp_vid', count=vid_count)} 个, {tr('supp_vid_save', size=vid_size/1024/1024)}, {tr('supp_vid_corrupt', count=self._last_supp_corrupt_vid)}"
            if elapsed:
                msg += f"\n  {tr('elapsed', sec=elapsed)}"
            self.log_box.append(msg)
            return
        
        # 统计增补报告（从文件解析的情况）
        img_count = len(self.supplement_img_files)
        vid_count = len(self.supplement_vid_files)
        img_size = 0
        for p in self.supplement_img_files:
            try:
                img_size += os.path.getsize(p)
            except Exception:
                pass
        vid_size = 0
        for p in self.supplement_vid_files:
            try:
                vid_size += os.path.getsize(p)
            except Exception:
                pass
        elapsed = None
        if self._last_report_start_time and self._last_report_end_time:
            elapsed = self._last_report_end_time - self._last_report_start_time
        msg = f"{tr('stat_supp')}"
        if self._last_supp_main_count is not None:
            msg += f"\n  {tr('main_scanned', count=self._last_supp_main_count)}"
        if self._last_supp_supp_count is not None:
            msg += f"\n  {tr('supp_scanned', count=self._last_supp_supp_count)}"
        msg += f"\n  {tr('supp_img', count=img_count)} 张, {tr('supp_img_save', size=img_size/1024/1024)}, {tr('supp_img_corrupt', count=self._last_supp_corrupt_img)}"
        msg += f"\n  {tr('supp_vid', count=vid_count)} 个, {tr('supp_vid_save', size=vid_size/1024/1024)}, {tr('supp_vid_corrupt', count=self._last_supp_corrupt_vid)}"
        if elapsed:
            msg += f"\n  {tr('elapsed', sec=elapsed)}"
        self.log_box.append(msg)

    def on_language_changed(self, idx):
        global LANG
        LANG = 'zh' if idx == 0 else 'en'
        import compare
        compare.LANG = LANG
        self.retranslate_ui()

    def retranslate_ui(self):
        self.setWindowTitle(tr('title'))
        self.btn_generate_report.setText(tr('generate_report'))
        self.btn_generate_supp_report.setText(tr('generate_supp_report'))
        self.btn_load.setText(tr('load_report'))
        self.btn_delete.setText(tr('delete'))
        self.btn_select_all.setText(tr('select_all'))
        self.btn_unselect_all.setText(tr('unselect_all'))
        self.batch_select_label.setText(tr('batch_select'))
        self.combo_strategy.setItemText(0, tr('keep_first'))
        self.combo_strategy.setItemText(1, tr('keep_newest'))
        self.combo_strategy.setItemText(2, tr('keep_largest'))
        self.tabs.setTabText(0, tr('img_tab'))
        self.tabs.setTabText(1, tr('vid_tab'))
        self.tabs.setTabText(2, tr('supp_tab'))
        self.btn_group_select_all.setText(tr('select_all'))
        self.btn_group_unselect_all.setText(tr('unselect_all'))
        self.btn_vid_group_select_all.setText(tr('select_all'))
        self.btn_vid_group_unselect_all.setText(tr('unselect_all'))
        self.img_group.setTitle(tr('img_tab'))
        self.vid_group_box.setTitle(tr('vid_tab'))
        self.btn_move_img_supp.setText(tr('move_supp_img'))
        self.btn_move_vid_supp.setText(tr('move_supp_vid'))
        # 重新设置增补tab标签
        self.supp_img_label.setText(tr('supp_img', count=len(self.supplement_img_files)) + ' 张')
        self.supp_vid_label.setText(tr('supp_vid', count=len(self.supplement_vid_files)) + ' 个')
        # 语言切换标签
        self.combo_lang.setItemText(0, '中文')
        self.combo_lang.setItemText(1, 'English')
        self.lang_label.setText(tr('choose_language'))
        # 刷新分组列表
        self.group_list.clear()
        for i, group in enumerate(self.img_groups):
            self.group_list.addItem(f"{tr('group')}{i+1} ({len(group)})")
        self.vid_group_list.clear()
        for i, group in enumerate(self.vid_groups):
            self.vid_group_list.addItem(f"{tr('video_group')}{i+1} ({len(group)})")

LANG = 'zh'
TRANSLATIONS = {
    'zh': {
        'title': '照片去重报告处理工具',
        'generate_report': '生成去重报告',
        'generate_supp_report': '生成增补报告',
        'load_report': '加载报告',
        'delete': '直接删除',
        'select_all': '所有组全选',
        'unselect_all': '所有组全不选',
        'batch_select': '批量选择:',
        'keep_first': '保留第一个',
        'keep_newest': '保留最新',
        'keep_largest': '保留最大',
        'img_tab': '图片重复组',
        'vid_tab': '视频重复组',
        'supp_tab': '增补结果',
        'supp_img': '成功增补的图片：',
        'supp_vid': '成功增补的视频：',
        'move_supp_img': '批量移动增补图片到指定目录',
        'move_supp_vid': '批量移动增补视频到指定目录',
        'select_main_folder': '选择主文件夹',
        'select_supp_folder': '选择补充文件夹',
        'select_target_folder': '选择待去重文件夹',
        'save_dedup_report_as': '保存去重报告为',
        'save_supp_report_as': '保存增补报告为',
        'text_files': 'Text Files (*.txt)',
        'param_error': '参数错误',
        'main_supp_same': '主文件夹和补充文件夹不能相同，请重新选择！',
        'no_files_to_move': '没有可移动的增补{label}。',
        'target_dir_not_found': '未能从报告中识别出增补{label}的目标目录。',
        'target_dir_create_fail': '目标目录不存在且创建失败：\n{target_dir}\n错误信息：{err}',
        'move_success': '成功移动 {count} 个{label}到\n{target_dir}',
        'move_corrupt': '\n其中 {corrupt} 个疑似损坏文件已移动到: {corrupt_dir}',
        'move_failed': '有 {count} 个{label}移动失败。\n{files}',
        'batch_move': '批量移动',
        'partial_move_failed': '部分移动失败',
        'select_report': '选择去重报告',
        'select_report_tip': 'Text Files (*.txt)',
        'file_not_exist': '文件不存在',
        'cannot_load_image': '无法加载图片',
        'no_thumbnail': '无缩略图',
        'keep': '保留',
        'group': '重复组',
        'video_group': '视频组',
        'supplement_report': '增补图片报告',
        'already_exists': '已存在',
        'dry_run': '[DRY-RUN] 只读模式，未做任何实际写入操作',
        'corrupted_files': '损坏文件',
        'stat_dedup': '[统计] 去重分析：',
        'stat_supp': '[统计] 增补分析：',
        'main_scanned': '主库共扫描: {count} 个文件',
        'supp_scanned': '补充库共扫描: {count} 个文件',
        'img_total': '总扫描图片: {count} 张',
        'img_del': '预计可删除: {count} 张',
        'img_save': '预计节省空间: {size:.2f} MB',
        'img_corrupt': '疑似损坏图片: {count} 张',
        'vid_total': '总扫描视频: {count} 个',
        'vid_del': '预计可删除: {count} 个',
        'vid_save': '预计节省空间: {size:.2f} MB',
        'vid_corrupt': '疑似损坏视频: {count} 个',
        'supp_img': '需增补图片: {count}',
        'supp_img_save': '预计增补空间: {size:.2f} MB',
        'supp_img_corrupt': '疑似损坏图片: {count}',
        'supp_vid': '需增补视频: {count}',
        'supp_vid_save': '预计增补空间: {size:.2f} MB',
        'supp_vid_corrupt': '疑似损坏视频: {count}',
        'elapsed': '分析/报告生成耗时: {sec:.1f} 秒',
        'report_done': '报告生成完成',
        'start_dedup': '开始生成去重报告...',
        'dedup_done': '报告生成完成: {path}',
        'start_supp': '开始生成增补报告...',
        'supp_done': '增补报告生成完成: {path}',
        'error': '发生错误: {err}\n{tb}',
        'choose_language': '语言/Language:',
        'corrupted': '损坏',
        'delete_corrupted': '删除损坏图片',
        'no_files_to_delete': '没有要删除的文件',
        'confirm_delete': '确认删除',
        'confirm_delete_msg': '确认删除',
        'files': '个文件',
        'delete_complete': '删除完成',
        'delete_complete_msg': '成功删除',
        'partial_delete_failed': '部分删除失败',
        'partial_delete_failed_msg': '部分删除失败',
        'delete_failed': '删除失败',
        'file_not_found': '文件不存在',
        'selected_target_folder': '选择的目标文件夹',
        'selected_main_folder': '选择的主文件夹',
        'selected_supp_folder': '选择的补充文件夹',
        'img': '图片',
        'vid': '视频',
        'to': '到',
        'supp_img_report': '增补图片报告',
        'partial_move_failed_msg': '部分移动失败',
        'move_corrupt': '移动损坏文件',
    },
    'en': {
        'title': 'Photo Deduplication & Supplement Tool',
        'generate_report': 'Generate Deduplication Report',
        'generate_supp_report': 'Generate Supplement Report',
        'load_report': 'Load Report',
        'delete': 'Delete Directly',
        'select_all': 'Select All Groups',
        'unselect_all': 'Unselect All Groups',
        'batch_select': 'Batch Select:',
        'keep_first': 'Keep First',
        'keep_newest': 'Keep Newest',
        'keep_largest': 'Keep Largest',
        'img_tab': 'Image Groups',
        'vid_tab': 'Video Groups',
        'supp_tab': 'Supplement Result',
        'supp_img': 'Supplemented Images:',
        'supp_vid': 'Supplemented Videos:',
        'move_supp_img': 'Batch Move Supplemented Images',
        'move_supp_vid': 'Batch Move Supplemented Videos',
        'select_main_folder': 'Select Main Folder',
        'select_supp_folder': 'Select Supplement Folder',
        'select_target_folder': 'Select Target Folder',
        'save_dedup_report_as': 'Save Deduplicate Report As',
        'save_supp_report_as': 'Save Supplement Report As',
        'text_files': 'Text Files (*.txt)',
        'param_error': 'Parameter Error',
        'main_supp_same': 'Main and supplement folders cannot be the same. Please reselect!',
        'no_files_to_move': 'No supplement {label} to move.',
        'target_dir_not_found': 'Failed to detect target directory for supplement {label} from report.',
        'target_dir_create_fail': 'Target directory does not exist and creation failed:\n{target_dir}\nError: {err}',
        'move_success': 'Successfully moved {count} {label} to\n{target_dir}',
        'move_corrupt': '\n{corrupt} suspected corrupted files moved to: {corrupt_dir}',
        'move_failed': '{count} {label} failed to move.\n{files}',
        'batch_move': 'Batch Move',
        'partial_move_failed': 'Partial Move Failed',
        'select_report': 'Select Deduplication Report',
        'select_report_tip': 'Text Files (*.txt)',
        'file_not_exist': 'File Not Exist',
        'cannot_load_image': 'Cannot Load Image',
        'no_thumbnail': 'No Thumbnail',
        'keep': 'Keep',
        'group': 'Group',
        'video_group': 'Video Group',
        'supplement_report': 'Supplement Report',
        'already_exists': 'Already Exists',
        'dry_run': '[DRY-RUN] Readonly mode, no actual file operation',
        'corrupted_files': 'Corrupted Files',
        'stat_dedup': '[Stats] Deduplication:',
        'stat_supp': '[Stats] Supplement:',
        'main_scanned': 'Main scanned: {count} files',
        'supp_scanned': 'Supplement scanned: {count} files',
        'img_total': 'Total images: {count}',
        'img_del': 'Deletable: {count}',
        'img_save': 'Space to save: {size:.2f} MB',
        'img_corrupt': 'Suspected corrupted images: {count}',
        'vid_total': 'Total videos: {count}',
        'vid_del': 'Deletable: {count}',
        'vid_save': 'Space to save: {size:.2f} MB',
        'vid_corrupt': 'Suspected corrupted videos: {count}',
        'supp_img': 'Images to supplement: {count}',
        'supp_img_save': 'Space to supplement: {size:.2f} MB',
        'supp_img_corrupt': 'Suspected corrupted images: {count}',
        'supp_vid': 'Videos to supplement: {count}',
        'supp_vid_save': 'Space to supplement: {size:.2f} MB',
        'supp_vid_corrupt': 'Suspected corrupted videos: {count}',
        'elapsed': 'Elapsed: {sec:.1f} s',
        'report_done': 'Report generated',
        'start_dedup': 'Generating deduplication report...',
        'dedup_done': 'Report generated: {path}',
        'start_supp': 'Generating supplement report...',
        'supp_done': 'Supplement report generated: {path}',
        'error': 'Error: {err}\n{tb}',
        'choose_language': 'Language:',
        'corrupted': 'Corrupted',
        'delete_corrupted': 'Delete Corrupted Images',
        'no_files_to_delete': 'No files to delete',
        'confirm_delete': 'Confirm Delete',
        'confirm_delete_msg': 'Confirm delete',
        'files': 'files',
        'delete_complete': 'Delete Complete',
        'delete_complete_msg': 'Successfully deleted',
        'partial_delete_failed': 'Partial Delete Failed',
        'partial_delete_failed_msg': 'Partial delete failed',
        'delete_failed': 'delete failed',
        'file_not_found': 'File not found',
        'selected_target_folder': 'Selected target folder',
        'selected_main_folder': 'Selected main folder',
        'selected_supp_folder': 'Selected supplement folder',
        'img': 'images',
        'vid': 'videos',
        'to': 'to',
        'supp_img_report': 'Supplement Report',
        'partial_move_failed_msg': 'Partial move failed',
        'move_corrupt': 'Move corrupted',
    }
}
def tr(key, **kwargs):
    s = TRANSLATIONS.get(LANG, TRANSLATIONS['zh']).get(key, key)
    return s.format(**kwargs) if kwargs else s
if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = DedupGui()
    gui.show()
    sys.exit(app.exec_())