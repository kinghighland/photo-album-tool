import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget, QListWidgetItem,
    QFileDialog, QCheckBox, QMessageBox, QScrollArea, QGroupBox, QDialog, QComboBox, QTabWidget, QLineEdit, QFrame,
    QTextEdit, QProgressBar, QInputDialog
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPalette, QColor
import subprocess
from PIL import Image
import re
import threading
import traceback
import importlib.util

THUMBNAIL_DIR = '.thumbnails'
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

# 动态导入 compare.py 的 find_duplicates
spec = importlib.util.spec_from_file_location("compare", "compare.py")
compare = importlib.util.module_from_spec(spec)
sys.modules["compare"] = compare
spec.loader.exec_module(compare)

class ReportThread(QThread):
    log_signal = pyqtSignal(str)
    done_signal = pyqtSignal(str)
    def __init__(self, folder, report_path, hash_method):
        super().__init__()
        self.folder = folder
        self.report_path = report_path
        self.hash_method = hash_method
    def run(self):
        try:
            self.log_signal.emit(f"开始生成去重报告...\n")
            compare.find_duplicates(self.folder, self.report_path, self.hash_method, dry_run=False)
            self.log_signal.emit(f"报告生成完成: {self.report_path}\n")
            self.done_signal.emit(self.report_path)
        except Exception as e:
            tb = traceback.format_exc()
            self.log_signal.emit(f"发生错误: {e}\n{tb}")

class SupplementReportThread(QThread):
    log_signal = pyqtSignal(str)
    done_signal = pyqtSignal(str)
    def __init__(self, main_folder, supplement_folder, report_path, hash_method):
        super().__init__()
        self.main_folder = main_folder
        self.supplement_folder = supplement_folder
        self.report_path = report_path
        self.hash_method = hash_method
    def run(self):
        try:
            self.log_signal.emit(f"开始生成增补报告...\n")
            compare.supplement_images(self.main_folder, self.supplement_folder, self.report_path, self.hash_method, dry_run=False)
            self.log_signal.emit(f"增补报告生成完成: {self.report_path}\n")
            self.done_signal.emit(self.report_path)
        except Exception as e:
            tb = traceback.format_exc()
            self.log_signal.emit(f"发生错误: {e}\n{tb}")

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
        self.img_groups = []  # 每组是[图片路径...]
        self.vid_groups = []  # 每组是[视频路径...]
        self.current_img_group = 0
        self.current_vid_group = 0
        self.img_checked = {}  # {group_idx: set(保留图片路径)}
        self.vid_checked = {}  # {group_idx: set(保留视频路径)}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        # 顶部操作区
        btn_layout = QHBoxLayout()
        self.btn_generate_report = QPushButton('生成去重报告')
        self.btn_generate_report.clicked.connect(self.generate_report_dialog)
        self.btn_generate_supp_report = QPushButton('生成增补报告')
        self.btn_generate_supp_report.clicked.connect(self.generate_supp_report_dialog)
        self.btn_load = QPushButton('加载报告')
        self.btn_load.clicked.connect(self.load_report)
        self.btn_export = QPushButton('导出删除清单')
        self.btn_export.clicked.connect(self.export_delete_list)
        self.btn_delete = QPushButton('直接删除')
        self.btn_delete.clicked.connect(self.delete_files)
        self.btn_select_all = QPushButton('所有组全选')
        self.btn_select_all.clicked.connect(self.select_all_groups)
        self.btn_unselect_all = QPushButton('所有组全不选')
        self.btn_unselect_all.clicked.connect(self.unselect_all_groups)
        self.combo_strategy = QComboBox()
        self.combo_strategy.addItems(['保留第一个', '保留最新', '保留最大'])
        self.combo_strategy.currentIndexChanged.connect(self.apply_strategy)
        btn_layout.addWidget(self.btn_generate_report)
        btn_layout.addWidget(self.btn_generate_supp_report)
        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_export)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_unselect_all)
        btn_layout.addWidget(QLabel('批量选择:'))
        btn_layout.addWidget(self.combo_strategy)
        layout.addLayout(btn_layout)
        # 日志输出区
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(120)
        layout.addWidget(self.log_box)
        # 进度条
        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(0)  # 不确定进度时为忙等待
        self.progress.hide()
        layout.addWidget(self.progress)
        # 搜索框
        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText('搜索分组...')
        self.search_box.textChanged.connect(self.filter_groups)
        search_layout.addWidget(QLabel('分组搜索:'))
        search_layout.addWidget(self.search_box)
        layout.addLayout(search_layout)
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
        self.btn_group_select_all = QPushButton('本组全选')
        self.btn_group_select_all.clicked.connect(self.select_all_current_group)
        self.btn_group_unselect_all = QPushButton('本组全不选')
        self.btn_group_unselect_all.clicked.connect(self.unselect_all_current_group)
        group_btn_layout.addWidget(self.btn_group_select_all)
        group_btn_layout.addWidget(self.btn_group_unselect_all)
        right.addLayout(group_btn_layout)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.img_group = QGroupBox('重复图片')
        self.img_layout = QVBoxLayout()
        self.img_group.setLayout(self.img_layout)
        self.scroll.setWidget(self.img_group)
        right.addWidget(self.scroll, 8)
        img_layout.addLayout(right, 8)
        self.tabs.addTab(img_tab, '图片重复组')
        # 视频Tab
        vid_tab = QWidget()
        vid_layout = QHBoxLayout(vid_tab)
        self.vid_group_list = QListWidget()
        self.vid_group_list.currentRowChanged.connect(self.on_vid_group_changed)
        vid_layout.addWidget(self.vid_group_list, 2)
        vid_right = QVBoxLayout()
        # 本组全选/全不选
        vid_group_btn_layout = QHBoxLayout()
        self.btn_vid_group_select_all = QPushButton('本组全选')
        self.btn_vid_group_select_all.clicked.connect(self.select_all_current_vid_group)
        self.btn_vid_group_unselect_all = QPushButton('本组全不选')
        self.btn_vid_group_unselect_all.clicked.connect(self.unselect_all_current_vid_group)
        vid_group_btn_layout.addWidget(self.btn_vid_group_select_all)
        vid_group_btn_layout.addWidget(self.btn_vid_group_unselect_all)
        vid_right.addLayout(vid_group_btn_layout)
        self.vid_scroll = QScrollArea()
        self.vid_scroll.setWidgetResizable(True)
        self.vid_group_box = QGroupBox('重复视频')
        self.vid_layout = QVBoxLayout()
        self.vid_group_box.setLayout(self.vid_layout)
        self.vid_scroll.setWidget(self.vid_group_box)
        vid_right.addWidget(self.vid_scroll, 8)
        vid_layout.addLayout(vid_right, 8)
        self.tabs.addTab(vid_tab, '视频重复组')
        # 增补结果Tab
        self.supplement_tab = QWidget()
        supp_layout = QVBoxLayout(self.supplement_tab)
        supp_layout.addWidget(QLabel('成功增补的图片：'))
        self.supplement_img_list = QListWidget()
        supp_layout.addWidget(self.supplement_img_list, 4)
        self.btn_move_img_supp = QPushButton('批量移动增补图片到指定目录')
        self.btn_move_img_supp.clicked.connect(lambda: self.move_supplement_files('img'))
        supp_layout.addWidget(self.btn_move_img_supp)
        supp_layout.addWidget(QLabel('成功增补的视频：'))
        self.supplement_vid_list = QListWidget()
        supp_layout.addWidget(self.supplement_vid_list, 2)
        self.btn_move_vid_supp = QPushButton('批量移动增补视频到指定目录')
        self.btn_move_vid_supp.clicked.connect(lambda: self.move_supplement_files('vid'))
        supp_layout.addWidget(self.btn_move_vid_supp)
        self.tabs.addTab(self.supplement_tab, '增补结果')
        layout.addWidget(self.tabs)
        self.supplement_img_files = []
        self.supplement_vid_files = []

    def apply_strategy(self):
        strategy = self.combo_strategy.currentText()
        for i, group in enumerate(self.img_groups):
            if not group:
                self.img_checked[i] = set()
                continue
            if strategy == '保留第一个':
                self.img_checked[i] = {group[0]}
            elif strategy == '保留最新':
                newest = max(group, key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0)
                self.img_checked[i] = {newest}
            elif strategy == '保留最大':
                largest = max(group, key=lambda p: os.path.getsize(p) if os.path.exists(p) else 0)
                self.img_checked[i] = {largest}
        self.show_group(self.current_img_group)

    def load_report(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择去重报告', '', 'Text Files (*.txt)')
        if not path:
            return
        self.report_path = path
        # 检查是否为增补报告
        with open(path, 'r', encoding='utf-8') as f:
            first_lines = [f.readline() for _ in range(5)]
        if any('增补图片报告' in line for line in first_lines):
            self.show_supplement_report(path)
            self.tabs.setCurrentWidget(self.supplement_tab)
            return
        # 否则为去重报告
        self.img_groups, self.vid_groups = self.parse_report(path)
        self.img_checked = {i: {group[0]} if group else set() for i, group in enumerate(self.img_groups)}
        self.vid_checked = {i: {group[0]} if group else set() for i, group in enumerate(self.vid_groups)}
        self.group_list.clear()
        for i, group in enumerate(self.img_groups):
            self.group_list.addItem(f'重复组{i+1} ({len(group)}张)')
        if self.img_groups:
            self.group_list.setCurrentRow(0)
        self.vid_group_list.clear()
        for i, group in enumerate(self.vid_groups):
            self.vid_group_list.addItem(f'视频组{i+1} ({len(group)}个)')
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
            if l.startswith('重复图片组') or l.startswith('重复组'):
                if group and mode == 'img':
                    img_groups.append(group)
                if group and mode == 'vid':
                    vid_groups.append(group)
                group = []
                mode = 'img'
            elif l.startswith('视频重复组') or l.startswith('重复视频文件'):
                if group and mode == 'img':
                    img_groups.append(group)
                if group and mode == 'vid':
                    vid_groups.append(group)
                group = []
                mode = 'vid'
            elif l.startswith('哈希:') or not l:
                continue
            elif line.startswith('    '):
                group.append(l)
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

    def filter_groups(self, text):
        # 只对图片分组做搜索
        self.group_list.clear()
        for i, group in enumerate(self.img_groups):
            label = f'重复组{i+1} ({len(group)}张)'
            if text.strip() == '' or text.strip() in label:
                self.group_list.addItem(label)
        if self.group_list.count() > 0:
            self.group_list.setCurrentRow(0)

    def show_group(self, idx):
        for i in reversed(range(self.img_layout.count())):
            w = self.img_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        group = self.img_groups[idx]
        for path in group:
            row = QHBoxLayout()
            label = ClickableLabel(path)
            if os.path.exists(path):
                pix = QPixmap(path)
                if not pix.isNull():
                    pix = pix.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    label.setPixmap(pix)
                else:
                    label.setText('无法加载图片')
            else:
                label.setText('文件不存在')
            row.addWidget(label)
            # 用 QFrame 分隔
            frame = QFrame()
            frame.setFrameShape(QFrame.VLine)
            frame.setFrameShadow(QFrame.Sunken)
            row.addWidget(frame)
            path_label = QLabel(path)
            path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row.addWidget(path_label, 2)
            cb = QCheckBox('保留')
            cb.setChecked(path in self.img_checked[idx])
            cb.stateChanged.connect(lambda state, p=path: self.on_check_changed(idx, p, state))
            row.addWidget(cb)
            row_widget = QWidget()
            row_widget.setLayout(row)
            row_widget.setStyleSheet('background: #f9f9f9; margin-bottom: 6px; border-radius: 8px;')
            self.img_layout.addWidget(row_widget)

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
            if thumb and os.path.exists(thumb):
                pix = QPixmap(thumb)
                if not pix.isNull():
                    pix = pix.scaled(160, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    thumb_label.setPixmap(pix)
                    thumb_label.setCursor(Qt.PointingHandCursor)
                    def show_big_thumb(p=thumb):
                        dlg = QDialog(self)
                        dlg.setWindowTitle(os.path.basename(path))
                        vbox = QVBoxLayout(dlg)
                        img_label = QLabel()
                        pix2 = QPixmap(p)
                        if not pix2.isNull():
                            screen = QApplication.primaryScreen().availableGeometry()
                            maxw, maxh = int(screen.width() * 0.8), int(screen.height() * 0.8)
                            pix2 = pix2.scaled(maxw, maxh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            img_label.setPixmap(pix2)
                        else:
                            img_label.setText('无法加载缩略图')
                        vbox.addWidget(img_label)
                        dlg.resize( min(pix2.width()+40, 1200), min(pix2.height()+80, 900) )
                        dlg.exec_()
                    thumb_label.mousePressEvent = lambda e, f=show_big_thumb: f()
                else:
                    thumb_label.setText('无缩略图')
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
            cb = QCheckBox('保留')
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

    def export_delete_list(self):
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
            QMessageBox.information(self, '导出删除清单', '没有需要删除的文件。')
            return
        save_path, _ = QFileDialog.getSaveFileName(self, '保存删除清单', 'delete_list.txt', 'Text Files (*.txt)')
        if not save_path:
            return
        with open(save_path, 'w', encoding='utf-8') as f:
            for path in delete_list:
                f.write(path + '\n')
        QMessageBox.information(self, '导出删除清单', f'已导出 {len(delete_list)} 条删除清单到\n{save_path}')

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
            QMessageBox.information(self, '直接删除', '没有需要删除的文件。')
            return
        reply = QMessageBox.question(self, '确认删除', f'确定要删除 {len(delete_list)} 个文件吗？此操作不可恢复！',
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
            QMessageBox.information(self, '删除完成', f'成功删除 {len(delete_list)} 个文件。')
        else:
            QMessageBox.warning(self, '部分删除失败', f'有 {len(failed)} 个文件删除失败。\n' + '\n'.join(f[0] for f in failed))
        self.load_report()

    def show_supplement_report(self, path):
        self.supplement_img_list.clear()
        self.supplement_vid_list.clear()
        self.supplement_img_files = []
        self.supplement_vid_files = []
        self.supplement_img_target_dir = None
        self.supplement_vid_target_dir = None
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        mode = None
        for line in lines:
            l = line.rstrip('\r\n')
            if l.startswith('成功增补') and '图片' in l:
                mode = 'img'
                m = re.search(r'到: (.+)$', l)
                if m:
                    self.supplement_img_target_dir = m.group(1).strip()
                continue
            if l.startswith('成功增补') and '视频' in l:
                mode = 'vid'
                m = re.search(r'到: (.+)$', l)
                if m:
                    self.supplement_vid_target_dir = m.group(1).strip()
                continue
            if l.startswith('已存在') or l.strip() == '' or l.startswith('[DRY-RUN]') or l.startswith('增补图片报告'):
                mode = None
                continue
            # 兼容 D:/ 和 D:\ 路径
            if re.search(r'[A-Za-z]:[\\/]', l):
                if mode == 'img':
                    self.supplement_img_files.append(l.strip())
                elif mode == 'vid':
                    self.supplement_vid_files.append(l.strip())
        for f in self.supplement_img_files:
            self.supplement_img_list.addItem(f)
        for f in self.supplement_vid_files:
            self.supplement_vid_list.addItem(f)


    def move_supplement_files(self, which):
        if which == 'img':
            files = self.supplement_img_files
            label = '图片'
            target_dir = self.supplement_img_target_dir
        else:
            files = self.supplement_vid_files
            label = '视频'
            target_dir = self.supplement_vid_target_dir
        if not files:
            QMessageBox.information(self, '批量移动', f'没有可移动的增补{label}。')
            return
        if not target_dir:
            QMessageBox.warning(self, '批量移动', f'未能从报告中识别出增补{label}的目标目录。')
            return
        failed = []
        for f in files:
            try:
                if os.path.exists(f):
                    base = os.path.basename(f)
                    target = os.path.join(target_dir, base)
                    count = 1
                    while os.path.exists(target):
                        name, ext = os.path.splitext(base)
                        target = os.path.join(target_dir, f"{name}_{count}{ext}")
                        count += 1
                    os.rename(f, target)
            except Exception as e:
                failed.append((f, str(e)))
        if not failed:
            QMessageBox.information(self, '批量移动', f'成功移动 {len(files)} 个{label}到\n{target_dir}')
        else:
            QMessageBox.warning(self, '部分移动失败', f'有 {len(failed)} 个{label}移动失败。\n' + '\n'.join(f[0] for f in failed))

    def generate_report_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, '选择待去重文件夹')
        if not folder:
            return
        report_path, _ = QFileDialog.getSaveFileName(self, '保存报告为', 'report.txt', 'Text Files (*.txt)')
        if not report_path:
            return
        hash_method, ok = QInputDialog.getItem(self, '选择哈希算法', '哈希算法：', ['md5', 'sha1'], 0, False)
        if not ok:
            return
        self.progress.show()
        self.log_box.clear()
        self.log_box.append(f'开始生成去重报告...')
        self.thread = ReportThread(folder, report_path, hash_method)
        self.thread.log_signal.connect(self.log_box.append)
        self.thread.done_signal.connect(self.on_report_done)
        self.thread.start()

    def generate_supp_report_dialog(self):
        main_folder = QFileDialog.getExistingDirectory(self, '选择主文件夹')
        if not main_folder:
            return
        supplement_folder = QFileDialog.getExistingDirectory(self, '选择补充文件夹')
        if not supplement_folder:
            return
        report_path, _ = QFileDialog.getSaveFileName(self, '保存增补报告为', 'supplement_report.txt', 'Text Files (*.txt)')
        if not report_path:
            return
        hash_method, ok = QInputDialog.getItem(self, '选择哈希算法', '哈希算法：', ['md5', 'sha1'], 0, False)
        if not ok:
            return
        self.progress.show()
        self.log_box.clear()
        self.log_box.append(f'开始生成增补报告...')
        self.supp_thread = SupplementReportThread(main_folder, supplement_folder, report_path, hash_method)
        self.supp_thread.log_signal.connect(self.log_box.append)
        self.supp_thread.done_signal.connect(self.on_report_done)
        self.supp_thread.start()

    def on_report_done(self, report_path):
        self.progress.hide()
        self.log_box.append(f'报告生成完成，自动加载报告...')
        self.load_report_path(report_path)

    def load_report_path(self, path):
        self.report_path = path
        # 检查是否为增补报告
        with open(path, 'r', encoding='utf-8') as f:
            first_lines = [f.readline() for _ in range(5)]
        if any('增补图片报告' in line for line in first_lines):
            self.show_supplement_report(path)
            self.tabs.setCurrentWidget(self.supplement_tab)
            return
        self.img_groups, self.vid_groups = self.parse_report(path)
        self.img_checked = {i: {group[0]} if group else set() for i, group in enumerate(self.img_groups)}
        self.vid_checked = {i: {group[0]} if group else set() for i, group in enumerate(self.vid_groups)}
        self.group_list.clear()
        for i, group in enumerate(self.img_groups):
            self.group_list.addItem(f'重复组{i+1} ({len(group)}张)')
        if self.img_groups:
            self.group_list.setCurrentRow(0)
        self.vid_group_list.clear()
        for i, group in enumerate(self.vid_groups):
            self.vid_group_list.addItem(f'视频组{i+1} ({len(group)}个)')
        if self.vid_groups:
            self.vid_group_list.setCurrentRow(0)
        self.combo_strategy.setCurrentIndex(0)
        self.tabs.setCurrentIndex(0)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = DedupGui()
    gui.show()
    sys.exit(app.exec_()) 