from PyQt6.QtWidgets import QLabel, QScrollArea
from PyQt6.QtCore import Qt, pyqtSignal

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

        super().wheelEvent(e)