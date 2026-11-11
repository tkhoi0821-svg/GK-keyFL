"""Timeline (clip, thuoc do, playhead) + Do thi key frame."""
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QFont, QFontMetrics, QPainterPath, QPolygonF, QLinearGradient
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QPushButton, QSlider,
                             QGraphicsView, QGraphicsScene, QGraphicsRectItem, QFrame)
import gk_theme as theme
from gk_theme import T, mk
from gk_model import TOTAL, TRACK_H, RULER_H, TRACKS, COLORS, CHANNELS


def tc(s):
    return "%02d:%02d" % (int(s) // 60, int(s) % 60)


class Clip(QGraphicsRectItem):
    def __init__(self, tl, name, row, start, dur):
        super().__init__()
        self.tl, self.name, self.row, self.start, self.dur = tl, name, row, start, dur
        self.color = QColor(COLORS[TRACKS[row]])
        self.setFlags(QGraphicsRectItem.ItemIsMovable | QGraphicsRectItem.ItemIsSelectable |
                      QGraphicsRectItem.ItemSendsGeometryChanges)
        self.layout()

    def layout(self):
        self.setRect(0, 0, self.dur * self.tl.pps, TRACK_H - 6)
        self.setPos(self.start * self.tl.pps, RULER_H + 3 + self.row * TRACK_H)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.ItemPositionChange:
            x = max(0, round(value.x() / self.tl.pps * 10) / 10)
            row = max(0, min(len(TRACKS) - 1, round((value.y() - RULER_H - 3) / TRACK_H)))
            self.start, self.row = x, row
            value.setX(x * self.tl.pps)
            value.setY(RULER_H + 3 + row * TRACK_H)
        return super().itemChange(change, value)

    def paint(self, p, *_):
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(0.5, 0.5, -0.5, -0.5)
        base = self.color
        g = QLinearGradient(0, r.top(), 0, r.bottom())
        g.setColorAt(0, base.lighter(125 if self.isSelected() else 112))
        g.setColorAt(1, base.darker(115))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor("#ffffff"), 2) if self.isSelected() else QPen(base.darker(150), 1))
        p.drawRoundedRect(r, 6, 6)
        p.setPen(QColor("#ffffff"))
        p.setFont(mk(theme.FONT_BODY, 11, QFont.DemiBold))
        w = int(r.width() - 14)
        if w > 12:
            p.drawText(QRectF(r.left() + 8, r.top(), w, r.height()), Qt.AlignVCenter | Qt.AlignLeft,
                       QFontMetrics(p.font()).elidedText(self.name, Qt.ElideRight, w))


class Timeline(QGraphicsView):
    seek = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.pps = 60.0
        self.sc = QGraphicsScene(self)
        self.setScene(self.sc)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.clips = []
        self.t = 0.0
        theme.bus.changed.connect(lambda: self.viewport().update())
        self.refresh()

    def add_clip(self, name, row, start, dur):
        c = Clip(self, name, row, start, dur)
        self.sc.addItem(c)
        self.clips.append(c)
        return c

    def refresh(self):
        self.sc.setSceneRect(0, 0, TOTAL * self.pps + 200, RULER_H + len(TRACKS) * TRACK_H)
        for c in self.clips:
            c.layout()
        self.set_time(self.t)
        self.viewport().update()

    def set_time(self, t):
        self.t = t
        self.viewport().update()

    def drawBackground(self, p, rect):
        p.fillRect(rect, QColor(T["bg0"]))
        for i in range(len(TRACKS)):
            y = RULER_H + i * TRACK_H
            p.fillRect(QRectF(rect.left(), y, rect.width(), TRACK_H), QColor(T["track_a"] if i % 2 == 0 else T["track_b"]))
            p.setPen(QPen(QColor(T["line"]), 1))
            p.drawLine(int(rect.left()), y + TRACK_H, int(rect.right()), y + TRACK_H)
        p.fillRect(QRectF(rect.left(), 0, rect.width(), RULER_H), QColor(T["bg2"]))
        p.setPen(QPen(QColor(T["line"]), 1))
        p.drawLine(int(rect.left()), RULER_H, int(rect.right()), RULER_H)
        lab = 1 if self.pps >= 90 else (2 if self.pps >= 45 else 5)
        sub = 0.5 if self.pps >= 120 else 1.0
        p.setFont(mk(theme.FONT_BODY, 10))
        s0 = max(0, int(rect.left() / self.pps) - 1)
        s1 = int(min(TOTAL, rect.right() / self.pps + 1))
        n = int(s0 / sub)
        while n * sub <= s1:
            s = n * sub
            x = int(s * self.pps)
            major = abs(s - round(s)) < 1e-6 and int(round(s)) % lab == 0
            p.setPen(QColor(T["text2"] if major else T["text3"]))
            p.drawLine(x, RULER_H - (12 if major else 6), x, RULER_H)
            if major:
                p.drawText(x + 4, 14, tc(s))
            n += 1

    def drawForeground(self, p, rect):
        x = self.t * self.pps
        p.setRenderHint(QPainter.Antialiasing)
        col = QColor(T["playhead"])
        p.setPen(QPen(col, 2))
        p.drawLine(QPointF(x, RULER_H - 2), QPointF(x, self.sc.height()))
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawPolygon(QPolygonF([QPointF(x - 7, 3), QPointF(x + 7, 3), QPointF(x + 7, 12), QPointF(x, RULER_H - 2),
                                 QPointF(x - 7, 12)]))

    def mousePressEvent(self, e):
        if e.y() < RULER_H:
            self.seek.emit(max(0, min(TOTAL, self.mapToScene(e.pos()).x() / self.pps)))
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and e.y() < RULER_H and not self.sc.mouseGrabberItem():
            self.seek.emit(max(0, min(TOTAL, self.mapToScene(e.pos()).x() / self.pps)))
        super().mouseMoveEvent(e)

    def split(self):
        for c in list(self.sc.selectedItems()):
            if c.start < self.t < c.start + c.dur:
                old = c.dur
                c.dur = self.t - c.start
                self.add_clip(c.name, c.row, self.t, old - c.dur)
        self.refresh()

    def delete(self):
        for c in list(self.sc.selectedItems()):
            self.sc.removeItem(c)
            self.clips.remove(c)


class LayerClip(Clip):
    def __init__(self, tl, L, row, start, dur):
        super().__init__(tl, L.name, row, start, dur)
        self.layer = L

    def paint(self, p, *a):
        super().paint(p, *a)
        times = {t for v in self.layer.kf.values() for t, _ in v}
        p.setBrush(QColor(T["key"]))
        p.setPen(QPen(QColor("#000000"), 1))
        y = self.rect().height() - 9
        for t in times:
            x = (t - self.start) * self.tl.pps
            if 0 <= x <= self.rect().width():
                p.drawPolygon(QPolygonF([QPointF(x, y - 6), QPointF(x + 6, y), QPointF(x, y + 6), QPointF(x - 6, y)]))


class LTimeline(Timeline):
    def add_layer_clip(self, L, row, start, dur):
        c = LayerClip(self, L, row, start, dur)
        self.sc.addItem(c)
        self.clips.append(c)
        L.clips.append(c)
        return c

    def remove_clip(self, c):
        self.sc.removeItem(c)
        self.clips.remove(c)
        c.layer.clips.remove(c)

    def clear(self):
        for c in list(self.clips):
            self.remove_clip(c)

    def split(self):
        for c in list(self.sc.selectedItems()):
            if isinstance(c, LayerClip) and c.start < self.t < c.start + c.dur:
                old = c.dur
                c.dur = self.t - c.start
                self.add_layer_clip(c.layer, c.row, self.t, old - c.dur)
        self.refresh()

    def delete(self):
        for c in list(self.sc.selectedItems()):
            if isinstance(c, LayerClip):
                self.remove_clip(c)
        self.viewport().update()


class TrackHeaders(QWidget):
    """Cot ten track ben trai timeline (khop voi thuoc do + hang track)."""

    def __init__(self):
        super().__init__()
        self.setFixedWidth(84)
        theme.bus.changed.connect(self.update)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(T["bg1"]))
        p.fillRect(QRectF(0, 0, self.width(), RULER_H), QColor(T["bg2"]))
        p.setPen(QPen(QColor(T["line"]), 1))
        p.drawLine(0, RULER_H, self.width(), RULER_H)
        p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())
        p.setFont(mk(theme.FONT_BODY, 12, QFont.DemiBold))
        for i, n in enumerate(TRACKS):
            y = RULER_H + i * TRACK_H
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(COLORS[n]))
            p.drawRoundedRect(QRectF(10, y + 12, 6, TRACK_H - 24), 3, 3)
            p.setPen(QColor(T["text"]))
            p.drawText(QRectF(24, y, self.width() - 28, TRACK_H), Qt.AlignVCenter | Qt.AlignLeft, n)
            p.setPen(QPen(QColor(T["line"]), 1))
            p.drawLine(0, y + TRACK_H, self.width(), y + TRACK_H)


class TimelinePanel(QWidget):
    """Thanh cong cu + cot track + timeline."""

    def __init__(self, tl):
        super().__init__()
        self.setObjectName("Panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.tl = tl
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        bar = QWidget()
        bar.setObjectName("ViewBar")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        h = QHBoxLayout(bar)
        h.setContentsMargins(10, 5, 10, 5)
        h.setSpacing(6)
        self.split_btn, self.del_btn = QPushButton("✂  Split"), QPushButton("🗑  Delete")
        for b in (self.split_btn, self.del_btn):
            b.setObjectName("SmallBtn")
            h.addWidget(b)
        self.split_btn.clicked.connect(tl.split)
        self.del_btn.clicked.connect(tl.delete)
        h.addSpacing(10)
        self.timelbl = QLabel("00:00.0 / 00:30.0")
        self.timelbl.setObjectName("Timecode")
        h.addWidget(self.timelbl)
        h.addStretch()
        h.addWidget(QLabel("Zoom"))
        self.zoom = QSlider(Qt.Horizontal)
        self.zoom.setRange(20, 200)
        self.zoom.setValue(60)
        self.zoom.setFixedWidth(150)
        self.zoom.valueChanged.connect(lambda val: (setattr(tl, "pps", float(val)), tl.refresh()))
        h.addWidget(self.zoom)
        v.addWidget(bar)
        row = QHBoxLayout()
        row.setSpacing(0)
        row.addWidget(TrackHeaders())
        row.addWidget(tl, 1)
        v.addLayout(row, 1)
        self.setMinimumHeight(RULER_H + len(TRACKS) * TRACK_H + 48)


# ====================================================================== do thi key frame
class GraphPlot(QWidget):
    """Ve duong cong cua 1 kenh (vi tri/xoay/ti le/do mo) theo thoi gian; keo diem de sua key frame."""
    seek = pyqtSignal(float)
    edited = pyqtSignal()
    ML, MR, MT, MB = 58, 16, 14, 26

    def __init__(self):
        super().__init__()
        self.layer, self.key, self.t = None, "pos0", 0.0
        self.drag, self.hot, self.yr = None, None, None
        self.setMouseTracking(True)
        self.setMinimumHeight(110)
        theme.bus.changed.connect(self.update)

    def set_layer(self, L):
        self.layer = L
        self.update()

    def set_key(self, k):
        self.key = k
        self.update()

    def set_time(self, t):
        self.t = t
        self.update()

    def plot(self):
        return QRectF(self.ML, self.MT, max(10, self.width() - self.ML - self.MR), max(10, self.height() - self.MT - self.MB))

    def keys(self):
        return sorted(self.layer.kf.get(self.key, [])) if self.layer else []

    def yrange(self):
        if self.yr and self.drag is not None:
            return self.yr
        L = self.layer
        vals = [v for _, v in self.keys()]
        if L:
            vals.append(L.get(self.key, 0.0))
            vals.append(L.get(self.key, TOTAL))
        if not vals:
            vals = [0.0, 1.0]
        lo, hi = min(vals), max(vals)
        pad = (hi - lo) * 0.2 or max(1.0, abs(hi) * 0.2)
        return lo - pad, hi + pad

    def px(self, t, v, yr):
        r = self.plot()
        return QPointF(r.left() + t / TOTAL * r.width(), r.bottom() - (v - yr[0]) / ((yr[1] - yr[0]) or 1) * r.height())

    def unpx(self, pos, yr):
        r = self.plot()
        t = max(0.0, min(TOTAL, (pos.x() - r.left()) / r.width() * TOTAL))
        v = yr[0] + (r.bottom() - pos.y()) / r.height() * (yr[1] - yr[0])
        return t, v

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(T["bg1"]))
        r = self.plot()
        p.fillRect(r, QColor(T["bg0"]))
        yr = self.yrange()
        p.setFont(mk(theme.FONT_BODY, 10))
        for i in range(5):
            y = r.top() + r.height() * i / 4
            p.setPen(QPen(QColor(T["line"]), 1))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            val = yr[1] - (yr[1] - yr[0]) * i / 4
            p.setPen(QColor(T["text3"]))
            p.drawText(QRectF(2, y - 8, self.ML - 8, 16), Qt.AlignRight | Qt.AlignVCenter, "%.4g" % val)
        step = 5 if r.width() < 700 else 1
        for s in range(0, int(TOTAL) + 1, step):
            x = r.left() + s / TOTAL * r.width()
            p.setPen(QPen(QColor(T["line"]), 1))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            p.setPen(QColor(T["text3"]))
            p.drawText(QRectF(x - 24, r.bottom() + 4, 48, 16), Qt.AlignCenter, tc(s))
        L = self.layer
        if L is None:
            p.setPen(QColor(T["text3"]))
            p.setFont(mk(theme.FONT_BODY, 13))
            p.drawText(r, Qt.AlignCenter, "Chọn một lớp để xem đồ thị key frame")
            return
        p.save()
        p.setClipRect(r)
        path = QPainterPath()
        n = 200
        for i in range(n + 1):
            t = TOTAL * i / n
            pt = self.px(t, L.get(self.key, t), yr)
            path.moveTo(pt) if i == 0 else path.lineTo(pt)
        p.setPen(QPen(QColor(T["accent_hi"]), 2.2))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        x = r.left() + self.t / TOTAL * r.width()
        p.setPen(QPen(QColor(T["playhead"]), 1.5))
        p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
        p.restore()
        ks = self.keys()
        for i, (t, v) in enumerate(ks):
            c = self.px(t, v, yr)
            hot = (i == self.hot)
            s = 7 if hot else 6
            p.setBrush(QColor("#ffffff") if hot else QColor(T["key"]))
            p.setPen(QPen(QColor("#000000"), 1))
            p.drawPolygon(QPolygonF([QPointF(c.x(), c.y() - s), QPointF(c.x() + s, c.y()),
                                     QPointF(c.x(), c.y() + s), QPointF(c.x() - s, c.y())]))
        if not ks:
            p.setPen(QColor(T["text3"]))
            p.setFont(mk(theme.FONT_BODY, 12))
            p.drawText(QRectF(r.left(), r.top() + 6, r.width(), 20), Qt.AlignCenter,
                       "Kênh này chưa có key frame — bấm ◆ Thêm key frame ở bảng Thuộc tính")

    def hit(self, pos):
        yr = self.yrange()
        for i, (t, v) in enumerate(self.keys()):
            c = self.px(t, v, yr)
            if abs(c.x() - pos.x()) < 10 and abs(c.y() - pos.y()) < 10:
                return i
        return None

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton or self.layer is None:
            return
        i = self.hit(e.pos())
        if i is None:
            if self.plot().contains(QPointF(e.pos())):
                self.seek.emit(self.unpx(QPointF(e.pos()), self.yrange())[0])
            return
        self.yr = self.yrange()
        self.drag = self.keys()[i]
        self.hot = i
        self.update()

    def mouseMoveEvent(self, e):
        if self.drag is None:
            h = self.hit(e.pos()) if self.layer else None
            if h != self.hot:
                self.hot = h
                self.setCursor(Qt.PointingHandCursor if h is not None else Qt.ArrowCursor)
                self.update()
            return
        t, v = self.unpx(QPointF(e.pos()), self.yr)
        lst = self.layer.kf[self.key]
        new = (round(t, 2), v)
        lst[lst.index(self.drag)] = new
        lst.sort()
        self.drag = new
        self.hot = lst.index(new)
        self.update()
        self.edited.emit()

    def mouseReleaseEvent(self, e):
        self.drag, self.yr = None, None
        self.update()


class GraphPanel(QWidget):
    """Do thi key frame: chon kenh, xem duong cong, keo diem de chinh."""
    seek = pyqtSignal(float)
    edited = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        bar = QWidget()
        bar.setObjectName("ViewBar")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        h = QHBoxLayout(bar)
        h.setContentsMargins(10, 5, 10, 5)
        h.setSpacing(8)
        h.addWidget(QLabel("Kênh"))
        self.combo = QComboBox()
        for k, n in CHANNELS:
            self.combo.addItem(n, k)
        self.combo.setMinimumWidth(130)
        h.addWidget(self.combo)
        h.addStretch()
        hint = QLabel("Kéo điểm vàng để đổi thời gian / giá trị · bấm vào đồ thị để tua")
        hint.setObjectName("Hint")
        h.addWidget(hint)
        v.addWidget(bar)
        self.plot = GraphPlot()
        v.addWidget(self.plot, 1)
        self.combo.currentIndexChanged.connect(lambda _: self.plot.set_key(self.combo.currentData()))
        self.plot.seek.connect(self.seek)
        self.plot.edited.connect(self.edited)

    def set_layer(self, L):
        self.plot.set_layer(L)

    def set_time(self, t):
        self.plot.set_time(t)

    def refresh(self):
        self.plot.update()
