"""Cac panel cua editor: Canvas, Lop, Thuoc tinh, Assets, Lenh + khung dock."""
import math
from PyQt5.QtCore import Qt, QRectF, QPointF, QSize, QEvent, pyqtSignal
from PyQt5.QtGui import (QColor, QPainter, QPen, QBrush, QFont, QPixmap, QIcon, QLinearGradient, QPainterPath,
                         QPolygonF, QFontMetrics, QTransform)
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QSlider,
                             QDoubleSpinBox, QComboBox, QLineEdit, QPlainTextEdit, QCheckBox, QFrame, QToolButton,
                             QScrollArea, QListWidget, QListWidgetItem, QDockWidget, QMenu)
import gk_theme as theme
from gk_theme import T, mk
from gk_model import LOGO, BODY, PKEYS, KINDS
from gk_pages import draw_cube


def styled(w, name=None):
    w.setAttribute(Qt.WA_StyledBackground, True)
    if name:
        w.setObjectName(name)
    return w


# ====================================================================== khung dock
class DockTitle(QWidget):
    """Thanh tieu de panel: ten + nut tach cua so / dong. Keo thanh nay de di chuyen panel."""

    def __init__(self, dock):
        super().__init__()
        styled(self, "DockTitle")
        self.dock = dock
        self.setFixedHeight(30)
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 0, 6, 0)
        h.setSpacing(2)
        self.lbl = QLabel(dock.windowTitle().upper())
        h.addWidget(self.lbl, 1)
        dock.windowTitleChanged.connect(lambda s: self.lbl.setText(s.upper()))
        for txt, tip, fn in (("⧉", "Tách / gắn lại panel", self.toggle_float), ("✕", "Đóng panel (mở lại ở menu View)", dock.close)):
            b = QToolButton()
            b.setText(txt)
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            h.addWidget(b)

    def toggle_float(self):
        self.dock.setFloating(not self.dock.isFloating())


def make_dock(win, title, widget, name):
    d = QDockWidget(title, win)
    d.setObjectName(name)
    d.setWidget(widget)
    d.setTitleBarWidget(DockTitle(d))
    d.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
    return d


# ====================================================================== logo + avatar
class LogoTile(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(38, 38)
        self.pm = QPixmap(LOGO)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(1, 1, 36, 36), 10, 10)
        p.drawPixmap(QRectF(6, 6, 26, 26), self.pm, QRectF(self.pm.rect()))


class Avatar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(38, 38)
        self.ch = "K"

    def set_name(self, name):
        self.ch = (name or "K")[:1].upper()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0, QColor("#ff5e5b"))
        g.setColorAt(1, QColor("#a56bff"))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        p.setPen(QColor("#fff"))
        p.setFont(mk(theme.FONT_DISPLAY, 17, QFont.Bold))
        p.drawText(self.rect(), Qt.AlignCenter, self.ch)


# ====================================================================== canvas
def arrow(p, x0, y0, dx, dy, col):
    pen = QPen(QColor(col), 4)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    x1, y1 = x0 + dx, y0 + dy
    p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
    a = math.atan2(dy, dx)
    for s in (-1, 1):
        q = a + math.pi + s * 0.5
        p.drawLine(QPointF(x1, y1), QPointF(x1 + 14 * math.cos(q), y1 + 14 * math.sin(q)))


class Stage(QWidget):
    """Canvas: ve moi lop theo transform + opacity + key frame; bam de chon, keo de di chuyen."""
    picked = pyqtSignal(object)

    def __init__(self, main):
        super().__init__()
        self.m = main
        self.ratio, self.t = 16 / 9, 0.0
        self.layers, self.sel, self.drag = [], None, None
        self.guides = False
        self.setMinimumSize(320, 200)
        theme.bus.changed.connect(self.update)

    def set_time(self, t):
        self.t = t
        self.update()

    def canvas(self):
        W, H = self.width(), self.height()
        w = max(80.0, min(W - 60.0, (H - 60.0) * self.ratio))
        return QRectF((W - w) / 2, (H - w / self.ratio) / 2, w, w / self.ratio)

    def body(self, L, r):
        if L.pix is not None and not L.pix.isNull():
            w = r.width() * .4
            h = w * L.pix.height() / max(1, L.pix.width())
        else:
            fw, fh = BODY.get(L.kind, (.3, .3))
            w, h = r.width() * fw, r.height() * fh
        return QRectF(-w / 2, -h / 2, w, h)

    def tf(self, L, r):
        t, c = self.t, r.center()
        z = max(-100.0, min(100.0, L.get("pos2", t)))
        f = 1 / (1 - z / 200)
        m = QTransform()
        m.translate(c.x() + L.get("pos0", t) * r.width() / 200, c.y() - L.get("pos1", t) * r.height() / 200)
        m.rotate(L.get("rot0", t), Qt.XAxis)
        m.rotate(L.get("rot1", t), Qt.YAxis)
        m.rotate(L.get("rot2", t))
        m.scale(f * L.get("scl0", t) / 100, f * L.get("scl1", t) / 100)
        return m

    def draw_layer(self, p, L, b):
        p.setPen(Qt.NoPen)
        if L.kind == "shape":
            p.setBrush(QColor(L.color))
            p.drawRoundedRect(b, 16, 16)
        elif L.kind == "text":
            p.setPen(QColor(L.color))
            p.setFont(mk(theme.FONT_DISPLAY, max(8, int(b.height() * .6)), QFont.Bold))
            p.drawText(b, Qt.AlignCenter, L.text)
        elif L.pix is not None and not L.pix.isNull():
            p.drawPixmap(b, L.pix, QRectF(L.pix.rect()))
        else:  # video / anh chua nap: khung giu cho
            p.setBrush(QColor("#1f2a44"))
            p.setPen(QPen(QColor(L.color), 2))
            p.drawRoundedRect(b, 10, 10)
            p.setPen(QColor("#ffffff"))
            p.setFont(mk(theme.FONT_BODY, max(9, int(b.height() * .14))))
            p.drawText(b, Qt.AlignCenter, "▶ " + L.name)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        s = 20
        ca, cb = QColor(T["checker_a"]), QColor(T["checker_b"])
        for i in range(self.width() // s + 1):
            for j in range(self.height() // s + 1):
                p.fillRect(i * s, j * s, s, s, ca if (i + j) % 2 else cb)
        r = self.canvas()
        for i in range(1, 5):
            p.fillRect(r.adjusted(-i * 3, -i * 3, i * 3, i * 3), QColor(0, 0, 0, 34))
        p.fillRect(r, QColor("#000000"))
        p.save()
        p.setClipRect(r)
        for L in self.layers:
            if not L.alive(self.t):
                continue
            if L.kind == "bg":
                p.fillRect(r, QColor(L.color))
            elif L.kind != "audio":
                p.save()
                p.setTransform(self.tf(L, r), True)
                p.setOpacity(max(0.0, min(1.0, L.get("op", self.t) / 100)))
                self.draw_layer(p, L, self.body(L, r))
                p.restore()
        if self.guides:
            p.setPen(QPen(QColor(255, 255, 255, 70), 1, Qt.DashLine))
            for k in (1, 2):
                p.drawLine(QPointF(r.left() + r.width() * k / 3, r.top()), QPointF(r.left() + r.width() * k / 3, r.bottom()))
                p.drawLine(QPointF(r.left(), r.top() + r.height() * k / 3), QPointF(r.right(), r.top() + r.height() * k / 3))
            p.setPen(QPen(QColor(255, 255, 255, 50), 1))
            p.drawLine(QPointF(r.center().x(), r.top()), QPointF(r.center().x(), r.bottom()))
            p.drawLine(QPointF(r.left(), r.center().y()), QPointF(r.right(), r.center().y()))
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(T["frame"]), 2))
        p.drawRect(r)
        names = {16 / 9: "16:9", 9 / 16: "9:16", 1.0: "1:1", 4 / 5: "4:5"}
        p.setPen(QColor(T["text2"]))
        p.setFont(mk(theme.FONT_BODY, 11, QFont.DemiBold))
        p.drawText(QRectF(r.left(), r.bottom() + 6, 240, 20), Qt.AlignLeft | Qt.AlignVCenter,
                   "Canvas " + names.get(self.ratio, "%.2f" % self.ratio))
        L = self.sel
        if L and L.kind not in ("bg", "audio") and L.alive(self.t):
            o = self.tf(L, r).map(QPointF(0, 0))
            arrow(p, o.x(), o.y(), 0, -70, "#5b7cff")
            arrow(p, o.x(), o.y(), 70, 0, "#ff4d5e")
            p.setPen(QPen(QColor("#22c4ee"), 4))
            p.drawArc(QRectF(o.x() - 22, o.y() - 22, 44, 44), 40 * 16, 270 * 16)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(o, 5, 5)

    def hit(self, pos):
        r = self.canvas()
        for L in reversed(self.layers):
            if L.kind in ("bg", "audio") or not L.alive(self.t):
                continue
            inv, ok = self.tf(L, r).inverted()
            if ok and self.body(L, r).contains(inv.map(QPointF(pos))):
                return L
        return None

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        L = self.hit(e.pos())
        self.picked.emit(L)
        self.drag = (e.pos(), L.get("pos0", self.t), L.get("pos1", self.t)) if L else None

    def mouseMoveEvent(self, e):
        if self.drag and self.sel:
            r = self.canvas()
            p0, x0, y0 = self.drag
            d = e.pos() - p0
            self.m.write(self.sel, "pos0", x0 + d.x() * 200 / r.width())
            self.m.write(self.sel, "pos1", y0 - d.y() * 200 / r.height())

    def mouseReleaseEvent(self, e):
        self.drag = None


class StagePanel(QWidget):
    """Canvas + thanh cong cu tren (ti le khung, luoi) + thanh phat duoi."""

    def __init__(self, main):
        super().__init__()
        styled(self, "Panel")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        top = styled(QWidget(), "ViewBar")
        h = QHBoxLayout(top)
        h.setContentsMargins(10, 5, 10, 5)
        h.setSpacing(8)
        h.addWidget(QLabel("Khung"))
        self.ratio_cb = QComboBox()
        self.ratios = [("16:9", 16 / 9), ("9:16", 9 / 16), ("1:1", 1.0), ("4:5", 4 / 5)]
        for n, _ in self.ratios:
            self.ratio_cb.addItem(n)
        h.addWidget(self.ratio_cb)
        self.guide_btn = QPushButton("▦  Lưới")
        self.guide_btn.setObjectName("SmallBtn")
        self.guide_btn.setCheckable(True)
        self.guide_btn.setToolTip("Hiện đường chia ba / tâm khung")
        h.addWidget(self.guide_btn)
        h.addStretch()
        hint = QLabel("Bấm để chọn  ·  kéo để di chuyển")
        hint.setObjectName("Hint")
        h.addWidget(hint)
        v.addWidget(top)
        self.stage = Stage(main)
        v.addWidget(self.stage, 1)
        bot = styled(QWidget(), "ViewBarBottom")
        b = QHBoxLayout(bot)
        b.setContentsMargins(10, 4, 10, 4)
        b.setSpacing(4)
        self.prev, self.play, self.nxt = QPushButton("⏮"), QPushButton("▶"), QPushButton("⏭")
        self.prev.setObjectName("Transport")
        self.nxt.setObjectName("Transport")
        self.play.setObjectName("Play")
        self.prev.setToolTip("Về đầu")
        self.nxt.setToolTip("Tới cuối")
        self.play.setToolTip("Phát / dừng")
        self.timelbl = QLabel("00:00.0 / 00:30.0")
        self.timelbl.setObjectName("Timecode")
        b.addStretch()
        for w in (self.prev, self.play, self.nxt):
            b.addWidget(w)
        b.addSpacing(14)
        b.addWidget(self.timelbl)
        b.addStretch()
        v.addWidget(bot)
        self.ratio_cb.currentIndexChanged.connect(self._ratio)
        self.guide_btn.toggled.connect(self._guides)

    def _ratio(self, i):
        self.stage.ratio = self.ratios[i][1]
        self.stage.update()

    def _guides(self, on):
        self.stage.guides = on
        self.stage.update()

    def set_ratio(self, r):
        i = min(range(len(self.ratios)), key=lambda k: abs(self.ratios[k][1] - r))
        self.ratio_cb.blockSignals(True)
        self.ratio_cb.setCurrentIndex(i)
        self.ratio_cb.blockSignals(False)
        self.stage.ratio = r
        self.stage.update()


# ====================================================================== danh sach lop (Hierarchy)
def draw_eye(p, c, on):
    p.save()
    col = QColor(T["text"] if on else T["text3"])
    p.setPen(QPen(col, 2))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath(QPointF(c.x() - 10, c.y()))
    path.quadTo(QPointF(c.x(), c.y() - 10), QPointF(c.x() + 10, c.y()))
    path.quadTo(QPointF(c.x(), c.y() + 10), QPointF(c.x() - 10, c.y()))
    p.drawPath(path)
    if on:
        p.setBrush(col)
        p.drawEllipse(c, 2.8, 2.8)
    else:
        p.drawLine(QPointF(c.x() - 8, c.y() + 8), QPointF(c.x() + 8, c.y() - 8))
    p.restore()


class LayerList(QWidget):
    """Danh sach lop ve tay: icon theo loai, hang chon sang, nut mat."""
    picked = pyqtSignal(object)
    toggled = pyqtSignal(object)
    ROW, TOP = 44, 46

    def __init__(self):
        super().__init__()
        self.layers, self.sel, self.hot, self.scroll = [], None, None, 0
        self.setMouseTracking(True)
        self.setMinimumWidth(180)
        theme.bus.changed.connect(self.update)

    def set_layers(self, layers, sel):
        self.layers, self.sel = list(reversed(layers)), sel
        self.update()

    def row_at(self, pos):
        i = int((pos.y() - self.TOP + self.scroll) // self.ROW)
        return i if pos.y() >= self.TOP and 0 <= i < len(self.layers) else None

    def wheelEvent(self, e):
        mx = max(0, self.TOP + len(self.layers) * self.ROW - self.height() + 10)
        self.scroll = max(0, min(mx, self.scroll - e.angleDelta().y() * 0.5))
        self.update()

    def mouseMoveEvent(self, e):
        h = self.row_at(e.pos())
        if h != self.hot:
            self.hot = h
            self.setCursor(Qt.PointingHandCursor if h is not None else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, e):
        self.hot = None
        self.update()

    def mousePressEvent(self, e):
        i = self.row_at(e.pos())
        if i is None or e.button() != Qt.LeftButton:
            return
        L = self.layers[i]
        if e.x() > self.width() - 52:
            self.toggled.emit(L)
        else:
            self.picked.emit(L)

    def icon(self, p, L, r):
        col = {"shape": L.color, "text": "#e0a526", "image": "#2f8fe0", "video": "#2f8fe0",
               "audio": "#2fb37a"}.get(L.kind, T["bg3"])
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(col))
        p.drawRoundedRect(r, 7, 7)
        c, k = r.center(), L.kind
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.setBrush(Qt.NoBrush)
        if k == "shape":
            p.drawRoundedRect(QRectF(c.x() - 6, c.y() - 6, 12, 12), 3, 3)
        elif k == "text":
            p.setFont(mk(theme.FONT_DISPLAY, 16, QFont.Black))
            p.drawText(r, Qt.AlignCenter, "T")
        elif k == "image":
            p.drawPolyline(QPolygonF([QPointF(c.x() - 7, c.y() + 6), QPointF(c.x() - 2, c.y() - 2),
                                      QPointF(c.x() + 2, c.y() + 3), QPointF(c.x() + 4, c.y()),
                                      QPointF(c.x() + 7, c.y() + 6)]))
        elif k == "video":
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#ffffff"))
            p.drawPolygon(QPolygonF([QPointF(c.x() - 4, c.y() - 6), QPointF(c.x() + 6, c.y()), QPointF(c.x() - 4, c.y() + 6)]))
        elif k == "audio":
            for dx, h in ((-5, 5), (0, 10), (5, 6)):
                p.drawLine(QPointF(c.x() + dx, c.y() - h / 2), QPointF(c.x() + dx, c.y() + h / 2))
        else:
            p.setPen(QPen(QColor("#ffffff"), 1.5, Qt.DashLine))
            p.drawRect(QRectF(c.x() - 6, c.y() - 6, 12, 12))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W = self.width()
        p.fillRect(self.rect(), QColor(T["bg0"]))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#f5a623"))
        p.drawRoundedRect(QRectF(14, 15, 12, 6), 2, 2)
        p.drawRoundedRect(QRectF(14, 19, 24, 15), 3, 3)
        p.setPen(QColor(T["text"]))
        p.setFont(mk(theme.FONT_DISPLAY, 14, QFont.Bold))
        p.drawText(QRectF(46, 10, W - 110, 28), Qt.AlignVCenter | Qt.AlignLeft, "Chính")
        p.setPen(QColor(T["text3"]))
        p.setFont(mk(theme.FONT_BODY, 11))
        p.drawText(QRectF(W - 76, 10, 62, 28), Qt.AlignRight | Qt.AlignVCenter, "%d lớp" % len(self.layers))
        p.save()
        p.setClipRect(QRectF(0, self.TOP - 6, W, self.height() - self.TOP + 6))
        for i, L in enumerate(self.layers):
            r = QRectF(8, self.TOP + i * self.ROW - self.scroll, W - 16, self.ROW - 6)
            if L is self.sel:
                p.setPen(QPen(QColor(T["accent"]), 1.5))
                p.setBrush(QColor(T["accent_dim"]))
            elif i == self.hot:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(T["bg2"]))
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r, 9, 9)
            self.icon(p, L, QRectF(r.left() + 9, r.center().y() - 12, 24, 24))
            p.setPen(QColor(T["text"] if L.visible else T["text3"]))
            p.setFont(mk(theme.FONT_BODY, 13, QFont.DemiBold))
            w = int(r.width() - 88)
            p.drawText(QRectF(r.left() + 42, r.top(), w, r.height()), Qt.AlignVCenter | Qt.AlignLeft,
                       QFontMetrics(p.font()).elidedText(L.name, Qt.ElideRight, w))
            draw_eye(p, QPointF(r.right() - 22, r.center().y()), L.visible)
        p.restore()


class LayerPanel(QWidget):
    """Thanh nut (len/xuong/xoa/Add) + danh sach lop."""

    def __init__(self):
        super().__init__()
        styled(self, "Panel")
        lv = QVBoxLayout(self)
        lv.setContentsMargins(8, 8, 8, 8)
        lv.setSpacing(8)
        hl = QHBoxLayout()
        hl.setSpacing(6)
        self.up, self.down, self.rm = QPushButton("▲"), QPushButton("▼"), QPushButton("✕")
        for b, tip in ((self.up, "Đưa lên trên"), (self.down, "Đưa xuống dưới"), (self.rm, "Xoá lớp")):
            b.setObjectName("SmallBtn")
            b.setFixedSize(34, 30)
            b.setToolTip(tip)
            hl.addWidget(b)
        hl.addStretch()
        self.add = QPushButton("＋ Add")
        self.add.setObjectName("Accent")
        self.add_menu = QMenu(self.add)
        for k in KINDS:
            self.add_menu.addAction(k)
        self.add.setMenu(self.add_menu)
        hl.addWidget(self.add)
        lv.addLayout(hl)
        self.llist = LayerList()
        lv.addWidget(self.llist, 1)


# ====================================================================== thuoc tinh (Inspector)
class ScrubSpin(QDoubleSpinBox):
    """O so kieu Blender: keo ngang de doi gia tri, bam (khong keo) de go so."""

    def __init__(self, axis, step=0.5):
        super().__init__()
        self.setRange(-9999, 9999)
        self.setDecimals(1)
        self.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.setAlignment(Qt.AlignCenter)
        self.setProperty("axis", axis)
        self.setMinimumWidth(58)
        self.setFixedHeight(28)
        self.scrub_step = step
        self._press = None
        self._moved = False
        self.lineEdit().installEventFilter(self)
        self.lineEdit().setCursor(Qt.SizeHorCursor)

    def eventFilter(self, o, e):
        if o is self.lineEdit() and self.isEnabled():
            t = e.type()
            if t == QEvent.MouseButtonPress and e.button() == Qt.LeftButton and not o.hasFocus():
                self._press, self._moved = (e.globalX(), self.value()), False
                return True
            if t == QEvent.MouseMove and self._press is not None:
                dx = e.globalX() - self._press[0]
                if abs(dx) > 3 or self._moved:
                    self._moved = True
                    self.setValue(self._press[1] + dx * self.scrub_step)
                return True
            if t == QEvent.MouseButtonRelease and self._press is not None:
                if not self._moved:
                    o.setFocus()
                    o.selectAll()
                self._press = None
                return True
        return super().eventFilter(o, e)


class Section(QFrame):
    """The co the thu gon."""

    def __init__(self, title, expanded=True):
        super().__init__()
        self.setObjectName("Section")
        self.title, self.open = title, expanded
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.head = QPushButton()
        self.head.setObjectName("SectionHead")
        self.head.setCursor(Qt.PointingHandCursor)
        self.head.setFlat(True)
        self.body = QWidget()
        self.bl = QVBoxLayout(self.body)
        self.bl.setContentsMargins(12, 0, 12, 12)
        self.bl.setSpacing(8)
        v.addWidget(self.head)
        v.addWidget(self.body)
        self.head.clicked.connect(lambda: self.set_open(not self.open))
        self.set_open(expanded)

    def set_open(self, on):
        self.open = on
        self.body.setVisible(on)
        self.head.setText(("▾   " if on else "▸   ") + self.title)


class Inspector(QScrollArea):
    pill_changed = pyqtSignal(str, float)
    opacity_changed = pyqtSignal(int)
    name_edited = pyqtSignal(str)
    color_clicked = pyqtSignal()
    key_add = pyqtSignal()
    key_del = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self._sync = False
        page = styled(QWidget(), "Panel")
        pv = QVBoxLayout(page)
        pv.setContentsMargins(10, 10, 10, 10)
        pv.setSpacing(10)

        self.title = QLabel("—")
        self.title.setObjectName("Title")
        self.kind = QLabel("Chưa chọn lớp nào")
        self.kind.setObjectName("Hint")
        pv.addWidget(self.title)
        pv.addWidget(self.kind)

        s1 = Section("Lớp")
        self.name_in = QLineEdit()
        self.name_in.setPlaceholderText("Tên lớp / nội dung chữ")
        self.name_in.textEdited.connect(self.name_edited)
        s1.bl.addWidget(self.name_in)
        orow = QHBoxLayout()
        orow.addWidget(QLabel("Độ mờ"))
        self.op_sl = QSlider(Qt.Horizontal)
        self.op_sl.setRange(0, 100)
        self.op_sl.valueChanged.connect(self._op)
        orow.addWidget(self.op_sl, 1)
        self.op_lbl = QLabel("100%")
        self.op_lbl.setFixedWidth(38)
        self.op_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        orow.addWidget(self.op_lbl)
        s1.bl.addLayout(orow)
        self.col_btn = QPushButton("Màu…")
        self.col_btn.setObjectName("SmallBtn")
        self.col_btn.clicked.connect(self.color_clicked)
        s1.bl.addWidget(self.col_btn)
        pv.addWidget(s1)

        s2 = Section("Biến đổi")
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(8)
        self.pills = {}
        for r, (cap, step) in enumerate((("Vị trí", 0.5), ("Xoay", 1.0), ("Tỉ lệ %", 0.5))):
            lab = QLabel(cap)
            lab.setObjectName("Sub")
            lab.setFixedWidth(52)
            grid.addWidget(lab, r, 0)
            for c, ax in enumerate("xyz"):
                key = PKEYS[r * 3 + c]
                sp = ScrubSpin(ax, step)
                sp.valueChanged.connect(lambda v, k=key: self._pill(k, v))
                self.pills[key] = sp
                grid.addWidget(sp, r, c + 1)
        self.pills["scl2"].setToolTip("Chưa dùng ở canvas 2D")
        s2.bl.addLayout(grid)
        hint = QLabel("Kéo ngang trên ô số để đổi giá trị · bấm để gõ số")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        s2.bl.addWidget(hint)
        pv.addWidget(s2)

        s3 = Section("Key frame")
        self.autokey = QCheckBox("Tự động key frame khi chỉnh")
        s3.bl.addWidget(self.autokey)
        krow = QHBoxLayout()
        kb1, kb2 = QPushButton("◆  Thêm key frame"), QPushButton("✕  Xoá")
        kb1.setObjectName("Accent")
        kb2.setObjectName("SmallBtn")
        kb1.clicked.connect(self.key_add)
        kb2.clicked.connect(self.key_del)
        krow.addWidget(kb1, 1)
        krow.addWidget(kb2)
        s3.bl.addLayout(krow)
        pv.addWidget(s3)
        pv.addStretch()
        self.setWidget(page)

    def _pill(self, key, v):
        if not self._sync:
            self.pill_changed.emit(key, float(v))

    def _op(self, v):
        self.op_lbl.setText("%d%%" % v)
        if not self._sync:
            self.opacity_changed.emit(v)

    def load(self, L, t):
        self._sync = True
        moves = L is not None and L.kind not in ("bg", "audio")
        for k, sp in self.pills.items():
            sp.setEnabled(moves and k != "scl2")
            sp.blockSignals(True)
            sp.setValue(L.get(k, t) if L else (100.0 if k.startswith("scl") else 0.0))
            sp.blockSignals(False)
        self.op_sl.setEnabled(moves)
        self.op_sl.setValue(int(L.get("op", t)) if L else 100)
        self.name_in.setEnabled(L is not None and L.kind != "bg")
        self.col_btn.setEnabled(L is not None and L.kind in ("bg", "shape", "text"))
        if not self.name_in.hasFocus():
            self.name_in.setText(L.text if L and L.kind == "text" else (L.name if L else ""))
        self.title.setText(L.name if L else "—")
        self.kind.setText(("Loại: %s" % L.kind) if L else "Chưa chọn lớp nào")
        self._sync = False


# ====================================================================== Assets (Project)
def draw_folder(p, key, x, y, w, h):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#e07b00"))
    p.drawRoundedRect(QRectF(x, y + 6, w, h - 6), 10, 10)
    p.drawRoundedRect(QRectF(x, y, 40, 18), 7, 7)
    g = QLinearGradient(x, y + 22, x, y + h)
    g.setColorAt(0, QColor("#ffcc4d"))
    g.setColorAt(1, QColor("#ff9d1a"))
    p.setBrush(QBrush(g))
    p.drawRoundedRect(QRectF(x, y + 22, w, h - 22), 10, 10)
    c = QPointF(x + w / 2, y + 22 + (h - 22) / 2)
    if key == "video":
        p.setBrush(QColor("#2b2b3a"))
        p.drawRoundedRect(QRectF(c.x() - 22, c.y() - 15, 44, 30), 5, 5)
        p.setBrush(QColor("#ffffff"))
        for i in range(4):
            p.drawRect(QRectF(c.x() - 19 + i * 10, c.y() - 12, 5, 4))
            p.drawRect(QRectF(c.x() - 19 + i * 10, c.y() + 8, 5, 4))
        p.setBrush(QColor("#4fc3f7"))
        p.drawRect(QRectF(c.x() - 14, c.y() - 6, 28, 12))
    elif key == "image":
        p.setBrush(QColor("#d7f0ff"))
        p.drawRoundedRect(QRectF(c.x() - 22, c.y() - 16, 44, 32), 5, 5)
        p.setBrush(QColor("#2f8fe0"))
        p.drawPolygon(QPolygonF([QPointF(c.x() - 22, c.y() + 16), QPointF(c.x() - 6, c.y() - 2),
                                 QPointF(c.x() + 4, c.y() + 8), QPointF(c.x() + 12, c.y() + 2),
                                 QPointF(c.x() + 22, c.y() + 16)]))
        p.setBrush(QColor("#ffcc4d"))
        p.drawEllipse(QPointF(c.x() + 10, c.y() - 7), 4, 4)
    elif key == "Model":
        draw_cube(p, c.x(), c.y(), 8, 0.9)
    else:
        p.setBrush(QColor("#2b2b3a"))
        p.drawRoundedRect(QRectF(c.x() - 15, c.y() - 15, 30, 30), 6, 6)
        p.drawEllipse(QPointF(c.x() + 15, c.y()), 6, 6)
        p.drawEllipse(QPointF(c.x(), c.y() - 15), 6, 6)


def folder_icon(key, size=76):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 112.0
    p.scale(s, s)
    draw_folder(p, key, 6, 8, 100, 84)
    p.end()
    return QIcon(pm)


class ProjectPanel(QWidget):
    """Assets kieu thu muc: nhap dup thu muc de nhap tep vao du an."""
    opened = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        styled(self, "Panel")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        bar = styled(QWidget(), "ViewBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(10, 5, 10, 5)
        crumb = QLabel("Assets")
        crumb.setObjectName("Title")
        crumb.setStyleSheet("font-size:13px;")
        h.addWidget(crumb)
        h.addStretch()
        hint = QLabel("Nhấp đúp một thư mục để nhập tệp")
        hint.setObjectName("Hint")
        h.addWidget(hint)
        v.addWidget(bar)
        self.lst = QListWidget()
        self.lst.setViewMode(QListWidget.IconMode)
        self.lst.setIconSize(QSize(76, 76))
        self.lst.setResizeMode(QListWidget.Adjust)
        self.lst.setMovement(QListWidget.Static)
        self.lst.setSpacing(12)
        self.lst.setWordWrap(True)
        self.lst.setUniformItemSizes(True)
        self.lst.setGridSize(QSize(112, 116))
        for key, label in (("video", "video"), ("image", "image"), ("Model", "Model"), ("Plugin", "Plugin")):
            it = QListWidgetItem(folder_icon(key), label)
            it.setData(Qt.UserRole, key)
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.lst.addItem(it)
        self.lst.itemDoubleClicked.connect(lambda it: self.opened.emit(it.data(Qt.UserRole)))
        v.addWidget(self.lst, 1)


# ====================================================================== Lenh (Console)
class ConsolePanel(QWidget):
    command = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        styled(self, "Panel")
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)
        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setPlainText("Gõ help để xem danh sách lệnh.")
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Nhập lệnh rồi Enter…")
        self.inp.returnPressed.connect(self._enter)
        v.addWidget(self.out, 1)
        v.addWidget(self.inp)

    def _enter(self):
        txt = self.inp.text().strip()
        self.inp.clear()
        if txt:
            self.command.emit(txt)

    def log(self, s):
        self.out.appendPlainText(s)
