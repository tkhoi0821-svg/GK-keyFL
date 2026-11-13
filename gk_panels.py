"""Cac panel cua editor: Canvas, Lop, Thuoc tinh, Assets, Lenh + khung dock."""
import math
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, QEvent, Signal
from PySide6.QtGui import (QColor, QPainter, QPen, QBrush, QFont, QPixmap, QIcon, QLinearGradient, QPainterPath,
                         QPolygonF, QFontMetrics, QTransform)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QSlider,
                             QDoubleSpinBox, QComboBox, QLineEdit, QPlainTextEdit, QCheckBox, QFrame, QToolButton,
                             QScrollArea, QListWidget, QListWidgetItem, QDockWidget, QMenu)
import gk_theme as theme
import gk_prefs as prefs
from gk_theme import T, mk, mixc
from gk_model import LOGO, BODY, PKEYS, KINDS, EASES, LOOPS
from gk_pages import draw_cube
from gk_assets import mime_paths


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
AXC = {"x": "#ff3352", "y": "#8bdc00", "z": "#2890ff"}     # mau truc cua Blender
ARM, RING = 84.0, 72.0
ZDIR = QPointF(-0.7071, 0.7071)                            # truc Z (chieu sau) huong xuong-trai
HINTS = {"select": "Bấm để chọn  ·  kéo để di chuyển",
         "move": "Kéo mũi tên đỏ/xanh để đổi từng trục  ·  giữ Ctrl để nhảy bước tròn",
         "rotate": "Kéo vòng xanh dương để xoay trong mặt phẳng, vòng đỏ/xanh lá để xoay quanh X/Y",
         "scale": "Kéo ô vuông trên trục để co giãn từng chiều  ·  ô giữa để co giãn đều"}


def tool_icon(kind, col):
    pm = QPixmap(28, 28)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(col), 2.0)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    c = 14.0
    if kind == "select":
        p.setBrush(QColor(col))
        p.drawPolygon(QPolygonF([QPointF(8, 5), QPointF(8, 21), QPointF(12.5, 17), QPointF(15.5, 23.5),
                                 QPointF(18, 22.3), QPointF(15, 16), QPointF(21, 16)]))
    elif kind == "move":
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            p.drawLine(QPointF(c, c), QPointF(c + dx * 10, c + dy * 10))
            tip = QPointF(c + dx * 11, c + dy * 11)
            px, py = -dy, dx
            p.drawLine(tip, QPointF(tip.x() - dx * 4 + px * 3.5, tip.y() - dy * 4 + py * 3.5))
            p.drawLine(tip, QPointF(tip.x() - dx * 4 - px * 3.5, tip.y() - dy * 4 - py * 3.5))
    elif kind == "rotate":
        p.drawArc(QRectF(6, 6, 16, 16), 40 * 16, 280 * 16)
        end = QPointF(c + 8 * math.cos(math.radians(320)), c - 8 * math.sin(math.radians(320)))
        d = QPointF(0.643, -0.766)
        n = QPointF(0.766, 0.643)
        p.setBrush(QColor(col))
        p.drawPolygon(QPolygonF([QPointF(end.x() + d.x() * 5, end.y() + d.y() * 5),
                                 QPointF(end.x() + n.x() * 3.5, end.y() + n.y() * 3.5),
                                 QPointF(end.x() - n.x() * 3.5, end.y() - n.y() * 3.5)]))
    else:
        p.drawRect(QRectF(6, 12, 10, 10))
        p.drawLine(QPointF(12, 16), QPointF(22, 6))
        p.drawLine(QPointF(22, 6), QPointF(16.5, 6))
        p.drawLine(QPointF(22, 6), QPointF(22, 11.5))
    p.end()
    return pm


class ToolRail(QWidget):
    """Thanh cong cu doc ben trai canvas: Chon / Di chuyen / Xoay / Kich thuoc."""
    changed = Signal(str)
    MODES = (("select", "Chọn  (Q)"), ("move", "Di chuyển  (W)"), ("rotate", "Xoay  (E)"), ("scale", "Kích thước  (R)"))

    def __init__(self):
        super().__init__()
        styled(self, "Rail")
        self.setFixedWidth(48)
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 8, 6, 8)
        v.setSpacing(4)
        self.btns = {}
        for key, tip in self.MODES:
            b = QPushButton()
            b.setObjectName("Tool")
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setToolTip(tip)
            b.setIconSize(QSize(28, 28))
            b.clicked.connect(lambda _=False, k=key: self.changed.emit(k))
            v.addWidget(b)
            self.btns[key] = b
        v.addStretch()
        self.btns["select"].setChecked(True)
        self.refresh_icons()
        theme.bus.changed.connect(self.refresh_icons)

    def refresh_icons(self):
        for key, b in self.btns.items():
            ic = QIcon()
            ic.addPixmap(tool_icon(key, T["text"]), QIcon.Normal, QIcon.Off)
            ic.addPixmap(tool_icon(key, T["on_accent"]), QIcon.Normal, QIcon.On)
            b.setIcon(ic)

    def set_mode(self, k):
        self.btns[k].setChecked(True)


def seg_dist(p, a, b):
    ab = b - a
    l2 = ab.x() ** 2 + ab.y() ** 2
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p.x() - a.x()) * ab.x() + (p.y() - a.y()) * ab.y()) / l2))
    q = a + ab * t
    return math.hypot(p.x() - q.x(), p.y() - q.y())


class Stage(QWidget):
    """Canvas: ve moi lop theo transform + opacity + key frame; gizmo kieu Blender de di chuyen / xoay / co gian."""
    picked = Signal(object)
    asset_dropped = Signal(str, float, float)    # duong dan, vi tri x, y (don vi pos0/pos1)

    def __init__(self, main):
        super().__init__()
        self.m = main
        self.setAcceptDrops(True)
        self.ratio, self.t = 16 / 9, 0.0
        self.layers, self.sel, self.drag = [], None, None
        self.guides = False
        self.mode, self.hot, self.gd = "select", None, None
        self.setMouseTracking(True)
        self.setMinimumSize(320, 200)
        theme.bus.changed.connect(self.update)

    def set_time(self, t):
        self.t = t
        self.update()

    def set_mode(self, m):
        self.mode, self.hot = m, None
        self.update()

    def canvas(self):
        W, H = self.width(), self.height()
        w = max(80.0, min(W - 60.0, (H - 60.0) * self.ratio))
        return QRectF((W - w) / 2, (H - w / self.ratio) / 2, w, w / self.ratio)

    def body(self, L, r):
        v = getattr(L, "vid", None)
        if L.pix is not None and not L.pix.isNull():
            w = r.width() * L.wfrac
            h = w * L.pix.height() / max(1, L.pix.width())
        elif L.kind == "video" and v is not None and v.w > 0:
            w = r.width() * L.wfrac
            h = w * v.h / v.w
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
        elif L.kind == "video" and self.video_frame(L) is not None:
            pm = self.video_frame(L)
            p.drawPixmap(b, pm, QRectF(pm.rect()))
        else:  # video / anh chua nap: khung giu cho
            p.setBrush(QColor("#1f2a44"))
            p.setPen(QPen(QColor(L.color), 2))
            p.drawRoundedRect(b, 10, 10)
            p.setPen(QColor("#ffffff"))
            p.setFont(mk(theme.FONT_BODY, max(9, int(b.height() * .14))))
            p.drawText(b, Qt.AlignCenter, "▶ " + L.name)

    def video_frame(self, L):
        v, c = getattr(L, "vid", None), L.clip_at(self.t)
        if v is None or c is None:
            return None
        return v.frame(self.t - c.start + getattr(c, "src_off", 0.0))

    # ---------------------------------------------------------------- gizmo
    def gizmo_layer(self):
        L = self.sel
        return L if (L and L.kind not in ("bg", "audio") and L.alive(self.t)) else None

    def origin(self, L, r):
        return self.tf(L, r).map(QPointF(0, 0))

    def active(self, hid):
        return self.hot == hid or (self.gd is not None and self.gd["h"] == hid)

    def acol(self, axis, hid):
        c = QColor(AXC[axis])
        return mixc(c, "#ffffff", 0.55) if self.active(hid) else c

    def _arrow(self, p, o, d, n, col, w):
        e = o + d * (n - 16)
        pen = QPen(col, w)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(o + d * 12, e)
        tip, perp = o + d * n, QPointF(-d.y(), d.x())
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawPolygon(QPolygonF([tip, e + perp * 7, e - perp * 7]))

    def draw_move(self, p, o):
        hp = self.active("xy")
        c = QColor(AXC["z"])
        c.setAlpha(220 if hp else 120)
        p.setPen(QPen(QColor(AXC["z"]), 1))
        p.setBrush(c)
        p.drawRect(QRectF(o.x() + 22, o.y() - 44, 22, 22))
        self._arrow(p, o, QPointF(0, -1), ARM, self.acol("y", "y"), 3.2)
        self._arrow(p, o, QPointF(1, 0), ARM, self.acol("x", "x"), 3.2)
        self._arrow(p, o, ZDIR, ARM * 0.74, self.acol("z", "z"), 3.2)

    def draw_rotate(self, p, o):
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.setBrush(QColor(255, 255, 255, 14))
        p.drawEllipse(o, RING, RING)
        p.setBrush(Qt.NoBrush)
        a = RING * 0.3
        p.setPen(QPen(self.acol("y", "ry"), 3.4 if self.active("ry") else 2.6))
        p.drawEllipse(QRectF(o.x() - RING, o.y() - a, RING * 2, a * 2))
        p.setPen(QPen(self.acol("x", "rx"), 3.4 if self.active("rx") else 2.6))
        p.drawEllipse(QRectF(o.x() - a, o.y() - RING, a * 2, RING * 2))
        p.setPen(QPen(self.acol("z", "rz"), 3.6 if self.active("rz") else 2.8))
        p.drawEllipse(o, RING, RING)

    def draw_scale(self, p, o):
        for hid, axis, d in (("sy", "y", QPointF(0, -1)), ("sx", "x", QPointF(1, 0))):
            col = self.acol(axis, hid)
            p.setPen(QPen(col, 3))
            p.drawLine(o + d * 10, o + d * ARM)
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            e = o + d * ARM
            p.drawRect(QRectF(e.x() - 8, e.y() - 8, 16, 16))
        p.setPen(QPen(QColor("#000000"), 1))
        p.setBrush(QColor("#ffffff") if self.active("sc") else QColor("#d4d4d4"))
        p.drawRect(QRectF(o.x() - 8, o.y() - 8, 16, 16))

    def draw_guide(self, p, o):
        h = self.gd["h"]
        d = {"x": (1, 0, "x"), "y": (0, -1, "y"), "z": (ZDIR.x(), ZDIR.y(), "z"), "sx": (1, 0, "x"), "sy": (0, -1, "y")}.get(h)
        if not d:
            return
        c = QColor(AXC[d[2]])
        c.setAlpha(170)
        p.setPen(QPen(c, 1.4, Qt.DashLine))
        k = max(self.width(), self.height())
        p.drawLine(QPointF(o.x() - d[0] * k, o.y() - d[1] * k), QPointF(o.x() + d[0] * k, o.y() + d[1] * k))

    def gizmo_hit(self, pos, o):
        pt = QPointF(pos)
        dx, dy = pt.x() - o.x(), pt.y() - o.y()
        if self.mode == "move":
            if math.hypot(dx, dy) < 11:
                return "c"
            if QRectF(o.x() + 22, o.y() - 44, 22, 22).contains(pt):
                return "xy"
            for h, d, n in (("x", QPointF(1, 0), ARM), ("y", QPointF(0, -1), ARM), ("z", ZDIR, ARM * 0.74)):
                if seg_dist(pt, o + d * 12, o + d * n) < 8:
                    return h
        elif self.mode == "rotate":
            a = RING * 0.3
            if abs(math.hypot(dx / a, dy / RING) - 1) * a < 7:
                return "rx"
            if abs(math.hypot(dx / RING, dy / a) - 1) * a < 7:
                return "ry"
            if abs(math.hypot(dx, dy) - RING) < 7:
                return "rz"
        elif self.mode == "scale":
            if abs(dx) < 11 and abs(dy) < 11:
                return "sc"
            for h, d in (("sx", QPointF(1, 0)), ("sy", QPointF(0, -1))):
                if seg_dist(pt, o + d * 10, o + d * (ARM + 6)) < 9:
                    return h
        return None

    def gdrag(self, e):
        g, L = self.gd, self.sel
        if not L:
            return
        r = self.canvas()
        h, b, o, p0 = g["h"], g["base"], g["o"], g["p0"]
        snap = bool(e.modifiers() & Qt.ControlModifier)

        def q(v, step):
            return round(v / step) * step if snap else v

        W = self.m.write
        d = QPointF(e.pos()) - p0
        if h in ("x", "xy", "c"):
            W(L, "pos0", q(b["pos0"] + d.x() * 200 / r.width(), prefs.get("snap_move")))
        if h in ("y", "xy", "c"):
            W(L, "pos1", q(b["pos1"] - d.y() * 200 / r.height(), prefs.get("snap_move")))
        if h == "z":
            along = d.x() * ZDIR.x() + d.y() * ZDIR.y()
            W(L, "pos2", max(-100.0, min(100.0, q(b["pos2"] + along * 0.5, prefs.get("snap_move")))))
        if h == "rz":
            a = math.degrees(math.atan2(e.y() - o.y(), e.x() - o.x()))
            g["acc"] += (a - g["last"] + 180) % 360 - 180
            g["last"] = a
            W(L, "rot2", q(b["rot2"] + g["acc"], prefs.get("snap_rot")))
        if h == "rx":
            W(L, "rot0", q(b["rot0"] + d.y() * 0.6, prefs.get("snap_rot")))
        if h == "ry":
            W(L, "rot1", q(b["rot1"] + d.x() * 0.6, prefs.get("snap_rot")))
        if h == "sc":
            f = max(0.01, math.hypot(e.x() - o.x(), e.y() - o.y()) / max(20.0, math.hypot(p0.x() - o.x(), p0.y() - o.y())))
            for k in ("scl0", "scl1"):
                W(L, k, max(1.0, q(b[k] * f, prefs.get("snap_scl"))))
        if h == "sx":
            sg = 1 if p0.x() >= o.x() else -1
            f = max(0.01, (e.x() - o.x()) * sg / max(30.0, abs(p0.x() - o.x())))
            W(L, "scl0", max(1.0, q(b["scl0"] * f, prefs.get("snap_scl"))))
        if h == "sy":
            f = max(0.01, -(e.y() - o.y()) / max(30.0, abs(p0.y() - o.y())))
            W(L, "scl1", max(1.0, q(b["scl1"] * f, prefs.get("snap_scl"))))

    def draw_outline(self, p, L, r):
        poly = self.tf(L, r).map(QPolygonF(self.body(L, r)))
        p.setPen(QPen(QColor("#ffa028"), 2))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(poly)

    # ---------------------------------------------------------------- ve
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
        L = self.gizmo_layer()
        if L:
            self.draw_outline(p, L, r)
            o = self.origin(L, r)
            if self.gd:
                self.draw_guide(p, self.gd["o"])
            if self.mode == "move":
                self.draw_move(p, o)
            elif self.mode == "rotate":
                self.draw_rotate(p, o)
            elif self.mode == "scale":
                self.draw_scale(p, o)
            p.setPen(QPen(QColor("#000000"), 1))
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(o, 4, 4)

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
        L = self.gizmo_layer()
        if L and self.mode != "select":
            o = self.origin(L, self.canvas())
            h = self.gizmo_hit(e.pos(), o)
            if h:
                ang = math.degrees(math.atan2(e.y() - o.y(), e.x() - o.x()))
                self.gd = dict(h=h, p0=QPointF(e.pos()), o=o, last=ang, acc=0.0,
                               base={k: L.get(k, self.t) for k in PKEYS})
                self.update()
                return
        Lh = self.hit(e.pos())
        self.picked.emit(Lh)
        movable = self.mode in ("select", "move")
        self.drag = (e.pos(), Lh.get("pos0", self.t), Lh.get("pos1", self.t)) if (Lh and movable) else None

    def mouseMoveEvent(self, e):
        if self.gd:
            self.gdrag(e)
            return
        if self.drag and self.sel:
            r = self.canvas()
            p0, x0, y0 = self.drag
            d = e.pos() - p0
            self.m.write(self.sel, "pos0", x0 + d.x() * 200 / r.width())
            self.m.write(self.sel, "pos1", y0 - d.y() * 200 / r.height())
            return
        L = self.gizmo_layer()
        h = self.gizmo_hit(e.pos(), self.origin(L, self.canvas())) if (L and self.mode != "select") else None
        if h != self.hot:
            self.hot = h
            self.setCursor(Qt.PointingHandCursor if h else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, e):
        self.hot = None
        self.update()

    def mouseReleaseEvent(self, e):
        self.drag, self.gd = None, None
        self.update()

    def dragEnterEvent(self, e):
        if mime_paths(e.mimeData()):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        r = self.canvas()
        x = (e.pos().x() - r.center().x()) * 200 / r.width()
        y = -(e.pos().y() - r.center().y()) * 200 / r.height()
        for p in mime_paths(e.mimeData()):
            self.asset_dropped.emit(p, x, y)
        e.acceptProposedAction()


class StagePanel(QWidget):
    """Canvas + thanh cong cu tren (ti le khung, luoi) + thanh chon cong cu ben trai + thanh phat duoi."""

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
        self.hint = QLabel(HINTS["select"])
        self.hint.setObjectName("Hint")
        h.addWidget(self.hint)
        v.addWidget(top)
        mid = QHBoxLayout()
        mid.setSpacing(0)
        self.rail = ToolRail()
        self.rail.changed.connect(self.set_mode)
        self.stage = Stage(main)
        mid.addWidget(self.rail)
        mid.addWidget(self.stage, 1)
        v.addLayout(mid, 1)
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

    def set_mode(self, mode):
        self.rail.set_mode(mode)
        self.stage.set_mode(mode)
        self.hint.setText(HINTS[mode])

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
    picked = Signal(object)
    toggled = Signal(object)
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
    pill_changed = Signal(str, float)
    opacity_changed = Signal(int)
    name_edited = Signal(str)
    color_clicked = Signal()
    key_add = Signal()
    key_del = Signal()
    key_nav = Signal(int)
    ease_chosen = Signal(str)
    loop_chosen = Signal(str)

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

        s1b = Section("Ảnh")
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        self.matte_btn = QPushButton("◐  Tách nền…")
        self.matte_btn.setObjectName("SmallBtn")
        self.matte_btn.setToolTip("Xoá nền ảnh bằng màu (chroma key) hoặc AI")
        self.vector_btn = QPushButton("✂  Cắt ảnh vector…")
        self.vector_btn.setObjectName("SmallBtn")
        self.vector_btn.setToolTip("Mở cửa sổ Vector Editor để vẽ vùng cắt (đầu, tay…) thành lớp riêng")
        row2.addWidget(self.matte_btn)
        row2.addWidget(self.vector_btn)
        s1b.bl.addLayout(row2)
        pv.addWidget(s1b)
        self.matte_clicked = self.matte_btn.clicked
        self.vector_clicked = self.vector_btn.clicked

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
        self.kstat = QLabel("Chưa chọn lớp")
        self.kstat.setObjectName("Sub")
        self.kstat.setWordWrap(True)
        s3.bl.addWidget(self.kstat)
        self.autokey = QCheckBox("Tự động key frame khi chỉnh")
        s3.bl.addWidget(self.autokey)
        krow = QHBoxLayout()
        krow.setSpacing(6)
        kp, ka, kn, kd = QPushButton("◀◆"), QPushButton("◆＋  Thêm"), QPushButton("◆▶"), QPushButton("✕")
        for b_, tip in ((kp, "Tới key frame trước"), (kn, "Tới key frame sau"), (kd, "Xoá key frame tại đầu phát")):
            b_.setObjectName("SmallBtn")
            b_.setToolTip(tip)
        ka.setObjectName("Accent")
        ka.setToolTip("Thêm key frame (lưu mọi thuộc tính) tại vị trí đầu phát")
        kp.clicked.connect(lambda: self.key_nav.emit(-1))
        kn.clicked.connect(lambda: self.key_nav.emit(1))
        ka.clicked.connect(self.key_add)
        kd.clicked.connect(self.key_del)
        krow.addWidget(kp)
        krow.addWidget(ka, 1)
        krow.addWidget(kn)
        krow.addWidget(kd)
        s3.bl.addLayout(krow)
        erow = QGridLayout()
        erow.setHorizontalSpacing(8)
        erow.setVerticalSpacing(8)
        lab1, lab2 = QLabel("Nội suy"), QLabel("Lặp")
        lab1.setObjectName("Sub")
        lab2.setObjectName("Sub")
        self.ease_cb, self.loop_cb = QComboBox(), QComboBox()
        for k, n in EASES:
            self.ease_cb.addItem(n, k)
        for k, n in LOOPS:
            self.loop_cb.addItem(n, k)
        self.ease_cb.setToolTip("Kiểu chuyển động từ key tại đầu phát tới key kế tiếp (mọi kênh)")
        self.loop_cb.setToolTip("Lặp chuyển động sau key cuối: Cyclic hoặc Ping-pong")
        self.ease_cb.activated.connect(lambda _: self.ease_chosen.emit(self.ease_cb.currentData()))
        self.loop_cb.activated.connect(lambda _: self.loop_chosen.emit(self.loop_cb.currentData()))
        erow.addWidget(lab1, 0, 0)
        erow.addWidget(self.ease_cb, 0, 1)
        erow.addWidget(lab2, 1, 0)
        erow.addWidget(self.loop_cb, 1, 1)
        erow.setColumnStretch(1, 1)
        s3.bl.addLayout(erow)
        legend = QLabel("◆ tuyến tính   ● ease / bezier   ■ dừng   ▲ nảy, đàn hồi, sóng, rung")
        legend.setObjectName("Hint")
        legend.setWordWrap(True)
        s3.bl.addWidget(legend)
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
        has_img = bool(L is not None and L.kind == "image" and L.pix is not None and not L.pix.isNull())
        self.matte_btn.setEnabled(has_img)
        self.vector_btn.setEnabled(has_img)
        if not self.name_in.hasFocus():
            self.name_in.setText(L.text if L and L.kind == "text" else (L.name if L else ""))
        self.title.setText(L.name if L else "—")
        self.kind.setText(("Loại: %s" % L.kind) if L else "Chưa chọn lớp nào")
        ks = L.keys_at(t) if L else []
        if L is None:
            self.kstat.setText("Chưa chọn lớp")
        elif ks:
            self.kstat.setText("◆ Có key frame tại %02d:%04.1f  (%d kênh)" % (int(t) // 60, t % 60, len(ks)))
        else:
            self.kstat.setText("Chưa có key tại đây · lớp có %d điểm key" % len(L.key_times()))
        self.ease_cb.setEnabled(bool(ks))
        self.loop_cb.setEnabled(L is not None and bool(L.kf))
        self.ease_cb.blockSignals(True)
        self.ease_cb.setCurrentIndex(max(0, self.ease_cb.findData(ks[0].e)) if ks else 0)
        self.ease_cb.blockSignals(False)
        self.loop_cb.blockSignals(True)
        ch = next(iter(L.kf), None) if L else None
        self.loop_cb.setCurrentIndex(max(0, self.loop_cb.findData(L.loop.get(ch, "none"))) if ch else 0)
        self.loop_cb.blockSignals(False)
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
    elif key == "audio":
        p.setBrush(QColor("#2b2b3a"))
        p.drawRoundedRect(QRectF(c.x() - 22, c.y() - 15, 44, 30), 6, 6)
        p.setBrush(QColor("#3ddc84"))
        for i, hh in enumerate((8, 16, 22, 12, 18, 9)):
            p.drawRoundedRect(QRectF(c.x() - 17 + i * 6.5, c.y() - hh / 2, 3.6, hh), 1.5, 1.5)
    elif key == "Plugin":
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


# ====================================================================== Lenh (Console)
class ConsolePanel(QWidget):
    command = Signal(str)

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
