import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QSplitter,
                             QComboBox, QSpinBox, QFrame, QCheckBox, QMessageBox,
                             QApplication)
from PyQt6.QtGui import QIcon, QPixmap, QCursor
from PyQt6.QtCore import Qt, QTimer

from utils.helpers import resource_path
from core.engine import PDFEngine
from ui.widgets import SyncedScrollArea  # [Update] FileDropLabel 제거


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

        # [Fix] 100ms 딜레이 후 위치 보정
        QTimer.singleShot(100, self._center_on_active_screen)

    def _init_ui(self):
        self.setWindowTitle("Selim PDF Diff Tool v1.1")

        # 초기 안전 크기
        self.resize(1000, 700)

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

        # [UX Update] DropLabel 제거 및 버튼만 유지
        self.btn_load1 = QPushButton("File 1 (Open)")
        self.btn_load1.setFixedWidth(150)  # 너비 약간 확보

        self.btn_load2 = QPushButton("File 2 (Open)")
        self.btn_load2.setFixedWidth(150)

        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Visual Diff"])

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
                color: #888888;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 16px; 
                height: 16px;
            }
            QCheckBox:checked {
                color: #0078D7;
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

        self.btn_capture = QPushButton("📷 Capture")
        self.btn_capture.setStyleSheet("padding: 4px 8px; font-weight: bold;")
        self.btn_capture.setToolTip("Save current view as Image")

        self.btn_clipboard = QPushButton("📋 Copy")
        self.btn_clipboard.setStyleSheet("padding: 4px 8px; font-weight: bold;")
        self.btn_clipboard.setToolTip("Copy current view to Clipboard")

        # [UX Update] Toolbar Items 재구성 (라벨 제거)
        items = [
            self.btn_load1, self._sep(),
            self.btn_load2, (None, 1),  # Spacer
            self.combo_mode, self._sep(),
            self.btn_prev, self.lbl_page, self.btn_next, self._sep(),
            QLabel("Zoom:"), self.zoom_spin, self.btn_fit, self._sep(),
            QLabel("Highlight:"), self.chk_hl1, self.chk_hl2, self._sep(),
            QLabel("Opacity:"), self.opacity_spin, self._sep(),
            self.btn_capture,
            self.btn_clipboard
        ]

        for item in items:
            if isinstance(item, tuple):
                tb_layout.addStretch(item[1])
            elif isinstance(item, QWidget):
                tb_layout.addWidget(item)

        layout.addWidget(self.toolbar_widget)

        # Splitter Setup
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # [UX Update] 뷰어 초기 상태 설정 (Drop 안내 문구)
        placeholder_style = """
            QLabel {
                color: #aaaaaa;
                font-size: 24px;
                font-weight: bold;
                border: 3px dashed #e0e0e0;
                background-color: #fafafa;
            }
        """

        # Slot 1 View (Left)
        self.scroll1 = SyncedScrollArea(1)
        self.view1 = QLabel("Drop PDF Here\n(File 1)")
        self.view1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view1.setStyleSheet(placeholder_style)
        self.view1.setScaledContents(False)
        self.scroll1.setWidget(self.view1)

        # Slot 2 View (Right)
        self.scroll2 = SyncedScrollArea(2)
        self.view2 = QLabel("Drop PDF Here\n(File 2)")
        self.view2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view2.setStyleSheet(placeholder_style)
        self.view2.setScaledContents(False)
        self.scroll2.setWidget(self.view2)

        self.splitter.addWidget(self.scroll1)
        self.splitter.addWidget(self.scroll2)
        self.splitter.setSizes([700, 700])
        layout.addWidget(self.splitter)

    # ... (기존 _center_on_active_screen, _sep 등 유지) ...
    def _center_on_active_screen(self):
        cursor_pos = QCursor.pos()
        screen = QApplication.screenAt(cursor_pos)
        if not screen:
            screen = QApplication.primaryScreen()
        if not screen: return

        avail_geo = screen.availableGeometry()

        max_w = avail_geo.width() - 50
        max_h = avail_geo.height() - 50
        target_w = int(avail_geo.width() * 0.7)
        target_h = int(avail_geo.height() * 0.7)

        target_w = max(1000, min(target_w, max_w))
        target_h = max(700, min(target_h, max_h))

        self.resize(target_w, target_h)

        center_x = avail_geo.x() + (avail_geo.width() - target_w) // 2
        center_y = avail_geo.y() + (avail_geo.height() - target_h) // 2
        self.move(center_x, center_y)

        frame_geo = self.frameGeometry()
        if frame_geo.right() > avail_geo.right():
            offset = frame_geo.right() - avail_geo.right()
            self.move(self.x() - offset, self.y())
        if frame_geo.bottom() > avail_geo.bottom():
            offset = frame_geo.bottom() - avail_geo.bottom()
            self.move(self.x(), self.y() - offset)
        if self.x() < avail_geo.x():
            self.move(avail_geo.x(), self.y())
        if self.y() < avail_geo.y():
            self.move(self.x(), avail_geo.y())

    def _sep(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def _connect_signals(self):
        self.btn_load1.clicked.connect(lambda: self._open_file_dialog(1))
        # [Update] lbl_file1 시그널 제거 (객체가 삭제됨)
        self.scroll1.file_dropped.connect(self._load_file)

        self.btn_load2.clicked.connect(lambda: self._open_file_dialog(2))
        # [Update] lbl_file2 시그널 제거 (객체가 삭제됨)
        self.scroll2.file_dropped.connect(self._load_file)

        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        self.combo_mode.currentIndexChanged.connect(self._refresh_comparison)

        self.zoom_spin.valueChanged.connect(self._on_zoom_changed)
        self.btn_fit.clicked.connect(self._update_render)
        self.opacity_spin.valueChanged.connect(self._update_render)
        self.chk_hl1.toggled.connect(self._update_render)
        self.chk_hl2.toggled.connect(self._update_render)

        self.btn_capture.clicked.connect(self._capture_screen)
        self.btn_clipboard.clicked.connect(self._copy_to_clipboard)

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

        # [UX Update] 버튼 텍스트에 파일명 표시
        filename = os.path.basename(path)
        btn = self.btn_load1 if slot == 1 else self.btn_load2

        btn.setToolTip(filename)
        metrics = btn.fontMetrics()
        # 버튼 너비에 맞춰 텍스트 줄임 (...)
        elided_text = metrics.elidedText(filename, Qt.TextElideMode.ElideMiddle, btn.width() - 20)
        btn.setText(elided_text)

        # 버튼 스타일 강조 (로드됨 표시)
        btn.setStyleSheet("border: 2px solid #4CAF50; color: #4CAF50; font-weight: bold;")

        # [UX Fix] 파일 하나만 로드돼도 일단 보여주기 위해 조건 완화
        # 기존: if self.engine.is_ready(): ...
        # 변경: 일단 렌더링 시도 (is_ready가 아니면 비교만 안함)

        # 전체 페이지 수는 둘 다 로드되었을 때만 계산 가능 (아니면 현재 로드된 것 기준)
        doc1_len = len(self.engine.docs[1]) if self.engine.docs[1] else 0
        doc2_len = len(self.engine.docs[2]) if self.engine.docs[2] else 0

        if self.engine.is_ready():
            self.total_pages = min(doc1_len, doc2_len)
            self.curr_page = 0
            self._check_duplicate_files()
            self._refresh_comparison()
        else:
            # 하나만 로드된 상태라도 보여주기
            self.total_pages = max(doc1_len, doc2_len)
            self.curr_page = 0
            self.lbl_page.setText(f"{self.curr_page + 1} / {self.total_pages}")
            self._update_render()  # 강제 렌더링 호출

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

        # [Update] is_ready() 체크 제거 -> 개별 파일만 있어도 줌 가능하게
        self.view1.setScaledContents(True)
        self.view2.setScaledContents(True)

        page_w, page_h = self.engine.get_page_size(1, self.curr_page)
        # 1번 없으면 2번 크기라도 참조
        if page_w == 0:
            page_w, page_h = self.engine.get_page_size(2, self.curr_page)

        if page_w > 0:
            new_w = int(page_w * self.scale)
            new_h = int(page_h * self.scale)
            self.view1.setFixedSize(new_w, new_h)
            self.view2.setFixedSize(new_w, new_h)

        self.render_timer.start(50)

    def _prev_page(self):
        if self.curr_page > 0:
            self.curr_page -= 1
            if self.engine.is_ready():
                self._refresh_comparison()
            else:
                self.lbl_page.setText(f"{self.curr_page + 1} / {self.total_pages}")
                self._update_render()

    def _next_page(self):
        if self.curr_page < self.total_pages - 1:
            self.curr_page += 1
            if self.engine.is_ready():
                self._refresh_comparison()
            else:
                self.lbl_page.setText(f"{self.curr_page + 1} / {self.total_pages}")
                self._update_render()

    def _refresh_comparison(self):
        # [Update] 비교 로직은 둘 다 있을 때만 실행
        if not self.engine.is_ready(): return

        self.lbl_page.setText(f"{self.curr_page + 1} / {self.total_pages}")

        if self.combo_mode.currentIndex() == 0:
            self.engine.compare_visual(self.curr_page)
        else:
            print(self.engine.compare_text(self.curr_page))
        self._update_render()

    def _update_render(self):
        # [Update] is_ready 체크 제거 -> 개별 파일 렌더링 허용
        # if not self.engine.is_ready(): return

        if self.btn_fit.isChecked():
            page_w, _ = self.engine.get_page_size(1, self.curr_page)
            if page_w == 0: page_w, _ = self.engine.get_page_size(2, self.curr_page)

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

        # Engine.get_pixmap은 문서가 없으면 None을 리턴하므로 안전함
        p1 = self.engine.get_pixmap(1, self.curr_page, self.scale, opacity, show_l)
        p2 = self.engine.get_pixmap(2, self.curr_page, self.scale, opacity, show_r)

        self.view1.setScaledContents(False)
        self.view2.setScaledContents(False)

        # Pixmap이 있으면 이미지 표시, 없으면 Drop 안내 유지
        if p1:
            self.view1.setStyleSheet("")  # 테두리 제거
            self.view1.setFixedSize(p1.width(), p1.height())
            self.view1.setPixmap(p1)

        if p2:
            self.view2.setStyleSheet("")  # 테두리 제거
            self.view2.setFixedSize(p2.width(), p2.height())
            self.view2.setPixmap(p2)

    def resizeEvent(self, event):
        if self.btn_fit.isChecked(): self._update_render()
        super().resizeEvent(event)