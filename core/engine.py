import fitz
import difflib
import numpy as np
from typing import Tuple, Optional
from PIL import Image, ImageChops

from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor
from PyQt6.QtCore import Qt, QRectF

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
        self.diff_boxes = []
        doc1, doc2 = self.docs[1], self.docs[2]

        if not doc1 or not doc2: return
        if page_num >= len(doc1) or page_num >= len(doc2): return

        pix1 = doc1[page_num].get_pixmap(matrix=fitz.Matrix(1, 1))
        pix2 = doc2[page_num].get_pixmap(matrix=fitz.Matrix(1, 1))

        if (pix1.width, pix1.height) != (pix2.width, pix2.height):
            return

        img1 = Image.frombytes("RGB", [pix1.width, pix1.height], pix1.samples)
        img2 = Image.frombytes("RGB", [pix2.width, pix2.height], pix2.samples)

        diff = ImageChops.difference(img1, img2)
        if not diff.getbbox():
            return

        diff_arr = np.array(diff.convert("L"))
        h, w = diff_arr.shape
        grid = self.grid_size

        pad_h = (grid - h % grid) % grid
        pad_w = (grid - w % grid) % grid
        if pad_h or pad_w:
            diff_arr = np.pad(diff_arr, ((0, pad_h), (0, pad_w)), mode='constant')

        new_h, new_w = diff_arr.shape
        blocks = diff_arr.reshape(new_h // grid, grid, new_w // grid, grid)
        block_max = blocks.max(axis=(1, 3))

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

        pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(scale, scale))
        fmt = QImage.Format.Format_RGB888
        qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()

        if show_diff and self.diff_boxes and opacity > 0:
            with QPainter(qimg) as p:
                p.setBrush(QColor(255, 0, 0, int(opacity * 2.55)))
                p.setPen(Qt.PenStyle.NoPen)
                for x, y, w, h in self.diff_boxes:
                    p.drawRect(QRectF(x * scale, y * scale, w * scale, h * scale))

        return QPixmap.fromImage(qimg)