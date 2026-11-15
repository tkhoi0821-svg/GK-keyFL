"""Cac panel cua editor: Canvas, Lop, Thuoc tinh, Assets, Lenh + khung dock."""
import math
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, QEvent, Signal
from PySide6.QtGui import (QColor, QPainter, QPen, QBrush, QFont, QPixmap, QIcon, QLinearGradient, QPainterPath,
                         QPolygonF, QFontMetrics, QTransform, QRadialGradient)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QSlider,
                             QDoubleSpinBox, QComboBox, QLineEdit, QPlainTextEdit, QCheckBox, QFrame, QToolButton,
                             QScrollArea, QListWidget, QListWidgetItem, QDockWidget, QMenu, QSpinBox)
import gk_theme as theme
import gk_prefs as prefs
import gk_material
from gk_theme import T, mk, mixc
from gk_model import LOGO, BODY, PKEYS, KINDS, EASES, LOOPS, PAINTERS, ICONS, FORM_NAMES, FORM_GROUPS, FORMS
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
         "scale": "Kéo ô vuông trên trục để co giãn từng chiều  ·  ô giữa để co giãn đều",
         "skew": "Kéo tay nắm hình bình hành ở 4 cạnh để nghiêng ngang / dọc  ·  Ctrl để nhảy bước",
         "mesh": "Kéo từng điểm: ảnh móp theo điểm đó  ·  Chuột phải vào điểm = bật/tắt key điểm đó  ·  ◆ vàng = đang có key tại đây"}


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
    elif kind == "skew":
        p.drawPolygon(QPolygonF([QPointF(10, 8), QPointF(22, 8), QPointF(18, 20), QPointF(6, 20)]))
    elif kind == "mesh":
        for k in range(4):
            x = 5 + k * 6
            p.drawLine(QPointF(x, 5), QPointF(x + (1.5 if k in (1, 2) else 0), 23))
            p.drawLine(QPointF(5, x), QPointF(23, x + (-1.5 if k in (1, 2) else 0)))
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
    MODES = (("select", "Chọn  (Q)"), ("move", "Di chuyển  (W)"), ("rotate", "Xoay  (E)"), ("scale", "Kích thước  (R)"),
             ("skew", "Nghiêng  (Y)"), ("mesh", "Lưới méo  (T)"))

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


def form_path(extra, b):
    """Duong vien cua hinh co ban trong khung b (QRectF). extra: Layer.extra (form, sides, inner, round)."""
    form = extra.get("form", "rect")
    x, y, w, h = b.x(), b.y(), b.width(), b.height()
    cx, cy, rx, ry = x + w / 2, y + h / 2, w / 2, h / 2

    def U(u, v):
        return QPointF(x + u * w, y + v * h)

    def poly(pts):
        pa = QPainterPath()
        pa.addPolygon(QPolygonF([q if isinstance(q, QPointF) else QPointF(*q) for q in pts]))
        pa.closeSubpath()
        return pa

    def reg(n, rot=-math.pi / 2):
        return [QPointF(cx + rx * math.cos(rot + 2 * math.pi * i / n), cy + ry * math.sin(rot + 2 * math.pi * i / n))
                for i in range(n)]

    def star(n, k):
        return [QPointF(cx + rx * (1 if i % 2 == 0 else k) * math.cos(-math.pi / 2 + math.pi * i / n),
                        cy + ry * (1 if i % 2 == 0 else k) * math.sin(-math.pi / 2 + math.pi * i / n)) for i in range(n * 2)]

    def uv(pts):
        return [U(*q) for q in pts]

    def ell(u0, v0, u1, v1):
        pa = QPainterPath()
        pa.addEllipse(QRectF(x + u0 * w, y + v0 * h, (u1 - u0) * w, (v1 - v0) * h))
        return pa

    def hollow(outer, inner):
        pa = QPainterPath()
        pa.setFillRule(Qt.OddEvenFill)
        pa.addPath(outer)
        pa.addPath(inner)
        return pa

    def flip(pts):
        return [(1 - u, v) for u, v in pts]

    def swap(pts):
        return [(v, u) for u, v in pts]

    ARROW = [(0, .3), (.58, .3), (.58, .05), (1, .5), (.58, .95), (.58, .7), (0, .7)]
    PLUS = [(.33, 0), (.67, 0), (.67, .33), (1, .33), (1, .67), (.67, .67), (.67, 1), (.33, 1), (.33, .67), (0, .67),
            (0, .33), (.33, .33)]
    CHEV = [(0, 0), (.6, 0), (1, .5), (.6, 1), (0, 1), (.4, .5)]
    path = QPainterPath()
    n_user = max(3, min(24, int(extra.get("sides", 6))))
    if form == "ellipse":
        path.addEllipse(b)
    elif form == "triangle":
        path = poly([(cx, y), (x + w, y + h), (x, y + h)])
    elif form == "rtri":
        path = poly([(x, y), (x, y + h), (x + w, y + h)])
    elif form == "dtri":
        path = poly([(x, y), (x + w, y), (cx, y + h)])
    elif form == "diamond":
        path = poly([(cx, y), (x + w, cy), (cx, y + h), (x, cy)])
    elif form == "trapezoid":
        path = poly(uv([(.2, 0), (.8, 0), (1, 1), (0, 1)]))
    elif form == "parallelogram":
        path = poly(uv([(.25, 0), (1, 0), (.75, 1), (0, 1)]))
    elif form == "semicircle":
        path.moveTo(x, y + h)
        path.arcTo(QRectF(x, y, w, 2 * h), 180, -180)
        path.closeSubpath()
    elif form == "quarter":
        path.moveTo(x, y + h)
        path.lineTo(x, y)
        path.arcTo(QRectF(x - w, y, 2 * w, 2 * h), 90, -90)
        path.closeSubpath()
    elif form == "pie":
        path.moveTo(cx, cy)
        path.arcTo(b, 40, 280)
        path.closeSubpath()
    elif form == "ring":
        path = hollow(ell(0, 0, 1, 1), ell(.24, .24, .76, .76))
    elif form == "frame":
        ou, inn = QPainterPath(), QPainterPath()
        ou.addRect(b)
        inn.addRect(QRectF(x + w * .2, y + h * .2, w * .6, h * .6))
        path = hollow(ou, inn)
    elif form == "arch":
        path.moveTo(x, y + h)
        path.lineTo(x, cy)
        path.arcTo(b, 180, -180)
        path.lineTo(x + w, y + h)
        path.closeSubpath()
    elif form == "polygon":
        path = poly(reg(n_user))
    elif form in ("pentagon", "hexagon", "heptagon", "octagon", "decagon"):
        path = poly(reg({"pentagon": 5, "hexagon": 6, "heptagon": 7, "octagon": 8, "decagon": 10}[form],
                        -math.pi / 2 if form != "hexagon" and form != "octagon" else -math.pi / 2 + math.pi / (6 if form == "hexagon" else 8)))
    elif form == "gem":
        path = poly(uv([(.25, 0), (.75, 0), (1, .35), (.5, 1), (0, .35)]))
    elif form == "star":
        path = poly(star(max(3, min(24, int(extra.get("sides", 5)))), max(0.1, min(0.9, extra.get("inner", 45) / 100.0))))
    elif form == "star4":
        path = poly(star(4, .42))
    elif form == "star6":
        path = poly(star(6, .55))
    elif form == "star8":
        path = poly(star(8, .6))
    elif form == "sparkle":
        path = poly(star(4, .2))
    elif form == "seal":
        path = poly(star(16, .86))
    elif form == "burst":
        path = poly(star(12, .62))
    elif form == "gear":
        n, pts = 8, []
        for i in range(n):
            a0, st = 2 * math.pi * i / n - math.pi / 2, 2 * math.pi / n
            for da, f in ((-.5, .78), (-.2, .78), (-.15, 1.0), (.15, 1.0), (.2, .78)):
                pts.append(QPointF(cx + rx * f * math.cos(a0 + da * st), cy + ry * f * math.sin(a0 + da * st)))
        path = hollow(poly(pts), ell(.35, .35, .65, .65))
    elif form == "flower":
        pts = []
        for i in range(144):
            a = 2 * math.pi * i / 144
            r = .55 + .45 * abs(math.cos(3 * a))
            pts.append(QPointF(cx + rx * r * math.cos(a - math.pi / 2), cy + ry * r * math.sin(a - math.pi / 2)))
        path = poly(pts)
    elif form == "bolt":
        path = poly(uv([(.55, 0), (.15, .55), (.45, .55), (.3, 1), (.85, .4), (.55, .4), (.8, 0)]))
    elif form == "arrow":
        path = poly(uv(ARROW))
    elif form == "arrow_l":
        path = poly(uv(flip(ARROW)))
    elif form == "arrow_d":
        path = poly(uv(swap(ARROW)))
    elif form == "arrow_u":
        path = poly(uv(swap(flip(ARROW))))
    elif form == "arrow_lr":
        path = poly(uv([(0, .5), (.22, .1), (.22, .32), (.78, .32), (.78, .1), (1, .5), (.78, .9), (.78, .68), (.22, .68),
                        (.22, .9)]))
    elif form == "arrow_ud":
        path = poly(uv(swap([(0, .5), (.22, .1), (.22, .32), (.78, .32), (.78, .1), (1, .5), (.78, .9), (.78, .68),
                             (.22, .68), (.22, .9)])))
    elif form == "chevron_r":
        path = poly(uv(CHEV))
    elif form == "chevron_l":
        path = poly(uv(flip(CHEV)))
    elif form == "homeplate":
        path = poly(uv([(0, .15), (.7, .15), (1, .5), (.7, .85), (0, .85)]))
    elif form == "play":
        path = poly(uv([(.12, 0), (1, .5), (.12, 1)]))
    elif form in ("bubble_round", "bubble_oval", "callout", "bubble_think"):
        body = QPainterPath()
        if form == "bubble_round":
            body.addRoundedRect(QRectF(x, y, w, h * .8), min(w, h) * .2, min(w, h) * .2)
            path = body.united(poly(uv([(.2, .75), (.2, 1), (.45, .75)])))
        elif form == "bubble_oval":
            body.addEllipse(QRectF(x, y, w, h * .82))
            path = body.united(poly(uv([(.22, .68), (.12, 1), (.45, .8)])))
        elif form == "callout":
            body.addRect(QRectF(x, y, w, h * .8))
            path = body.united(poly(uv([(.15, .78), (.1, 1), (.4, .78)])))
        else:
            path = (ell(.02, .1, .4, .55).united(ell(.25, 0, .75, .5)).united(ell(.6, .1, .98, .55))
                    .united(ell(.15, .3, .85, .7)).united(ell(.12, .76, .26, .9)).united(ell(.02, .9, .1, 1)))
    elif form == "bubble_spike":
        path = poly(star(14, .62))
    elif form == "heart":
        path.moveTo(U(0.5, 0.92))
        path.cubicTo(U(0.0, 0.58), U(0.0, 0.08), U(0.25, 0.08))
        path.cubicTo(U(0.4, 0.08), U(0.5, 0.18), U(0.5, 0.3))
        path.cubicTo(U(0.5, 0.18), U(0.6, 0.08), U(0.75, 0.08))
        path.cubicTo(U(1.0, 0.08), U(1.0, 0.58), U(0.5, 0.92))
        path.closeSubpath()
    elif form == "plus":
        path = poly(uv(PLUS))
    elif form == "cross":
        ctr = [(.5 + (q[0] - .5) * 1.3 * math.cos(math.pi / 4) - (q[1] - .5) * 1.3 * math.sin(math.pi / 4),
                .5 + (q[0] - .5) * 1.3 * math.sin(math.pi / 4) + (q[1] - .5) * 1.3 * math.cos(math.pi / 4)) for q in PLUS]
        path = poly(uv(ctr))
    elif form == "minus":
        path = poly(uv([(0, .36), (1, .36), (1, .64), (0, .64)]))
    elif form == "check":
        path = poly(uv([(0, .55), (.17, .4), (.38, .62), (.83, .1), (1, .26), (.38, .95)]))
    elif form == "cloud":
        path = (ell(.0, .35, .42, .85).united(ell(.2, .1, .62, .6)).united(ell(.45, .2, .85, .7)).united(ell(.6, .38, 1, .85))
                .united(ell(.15, .45, .85, .9)))
    elif form == "crescent":
        path = ell(0, 0, 1, 1).subtracted(ell(.3, .05, 1.05, .95))
    elif form == "drop":
        path.moveTo(U(.5, 0))
        path.cubicTo(U(.62, .2), U(1, .42), U(1, .68))
        path.cubicTo(U(1, .86), U(.78, 1), U(.5, 1))
        path.cubicTo(U(.22, 1), U(0, .86), U(0, .68))
        path.cubicTo(U(0, .42), U(.38, .2), U(.5, 0))
        path.closeSubpath()
    elif form == "leaf":
        path.moveTo(U(0, 1))
        path.cubicTo(U(0, .4), U(.4, 0), U(1, 0))
        path.cubicTo(U(1, .6), U(.6, 1), U(0, 1))
        path.closeSubpath()
    elif form == "shield":
        path.moveTo(U(.5, 0))
        path.cubicTo(U(.65, .12), U(.85, .15), U(1, .15))
        path.lineTo(U(1, .5))
        path.cubicTo(U(1, .75), U(.75, .92), U(.5, 1))
        path.cubicTo(U(.25, .92), U(0, .75), U(0, .5))
        path.lineTo(U(0, .15))
        path.cubicTo(U(.15, .15), U(.35, .12), U(.5, 0))
        path.closeSubpath()
    elif form == "house":
        path = poly(uv([(.5, 0), (1, .45), (.85, .45), (.85, 1), (.15, 1), (.15, .45), (0, .45)]))
    elif form == "bookmark":
        path = poly(uv([(.15, 0), (.85, 0), (.85, 1), (.5, .72), (.15, 1)]))
    elif form == "smiley":
        mouth = [(.26 + .48 * t / 20, .6 + .17 * math.sin(math.pi * t / 20)) for t in range(21)]
        mouth += [(.26 + .48 * t / 20, .68 + .17 * math.sin(math.pi * t / 20)) for t in range(20, -1, -1)]
        face = hollow(ell(0, 0, 1, 1), ell(.3, .28, .42, .46))
        face = hollow(face, ell(.58, .28, .7, .46))
        path = hollow(face, poly(uv(mouth)))
    elif form == "letter_l":
        path = poly(uv([(0, 0), (.35, 0), (.35, .65), (1, .65), (1, 1), (0, 1)]))
    elif form == "letter_t":
        path = poly(uv([(0, 0), (1, 0), (1, .32), (.65, .32), (.65, 1), (.35, 1), (.35, .32), (0, .32)]))
    elif form == "stairs":
        path = poly(uv([(0, 1), (0, .66), (.34, .66), (.34, .33), (.67, .33), (.67, 0), (1, 0), (1, 1)]))
    elif form == "rrect":
        r = min(w, h) * .25
        path.addRoundedRect(b, r, r)
    elif form == "pill":
        r = min(w, h) / 2
        path.addRoundedRect(b, r, r)
    else:
        r = float(extra.get("round", 16))
        path.addRoundedRect(b, r, r)
    return path


def seg_dist(p, a, b):
    ab = b - a
    l2 = ab.x() ** 2 + ab.y() ** 2
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p.x() - a.x()) * ab.x() + (p.y() - a.y()) * ab.y()) / l2))
    q = a + ab * t
    return math.hypot(p.x() - q.x(), p.y() - q.y())


class Stage(QWidget):
    """Canvas: ve moi lop theo transform + opacity + key frame; gizmo kieu Blender de di chuyen / xoay / co gian."""
    picked = Signal(object)
    mesh_picked = Signal(int)               # diem luoi vua bam / keo (de do thi chuyen sang kenh cua no)
    asset_dropped = Signal(str, float, float)    # duong dan, vi tri x, y (don vi pos0/pos1)

    def __init__(self, main):
        super().__init__()
        self.m = main
        self.setAcceptDrops(True)
        self.ratio, self.t = 16 / 9, 0.0
        self.layers, self.sel, self.drag = [], None, None
        self.guides = False
        self.mode, self.hot, self.gd = "select", None, None
        self.zoom, self.pan, self.pan_d = 1.0, QPointF(0, 0), None     # zoom / keo canvas (chuot giua hoac Alt+keo)
        self.cam_view = False                        # True: nhin qua camera
        self.md, self.mesh_hot = None, None          # diem luoi dang keo / dang tro (cot, hang)
        self.setMouseTracking(True)
        self.setMinimumSize(320, 200)
        theme.bus.changed.connect(self.update)

    def set_time(self, t):
        self.t = t
        self.update()

    def set_mode(self, m):
        self.mode, self.hot, self.md, self.mesh_hot = m, None, None, None
        self.update()

    def base_w(self):
        return max(80.0, min(self.width() - 60.0, (self.height() - 60.0) * self.ratio))

    def canvas(self):
        W, H = self.width(), self.height()
        w = self.base_w() * self.zoom
        return QRectF((W - w) / 2 + self.pan.x(), (H - w / self.ratio) / 2 + self.pan.y(), w, w / self.ratio)

    def fit_view(self):
        """Ve zoom 100% va canvas nam giua khung."""
        self.zoom, self.pan = 1.0, QPointF(0, 0)
        self.update()

    def zoom_at(self, pos, factor):
        r = self.canvas()
        u, v = (pos.x() - r.left()) / r.width(), (pos.y() - r.top()) / r.height()
        self.zoom = max(0.1, min(16.0, self.zoom * factor))
        W, H = self.width(), self.height()
        w = self.base_w() * self.zoom
        h = w / self.ratio
        self.pan = QPointF(pos.x() - u * w - (W - w) / 2, pos.y() - v * h - (H - h) / 2)
        self.update()

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if d:
            self.zoom_at(e.position(), 1.15 ** (d / 120.0))
        e.accept()

    def body(self, L, r):
        if L.kind == "camera":
            return QRectF(-r.width() / 2, -r.height() / 2, r.width(), r.height())
        if L.kind == "light":
            return QRectF(-18, -18, 36, 36)            # tay nam de chon / keo; hieu ung ve bang draw_lights
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

    # ---------------------------------------------------------------- camera
    def view_cam(self):
        """Camera dang ap dung (khi bat 'Xem qua camera' hoac dang phat), hoac None."""
        if not (self.cam_view or getattr(self.m, "playing", False)):
            return None
        return next((C for C in self.layers if C.kind == "camera" and C.alive(self.t)), None)

    def cam_frame_tf(self, L, r):
        """Khung camera tren canvas (che do chinh sua): vi tri / xoay cua camera, co = 1/zoom."""
        t, c = self.t, r.center()
        m = QTransform()
        m.translate(c.x() + L.get("pos0", t) * r.width() / 200, c.y() - L.get("pos1", t) * r.height() / 200)
        s = 100.0 / max(5.0, L.get("scl0", t))
        if L.extra.get("cam") == "3d":
            m.rotate(L.get("rot0", t), Qt.XAxis)
            m.rotate(L.get("rot1", t), Qt.YAxis)
            s *= 1 + max(-100.0, min(100.0, L.get("pos2", t))) / 200
        m.rotate(L.get("rot2", t))
        m.scale(s, s)
        return m

    def cam_xf(self, C, r):
        """Phep bien doi canh -> man hinh khi nhin qua camera C (nghich dao cua phep bien doi camera)."""
        t, c = self.t, r.center()
        off = QPointF(C.get("pos0", t) * r.width() / 200, -C.get("pos1", t) * r.height() / 200)
        s = max(0.05, C.get("scl0", t) / 100)
        m = QTransform()
        m.translate(c.x(), c.y())
        m.rotate(-C.get("rot2", t))
        if C.extra.get("cam") == "3d":
            m.rotate(-C.get("rot1", t), Qt.YAxis)
            m.rotate(-C.get("rot0", t), Qt.XAxis)
            s /= 1 + max(-100.0, min(100.0, C.get("pos2", t))) / 200      # Z duong = lui ra xa
        m.scale(s, s)
        m.translate(-c.x() - off.x(), -c.y() - off.y())
        return m

    # ---------------------------------------------------------------- anh sang (2D: phu sang)
    def draw_lights(self, p, r):
        t = self.t
        for L in self.layers:
            if L.kind != "light" or not L.alive(t):
                continue
            a = max(0.0, min(1.0, L.get("op", t) / 100))
            col = QColor(L.color)
            p.save()
            p.setTransform(self.tf(L, r), True)
            p.setPen(Qt.NoPen)
            if L.extra.get("mode") == "3d":              # nguon sang 3D: chi hien dau hieu o 2D (hieu ung that nam o che do 3D F4)
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(col, 1.5, Qt.DashLine))
                p.drawEllipse(QPointF(0, 0), 12, 12)
                p.setFont(mk(theme.FONT_BODY, 9, QFont.DemiBold))
                p.drawText(QPointF(16, 4), "%s 3D" % L.extra.get("lt", "sun").upper())
                p.restore()
                continue
            p.setCompositionMode(QPainter.CompositionMode_Screen)
            lt, W, H = L.extra.get("lt", "sun"), r.width(), r.height()

            def tone(alpha, c=col):
                q = QColor(c)
                q.setAlphaF(max(0.0, min(1.0, alpha)))
                return q

            if lt == "ray":                              # tia: chum sang hinh non, huong theo goc xoay (0 = chieu xuong)
                Lg, w0, w1 = H * 1.3, W * 0.012, W * 0.22
                g = QLinearGradient(0, 0, 0, Lg)
                g.setColorAt(0, tone(a * 0.85))
                g.setColorAt(0.5, tone(a * 0.3))
                g.setColorAt(1, tone(0))
                p.setBrush(QBrush(g))
                p.drawPolygon(QPolygonF([QPointF(-w0, 0), QPointF(w0, 0), QPointF(w1, Lg), QPointF(-w1, Lg)]))
                g2 = QLinearGradient(0, 0, 0, Lg)
                g2.setColorAt(0, tone(a * 0.7))
                g2.setColorAt(1, tone(0))
                p.setBrush(QBrush(g2))
                p.drawPolygon(QPolygonF([QPointF(-w0 * 0.5, 0), QPointF(w0 * 0.5, 0), QPointF(w1 * 0.45, Lg), QPointF(-w1 * 0.45, Lg)]))
                R = W * 0.05
                gg = QRadialGradient(QPointF(0, 0), R)
                gg.setColorAt(0, tone(a))
                gg.setColorAt(1, tone(0))
                p.setBrush(QBrush(gg))
                p.drawEllipse(QPointF(0, 0), R, R)
            elif lt == "moon":                           # trang: quang xanh lanh + luoi liem
                R = W * 0.25
                g = QRadialGradient(QPointF(0, 0), R)
                g.setColorAt(0, tone(a * 0.8))
                g.setColorAt(0.3, tone(a * 0.3))
                g.setColorAt(1, tone(0))
                p.setBrush(QBrush(g))
                p.drawEllipse(QPointF(0, 0), R, R)
                rm = R * 0.12
                path = QPainterPath()
                path.addEllipse(QPointF(0, 0), rm, rm)
                cut = QPainterPath()
                cut.addEllipse(QPointF(rm * 0.45, -rm * 0.15), rm * 0.85, rm * 0.85)
                p.setBrush(tone(a, QColor("#f4f8ff")))
                p.drawPath(path.subtracted(cut))
            else:                                        # sun: quang nong + tia toa
                R = W * 0.4
                g = QRadialGradient(QPointF(0, 0), R)
                g.setColorAt(0, tone(a * 0.95))
                g.setColorAt(0.25, tone(a * 0.35))
                g.setColorAt(1, tone(0))
                p.setBrush(QBrush(g))
                p.drawEllipse(QPointF(0, 0), R, R)
                for i in range(14):
                    p.save()
                    p.rotate(i * 360 / 14)
                    p.drawPolygon(QPolygonF([QPointF(-R * 0.03, 0), QPointF(R * 0.03, 0), QPointF(0, -R * 0.95)]))
                    p.restore()
                p.setBrush(tone(a, QColor("#ffffff")))
                p.drawEllipse(QPointF(0, 0), R * 0.05, R * 0.05)
            p.restore()

    def draw_camera(self, p, r):
        if self.view_cam() is not None:
            return
        for C in self.layers:
            if C.kind != "camera" or not C.alive(self.t):
                continue
            m = self.tf(C, r)
            poly = m.map(QPolygonF(self.body(C, r)))
            sel = C is self.sel
            col = QColor("#ff8a3d")
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(col, 3 if sel else 2, Qt.SolidLine if sel else Qt.DashLine))
            p.drawPolygon(poly)
            o = m.map(QPointF(0, 0))
            p.setPen(QPen(col, 1.5))
            p.drawLine(QPointF(o.x() - 9, o.y()), QPointF(o.x() + 9, o.y()))
            p.drawLine(QPointF(o.x(), o.y() - 9), QPointF(o.x(), o.y() + 9))
            p.setFont(mk(theme.FONT_BODY, 10, QFont.DemiBold))
            p.drawText(poly.at(0) + QPointF(6, 16), "CAM " + ("3D" if C.extra.get("cam") == "3d" else "2D"))

    def tf(self, L, r, skew=True):
        if L.kind == "camera":
            return self.cam_frame_tf(L, r)
        t, c = self.t, r.center()
        z = max(-100.0, min(100.0, L.get("pos2", t)))
        f = 1 / (1 - z / 200)
        m = QTransform()
        m.translate(c.x() + L.get("pos0", t) * r.width() / 200, c.y() - L.get("pos1", t) * r.height() / 200)
        m.rotate(L.get("rot0", t), Qt.XAxis)
        m.rotate(L.get("rot1", t), Qt.YAxis)
        m.rotate(L.get("rot2", t))
        m.scale(f * L.get("scl0", t) / 100, f * L.get("scl1", t) / 100)
        if skew:                       # nghieng (hinh binh hanh) trong he toa do cua vat the
            ta = math.tan(math.radians(max(-80.0, min(80.0, L.get("skw0", t)))))
            tb = math.tan(math.radians(max(-80.0, min(80.0, L.get("skw1", t)))))
            if ta or tb:
                m = QTransform(1, tb, ta, 1, 0, 0) * m
        C = self.view_cam() if L.kind != "bg" else None
        if C is not None:
            m = m * self.cam_xf(C, r)
        return m

    def draw_layer(self, p, L, b):
        p.setPen(Qt.NoPen)
        if L.kind == "shape":
            p.setBrush(QColor(L.color))
            p.drawPath(form_path(L.extra, b))
        elif L.kind == "text":
            p.setPen(QColor(L.color))
            p.setFont(mk(theme.FONT_DISPLAY, max(8, int(b.height() * .6)), QFont.Bold))
            p.drawText(b, Qt.AlignCenter, L.text)
        elif L.kind in PAINTERS:               # loai lop do plugin them
            PAINTERS[L.kind](p, L, b, self.t)
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

    # ---------------------------------------------------------------- luoi meo (Mesh Warp)
    def mesh_points(self, L, b, t=None):
        """Luoi diem (hang x cot) trong toa do than lop; diem lech theo % kich thuoc (co key frame)."""
        t = self.t if t is None else t
        c, rw = L.mesh["cols"], L.mesh["rows"]
        pts = []
        for j in range(rw + 1):
            row = []
            for i in range(c + 1):
                dx, dy = L.mesh_off(i, j, t)
                row.append(QPointF(b.left() + b.width() * (i / c + dx / 100), b.top() + b.height() * (j / rw + dy / 100)))
            pts.append(row)
        return pts

    @staticmethod
    def _tri_xf(s, d):
        """Phep affine dua tam giac nguon s (3 diem) len tam giac dich d; None neu suy bien."""
        e1x, e1y, e2x, e2y = s[1].x() - s[0].x(), s[1].y() - s[0].y(), s[2].x() - s[0].x(), s[2].y() - s[0].y()
        f1x, f1y, f2x, f2y = d[1].x() - d[0].x(), d[1].y() - d[0].y(), d[2].x() - d[0].x(), d[2].y() - d[0].y()
        det = e1x * e2y - e1y * e2x
        if abs(det) < 1e-9:
            return None
        a11 = (f1x * e2y - f2x * e1y) / det
        a12 = (f2x * e1x - f1x * e2x) / det
        a21 = (f1y * e2y - f2y * e1y) / det
        a22 = (f2y * e1x - f1y * e2x) / det
        dx = d[0].x() - (a11 * s[0].x() + a12 * s[0].y())
        dy = d[0].y() - (a21 * s[0].x() + a22 * s[0].y())
        return QTransform(a11, a21, a12, a22, dx, dy)

    def draw_warped(self, p, L, b):
        """Ve lop vao 1 anh roi map tung o luoi (2 tam giac) len luoi da keo -> anh mop theo diem."""
        wt = p.worldTransform()
        sc = max(0.05, math.hypot(wt.m11(), wt.m12()))
        w, h = max(1.0, b.width()), max(1.0, b.height())
        s = max(1.0, min(4.0, sc * 1.5, 2000.0 / max(w, h)))
        src = QPixmap(int(math.ceil(w * s)), int(math.ceil(h * s)))
        src.fill(Qt.transparent)
        q = QPainter(src)
        q.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        q.scale(s, s)
        q.translate(-b.left(), -b.top())
        self.draw_layer(q, L, b)
        q.end()
        pts = self.mesh_points(L, b)
        xs = [pt.x() for row in pts for pt in row]
        ys = [pt.y() for row in pts for pt in row]
        bb = QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)).adjusted(-2, -2, 2, 2)
        os_ = max(1.0, min(s, 2400.0 / max(bb.width(), bb.height(), 1.0)))
        out = QPixmap(int(math.ceil(bb.width() * os_)), int(math.ceil(bb.height() * os_)))
        out.fill(Qt.transparent)
        o = QPainter(out)
        o.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        o.scale(os_, os_)
        o.translate(-bb.left(), -bb.top())
        cols, rows = L.mesh["cols"], L.mesh["rows"]
        cw, ch = src.width() / cols, src.height() / rows
        grow = 0.8 / os_
        for j in range(rows):
            for i in range(cols):
                sp = [QPointF(i * cw, j * ch), QPointF((i + 1) * cw, j * ch),
                      QPointF((i + 1) * cw, (j + 1) * ch), QPointF(i * cw, (j + 1) * ch)]
                dp = [pts[j][i], pts[j][i + 1], pts[j + 1][i + 1], pts[j + 1][i]]
                cell = QRectF(i * cw - 1, j * ch - 1, cw + 2, ch + 2).intersected(QRectF(src.rect()))
                for tri in ((0, 1, 2), (0, 2, 3)):
                    ss, dd = [sp[k] for k in tri], [dp[k] for k in tri]
                    xf = self._tri_xf(ss, dd)
                    if xf is None:
                        continue
                    cx = sum(v.x() for v in dd) / 3
                    cy = sum(v.y() for v in dd) / 3
                    big = []
                    for v in dd:                       # no tam giac ra ~1px de khong ho khe giua cac o
                        ex, ey = v.x() - cx, v.y() - cy
                        ln = math.hypot(ex, ey) or 1.0
                        big.append(QPointF(v.x() + ex / ln * grow, v.y() + ey / ln * grow))
                    path = QPainterPath()
                    path.addPolygon(QPolygonF(big))
                    path.closeSubpath()
                    o.save()
                    o.setClipPath(path, Qt.IntersectClip)
                    o.setTransform(xf, True)
                    o.drawPixmap(cell, src, cell)
                    o.restore()
        o.end()
        p.drawPixmap(bb, out, QRectF(out.rect()))

    def draw_full(self, p, L, b):
        if L.mesh_active() and L.kind not in ("bg", "audio"):
            self.draw_warped(p, L, b)
        else:
            self.draw_layer(p, L, b)

    def mesh_hit(self, L, pos):
        r = self.canvas()
        m = self.tf(L, r)
        pts = self.mesh_points(L, self.body(L, r))
        best = None
        for j, row in enumerate(pts):
            for i, pt in enumerate(row):
                w = m.map(pt)
                d = math.hypot(w.x() - pos.x(), w.y() - pos.y())
                if d < 10 and (best is None or d < best[0]):
                    best = (d, i, j)
        return (best[1], best[2]) if best else None

    def draw_mesh_edit(self, p, L, r):
        if not L.mesh_active():
            return
        m = self.tf(L, r)
        pts = self.mesh_points(L, self.body(L, r))
        wp = [[m.map(pt) for pt in row] for row in pts]
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(80, 200, 255, 210), 1.3))
        for row in wp:
            p.drawPolyline(QPolygonF(row))
        for i in range(len(wp[0])):
            p.drawPolyline(QPolygonF([wp[j][i] for j in range(len(wp))]))
        for j, row in enumerate(wp):
            for i, pt in enumerate(row):
                on = self.mesh_hot == (i, j) or self.md == (i, j)
                idx = j * (L.mesh["cols"] + 1) + i
                p.setPen(QPen(QColor("#000000"), 1))
                if L.mesh_has_key(idx):                     # diem co key frame: hinh thoi, vang dac neu key nam dung tai dau phat
                    now = L.mesh_has_key(idx, self.t)
                    p.setBrush(QColor("#ffd54a") if now else (QColor("#ffffff") if not on else QColor("#ffd54a")))
                    p.setPen(QPen(QColor("#ff9800" if now else "#000000"), 1.6))
                    s_ = 7.5 if on or now else 6.5
                    p.drawPolygon(QPolygonF([QPointF(pt.x(), pt.y() - s_), QPointF(pt.x() + s_, pt.y()),
                                             QPointF(pt.x(), pt.y() + s_), QPointF(pt.x() - s_, pt.y())]))
                else:
                    p.setBrush(QColor("#ffd54a") if on else QColor("#ffffff"))
                    p.drawEllipse(pt, 6 if on else 4.5, 6 if on else 4.5)

    # ---------------------------------------------------------------- nghieng (Skew)
    def skew_handles(self, L, r):
        b = self.body(L, r)
        m = self.tf(L, r)
        hw, hh = b.width() / 2, b.height() / 2
        return {"kt": m.map(QPointF(0, -hh)), "kb": m.map(QPointF(0, hh)),
                "kr": m.map(QPointF(hw, 0)), "kl": m.map(QPointF(-hw, 0))}

    def draw_skew(self, p, L, r):
        for hid, pt in self.skew_handles(L, r).items():
            on = self.active(hid)
            horiz = hid in ("kt", "kb")
            sl = 5.0 if horiz else 0.0
            sv = 0.0 if horiz else 5.0
            poly = QPolygonF([QPointF(pt.x() - 10 + sl, pt.y() - 5 - sv), QPointF(pt.x() + 10 + sl, pt.y() - 5 + sv),
                              QPointF(pt.x() + 10 - sl, pt.y() + 5 + sv), QPointF(pt.x() - 10 - sl, pt.y() + 5 - sv)])
            p.setPen(QPen(QColor("#000000"), 1))
            p.setBrush(QColor("#ffd54a") if on else QColor("#4cd0ff"))
            p.drawPolygon(poly)

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
        if self.mode == "skew":
            L = self.gizmo_layer()
            if L:
                for hid, hp in self.skew_handles(L, self.canvas()).items():
                    if abs(pt.x() - hp.x()) < 13 and abs(pt.y() - hp.y()) < 10:
                        return hid
            return None
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
        if h in ("kt", "kb", "kl", "kr"):
            inv, ok = g["m0"].inverted()
            if ok:
                qp = inv.map(QPointF(e.pos()))
                bd = self.body(L, r)
                hw, hh = max(1.0, bd.width() / 2), max(1.0, bd.height() / 2)
                step = prefs.get("snap_rot")
                if h in ("kt", "kb"):
                    ang = math.degrees(math.atan((-qp.x() if h == "kt" else qp.x()) / hh))
                    W(L, "skw0", max(-80.0, min(80.0, q(ang, step))))
                else:
                    ang = math.degrees(math.atan((qp.y() if h == "kr" else -qp.y()) / hw))
                    W(L, "skw1", max(-80.0, min(80.0, q(ang, step))))
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
        key = (T["checker_a"], T["checker_b"])
        if getattr(self, "_chk_key", None) != key:        # o ban co ve 1 lan thanh gach 40x40 (truoc day ~1000 fillRect / khung hinh)
            tile = QPixmap(40, 40)
            tp = QPainter(tile)
            for i in range(2):
                for j in range(2):
                    tp.fillRect(i * 20, j * 20, 20, 20, QColor(key[0]) if (i + j) % 2 else QColor(key[1]))
            tp.end()
            self._chk_tile, self._chk_key = tile, key
        p.fillRect(self.rect(), QBrush(self._chk_tile))
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
            elif L.kind not in ("audio", "camera", "light"):
                p.save()
                p.setTransform(self.tf(L, r), True)
                p.setOpacity(max(0.0, min(1.0, L.get("op", self.t) / 100)))
                if gk_material.mat_of(L):
                    gk_material.paint(self, p, L, self.body(L, r))
                else:
                    self.draw_full(p, L, self.body(L, r))
                p.restore()
        self.draw_lights(p, r)
        if self.guides:
            p.setPen(QPen(QColor(255, 255, 255, 70), 1, Qt.DashLine))
            for k in (1, 2):
                p.drawLine(QPointF(r.left() + r.width() * k / 3, r.top()), QPointF(r.left() + r.width() * k / 3, r.bottom()))
                p.drawLine(QPointF(r.left(), r.top() + r.height() * k / 3), QPointF(r.right(), r.top() + r.height() * k / 3))
            p.setPen(QPen(QColor(255, 255, 255, 50), 1))
            p.drawLine(QPointF(r.center().x(), r.top()), QPointF(r.center().x(), r.bottom()))
            p.drawLine(QPointF(r.left(), r.center().y()), QPointF(r.right(), r.center().y()))
        p.restore()
        self.draw_camera(p, r)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(T["frame"]), 2))
        p.drawRect(r)
        names = {16 / 9: "16:9", 9 / 16: "9:16", 1.0: "1:1", 4 / 5: "4:5"}
        p.setPen(QColor(T["text2"]))
        p.setFont(mk(theme.FONT_BODY, 11, QFont.DemiBold))
        p.drawText(QRectF(r.left(), r.bottom() + 6, 240, 20), Qt.AlignLeft | Qt.AlignVCenter,
                   "Canvas " + names.get(self.ratio, "%.2f" % self.ratio) + ("   ·   %d%%" % round(self.zoom * 100) if abs(self.zoom - 1) > 1e-3 else ""))
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
            elif self.mode == "skew":
                self.draw_skew(p, L, r)
            elif self.mode == "mesh":
                self.draw_mesh_edit(p, L, r)
            p.setPen(QPen(QColor("#000000"), 1))
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(o, 4, 4)

    def hit(self, pos):
        r = self.canvas()
        if self.view_cam() is None:                      # khung camera: chon bang cach bam vao vien
            for C in reversed(self.layers):
                if C.kind == "camera" and C.alive(self.t):
                    poly = self.tf(C, r).map(QPolygonF(self.body(C, r)))
                    pts = [poly.at(i) for i in range(poly.count())]
                    if any(seg_dist(QPointF(pos), pts[i], pts[(i + 1) % len(pts)]) < 8 for i in range(len(pts))):
                        return C
        for L in reversed(self.layers):
            if L.kind in ("bg", "audio", "camera") or not L.alive(self.t):
                continue
            inv, ok = self.tf(L, r).inverted()
            if ok and self.body(L, r).contains(inv.map(QPointF(pos))):
                return L
        return None

    def mousePressEvent(self, e):
        if e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton and e.modifiers() & Qt.AltModifier):
            self.pan_d = (QPointF(e.pos()), QPointF(self.pan))
            self.setCursor(Qt.ClosedHandCursor)
            return
        if e.button() == Qt.RightButton and self.mode == "mesh":
            L = self.gizmo_layer()
            hit = self.mesh_hit(L, QPointF(e.pos())) if (L and L.mesh_active()) else None
            if hit:
                self.m.mesh_toggle_key(L, hit[1] * (L.mesh["cols"] + 1) + hit[0])
                self.mesh_picked.emit(hit[1] * (L.mesh["cols"] + 1) + hit[0])
            return
        if e.button() != Qt.LeftButton:
            return
        L = self.gizmo_layer()
        if L and self.mode == "mesh" and L.mesh_active():
            hit = self.mesh_hit(L, QPointF(e.pos()))
            if hit:
                self.md = hit
                self.mesh_picked.emit(hit[1] * (L.mesh["cols"] + 1) + hit[0])
                self.update()
                return
        if L and self.mode != "select":
            o = self.origin(L, self.canvas())
            h = self.gizmo_hit(e.pos(), o)
            if h:
                ang = math.degrees(math.atan2(e.y() - o.y(), e.x() - o.x()))
                self.gd = dict(h=h, p0=QPointF(e.pos()), o=o, last=ang, acc=0.0, m0=self.tf(L, self.canvas(), skew=False),
                               base={k: L.get(k, self.t) for k in PKEYS})
                self.update()
                return
        Lh = self.hit(e.pos())
        self.picked.emit(Lh)
        movable = self.mode in ("select", "move")
        self.drag = (e.pos(), Lh.get("pos0", self.t), Lh.get("pos1", self.t)) if (Lh and movable) else None

    def mouseMoveEvent(self, e):
        if self.pan_d is not None:
            self.pan = self.pan_d[1] + (QPointF(e.pos()) - self.pan_d[0])
            self.update()
            return
        if self.md is not None and self.sel is not None:
            self.mesh_drag(e)
            return
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
        if L and self.mode == "mesh":
            hit = self.mesh_hit(L, QPointF(e.pos())) if L.mesh_active() else None
            if hit != self.mesh_hot:
                self.mesh_hot = hit
                self.setCursor(Qt.PointingHandCursor if hit else Qt.ArrowCursor)
                self.update()
            return
        h = self.gizmo_hit(e.pos(), self.origin(L, self.canvas())) if (L and self.mode != "select") else None
        if h != self.hot:
            self.hot = h
            self.setCursor(Qt.PointingHandCursor if h else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, e):
        self.hot = None
        self.update()

    def mesh_drag(self, e):
        L, r = self.sel, self.canvas()
        inv, ok = self.tf(L, r).inverted()
        if not ok:
            return
        i, j = self.md
        loc = inv.map(QPointF(e.pos()))
        b = self.body(L, r)
        c, rw = L.mesh["cols"], L.mesh["rows"]
        idx = j * (c + 1) + i
        dx = (loc.x() - b.left()) / max(1.0, b.width()) * 100 - i / c * 100
        dy = (loc.y() - b.top()) / max(1.0, b.height()) * 100 - j / rw * 100
        if e.modifiers() & Qt.ControlModifier:
            dx, dy = round(dx / 2) * 2, round(dy / 2) * 2
        self.m.write(L, "mwx%d" % idx, dx)
        self.m.write(L, "mwy%d" % idx, dy)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MiddleButton:
            self.fit_view()

    def mouseReleaseEvent(self, e):
        if self.pan_d is not None:
            self.pan_d = None
            self.setCursor(Qt.ArrowCursor)
            return
        self.drag, self.gd, self.md = None, None, None
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
        self.timelbl = QLabel("00:00.0 / 00:05.0")
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
    reordered = Signal(object, int)          # keo tha: (lop, vi tri moi trong stage.layers)
    ROW, TOP = 44, 46

    def __init__(self):
        super().__init__()
        self.layers, self.sel, self.hot, self.scroll = [], None, None, 0
        self.press, self.drag_y, self.drop = None, None, None       # keo tha doi thu tu lop
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

    def drop_index(self, y):
        """Hang (theo danh sach hien thi, tren xuong duoi) ma lop keo duoc tha vao."""
        i = int(round((y - self.TOP + self.scroll) / self.ROW - 0.5))
        return max(0, min(len(self.layers) - 2, i))          # hang cuoi (Nen) khong dung duoc

    def mouseMoveEvent(self, e):
        if self.press is not None and (e.buttons() & Qt.LeftButton):
            L = self.layers[self.press[0]]
            if self.drag_y is None and abs(e.y() - self.press[1]) > 6 and L.kind != "bg":
                self.drag_y = e.y()
                self.setCursor(Qt.ClosedHandCursor)
            if self.drag_y is not None:
                self.drag_y = e.y()
                self.drop = self.drop_index(e.y())
                self.update()
                return
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
            self.press = (i, e.y())

    def mouseReleaseEvent(self, e):
        if self.press is not None and self.drag_y is not None and self.drop is not None:
            L = self.layers[self.press[0]]
            n = len(self.layers)
            self.reordered.emit(L, n - 1 - self.drop)        # hang hien thi -> chi so trong stage.layers
        self.press = self.drag_y = self.drop = None
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def icon(self, p, L, r):
        col = {"shape": L.color, "text": "#e0a526", "image": "#2f8fe0", "video": "#2f8fe0",
               "audio": "#2fb37a", "camera": "#ff8a3d", "light": "#f5c542"}.get(L.kind, L.color if L.kind in PAINTERS else T["bg3"])
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(col))
        p.drawRoundedRect(r, 7, 7)
        c, k = r.center(), L.kind
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.setBrush(Qt.NoBrush)
        if k == "shape":
            p.drawPath(form_path({**L.extra, "round": 3}, QRectF(c.x() - 6, c.y() - 6, 12, 12)))
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
        elif k == "light":
            p.drawEllipse(QPointF(c.x(), c.y()), 3.5, 3.5)
            for i in range(8):
                a_ = math.radians(i * 45)
                p.drawLine(QPointF(c.x() + 6 * math.cos(a_), c.y() + 6 * math.sin(a_)), QPointF(c.x() + 9 * math.cos(a_), c.y() + 9 * math.sin(a_)))
        elif k == "camera":
            p.drawRoundedRect(QRectF(c.x() - 7, c.y() - 4, 10, 8), 2, 2)
            p.drawPolyline(QPolygonF([QPointF(c.x() + 3, c.y() - 1), QPointF(c.x() + 8, c.y() - 4), QPointF(c.x() + 8, c.y() + 4), QPointF(c.x() + 3, c.y() + 1)]))
        elif k == "audio":
            for dx, h in ((-5, 5), (0, 10), (5, 6)):
                p.drawLine(QPointF(c.x() + dx, c.y() - h / 2), QPointF(c.x() + dx, c.y() + h / 2))
        elif k in ICONS:                       # bieu tuong do plugin them (but trang, khong to)
            p.setBrush(QColor("#ffffff"))
            ICONS[k](p, r)
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
        if self.drag_y is not None and self.drop is not None:      # vach chen + ban sao noi cua lop dang keo
            src = self.press[0]
            ly = self.TOP + (self.drop + (1 if self.drop > src else 0)) * self.ROW - self.scroll - 3
            p.setPen(QPen(QColor(T["accent"]), 3))
            p.drawLine(QPointF(10, ly), QPointF(W - 10, ly))
            gr = QRectF(8, self.drag_y - (self.ROW - 6) / 2, W - 16, self.ROW - 6)
            p.setOpacity(0.55)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(T["accent_dim"]))
            p.drawRoundedRect(gr, 9, 9)
            p.setOpacity(1)
            p.setPen(QColor(T["text"]))
            p.drawText(QRectF(gr.left() + 42, gr.top(), gr.width() - 60, gr.height()), Qt.AlignVCenter, self.layers[src].name)
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
        for k, (kd, _r, _c) in KINDS.items():
            if kd == "light":
                continue                                   # nam trong menu con "Ánh sáng"
            if kd == "shape" and k in FORMS and k != "Hình vuông":
                continue                                   # cac hinh khac nam trong menu con "Hình dạng"
            self.add_menu.addAction(k)
        lm = self.add_menu.addMenu("💡 Ánh sáng")
        for md, hint in (("2D", "phủ sáng"), ("3D", "nguồn sáng thật, có bóng đổ")):
            sm = lm.addMenu("%s  (%s)" % (md, hint))
            for k, (kd, _r, _c) in KINDS.items():
                if kd == "light" and k.endswith(md):
                    sm.addAction(k)
        shapes = self.add_menu.addMenu("Hình dạng  (%d)" % len(FORMS))
        for grp, items in FORM_GROUPS:
            gm = shapes.addMenu(grp)
            for name, _k in items:
                gm.addAction(name)
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
    mesh_changed = Signal(bool, int, int)      # bat/tat, so cot, so hang
    mesh_reset = Signal()
    mesh_keys = Signal(bool)                     # True: key ca luoi tai dau phat / False: xoa key luoi
    ease_all = Signal(str)                       # dat 1 kieu noi suy cho moi key cua lop
    mat_changed = Signal(str, int)             # chat lieu, cuong do %
    shape_changed = Signal(str, int, int, int)   # dang, so canh, do nhon %, bo goc

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

        self.s_shape = Section("Hình dạng")
        self.form_cb = QComboBox()
        self.form_cb.setMaxVisibleItems(20)
        for k, n in FORM_NAMES:
            self.form_cb.addItem(n, k)
        self.s_shape.bl.addWidget(self.form_cb)
        shg = QGridLayout()
        self.sh_sides, self.sh_inner, self.sh_round = QSpinBox(), QSpinBox(), QSpinBox()
        self.sh_sides.setRange(3, 24)
        self.sh_inner.setRange(10, 90)
        self.sh_inner.setSuffix(" %")
        self.sh_round.setRange(0, 400)
        for r_, (cap, w_) in enumerate((("Số cạnh / cánh", self.sh_sides), ("Độ nhọn sao", self.sh_inner),
                                         ("Bo góc (px)", self.sh_round))):
            shg.addWidget(QLabel(cap), r_, 0)
            shg.addWidget(w_, r_, 1)
        self.s_shape.bl.addLayout(shg)
        for w_ in (self.sh_sides, self.sh_inner, self.sh_round):
            w_.valueChanged.connect(self._shape)
        self.form_cb.activated.connect(lambda _: self._shape())
        pv.addWidget(self.s_shape)

        self.s_mat = Section("Chất liệu")
        self.mat_cb = QComboBox()
        for k, n in gk_material.MATS:
            self.mat_cb.addItem(n, k)
        self.mat_amt = QSlider(Qt.Horizontal)
        self.mat_amt.setRange(0, 100)
        self.mat_amt.setValue(70)
        self.s_mat.bl.addWidget(self.mat_cb)
        self.s_mat.bl.addWidget(QLabel("Cường độ"))
        self.s_mat.bl.addWidget(self.mat_amt)
        self.mat_cb.activated.connect(lambda _: self._mat())
        self.mat_amt.valueChanged.connect(self._mat)
        pv.addWidget(self.s_mat)

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
        lab = QLabel("Nghiêng °")
        lab.setObjectName("Sub")
        lab.setFixedWidth(52)
        grid.addWidget(lab, 3, 0)
        for c, (key, ax) in enumerate((("skw0", "x"), ("skw1", "y"))):
            sp = ScrubSpin(ax, 0.5)
            sp.setToolTip("Nghiêng ngang (X) / dọc (Y) theo độ · hoặc dùng công cụ Nghiêng (Y) kéo trên canvas")
            sp.valueChanged.connect(lambda v, k=key: self._pill(k, v))
            self.pills[key] = sp
            grid.addWidget(sp, 3, c + 1)
        self.pills["scl2"].setToolTip("Chưa dùng ở canvas 2D")
        s2.bl.addLayout(grid)
        hint = QLabel("Kéo ngang trên ô số để đổi giá trị · bấm để gõ số")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        s2.bl.addWidget(hint)
        pv.addWidget(s2)

        s2m = Section("Lưới méo (Mesh Warp)")
        self.mesh_on = QCheckBox("Bật lưới méo cho lớp này")
        self.mesh_on.setToolTip("Phủ lưới lên vật thể: kéo điểm nào ảnh móp theo điểm đó (công cụ Lưới méo - T)")
        s2m.bl.addWidget(self.mesh_on)
        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("Cột"))
        self.mesh_c = QSpinBox()
        self.mesh_c.setRange(1, 32)
        self.mesh_c.setValue(3)
        mrow.addWidget(self.mesh_c)
        mrow.addWidget(QLabel("Hàng"))
        self.mesh_r = QSpinBox()
        self.mesh_r.setRange(1, 32)
        self.mesh_r.setValue(3)
        mrow.addWidget(self.mesh_r)
        mrow.addStretch()
        s2m.bl.addLayout(mrow)
        kr = QHBoxLayout()
        self.mesh_key = QPushButton("◆  Key cả lưới")
        self.mesh_key.setObjectName("SmallBtn")
        self.mesh_key.setToolTip("Ghi key cho mọi điểm lưới tại đầu phát (hoặc nhấp chuột phải vào 1 điểm để key riêng điểm đó)")
        self.mesh_unkey = QPushButton("◇  Xoá key lưới")
        self.mesh_unkey.setObjectName("SmallBtn")
        self.mesh_unkey.setToolTip("Xoá key của mọi điểm lưới tại đầu phát")
        kr.addWidget(self.mesh_key)
        kr.addWidget(self.mesh_unkey)
        s2m.bl.addLayout(kr)
        self.mesh_key.clicked.connect(lambda: self.mesh_keys.emit(True))
        self.mesh_unkey.clicked.connect(lambda: self.mesh_keys.emit(False))
        self.mesh_rst = QPushButton("↺  Đặt lại lưới")
        self.mesh_rst.setObjectName("SmallBtn")
        self.mesh_rst.setToolTip("Xoá mọi độ lệch + key frame của các điểm lưới")
        s2m.bl.addWidget(self.mesh_rst)
        mh = QLabel("Đổi số cột/hàng sẽ đặt lại lưới. Bật Tự động key rồi kéo điểm ở các thời điểm khác nhau để tạo chuyển động méo.")
        mh.setObjectName("Hint")
        mh.setWordWrap(True)
        s2m.bl.addWidget(mh)
        self.mesh_on.toggled.connect(self._mesh)
        self.mesh_c.valueChanged.connect(self._mesh)
        self.mesh_r.valueChanged.connect(self._mesh)
        self.mesh_rst.clicked.connect(self.mesh_reset)
        pv.addWidget(s2m)

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
        self.smooth_btn = QPushButton("〰  Làm mượt toàn bộ")
        self.smooth_btn.setObjectName("SmallBtn")
        self.smooth_btn.setToolTip("Đặt mọi key của lớp sang nội suy Spline: tốc độ liền mạch qua từng key, không khựng, không vượt quá giá trị key")
        self.smooth_btn.clicked.connect(lambda: self.ease_all.emit("smooth"))
        s3.bl.addWidget(self.smooth_btn)
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

    def _mat(self, *_):
        if not self._sync:
            self.mat_changed.emit(self.mat_cb.currentData(), self.mat_amt.value())

    def _shape(self, *_):
        if not self._sync:
            self.shape_changed.emit(self.form_cb.currentData(), self.sh_sides.value(), self.sh_inner.value(),
                                    self.sh_round.value())

    def _mesh(self, *_):
        if not self._sync:
            self.mesh_changed.emit(self.mesh_on.isChecked(), self.mesh_c.value(), self.mesh_r.value())

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
        has_mat = L is not None and L.kind in gk_material.KINDS
        self.s_mat.setVisible(has_mat)
        if has_mat:
            m = L.extra.get("mat") or {}
            self.mat_cb.setCurrentIndex(max(0, self.mat_cb.findData(m.get("type", "none"))))
            self.mat_amt.setValue(int(m.get("amt", 70)))
        is_shape = L is not None and L.kind == "shape"
        self.s_shape.setVisible(is_shape)
        if is_shape:
            ex = L.extra
            form = ex.get("form", "rect")
            self.form_cb.setCurrentIndex(max(0, self.form_cb.findData(form)))
            self.sh_sides.setValue(int(ex.get("sides", 5 if form == "star" else 6)))
            self.sh_inner.setValue(int(ex.get("inner", 45)))
            self.sh_round.setValue(int(ex.get("round", 16)))
            self.sh_sides.setEnabled(form in ("polygon", "star"))
            self.sh_inner.setEnabled(form == "star")
            self.sh_round.setEnabled(form == "rect")
        for w in (self.mesh_on, self.mesh_c, self.mesh_r, self.mesh_rst, self.mesh_key, self.mesh_unkey):
            w.setEnabled(moves)
        if L is not None:
            for w, v in ((self.mesh_on, bool(L.mesh.get("on"))), (self.mesh_c, L.mesh["cols"]), (self.mesh_r, L.mesh["rows"])):
                w.blockSignals(True)
                (w.setChecked if w is self.mesh_on else w.setValue)(v)
                w.blockSignals(False)
        self.op_sl.setEnabled(moves)
        self.op_sl.setValue(int(L.get("op", t)) if L else 100)
        self.name_in.setEnabled(L is not None and L.kind != "bg")
        self.col_btn.setEnabled(L is not None and (L.kind in ("bg", "shape", "text", "light") or L.kind in PAINTERS))
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
        self.smooth_btn.setEnabled(L is not None and bool(L.kf))
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
