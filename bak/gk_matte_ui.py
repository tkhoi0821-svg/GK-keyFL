"""Hop thoai Tach nen: chroma key (hut mau tu anh) hoac AI, xem truoc truc tiep, ap vao lop dang chon."""
import os
import numpy as np
from PySide6.QtCore import Qt, QRectF, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap, QImage, QCursor
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QComboBox,
                             QColorDialog, QMessageBox, QWidget, QFrame)
import gk_theme as theme
from gk_theme import T, mk
from gk_panels import styled, Section, ScrubSpin
import gk_matting as M


class PreviewLabel(QWidget):
    """Anh xem truoc tren nen co-ban cho thay do trong suot; bam de hut mau."""
    picked = Signal(int, int, int)

    def __init__(self):
        super().__init__()
        self.pm = None
        self.setMinimumSize(320, 220)
        self.setCursor(Qt.CrossCursor)

    def set_pixmap(self, pm):
        self.pm = pm
        self.update()

    def fit_rect(self):
        if self.pm is None or self.pm.isNull():
            return QRectF(0, 0, 0, 0)
        w, h = self.pm.width(), self.pm.height()
        s = min(self.width() / w, self.height() / h)
        rw, rh = w * s, h * s
        return QRectF((self.width() - rw) / 2, (self.height() - rh) / 2, rw, rh)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(T["bg0"]))
        s = 14
        for i in range(self.width() // s + 1):
            for j in range(self.height() // s + 1):
                p.fillRect(i * s, j * s, s, s, QColor(T["checker_a"] if (i + j) % 2 else T["checker_b"]))
        if self.pm is not None and not self.pm.isNull():
            p.drawPixmap(self.fit_rect(), self.pm, QRectF(self.pm.rect()))

    def mousePressEvent(self, e):
        r = self.fit_rect()
        if self.pm is None or not r.contains(e.pos()):
            return
        x = int((e.x() - r.left()) / r.width() * self.pm.width())
        y = int((e.y() - r.top()) / r.height() * self.pm.height())
        img = self.pm.toImage().convertToFormat(QImage.Format_RGB888)
        if 0 <= x < img.width() and 0 <= y < img.height():
            c = img.pixelColor(x, y)
            self.picked.emit(c.red(), c.green(), c.blue())


class MatteDialog(QDialog):
    """Tach nen cho 1 lop anh (chroma key hoac AI) + xem truoc, roi ghi lai alpha vao chinh anh cua lop."""
    applied = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tách nền")
        self.resize(820, 540)
        self.layer, self.src_rgb, self.base_rgba = None, None, None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(self.recompute)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(14)
        self.prev = PreviewLabel()
        root.addWidget(self.prev, 1)

        side = QWidget()
        side.setFixedWidth(260)
        sv = QVBoxLayout(side)
        sv.setSpacing(10)
        self.name_lbl = QLabel("Chưa chọn lớp")
        self.name_lbl.setObjectName("Title")
        sv.addWidget(self.name_lbl)

        s1 = Section("Phương pháp")
        self.method = QComboBox()
        self.method.addItem("Xoá theo màu nền (Chroma key)", "chroma")
        self.method.addItem("Tự động bằng AI", "ai")
        s1.bl.addWidget(self.method)
        self.ai_hint = QLabel("")
        self.ai_hint.setObjectName("Hint")
        self.ai_hint.setWordWrap(True)
        s1.bl.addWidget(self.ai_hint)
        sv.addWidget(s1)

        self.s2 = Section("Màu nền")
        row = QHBoxLayout()
        self.swatch = QPushButton()
        self.swatch.setFixedSize(30, 26)
        self.pick_btn = QPushButton("Hút màu trên ảnh")
        self.pick_btn.setObjectName("SmallBtn")
        row.addWidget(self.swatch)
        row.addWidget(self.pick_btn, 1)
        self.s2.bl.addLayout(row)
        self.tol = self._slider(self.s2, "Dung sai màu", 0, 100, 25)
        self.soft = self._slider(self.s2, "Độ mềm biên", 0, 100, 15)
        self.spill = self._slider(self.s2, "Khử viền ám màu", 0, 100, 60)
        sv.addWidget(self.s2)

        self.s3 = Section("Tinh chỉnh mép")
        self.grow = self._slider(self.s3, "Nở / co mép", -20, 20, 0)
        self.feather = self._slider(self.s3, "Làm mềm mép", 0, 20, 2)
        sv.addWidget(self.s3)
        sv.addStretch()

        foot = QHBoxLayout()
        self.apply_btn = QPushButton("Áp dụng")
        self.apply_btn.setObjectName("Accent")
        self.cancel_btn = QPushButton("Đóng")
        foot.addStretch()
        foot.addWidget(self.cancel_btn)
        foot.addWidget(self.apply_btn)
        sv.addLayout(foot)
        root.addWidget(side)

        self.bg_col = (20, 200, 40)
        self._swatch_col()
        self.method.currentIndexChanged.connect(self._method)
        self.pick_btn.clicked.connect(self._pick_mode)
        self.swatch.clicked.connect(self._choose_color)
        self.prev.picked.connect(self._picked)
        for s, _ in (self.tol, self.soft, self.spill, self.grow, self.feather):
            s.valueChanged.connect(self._debounce.start)
        self.apply_btn.clicked.connect(self.apply)
        self.cancel_btn.clicked.connect(self.close)
        self._method(0)

    def _slider(self, sec, label, lo, hi, val):
        row = QHBoxLayout()
        lab = QLabel(label)
        lab.setObjectName("Sub")
        lab.setFixedWidth(108)
        sl = QSlider(Qt.Horizontal)
        sl.setRange(lo, hi)
        sl.setValue(val)
        vlab = QLabel(str(val))
        vlab.setFixedWidth(28)
        vlab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sl.valueChanged.connect(lambda v: vlab.setText(str(v)))
        row.addWidget(lab)
        row.addWidget(sl, 1)
        row.addWidget(vlab)
        sec.bl.addLayout(row)
        return sl, vlab

    def _swatch_col(self):
        self.swatch.setStyleSheet("background:rgb(%d,%d,%d);border-radius:5px;border:1px solid %s;" % (*self.bg_col, T["line"]))

    def _choose_color(self):
        c = QColorDialog.getColor(QColor(*self.bg_col), self)
        if c.isValid():
            self.bg_col = (c.red(), c.green(), c.blue())
            self._swatch_col()
            self.recompute()

    def _pick_mode(self):
        QMessageBox.information(self, "Hút màu", "Bấm vào vùng nền trên ảnh xem trước để lấy màu nền.")

    def _picked(self, r, g, b):
        self.bg_col = (r, g, b)
        self._swatch_col()
        self.recompute()

    def _method(self, _):
        ai = self.method.currentData() == "ai"
        self.s2.setVisible(not ai)
        ok, why = M.ai_available()
        self.ai_hint.setText("" if (not ai) else (why if not ok else "Dùng mạng U2-Net chạy cục bộ, không cần mạng."))
        self.apply_btn.setEnabled(not ai or ok)
        self.recompute()

    # ---------------------------------------------------------------- du lieu
    def set_layer(self, L):
        self.layer = L
        self.name_lbl.setText(L.name if L else "Chưa chọn lớp")
        ok = bool(L and L.pix is not None and not L.pix.isNull())
        for w in (self.method, self.tol[0], self.soft[0], self.spill[0], self.grow[0], self.feather[0], self.apply_btn):
            w.setEnabled(ok and (w is not self.method or True))
        if not ok:
            self.prev.set_pixmap(None)
            self.src_rgb = self.base_rgba = None
            return
        img = L.pix.toImage().convertToFormat(QImage.Format_RGBA8888)
        self.base_rgba = M.qimage_to_rgba(img)
        self.src_rgb = self.base_rgba[..., :3]
        self.prev.set_pixmap(L.pix)
        self._method(0)

    def recompute(self):
        if self.src_rgb is None:
            return
        method = self.method.currentData()
        if method == "ai":
            ok, _ = M.ai_available()
            if not ok:
                self.prev.set_pixmap(QPixmap.fromImage(M.rgba_to_qimage(self.base_rgba)))
                return
            try:
                alpha = M.ai_alpha(self.src_rgb)
            except Exception as ex:
                QMessageBox.warning(self, "Lỗi AI", str(ex))
                self.method.setCurrentIndex(0)
                return
        else:
            tol, soft = self.tol[0].value() / 100.0, max(1, self.soft[0].value()) / 100.0
            alpha = M.chroma_alpha(self.src_rgb, self.bg_col, tol, soft)   # 0 = giong nen (bi xoa), 1 = giu lai
        alpha = M.refine(alpha, self.grow[0].value(), self.feather[0].value())
        rgb = self.src_rgb
        if method == "chroma" and self.spill[0].value() > 0:
            rgb = M.despill(rgb, self.bg_col, self.spill[0].value() / 100.0)
        out = np.dstack([rgb, self.base_rgba[..., 3]])
        out = M.apply_alpha(out, alpha, multiply=True)
        self.prev.set_pixmap(QPixmap.fromImage(M.rgba_to_qimage(out)))
        self._last = out

    def apply(self):
        if self.layer is None or self.src_rgb is None or not hasattr(self, "_last"):
            self.recompute()
        if self.layer is not None and hasattr(self, "_last"):
            self.layer.pix = QPixmap.fromImage(M.rgba_to_qimage(self._last))
            self.applied.emit()
            self.close()
