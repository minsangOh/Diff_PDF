import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QSplitter,
                             QComboBox, QSpinBox, QFrame, QCheckBox, QMessageBox,
                             QApplication)  # [Update] QApplication 추가
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import Qt, QTimer

from utils.helpers import resource_path
from core.engine import PDFEngine
from ui.widgets import FileDropLabel, SyncedScrollArea


class DiffApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.engine = PDFEngine()

        # State
        self.curr_page = 0
        self.total_pages = 0
        self.scale = 1.0

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

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar Setup
        self.toolbar_widget = QWidget()
        self.toolbar_widget.setFixedHeight(50)
        self.toolbar_widget.setStyleSheet("background-color: #f5f5f5; border-bottom: 1px solid #ddd;")
        tb_layout = QHBoxLayout(self.toolbar_widget)
        tb_layout.setContentsMargins(10, 5, 10, 5)

        self.btn_load1 = QPushButton("File 1")
        self.lbl_file1 = FileDropLabel(1)
        self.lbl_file1.setFixedWidth(200)

        self.btn_load2 = QPushButton("File 2")
        self.lbl_file2 = FileDropLabel(2)
        self.lbl_file2.setFixedWidth(200)

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

        # --- Highlight Checkboxes Customization ---
        chk_style = """
            QCheckBox {
                font-weight: bold;
                color: #888888; /* OFF 상태: 회색 */
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 16px; 
                height: 16px;
            }
            QCheckBox:checked {
                color: #0078D7; /* ON 상태: 파란색 강조 */
            }
        """

        self.chk_hl1 = QCheckBox("Left")
        self.chk_hl1.setChecked(True)
        self.chk_hl1.setToolTip("Show Highlight on Left File")
        self.chk_hl1.setStyleSheet(chk_style)

        self.chk_hl2 = QCheckBox("Right")
        self.chk_hl2.setChecked(True)
        self.chk_hl2.setToolTip("Show Highlight on Right File")
        self.chk_hl2.setStyleSheet(chk_style)
        # ------------------------------------------

        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(0, 100)
        self.opacity_spin.setValue(30)
        self.opacity_spin.setSuffix("%")

        self.btn_compare = QPushButton("RUN COMPARE")
        self.btn_compare.setStyleSheet("background: #0078D7; color: white; font-weight: bold; padding: 4px 10px;")
        self.btn_compare.setEnabled(False)

        # [Capture Button]
        self.btn_capture = QPushButton("📷 Capture")
        self.btn_capture.setStyleSheet("padding: 4px 8px; font-weight: bold;")
        self.btn_capture.setToolTip("Save current view as Image")

        # [New] Clipboard Copy Button
        self.btn_clipboard = QPushButton("📋 Copy")
        self.btn_clipboard.setStyleSheet("padding: 4px 8px; font-weight: bold;")
        self.btn_clipboard.setToolTip("Copy current view to Clipboard")

        items = [
            self.btn_load1, self.lbl_file1, self._sep(),
            self.btn_load2, self.lbl_file2, (None, 1),
            self.combo_mode, self._sep(),
            self.btn_compare, self._sep(),
            self.btn_prev, self.lbl_page, self.btn_next, self._sep(),
            QLabel("Zoom:"), self.zoom_spin, self.btn_fit, self._sep(),
            QLabel("Highlight:"), self.chk_hl1, self.chk_hl2, self._sep(),
            QLabel("Opacity:"), self.opacity_spin, self._sep(),
            self.btn_capture,
            self.btn_clipboard  # Add to toolbar
        ]

        for item in items:
            if isinstance(item, tuple):
                tb_layout.addStretch(item[1])
            elif isinstance(item, QWidget):
                tb_layout.addWidget(item)

        layout.addWidget(self.toolbar_widget)

        # Splitter Setup
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Slot 1 View (Left)
        self.scroll1 = SyncedScrollArea(1)
        self.view1 = QLabel()
        self.view1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view1.setScaledContents(False)
        self.scroll1.setWidget(self.view1)

        # Slot 2 View (Right)
        self.scroll2 = SyncedScrollArea(2)
        self.view2 = QLabel()
        self.view2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view2.setScaledContents(False)
        self.scroll2.setWidget(self.view2)

        self.splitter.addWidget(self.scroll1)
        self.splitter.addWidget(self.scroll2)
        self.splitter.setSizes([700, 700])
        layout.addWidget(self.splitter)

    def _sep(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def _connect_signals(self):
        self.btn_load1.clicked.connect(lambda: self._open_file_dialog(1))
        self.lbl_file1.file_dropped.connect(self._load_file)
        self.scroll1.file_dropped.connect(self._load_file)

        self.btn_load2.clicked.connect(lambda: self._open_file_dialog(2))
        self.lbl_file2.file_dropped.connect(self._load_file)
        self.scroll2.file_dropped.connect(self._load_file)

        self.btn_compare.clicked.connect(self._refresh_comparison)
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        self.combo_mode.currentIndexChanged.connect(self._refresh_comparison)

        self.zoom_spin.valueChanged.connect(self._on_zoom_changed)
        self.btn_fit.clicked.connect(self._update_render)
        self.opacity_spin.valueChanged.connect(self._update_render)
        self.chk_hl1.toggled.connect(self._update_render)
        self.chk_hl2.toggled.connect(self._update_render)

        self.btn_capture.clicked.connect(self._capture_screen)
        self.btn_clipboard.clicked.connect(self._copy_to_clipboard)  # [New] Connect Signal

        s1_v, s2_v = self.scroll1.verticalScrollBar(), self.scroll2.verticalScrollBar()
        s1_h, s2_h = self.scroll1.horizontalScrollBar(), self.scroll2.horizontalScrollBar()
        s1_v.valueChanged.connect(s2_v.setValue)
        s2_v.valueChanged.connect(s1_v.setValue)
        s1_h.valueChanged.connect(s2_h.setValue)
        s2_h.valueChanged.connect(s1_h.setValue)

        self.scroll1.zoom_request.connect(self._handle_wheel_zoom)
        self.scroll2.zoom_request.connect(self._handle_wheel_zoom)

    # --- Logic Handlers (Delegators) ---
    def _open_file_dialog(self, slot: int):
        fpath, _ = QFileDialog.getOpenFileName(self, f"Open PDF {slot}", "", "PDF (*.pdf)")
        if fpath: self._load_file(slot, fpath)

    def _load_file(self, slot: int, path: str):
        self.engine.load_doc(slot, path)
        lbl = self.lbl_file1 if slot == 1 else self.lbl_file2

        filename = os.path.basename(path)
        lbl.setToolTip(filename)

        metrics = lbl.fontMetrics()
        elided_text = metrics.elidedText(filename, Qt.TextElideMode.ElideMiddle, lbl.width() - 20)
        lbl.setText(elided_text)

        lbl.setStyleSheet("border: 2px solid #4CAF50; color: black; font-weight: bold;")

        if self.engine.is_ready():
            self.btn_compare.setEnabled(True)
            self.total_pages = min(len(self.engine.docs[1]), len(self.engine.docs[2]))
            self.curr_page = 0

            self._check_duplicate_files()
            self._refresh_comparison()

    def _check_duplicate_files(self):
        path1 = self.engine.paths.get(1)
        path2 = self.engine.paths.get(2)

        if path1 and path2:
            if path1 == path2:
                QMessageBox.warning(self, "중복 파일 감지",
                                    "양쪽 슬롯에 완전히 동일한 파일(경로 일치)이 로드되었습니다.")
                return

            try:
                if os.path.getsize(path1) != os.path.getsize(path2):
                    return

                with open(path1, 'rb') as f1, open(path2, 'rb') as f2:
                    if f1.read() == f2.read():
                        QMessageBox.warning(self, "중복 파일 감지",
                                            "파일명(경로)은 다르지만 내용이 완벽하게 동일한 파일입니다.")
            except Exception as e:
                print(f"Duplicate check failed: {e}")

    def _capture_screen(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Screenshot", "compare_result.png",
                                                  "PNG Files (*.png);;JPEG Files (*.jpg)")
        if filename:
            try:
                screenshot = self.splitter.grab()
                if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    filename += '.png'
                screenshot.save(filename)
                QMessageBox.information(self, "Success", f"Screenshot saved to:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save screenshot:\n{str(e)}")

    # [New] Copy to Clipboard Logic
    def _copy_to_clipboard(self):
        try:
            screenshot = self.splitter.grab()
            QApplication.clipboard().setPixmap(screenshot)
            QMessageBox.information(self, "Success", "Current view copied to clipboard!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to copy to clipboard:\n{str(e)}")

    def _handle_wheel_zoom(self, delta):
        self.btn_fit.setChecked(False)
        step = 10 if delta > 0 else -10
        self.zoom_spin.setValue(max(10, min(500, self.zoom_spin.value() + step)))

    def _on_zoom_changed(self):
        self.btn_fit.setChecked(False)
        self.scale = self.zoom_spin.value() / 100.0

        if self.engine.is_ready():
            self.view1.setScaledContents(True)
            self.view2.setScaledContents(True)

            page_w, page_h = self.engine.get_page_size(1, self.curr_page)
            if page_w > 0:
                new_w = int(page_w * self.scale)
                new_h = int(page_h * self.scale)
                self.view1.setFixedSize(new_w, new_h)
                self.view2.setFixedSize(new_w, new_h)

        self.render_timer.start(50)

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

        if self.combo_mode.currentIndex() == 0:
            self.engine.compare_visual(self.curr_page)
        else:
            print(self.engine.compare_text(self.curr_page))
        self._update_render()

    def _update_render(self):
        if not self.engine.is_ready(): return

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
        show_l = is_visual and self.chk_hl1.isChecked()
        show_r = is_visual and self.chk_hl2.isChecked()

        p1 = self.engine.get_pixmap(1, self.curr_page, self.scale, opacity, show_l)
        p2 = self.engine.get_pixmap(2, self.curr_page, self.scale, opacity, show_r)

        self.view1.setScaledContents(False)
        self.view2.setScaledContents(False)

        if p1:
            self.view1.setFixedSize(p1.width(), p1.height())
            self.view1.setPixmap(p1)
        if p2:
            self.view2.setFixedSize(p2.width(), p2.height())
            self.view2.setPixmap(p2)

    def resizeEvent(self, event):
        if self.btn_fit.isChecked(): self._update_render()
        super().resizeEvent(event)