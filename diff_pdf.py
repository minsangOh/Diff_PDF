import sys
import os
import ctypes
import fitz
import difflib
import numpy as np
from PIL import Image, ImageChops
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFileDialog,
                             QSplitter, QComboBox, QScrollArea, QSpinBox)
from PyQt6.QtGui import QPixmap, QImage, QIcon, QPainter, QColor, QPen
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class PDFComparator:
    def __init__(self):
        self.doc1 = None
        self.doc2 = None
        self.doc1_path = ""
        self.doc2_path = ""
        self.grid_size = 5

        self.cached_diff_boxes = []
        self.is_analyzed = False

    def load_file1(self, path):
        self.doc1_path = path
        self.doc1 = fitz.open(path)
        self.is_analyzed = False
        return len(self.doc1)

    def load_file2(self, path):
        self.doc2_path = path
        self.doc2 = fitz.open(path)
        self.is_analyzed = False
        return len(self.doc2)

    def get_page_size(self, doc_idx, page_num):
        doc = self.doc1 if doc_idx == 1 else self.doc2
        if not doc or page_num >= len(doc):
            return (0, 0)
        rect = doc[page_num].rect
        return (rect.width, rect.height)

    def analyze_visual_diff(self, page_num):
        self.cached_diff_boxes = []
        self.is_analyzed = True

        if not self.doc1 or not self.doc2: return True
        if page_num >= len(self.doc1) or page_num >= len(self.doc2): return False

        pix1 = self.doc1[page_num].get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
        pix2 = self.doc2[page_num].get_pixmap(matrix=fitz.Matrix(1.0, 1.0))

        if (pix1.width, pix1.height) != (pix2.width, pix2.height):
            return False

        img1 = Image.frombytes("RGB", [pix1.width, pix1.height], pix1.samples)
        img2 = Image.frombytes("RGB", [pix2.width, pix2.height], pix2.samples)

        diff = ImageChops.difference(img1, img2)
        if not diff.getbbox():
            return True

        diff_l = diff.convert("L")
        arr = np.array(diff_l)
        h, w = arr.shape
        grid = self.grid_size

        pad_h = (grid - h % grid) % grid
        pad_w = (grid - w % grid) % grid
        if pad_h > 0 or pad_w > 0:
            arr = np.pad(arr, ((0, pad_h), (0, pad_w)), mode='constant', constant_values=0)

        new_h, new_w = arr.shape
        view = arr.reshape(new_h // grid, grid, new_w // grid, grid)
        block_max = view.max(axis=(1, 3))

        y_indices, x_indices = np.where(block_max > 20)

        for y_idx, x_idx in zip(y_indices, x_indices):
            x = int(x_idx * grid)
            y = int(y_idx * grid)
            if x < w and y < h:
                rw = min(grid, w - x)
                rh = min(grid, h - y)
                self.cached_diff_boxes.append((x, y, rw, rh))

        return False

    def get_rendered_pixmap(self, doc_idx, page_num, scale, opacity_percent, draw_diffs=False):
        doc = self.doc1 if doc_idx == 1 else self.doc2
        if not doc or page_num >= len(doc):
            return None

        page = doc[page_num]
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat)

        fmt = QImage.Format.Format_RGB888
        qt_img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()

        if draw_diffs and self.cached_diff_boxes and opacity_percent > 0:
            painter = QPainter(qt_img)
            color = QColor(255, 0, 0, int(opacity_percent * 2.55))
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)

            for (x, y, w, h) in self.cached_diff_boxes:
                rect = QRectF(x * scale, y * scale, w * scale, h * scale)
                painter.drawRect(rect)

            painter.end()

        return QPixmap.fromImage(qt_img)

    def compare_text(self, page_num):
        if page_num >= len(self.doc1) or page_num >= len(self.doc2):
            return False, "Page count mismatch"
        text1 = self.doc1[page_num].get_text("text")
        text2 = self.doc2[page_num].get_text("text")
        matcher = difflib.SequenceMatcher(None, text1, text2)
        ratio = matcher.ratio()
        return ratio == 1.0, f"Match: {ratio * 100:.2f}%"


class DroppableLabel(QLabel):
    file_dropped = pyqtSignal(int, str)

    def __init__(self, file_id, parent=None):
        super().__init__(parent)
        self.file_id = file_id
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith('.pdf'):
                    event.accept();
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith('.pdf'):
                self.file_dropped.emit(self.file_id, path);
                break


class ZoomableScrollArea(QScrollArea):
    zoom_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.last_pos = None
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor);
            self.last_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.last_pos and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.pos() - self.last_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self.last_pos = event.pos()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor);
        self.last_pos = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.zoom_signal.emit(event.angleDelta().y());
            event.accept();
            return

        dx, dy = event.angleDelta().x(), event.angleDelta().y()
        if event.modifiers() == Qt.KeyboardModifier.ShiftModifier and dx == 0 and dy != 0: dx = dy; dy = 0
        if dx != 0:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - dx);
            event.accept()
        elif dy != 0:
            super().wheelEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.comparator = PDFComparator()
        self.current_page = 0
        self.total_pages = 0
        self.zoom_scale = 1.0

        self.zoom_timer = QTimer()
        self.zoom_timer.setSingleShot(True)
        self.zoom_timer.timeout.connect(self.refresh_view)

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Diff PDF_SELIM")
        self.resize(1400, 900)
        if os.path.exists(resource_path("diff_icon.ico")):
            self.setWindowIcon(QIcon(resource_path("diff_icon.ico")))

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(5, 5, 5, 5)
        toolbar.setSpacing(10)

        self.btn_f1 = QPushButton("File 1")
        self.btn_f1.clicked.connect(lambda: self.open_file(1))
        self.lbl_f1 = DroppableLabel(1)
        self.lbl_f1.setText("(Drop PDF)")
        self.lbl_f1.file_dropped.connect(self.load_file_path)
        self.lbl_f1.setStyleSheet("border:1px dashed #aaa; padding:2px; color:gray")

        self.btn_f2 = QPushButton("File 2")
        self.btn_f2.clicked.connect(lambda: self.open_file(2))
        self.lbl_f2 = DroppableLabel(2)
        self.lbl_f2.setText("(Drop PDF)")
        self.lbl_f2.file_dropped.connect(self.load_file_path)
        self.lbl_f2.setStyleSheet("border:1px dashed #aaa; padding:2px; color:gray")

        self.mode = QComboBox()
        self.mode.addItems(["Visual Diff", "Text Diff"])
        self.mode.currentIndexChanged.connect(self.refresh_full)

        self.btn_prev = QPushButton("◀")
        self.btn_prev.setFixedWidth(30)
        self.btn_prev.clicked.connect(self.prev_page)
        self.lbl_page = QLabel("0/0")
        self.lbl_page.setFixedWidth(50)
        self.lbl_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_next = QPushButton("▶")
        self.btn_next.setFixedWidth(30)
        self.btn_next.clicked.connect(self.next_page)

        self.btn_zout = QPushButton("-")
        self.btn_zout.setFixedWidth(30)
        self.btn_zout.clicked.connect(self.zoom_out)
        self.spin_zoom = QSpinBox()
        self.spin_zoom.setRange(10, 500)
        self.spin_zoom.setSingleStep(10)
        self.spin_zoom.setValue(100)
        self.spin_zoom.setSuffix("%")
        self.spin_zoom.setFixedWidth(70)
        self.spin_zoom.setKeyboardTracking(False)
        self.spin_zoom.valueChanged.connect(self.on_zoom_change)
        self.btn_zin = QPushButton("+")
        self.btn_zin.setFixedWidth(30)
        self.btn_zin.clicked.connect(self.zoom_in)

        self.btn_fit = QPushButton("Fit")
        self.btn_fit.setCheckable(True)
        self.btn_fit.clicked.connect(self.toggle_fit)

        self.lbl_op = QLabel("Opacity:")
        self.spin_op = QSpinBox()
        self.spin_op.setRange(0, 100);
        self.spin_op.setValue(30)
        self.spin_op.setSuffix("%")
        self.spin_op.setFixedWidth(60)
        self.spin_op.valueChanged.connect(self.refresh_view)

        self.btn_cmp = QPushButton("COMPARE")
        self.btn_cmp.setStyleSheet("background:#2196F3;color:white;font-weight:bold")
        self.btn_cmp.clicked.connect(self.refresh_full)
        self.btn_cmp.setEnabled(False)

        widgets = [self.btn_f1, self.lbl_f1, QLabel("|"), self.btn_f2, self.lbl_f2, (None, 1),
                   self.mode, self.btn_cmp, QLabel("|"), self.btn_prev, self.lbl_page, self.btn_next, QLabel("|"),
                   QLabel("Z:"), self.btn_zout, self.spin_zoom, self.btn_zin, self.btn_fit, QLabel("|"), self.lbl_op,
                   self.spin_op]

        for w in widgets:
            if isinstance(w, tuple):
                toolbar.addStretch(w[1])
            else:
                toolbar.addWidget(w)

        top_con = QWidget()
        top_con.setLayout(toolbar)
        top_con.setFixedHeight(50)
        top_con.setStyleSheet("background:#f0f0f0; border-bottom:1px solid #ccc")
        main_layout.addWidget(top_con)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.scr1 = ZoomableScrollArea()
        self.view1 = DroppableLabel(1)
        self.view1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view1.file_dropped.connect(self.load_file_path)
        self.scr1.setWidget(self.view1)

        self.scr2 = ZoomableScrollArea()
        self.view2 = DroppableLabel(2)
        self.view2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view2.file_dropped.connect(self.load_file_path)
        self.scr2.setWidget(self.view2)

        splitter.addWidget(self.scr1)
        splitter.addWidget(self.scr2)
        splitter.setSizes([700, 700])
        main_layout.addWidget(splitter)

        self.scr1.verticalScrollBar().valueChanged.connect(self.scr2.verticalScrollBar().setValue)
        self.scr2.verticalScrollBar().valueChanged.connect(self.scr1.verticalScrollBar().setValue)
        self.scr1.horizontalScrollBar().valueChanged.connect(self.scr2.horizontalScrollBar().setValue)
        self.scr2.horizontalScrollBar().valueChanged.connect(self.scr1.horizontalScrollBar().setValue)
        self.scr1.zoom_signal.connect(self.handle_wheel_zoom)
        self.scr2.zoom_signal.connect(self.handle_wheel_zoom)

    def open_file(self, num):
        f, _ = QFileDialog.getOpenFileName(self, f"File {num}", "", "PDF (*.pdf)")
        if f: self.load_file_path(num, f)

    def load_file_path(self, num, path):
        lbl = self.lbl_f1 if num == 1 else self.lbl_f2
        loader = self.comparator.load_file1 if num == 1 else self.comparator.load_file2
        loader(path)
        sname = path.split('/')[-1]
        lbl.setText(sname[:15] + "..." if len(sname) > 18 else sname)
        lbl.setToolTip(path)
        lbl.setStyleSheet("color:black; border:1px solid #aaa; padding:2px; font-weight:bold")

        if self.comparator.doc1 and self.comparator.doc2:
            self.btn_cmp.setEnabled(True)
            self.total_pages = min(len(self.comparator.doc1), len(self.comparator.doc2))
            self.current_page = 0
            self.btn_fit.setChecked(False)
            self.spin_zoom.setValue(100)
            self.refresh_full()

    def handle_wheel_zoom(self, delta):
        self.btn_fit.setChecked(False)
        step = 10 if delta > 0 else -10
        val = max(10, min(500, self.spin_zoom.value() + step))
        self.spin_zoom.blockSignals(True)
        self.spin_zoom.setValue(val)
        self.spin_zoom.blockSignals(False)
        self.zoom_scale = val / 100.0

        self.zoom_timer.start(100)

    def on_zoom_change(self):
        self.btn_fit.setChecked(False)
        self.refresh_view()

    def zoom_in(self):
        self.spin_zoom.stepUp()

    def zoom_out(self):
        self.spin_zoom.stepDown()

    def toggle_fit(self):
        self.refresh_view()

    def prev_page(self):
        if self.current_page > 0: self.current_page -= 1; self.refresh_full()

    def next_page(self):
        if self.current_page < self.total_pages - 1: self.current_page += 1; self.refresh_full()

    def calculate_fit(self):
        if not self.comparator.doc1: return 1.0
        w, _ = self.comparator.get_page_size(1, self.current_page)
        return (self.scr1.viewport().width() - 10) / w if w > 0 else 1.0

    def refresh_full(self):
        if not self.comparator.doc1 or not self.comparator.doc2: return
        self.lbl_page.setText(f"{self.current_page + 1}/{self.total_pages}")

        if self.mode.currentIndex() == 0:
            is_match = self.comparator.analyze_visual_diff(self.current_page)
        else:
            match, msg = self.comparator.compare_text(self.current_page)

        self.refresh_view()

    def refresh_view(self):
        if not self.comparator.doc1 or not self.comparator.doc2: return

        if self.btn_fit.isChecked():
            scale = self.calculate_fit()
            self.spin_zoom.blockSignals(True)
            self.spin_zoom.setValue(int(scale * 100));
            self.spin_zoom.blockSignals(False)
            self.zoom_scale = scale
        else:
            self.zoom_scale = self.spin_zoom.value() / 100.0

        op = self.spin_op.value()
        draw_diff = (self.mode.currentIndex() == 0)

        pix1 = self.comparator.get_rendered_pixmap(1, self.current_page, self.zoom_scale, op, draw_diff)
        pix2 = self.comparator.get_rendered_pixmap(2, self.current_page, self.zoom_scale, op, draw_diff)

        self.view1.setPixmap(pix1)
        self.view2.setPixmap(pix2)

    def resizeEvent(self, e):
        if self.btn_fit.isChecked(): self.refresh_view()
        super().resizeEvent(e)


if __name__ == "__main__":
    try:
        myappid = 'selim.diffpdf.version.1.0.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("diff_icon.ico")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
