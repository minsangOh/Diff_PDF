import sys
import os
import ctypes
import fitz  # PyMuPDF
import difflib
import numpy as np
from typing import Tuple, List, Optional
from PIL import Image, ImageChops

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFileDialog,
                             QSplitter, QComboBox, QScrollArea, QSpinBox, QFrame, QCheckBox)
from PyQt6.QtGui import QPixmap, QImage, QIcon, QPainter, QColor, QCursor
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF, QSize


# --- Utils ---
def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)


# --- Core Logic ---
class PDFEngine:
    """Handles PDF loading, rendering, and visual/text comparison logic."""

    def __init__(self):
        self.docs = {1: None, 2: None}
        self.paths = {1: "", 2: ""}
        self.grid_size = 5
        self.diff_boxes = []  # Cached diff rectangles

    def load_doc(self, slot: int, path: str) -> int:
        self.paths[slot] = path
        self.docs[slot] = fitz.open(path)
        return len(self.docs[slot])

    def is_ready(self) -> bool:
        return self.docs[1] is not None and self.docs[2] is not None

    def get_page_size(self, slot: int, page_num: int) -> Tuple[float, float]:
        doc = self.docs.get(slot)
        if not doc or page_num >= len(doc):
            return 0, 0
        rect = doc[page_num].rect
        return rect.width, rect.height

    def compare_visual(self, page_num: int) -> None:
        """Calculates visual differences using NumPy optimizations."""
        self.diff_boxes = []
        doc1, doc2 = self.docs[1], self.docs[2]

        if not doc1 or not doc2: return
        if page_num >= len(doc1) or page_num >= len(doc2): return

        # Render pages to pixmaps for pixel comparison
        pix1 = doc1[page_num].get_pixmap(matrix=fitz.Matrix(1, 1))
        pix2 = doc2[page_num].get_pixmap(matrix=fitz.Matrix(1, 1))

        if (pix1.width, pix1.height) != (pix2.width, pix2.height):
            return  # Dimension mismatch, skip heavy calculation

        # Convert to PIL -> NumPy
        img1 = Image.frombytes("RGB", [pix1.width, pix1.height], pix1.samples)
        img2 = Image.frombytes("RGB", [pix2.width, pix2.height], pix2.samples)

        diff = ImageChops.difference(img1, img2)
        if not diff.getbbox():
            return  # No differences

        # NumPy Grid Analysis
        diff_arr = np.array(diff.convert("L"))
        h, w = diff_arr.shape
        grid = self.grid_size

        # Padding for exact grid division
        pad_h = (grid - h % grid) % grid
        pad_w = (grid - w % grid) % grid
        if pad_h or pad_w:
            diff_arr = np.pad(diff_arr, ((0, pad_h), (0, pad_w)), mode='constant')

        # Reshape to 4D blocks to find max value in each grid
        new_h, new_w = diff_arr.shape
        blocks = diff_arr.reshape(new_h // grid, grid, new_w // grid, grid)
        block_max = blocks.max(axis=(1, 3))

        # Filter blocks with significant difference (> 20 intensity)
        y_idxs, x_idxs = np.where(block_max > 20)

        for y_idx, x_idx in zip(y_idxs, x_idxs):
            real_x, real_y = int(x_idx * grid), int(y_idx * grid)
            if real_x < w and real_y < h:
                self.diff_boxes.append((real_x, real_y, grid, grid))

    def compare_text(self, page_num: int) -> str:
        if page_num >= len(self.docs[1]) or page_num >= len(self.docs[2]):
            return "Page Range Error"

        t1 = self.docs[1][page_num].get_text("text")
        t2 = self.docs[2][page_num].get_text("text")
        ratio = difflib.SequenceMatcher(None, t1, t2).ratio()
        return f"Match: {ratio * 100:.1f}%"

    def get_pixmap(self, slot: int, page_num: int, scale: float, opacity: int, show_diff: bool) -> Optional[QPixmap]:
        doc = self.docs.get(slot)
        if not doc or page_num >= len(doc):
            return None

        # Render basic page
        pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(scale, scale))
        fmt = QImage.Format.Format_RGB888
        qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()

        # Overlay diff boxes
        if show_diff and self.diff_boxes and opacity > 0:
            with QPainter(qimg) as p:
                p.setBrush(QColor(255, 0, 0, int(opacity * 2.55)))
                p.setPen(Qt.PenStyle.NoPen)
                for x, y, w, h in self.diff_boxes:
                    p.drawRect(QRectF(x * scale, y * scale, w * scale, h * scale))

        return QPixmap.fromImage(qimg)


# --- Custom Widgets ---
class FileDropLabel(QLabel):
    file_dropped = pyqtSignal(int, str)

    def __init__(self, slot_id: int):
        super().__init__("(Drop PDF)")
        self.slot_id = slot_id
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel { border: 2px dashed #ccc; color: #888; border-radius: 4px; padding: 4px; }
            QLabel:hover { border-color: #2196F3; color: #2196F3; }
        """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith('.pdf'):
                self.file_dropped.emit(self.slot_id, path)
                break


class SyncedScrollArea(QScrollArea):
    zoom_request = pyqtSignal(int)  # delta

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._last_drag_pos = None

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._last_drag_pos = e.pos()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._last_drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            delta = e.pos() - self._last_drag_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._last_drag_pos = e.pos()
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._last_drag_pos = None
        super().mouseReleaseEvent(e)

    def wheelEvent(self, e):
        # 1. Ctrl + Wheel : Zoom
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_request.emit(e.angleDelta().y())
            e.accept()
            return

        # 2. Shift + Wheel : Horizontal Scroll
        if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            delta = e.angleDelta().y()
            if delta != 0:
                h_bar = self.horizontalScrollBar()
                h_bar.setValue(h_bar.value() - delta)
                e.accept()
                return

        # 3. Default: Vertical Scroll
        super().wheelEvent(e)


# --- Main UI ---
class DiffApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.engine = PDFEngine()

        # State
        self.curr_page = 0
        self.total_pages = 0
        self.scale = 1.0

        # Debounce timer for smooth zooming
        self.render_timer = QTimer()
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self._update_render)

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        self.setWindowTitle("Selim PDF Diff Tool v1.1")
        self.resize(1400, 900)
        if os.path.exists(resource_path("diff_icon.ico")):
            self.setWindowIcon(QIcon(resource_path("diff_icon.ico")))

        # Layout Containers
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Toolbar
        self.toolbar_widget = QWidget()
        self.toolbar_widget.setFixedHeight(50)
        self.toolbar_widget.setStyleSheet("background-color: #f5f5f5; border-bottom: 1px solid #ddd;")
        tb_layout = QHBoxLayout(self.toolbar_widget)
        tb_layout.setContentsMargins(10, 5, 10, 5)

        # File Loaders
        self.btn_load1 = QPushButton("File 1")
        self.lbl_file1 = FileDropLabel(1)
        self.btn_load2 = QPushButton("File 2")
        self.lbl_file2 = FileDropLabel(2)

        # Controls
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Visual Diff", "Text Diff"])

        self.btn_prev = QPushButton("◀")
        self.lbl_page = QLabel("0 / 0")
        self.lbl_page.setFixedWidth(60)
        self.lbl_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_next = QPushButton("▶")

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(10, 500)
        self.zoom_spin.setValue(100)
        self.zoom_spin.setSuffix("%")

        self.btn_fit = QPushButton("Fit Width")
        self.btn_fit.setCheckable(True)

        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(0, 100)
        self.opacity_spin.setValue(30)
        self.opacity_spin.setSuffix("%")

        # Highlight Toggles (New Feature)
        self.chk_hl1 = QCheckBox("L")
        self.chk_hl1.setChecked(True)
        self.chk_hl1.setToolTip("Show Highlight on Left File")

        self.chk_hl2 = QCheckBox("R")
        self.chk_hl2.setChecked(True)
        self.chk_hl2.setToolTip("Show Highlight on Right File")

        self.btn_compare = QPushButton("RUN COMPARE")
        self.btn_compare.setStyleSheet("background: #0078D7; color: white; font-weight: bold; padding: 4px 10px;")
        self.btn_compare.setEnabled(False)

        # Assemble Toolbar
        items = [
            self.btn_load1, self.lbl_file1, self._sep(),
            self.btn_load2, self.lbl_file2, (None, 1),  # Stretch
            self.combo_mode, self._sep(),
            self.btn_compare, self._sep(),
            self.btn_prev, self.lbl_page, self.btn_next, self._sep(),
            QLabel("Zoom:"), self.zoom_spin, self.btn_fit, self._sep(),
            QLabel("Highlight:"), self.chk_hl1, self.chk_hl2, self._sep(),  # Added
            QLabel("Opacity:"), self.opacity_spin
        ]

        for item in items:
            if isinstance(item, tuple):
                tb_layout.addStretch(item[1])
            elif isinstance(item, QWidget):
                tb_layout.addWidget(item)

        layout.addWidget(self.toolbar_widget)

        # 2. Split View
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.scroll1 = SyncedScrollArea()
        self.view1 = QLabel()
        self.view1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll1.setWidget(self.view1)

        self.scroll2 = SyncedScrollArea()
        self.view2 = QLabel()
        self.view2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll2.setWidget(self.view2)

        splitter.addWidget(self.scroll1)
        splitter.addWidget(self.scroll2)
        splitter.setSizes([700, 700])
        layout.addWidget(splitter)

    def _sep(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def _connect_signals(self):
        # File Loading
        self.btn_load1.clicked.connect(lambda: self._open_file_dialog(1))
        self.lbl_file1.file_dropped.connect(self._load_file)
        self.btn_load2.clicked.connect(lambda: self._open_file_dialog(2))
        self.lbl_file2.file_dropped.connect(self._load_file)

        # Navigation & Actions
        self.btn_compare.clicked.connect(self._refresh_comparison)
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        self.combo_mode.currentIndexChanged.connect(self._refresh_comparison)

        # Zoom & Display
        self.zoom_spin.valueChanged.connect(self._on_zoom_changed)
        self.btn_fit.clicked.connect(self._update_render)
        self.opacity_spin.valueChanged.connect(self._update_render)

        # Highlight Toggles
        self.chk_hl1.toggled.connect(self._update_render)
        self.chk_hl2.toggled.connect(self._update_render)

        # Scroll Sync
        s1_v, s2_v = self.scroll1.verticalScrollBar(), self.scroll2.verticalScrollBar()
        s1_h, s2_h = self.scroll1.horizontalScrollBar(), self.scroll2.horizontalScrollBar()

        s1_v.valueChanged.connect(s2_v.setValue)
        s2_v.valueChanged.connect(s1_v.setValue)
        s1_h.valueChanged.connect(s2_h.setValue)
        s2_h.valueChanged.connect(s1_h.setValue)

        # Zoom Sync
        self.scroll1.zoom_request.connect(self._handle_wheel_zoom)
        self.scroll2.zoom_request.connect(self._handle_wheel_zoom)

    # --- Logic Handlers ---
    def _open_file_dialog(self, slot: int):
        fpath, _ = QFileDialog.getOpenFileName(self, f"Open PDF {slot}", "", "PDF (*.pdf)")
        if fpath: self._load_file(slot, fpath)

    def _load_file(self, slot: int, path: str):
        self.engine.load_doc(slot, path)
        lbl = self.lbl_file1 if slot == 1 else self.lbl_file2
        lbl.setText(os.path.basename(path))
        lbl.setStyleSheet("border: 2px solid #4CAF50; color: black; font-weight: bold;")

        if self.engine.is_ready():
            self.btn_compare.setEnabled(True)
            self.total_pages = min(len(self.engine.docs[1]), len(self.engine.docs[2]))
            self.curr_page = 0
            self._refresh_comparison()

    def _handle_wheel_zoom(self, delta):
        self.btn_fit.setChecked(False)
        step = 10 if delta > 0 else -10
        new_val = max(10, min(500, self.zoom_spin.value() + step))
        self.zoom_spin.setValue(new_val)  # Triggers _on_zoom_changed

    def _on_zoom_changed(self):
        self.btn_fit.setChecked(False)
        self.scale = self.zoom_spin.value() / 100.0
        self.render_timer.start(50)  # Debounce

    def _prev_page(self):
        if self.curr_page > 0:
            self.curr_page -= 1
            self._refresh_comparison()

    def _next_page(self):
        if self.curr_page < self.total_pages - 1:
            self.curr_page += 1
            self._refresh_comparison()

    def _refresh_comparison(self):
        if not self.engine.is_ready(): return
        self.lbl_page.setText(f"{self.curr_page + 1} / {self.total_pages}")

        is_visual = (self.combo_mode.currentIndex() == 0)
        if is_visual:
            self.engine.compare_visual(self.curr_page)
        else:
            msg = self.engine.compare_text(self.curr_page)
            print(msg)  # Or update a status label

        self._update_render()

    def _update_render(self):
        if not self.engine.is_ready(): return

        # Handle Fit Width
        if self.btn_fit.isChecked():
            page_w, _ = self.engine.get_page_size(1, self.curr_page)
            view_w = self.scroll1.viewport().width() - 20
            if page_w > 0:
                self.scale = view_w / page_w
                self.zoom_spin.blockSignals(True)
                self.zoom_spin.setValue(int(self.scale * 100))
                self.zoom_spin.blockSignals(False)

        opacity = self.opacity_spin.value()
        is_visual = (self.combo_mode.currentIndex() == 0)

        # Check Toggles
        show_l = is_visual and self.chk_hl1.isChecked()
        show_r = is_visual and self.chk_hl2.isChecked()

        p1 = self.engine.get_pixmap(1, self.curr_page, self.scale, opacity, show_l)
        p2 = self.engine.get_pixmap(2, self.curr_page, self.scale, opacity, show_r)

        if p1: self.view1.setPixmap(p1)
        if p2: self.view2.setPixmap(p2)

    def resizeEvent(self, event):
        if self.btn_fit.isChecked():
            self._update_render()
        super().resizeEvent(event)


if __name__ == "__main__":
    try:
        # Taskbar icon fix for Windows
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('selim.pdfdiff.tool.1.0')
    except:
        pass

    app = QApplication(sys.argv)
    window = DiffApp()
    window.show()
    sys.exit(app.exec())