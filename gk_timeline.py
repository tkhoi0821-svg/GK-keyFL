"""Timeline (clip, thuoc do, playhead) + Do thi key frame."""
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, QTimer, Signal
from PySide6.QtGui import (QColor, QPainter, QPen, QBrush, QFont, QFontMetrics, QPainterPath, QPolygonF, QLinearGradient,
                         QPixmap, QIcon)
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QPushButton, QSlider,
                             QGraphicsView, QGraphicsScene, QGraphicsRectItem, QFrame, QListWidget, QListWidgetItem, QMenu,
                             QSizePolicy, QButtonGroup)
import math
import gk_theme as theme
from gk_theme import T, mk
from gk_assets import mime_paths
from gk_panels import ScrubSpin
from gk_model import total, fit_duration, MAXT, TRACK_H, RULER_H, TRACKS, COLORS, CHANNELS, EASES, LOOPS, BEZ, Key, ease_u


def tc(s):
    return "%02d:%02d" % (int(s) // 60, int(s) % 60)


def key_shape(p, cx, cy, e, hot=False, sel=False):
    """Hinh key frame theo kieu noi suy: thoi = tuyen tinh, tron = ease/bezier, vuong = hold, tam giac = bounce/elastic."""
    s = 7.0 if (hot or sel) else 6.0
    p.setBrush(QColor("#ffffff") if (hot or sel) else QColor(T["key"]))
    p.setPen(QPen(QColor("#000000"), 1))
    if e == "hold":
        p.drawRect(QRectF(cx - s + 1, cy - s + 1, 2 * s - 2, 2 * s - 2))
    elif e in ("bounce", "elastic", "cyclic", "noise"):
        p.drawPolygon(QPolygonF([QPointF(cx, cy - s), QPointF(cx + s, cy + s - 1), QPointF(cx - s, cy + s - 1)]))
    elif e == "linear":
        p.drawPolygon(QPolygonF([QPointF(cx, cy - s), QPointF(cx + s, cy), QPointF(cx, cy + s), QPointF(cx - s, cy)]))
    else:
        p.drawEllipse(QPointF(cx, cy), s - 0.5, s - 0.5)


class Clip(QGraphicsRectItem):
    def __init__(self, tl, name, row, start, dur):
        super().__init__()
        self.tl, self.name, self.row, self.start, self.dur = tl, name, row, start, dur
        self.color = QColor(COLORS[TRACKS[min(row, len(TRACKS) - 1)]])
        self._rs = None            # dang keo mep clip de doi thoi gian: (mep, start, dur, src_off)
        self.setAcceptHoverEvents(True)
        self.setFlags(QGraphicsRectItem.ItemIsMovable | QGraphicsRectItem.ItemIsSelectable |
                      QGraphicsRectItem.ItemSendsGeometryChanges)
        self.layout()

    def layout(self):
        self.setRect(0, 0, self.dur * self.tl.pps, self.tl.th - 6)
        self.setPos(self.start * self.tl.pps, RULER_H + 3 + self.row * self.tl.th)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.ItemPositionChange:
            x = max(0, round(value.x() / self.tl.pps * 10) / 10)
            row = max(0, min(self.tl.nrows - 1, round((value.y() - RULER_H - 3) / self.tl.th)))
            self.start, self.row = x, row
            value.setX(x * self.tl.pps)
            value.setY(RULER_H + 3 + row * self.tl.th)
        return super().itemChange(change, value)

    EDGE = 7       # be rong vung keo mep clip (px)

    def edge_at(self, x):
        w = self.rect().width()
        if w < self.EDGE * 3:          # clip qua ngan: chi cho keo mep phai
            return "R" if x > w - self.EDGE else None
        return "L" if x < self.EDGE else ("R" if x > w - self.EDGE else None)

    def hoverMoveEvent(self, e):
        self.setCursor(Qt.SizeHorCursor if self.edge_at(e.pos().x()) else Qt.ArrowCursor)
        super().hoverMoveEvent(e)

    def mousePressEvent(self, e):
        edge = self.edge_at(e.pos().x()) if e.button() == Qt.LeftButton else None
        if edge:
            self._rs = (edge, self.start, self.dur, getattr(self, "src_off", 0.0))
            self.setSelected(True)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._rs is None:
            super().mouseMoveEvent(e)
            return
        edge, s0, d0, off0 = self._rs
        t = max(0.0, min(MAXT, round(self.mapToScene(e.pos()).x() / self.tl.pps * 20) / 20))
        end = s0 + d0
        if edge == "R":
            self.dur = round(max(0.1, t - s0), 3)
        else:
            lo = 0.0
            if hasattr(self, "layer") and self.layer.kind in ("video", "audio"):
                lo = max(0.0, s0 - off0)           # khong keo lui qua dau tep media
            ns = min(max(t, lo), end - 0.1)
            self.start, self.dur = round(ns, 3), round(end - ns, 3)
            if hasattr(self, "src_off"):
                self.src_off = round(max(0.0, off0 + (ns - s0)), 3)
        self.layout()
        self.tl.clips_changed.emit()

    def mouseReleaseEvent(self, e):
        self._rs = None
        super().mouseReleaseEvent(e)
        self.tl.clips_changed.emit()

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
        p.setPen(QPen(QColor(255, 255, 255, 150), 2))          # tay nam 2 mep: keo de doi thoi gian
        cy = r.center().y()
        for x in (r.left() + 3.5, r.right() - 3.5):
            p.drawLine(QPointF(x, cy - 6), QPointF(x, cy + 6))


class Timeline(QGraphicsView):
    seek = Signal(float)
    refreshed = Signal()          # sau moi lan refresh (chieu dai timeline co the da doi)
    clips_changed = Signal()      # clip bi keo / doi do dai -> editor tinh lai chieu dai timeline
    key_picked = Signal(float)   # bam / keo 1 key tren clip
    keys_edited = Signal()        # key bi doi thoi gian hoac them moi
    asset_dropped = Signal(str, float)   # tep tu Assets tha vao timeline (duong dan, thoi gian)

    def __init__(self):
        super().__init__()
        self.pps = 60.0
        self.th, self.nrows = TRACK_H, len(TRACKS)      # cao 1 hang / so hang: tu gian theo so lop
        self.sc = QGraphicsScene(self)
        self.setScene(self.sc)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setAcceptDrops(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
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
        fit_duration(self.clips)        # timeline bam theo clip cuoi, khong co dinh 30s
        used = max((c.row for c in self.clips), default=-1) + 1
        self.nrows = max(len(TRACKS), used + 1)            # luon con 1 hang trong de tha clip vao
        avail = self.viewport().height() - RULER_H
        self.th = max(32, min(TRACK_H, avail // self.nrows)) if avail > 0 else TRACK_H
        self.sc.setSceneRect(0, 0, total() * self.pps + 200, RULER_H + self.nrows * self.th)
        for c in self.clips:
            c.layout()
        self.set_time(self.t)
        self.viewport().update()
        self.refreshed.emit()

    def set_time(self, t):
        self.t = t
        self.viewport().update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.refresh()

    def free_row(self, pref, start, dur, ignore=None):
        """Hang dau tien (tu pref tro xuong) khong co clip nao chong len khoang [start, start+dur]."""
        r = max(0, pref)
        while True:
            if not any(c is not ignore and c.row == r and c.start < start + dur - 1e-6 and start < c.start + c.dur - 1e-6
                       for c in self.clips):
                return r
            r += 1

    def drawBackground(self, p, rect):
        p.fillRect(rect, QColor(T["bg0"]))
        for i in range(self.nrows):
            y = RULER_H + i * self.th
            p.fillRect(QRectF(rect.left(), y, rect.width(), self.th), QColor(T["track_a"] if i % 2 == 0 else T["track_b"]))
            p.setPen(QPen(QColor(T["line"]), 1))
            p.drawLine(int(rect.left()), y + self.th, int(rect.right()), y + self.th)

    def drawForeground(self, p, rect):
        y0 = rect.top()                                    # thuoc do luon dinh o dau khung nhin
        p.fillRect(QRectF(rect.left(), y0, rect.width(), RULER_H), QColor(T["bg2"]))
        p.setPen(QPen(QColor(T["line"]), 1))
        p.drawLine(int(rect.left()), int(y0 + RULER_H), int(rect.right()), int(y0 + RULER_H))
        lab = 1 if self.pps >= 90 else (2 if self.pps >= 45 else 5)
        sub = 0.5 if self.pps >= 120 else 1.0
        p.setFont(mk(theme.FONT_BODY, 10))
        s0 = max(0, int(rect.left() / self.pps) - 1)
        s1 = int(min(total(), rect.right() / self.pps + 1))
        n = int(s0 / sub)
        while n * sub <= s1:
            s = n * sub
            x = int(s * self.pps)
            major = abs(s - round(s)) < 1e-6 and int(round(s)) % lab == 0
            p.setPen(QColor(T["text2"] if major else T["text3"]))
            p.drawLine(x, int(y0 + RULER_H - (12 if major else 6)), x, int(y0 + RULER_H))
            if major:
                p.drawText(x + 4, int(y0 + 14), tc(s))
            n += 1
        x = self.t * self.pps
        p.setRenderHint(QPainter.Antialiasing)
        col = QColor(T["playhead"])
        p.setPen(QPen(col, 2))
        p.drawLine(QPointF(x, y0 + RULER_H - 2), QPointF(x, self.sc.height()))
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawPolygon(QPolygonF([QPointF(x - 7, y0 + 3), QPointF(x + 7, y0 + 3), QPointF(x + 7, y0 + 12),
                                 QPointF(x, y0 + RULER_H - 2), QPointF(x - 7, y0 + 12)]))

    def mousePressEvent(self, e):
        if e.y() < RULER_H:
            self.seek.emit(max(0, min(total(), self.mapToScene(e.pos()).x() / self.pps)))
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and e.y() < RULER_H and not self.sc.mouseGrabberItem():
            self.seek.emit(max(0, min(total(), self.mapToScene(e.pos()).x() / self.pps)))
        super().mouseMoveEvent(e)

    def dragEnterEvent(self, e):
        if mime_paths(e.mimeData()):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        t = max(0.0, self.mapToScene(e.pos()).x() / self.pps)
        for p in mime_paths(e.mimeData()):
            self.asset_dropped.emit(p, t)
        e.acceptProposedAction()

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
    BAND = 20      # vung o day clip de thao tac key frame

    def __init__(self, tl, L, row, start, dur):
        super().__init__(tl, L.name, row, start, dur)
        self.layer = L
        self.color = QColor(COLORS[{"text": "Text", "video": "Video", "audio": "Audio"}.get(L.kind, "Overlay")])
        self._kt = None
        self.src_off = 0.0        # giay bo qua o dau tep media (sau khi cat)

    def paint(self, p, *a):
        super().paint(p, *a)
        y = self.rect().height() - 10
        for t in self.layer.key_times():
            x = (t - self.start) * self.tl.pps
            if 0 <= x <= self.rect().width():
                ks = self.layer.keys_at(t)
                cur = abs(t - self.tl.t) < 0.05
                key_shape(p, x, y, ks[0].e if ks else "linear", sel=cur)

    def key_at(self, x):
        for t in self.layer.key_times():
            if abs((t - self.start) * self.tl.pps - x) < 9:
                return t
        return None

    def in_band(self, e):
        return e.pos().y() > self.rect().height() - self.BAND

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.in_band(e):
            t = self.key_at(e.pos().x())
            if t is not None:
                self._kt = t
                self.setSelected(True)
                self.tl.key_picked.emit(t)
                e.accept()
                return
        self._kt = None
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._kt is not None:
            nt = max(0.0, min(MAXT, round(self.start + e.pos().x() / self.tl.pps, 2)))
            if abs(nt - self._kt) >= 0.01:
                self.layer.move_keys(self._kt, nt)
                self._kt = nt
                self.tl.key_picked.emit(nt)
                self.tl.keys_edited.emit()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._kt = None
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if self.in_band(e) and self.key_at(e.pos().x()) is None:
            t = max(0.0, min(MAXT, round(self.start + e.pos().x() / self.tl.pps, 2)))
            self.layer.add_keys(t)
            self.tl.key_picked.emit(t)
            self.tl.keys_edited.emit()
            e.accept()
            return
        super().mouseDoubleClickEvent(e)


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
                n = self.add_layer_clip(c.layer, c.row, self.t, old - c.dur)
                n.src_off = c.src_off + c.dur
        self.refresh()

    def delete(self):
        for c in list(self.sc.selectedItems()):
            if isinstance(c, LayerClip):
                self.remove_clip(c)
        self.refresh()
        self.clips_changed.emit()


class TrackHeaders(QWidget):
    """Cot ten track ben trai timeline (khop voi thuoc do + hang track; so hang tu tang theo so lop)."""

    def __init__(self, tl):
        super().__init__()
        self.tl = tl
        self.setFixedWidth(84)
        theme.bus.changed.connect(self.update)
        tl.refreshed.connect(self.update)
        tl.verticalScrollBar().valueChanged.connect(lambda _: (self.update(), tl.viewport().update()))

    def paintEvent(self, _):
        tl, p = self.tl, QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(T["bg1"]))
        off = tl.verticalScrollBar().value()
        p.setFont(mk(theme.FONT_BODY, 12, QFont.DemiBold))
        for i in range(tl.nrows):
            y = RULER_H + i * tl.th - off
            if y + tl.th < RULER_H or y > self.height():
                continue
            cl = next((c for c in tl.clips if c.row == i), None)
            p.setPen(Qt.NoPen)
            p.setBrush(cl.color if cl else QColor(T["bg3"]))
            p.drawRoundedRect(QRectF(10, y + 10, 6, tl.th - 20), 3, 3)
            p.setPen(QColor(T["text"] if cl else T["text3"]))
            p.drawText(QRectF(24, y, self.width() - 28, tl.th), Qt.AlignVCenter | Qt.AlignLeft, "Track %d" % (i + 1))
            p.setPen(QPen(QColor(T["line"]), 1))
            p.drawLine(0, y + tl.th, self.width(), y + tl.th)
        p.fillRect(QRectF(0, 0, self.width(), RULER_H), QColor(T["bg2"]))
        p.setPen(QPen(QColor(T["line"]), 1))
        p.drawLine(0, RULER_H, self.width(), RULER_H)
        p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())


class TimelinePanel(QWidget):
    """Thanh cong cu + cot track + timeline."""
    key_add = Signal()
    key_del = Signal()
    key_prev = Signal()
    key_next = Signal()

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
        h.addSpacing(8)
        for txt, tip, sig, acc in (("◀◆", "Tới key frame trước", self.key_prev, False),
                                   ("◆＋", "Thêm key frame tại vị trí đầu phát (hoặc nhấp đúp vào dải dưới clip)", self.key_add, True),
                                   ("◆▶", "Tới key frame sau", self.key_next, False),
                                   ("◆✕", "Xoá key frame tại vị trí đầu phát", self.key_del, False)):
            b = QPushButton(txt)
            b.setObjectName("Accent" if acc else "SmallBtn")
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, sg=sig: sg.emit())
            h.addWidget(b)
        h.addSpacing(10)
        self.timelbl = QLabel("00:00.0 / 00:05.0")
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
        row.addWidget(TrackHeaders(tl))
        row.addWidget(tl, 1)
        v.addLayout(row, 1)
        self.setMinimumHeight(RULER_H + len(TRACKS) * TRACK_H + 48)


# ====================================================================== do thi key frame
GREEN, YELLOW = "#3ddc84", "#f2d45c"
WAVE_MAX = 12.0


def ease_icon(key, w=88, h=56):
    """Thumbnail duong cong cua 1 kieu chuyen dong (ve tu chinh ham easing)."""
    pm = QPixmap(w, h)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(T["bg2"]))
    p.drawRoundedRect(QRectF(0, 0, w, h), 9, 9)
    k = Key(0, 0, key)
    n = 48
    ys = [ease_u(k, i / n) for i in range(n + 1)]
    lo, hi = min(min(ys), 0.0), max(max(ys), 1.0)
    pad = 11.0
    path = QPainterPath()
    for i, y in enumerate(ys):
        x = pad + (w - 2 * pad) * i / n
        yy = h - pad - (h - 2 * pad) * (y - lo) / ((hi - lo) or 1)
        path.moveTo(x, yy) if i == 0 else path.lineTo(x, yy)
    p.setPen(QPen(QColor(GREEN), 2.2))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#ffffff"))
    p.drawEllipse(QPointF(pad, h - pad - (h - 2 * pad) * (0 - lo) / ((hi - lo) or 1)), 3, 3)
    p.drawEllipse(QPointF(w - pad, h - pad - (h - 2 * pad) * (1 - lo) / ((hi - lo) or 1)), 3, 3)
    p.end()
    return QIcon(pm)


class GraphPlot(QWidget):
    """Do thi gia tri 1 kenh theo thoi gian (kieu Alight Motion), co zoom / keo / chon nhieu key.
    - Cuon chuot: phong to thoi gian · Shift+cuon: phong to gia tri · Ctrl+cuon: cuon ngang
    - Chuot giua / phai keo: di chuyen khung nhin · Home hoac F: vua khung
    - Keo vung trong: chon nhieu key · Shift/Ctrl+bam: them/bo key khoi vung chon
    - Nhap dup: them key tren duong cong · Del: xoa · phim mui ten: day key (Shift = buoc lon)
    - Chon key roi keo cham trang: be cong toc do (Bezier) / doi so song (Cyclic, Noise)"""
    seek = Signal(float)
    edited = Signal()
    picked = Signal(object)          # key chinh (key chon cuoi) hoac None
    sel_changed = Signal()
    ML, MR, MT, MB = 68, 22, 18, 30
    STEPS = (0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30)

    def __init__(self):
        super().__init__()
        self.layer, self.key, self.t = None, "pos0", 0.0
        self.sel, self.hot, self.d = [], None, None
        self.vt0, self.vt1 = 0.0, total()          # khoang thoi gian dang xem
        self.vy = None                           # (thap, cao) khi nguoi dung zoom doc; None = tu dong
        self.frozen = None                       # khoa truc doc trong luc keo
        self.mode = "value"                       # "value" = do thi gia tri · "speed" = do thi toc do
        self._sc = None                          # cache mau toc do (xoa moi lan ve)
        self._yr_last = None                     # truc doc vua ve: hit-test / bat dau keo dung lai, khong tinh lai
        self._dirty, self._pick = False, None
        self._et = QTimer(self)                  # gom cac lan sua khi keo: toi da 1 lan / khung hinh
        self._et.setSingleShot(True)
        self._et.setInterval(16)
        self._et.timeout.connect(self._flush_edit)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(110)
        theme.bus.changed.connect(self.update)

    @property
    def selk(self):
        return self.sel[-1] if self.sel else None

    def set_sel(self, lst):
        self.sel = list(lst)
        self.picked.emit(self.selk)
        self.sel_changed.emit()
        self.update()

    def set_layer(self, L):
        self.layer = L
        self.set_sel([])
        self.fit()

    def set_key(self, k):
        self.key = k
        self.set_sel([])
        self.fit()

    def set_time(self, t):
        self.t = t
        self.update()

    def keys(self):
        return sorted(self.layer.kf.get(self.key, [])) if self.layer else []

    def next_of(self, a):
        ks = self.keys()
        i = ks.index(a) if a in ks else -1
        return ks[i + 1] if 0 <= i < len(ks) - 1 else None

    # ---------------------------------------------------------------- he toa do / khung nhin
    def plot(self):
        return QRectF(self.ML, self.MT, max(10, self.width() - self.ML - self.MR), max(10, self.height() - self.MT - self.MB))

    def yr(self):
        if self.mode == "speed":
            return self.spd_range()
        if self.frozen is not None:
            return self.frozen
        if self.vy is not None:
            return self.vy
        a, b = self.vt0, self.vt1
        vals = [k.v for k in self.keys() if a <= k.t <= b]
        if self.layer:
            vals += [self.layer.get(self.key, a + (b - a) * i / 120) for i in range(121)]
        if not vals:
            vals = [0.0, 1.0]
        lo, hi = min(vals), max(vals)
        pad = (hi - lo) * 0.18 or max(1.0, abs(hi) * 0.2)
        return lo - pad, hi + pad

    def tx(self, t):
        r = self.plot()
        return r.left() + (t - self.vt0) / ((self.vt1 - self.vt0) or 1) * r.width()

    def xt(self, x):
        r = self.plot()
        return self.vt0 + (x - r.left()) / r.width() * (self.vt1 - self.vt0)

    def px(self, t, v, yr=None):
        yr = yr or self.yr()
        r = self.plot()
        return QPointF(self.tx(t), r.bottom() - (v - yr[0]) / ((yr[1] - yr[0]) or 1) * r.height())

    def unpx(self, pos, yr=None):
        yr = yr or self.yr()
        r = self.plot()
        return self.xt(pos.x()), yr[0] + (r.bottom() - pos.y()) / r.height() * (yr[1] - yr[0])

    def clampt(self, t):
        return max(0.0, min(MAXT, t))

    def fit(self, keys=None):
        ks = keys if keys is not None else self.keys()
        if ks:
            a, b = min(k.t for k in ks), max(k.t for k in ks)
            pad = max(b - a, 1.0) * 0.15 + 0.2
            self.vt0, self.vt1 = max(-0.5, a - pad), min(MAXT, b + pad)
        else:
            self.vt0, self.vt1 = 0.0, total()
        self.vy = None
        self.update()

    def zoom_t(self, factor, anchor):
        span = self.vt1 - self.vt0
        new = max(0.2, min(max(total(), self.vt1) + 1.0, span * factor))
        ratio = new / span
        self.vt0 = anchor - (anchor - self.vt0) * ratio
        self.vt1 = self.vt0 + new
        shift = max(0.0, -0.5 - self.vt0) - max(0.0, self.vt1 - (max(total(), self.vt1) + 0.5))
        self.vt0, self.vt1 = self.vt0 + shift, self.vt1 + shift
        self.update()

    def zoom_y(self, factor, anchor):
        lo, hi = self.yr()
        new = max(1e-6, (hi - lo) * factor)
        ratio = new / ((hi - lo) or 1)
        lo2 = anchor - (anchor - lo) * ratio
        self.vy = (lo2, lo2 + new)
        self.update()

    def pan_t(self, dt):
        self.vt0 += dt
        self.vt1 += dt
        self.update()

    # ---------------------------------------------------------------- gom su kien sua (keo muot)
    def _queue_edit(self):
        """Khi keo chuot, su kien den rat day. Chi bao cho phan con lai cua app (canvas, thuoc tinh, timeline, plugin)
        toi da 1 lan moi ~16ms; do thi van ve lai ngay theo chuot."""
        self._dirty = True
        if not self._et.isActive():
            self._et.start()

    def _flush_edit(self):
        self._et.stop()
        if self._dirty:
            self._dirty = False
            if self._pick is not None:
                self.picked.emit(self._pick)
                self._pick = None
            self.sel_changed.emit()
            self.edited.emit()

    # ---------------------------------------------------------------- do thi toc do (dao ham cua gia tri theo thoi gian)
    def spd_h(self):
        return max(1e-3, ((self.vt1 - self.vt0) or 1.0) / 1500.0)

    def spd_at(self, t):
        h = self.spd_h()
        return (self.layer.get(self.key, t + h) - self.layer.get(self.key, t - h)) / (2 * h)

    def spd_samples(self):
        if self._sc is None:
            pts, n = [], 300
            if self.layer is not None:
                span = (self.vt1 - self.vt0) or 1.0
                for i in range(n + 1):
                    t = self.vt0 + span * i / n
                    pts.append((t, self.spd_at(t)))
            self._sc = pts
        return self._sc

    def spd_range(self):
        vals = [v for _, v in self.spd_samples()] or [0.0, 1.0]
        lo, hi = min(0.0, min(vals)), max(0.0, max(vals))
        a = sorted(abs(v) for v in vals)
        cap = a[int(0.97 * (len(a) - 1))] * 1.6     # key "hold" tao dinh vo han: bo qua khi chon khung
        if cap > 1e-9:
            lo, hi = max(lo, -cap), min(hi, cap)
        pad = (hi - lo) * 0.12 or 1.0
        return lo - pad * 0.5, hi + pad

    def _hit_speed(self, pos):
        if not self.layer:
            return None
        y0 = self.px(self.vt0, 0.0, self.yr()).y()
        for k in self.keys():
            if abs(self.tx(k.t) - pos.x()) < 11 and abs(y0 - pos.y()) < 14:
                return ("key", k)
        return None

    def _press_speed(self, e, pos):
        h = self._hit_speed(pos)
        add = bool(e.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier))
        if h is None:
            if not add:
                self.set_sel([])
            self.seek.emit(self.clampt(self.xt(pos.x())))
            self.d = dict(m="scrub")
            return
        k = h[1]
        if add and k in self.sel:
            self.set_sel([x for x in self.sel if x is not k])
            return
        if add:
            self.set_sel(self.sel + [k])
        elif k not in self.sel:
            self.set_sel([k])
        self.d = dict(m="skey", x0=pos.x(), snap=[(q, q.t) for q in self.sel])
        self.hot = h
        self.update()

    def _paint_speed(self, p, r, yr, L):
        ks = self.keys()
        y0 = self.px(self.vt0, 0.0, yr).y()
        p.save()
        p.setClipRect(r)
        p.setPen(QPen(QColor(T["text3"]), 1, Qt.DashLine))
        p.drawLine(QPointF(r.left(), y0), QPointF(r.right(), y0))
        path = QPainterPath()
        pts = self.spd_samples()
        for i, (tt, s) in enumerate(pts):
            pt = self.px(tt, s, yr)
            path.moveTo(pt) if i == 0 else path.lineTo(pt)
        if pts:
            area = QPainterPath(path)
            area.lineTo(QPointF(self.tx(pts[-1][0]), y0))
            area.lineTo(QPointF(self.tx(pts[0][0]), y0))
            area.closeSubpath()
            c = QColor(GREEN)
            c.setAlpha(45)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawPath(area)
        p.setPen(QPen(QColor(GREEN), 2.6))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.restore()
        for k in ks:                                   # key = vach doc + cham vang tren duong 0
            x = self.tx(k.t)
            if not (r.left() - 12 <= x <= r.right() + 12):
                continue
            sel, hot = k in self.sel, self.hot == ("key", k)
            p.setPen(QPen(QColor(T["text3"]), 1, Qt.DotLine))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            p.setPen(QPen(QColor("#ffffff"), 2.4) if sel else QPen(QColor("#000000"), 1))
            p.setBrush(QColor("#ffffff") if hot else QColor(YELLOW))
            p.drawEllipse(QPointF(x, y0), 9 if (sel or hot) else 8, 9 if (sel or hot) else 8)
        xh = self.tx(self.t)
        if r.left() <= xh <= r.right():
            p.setPen(QPen(QColor(T["playhead"]), 1.5))
            p.drawLine(QPointF(xh, r.top()), QPointF(xh, r.bottom() + 8))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(T["playhead"]))
            p.drawPolygon(QPolygonF([QPointF(xh - 6, r.bottom() + 8), QPointF(xh + 6, r.bottom() + 8), QPointF(xh, r.bottom() + 1)]))
        p.setPen(QColor(T["text2"]))
        p.setFont(mk(theme.FONT_BODY, 11, QFont.DemiBold))
        p.drawText(QRectF(r.left() + 8, r.top() + 4, 260, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   "Tốc độ tại đầu phát: %.4g /giây" % self.spd_at(self.t))

    # ---------------------------------------------------------------- tay nam
    def bez_segments(self):
        ks, out = self.keys(), []
        for a, b in zip(ks, ks[1:]):
            if (a in self.sel or b in self.sel) and a.handles() is not None:
                out.append((a, b))
        return out

    def handle_pts(self, a, b, yr):
        x1, y1, x2, y2 = a.handles()
        dt, dv = b.t - a.t, b.v - a.v
        return (self.px(a.t + x1 * dt, a.v + y1 * dv, yr), self.px(a.t + x2 * dt, a.v + y2 * dv, yr))

    def param_pt(self, a, b, yr):
        dt, dv = b.t - a.t, b.v - a.v
        y = a.v + dv * (a.a if a.e == "noise" else 0.0)
        return self.px(a.t + dt * min(1.0, a.n / WAVE_MAX), y, yr)

    def param_seg(self):
        a = self.selk
        if a is not None and a.e in ("cyclic", "noise"):
            b = self.next_of(a)
            if b is not None:
                return a, b
        return None

    # ---------------------------------------------------------------- ve
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(T["bg0"]))
        r = self.plot()
        self._sc = None
        yr = self.yr()
        self._yr_last = yr
        p.fillRect(QRectF(r.left(), r.bottom(), r.width(), self.MB), QColor(T["bg2"]))
        p.setFont(mk(theme.FONT_BODY, 10))
        for i in range(5):
            y = r.top() + r.height() * i / 4
            p.setPen(QPen(QColor(T["line"]), 1))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            val = yr[1] - (yr[1] - yr[0]) * i / 4
            p.setPen(QColor(T["text3"]))
            p.drawText(QRectF(2, y - 8, self.ML - 8, 16), Qt.AlignRight | Qt.AlignVCenter, ("%.4g" % val) + (" /s" if self.mode == "speed" else ""))
        pxs = r.width() / ((self.vt1 - self.vt0) or 1)
        step = next((s_ for s_ in self.STEPS if s_ * pxs >= 70), self.STEPS[-1])
        t = math.floor(self.vt0 / step) * step
        while t <= self.vt1 + step:
            x = self.tx(t)
            if r.left() - 1 <= x <= r.right() + 1:
                p.setPen(QPen(QColor(T["line"]), 1))
                p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
                p.setPen(QColor(T["text2"]))
                lab = ("%d:%02d" % (int(t) // 60, int(t) % 60)) if step >= 1 else ("%.2fs" % t)
                p.drawText(QRectF(x - 30, r.bottom() + 6, 60, 16), Qt.AlignCenter, lab)
            t += step
        L = self.layer
        if L is None:
            p.setPen(QColor(T["text3"]))
            p.setFont(mk(theme.FONT_BODY, 13))
            p.drawText(r, Qt.AlignCenter, "Chọn một lớp để xem đồ thị key frame")
            return
        if self.mode == "speed":
            self._paint_speed(p, r, yr, L)
            return
        ks = self.keys()
        # khung net dut quanh doan cua key duoc chon
        for a in self.sel:
            b = self.next_of(a)
            if b is None:
                continue
            p0, p1 = self.px(a.t, a.v, yr), self.px(b.t, b.v, yr)
            p.setPen(QPen(QColor(T["text3"]), 1, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(QPointF(p0.x(), min(p0.y(), p1.y())), QPointF(p1.x(), max(p0.y(), p1.y()))))
        p.save()
        p.setClipRect(r)
        path = QPainterPath()
        n = 400
        for i in range(n + 1):
            tt = self.vt0 + (self.vt1 - self.vt0) * i / n
            pt = self.px(tt, L.get(self.key, tt), yr)
            path.moveTo(pt) if i == 0 else path.lineTo(pt)
        p.setPen(QPen(QColor(GREEN), 2.6))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.restore()
        xh = self.tx(self.t)
        if r.left() <= xh <= r.right():
            p.setPen(QPen(QColor(T["playhead"]), 1.5))
            p.drawLine(QPointF(xh, r.top()), QPointF(xh, r.bottom() + 8))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(T["playhead"]))
            p.drawPolygon(QPolygonF([QPointF(xh - 6, r.bottom() + 8), QPointF(xh + 6, r.bottom() + 8), QPointF(xh, r.bottom() + 1)]))
        # tay nam bezier
        for a, b in self.bez_segments():
            h1, h2 = self.handle_pts(a, b, yr)
            p.setPen(QPen(QColor("#ffffff"), 2))
            p.drawLine(self.px(a.t, a.v, yr), h1)
            p.drawLine(self.px(b.t, b.v, yr), h2)
            for n_, h in ((1, h1), (2, h2)):
                hot = self.hot == ("h", a, n_)
                p.setPen(QPen(QColor("#ffffff"), 1))
                p.setBrush(QColor("#ffffff"))
                p.drawEllipse(h, 8.5 if hot else 7.5, 8.5 if hot else 7.5)
        ps = self.param_seg()
        if ps:
            a, b = ps
            h = self.param_pt(a, b, yr)
            p.setPen(QPen(QColor("#ffffff"), 3))
            p.drawLine(self.px(a.t, a.v, yr), h)
            hot = self.hot == ("p", a)
            p.setPen(QPen(QColor("#ffffff"), 1))
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(h, 11 if hot else 10, 11 if hot else 10)
            p.setPen(QColor(T["text2"]))
            p.setFont(mk(theme.FONT_BODY, 11, QFont.DemiBold))
            p.drawText(QRectF(h.x() - 40, h.y() - 32, 80, 16), Qt.AlignCenter, "× %d" % round(a.n))
        # key = cham vang (chon = vien trang)
        for k in ks:
            c = self.px(k.t, k.v, yr)
            if not (r.left() - 12 <= c.x() <= r.right() + 12):
                continue
            sel, hot = k in self.sel, self.hot == ("key", k)
            p.setPen(QPen(QColor("#ffffff"), 2.4) if sel else QPen(QColor("#000000"), 1))
            p.setBrush(QColor("#ffffff") if hot else QColor(YELLOW))
            p.drawEllipse(c, 9 if (sel or hot) else 8, 9 if (sel or hot) else 8)
        # the doc so cua key chinh
        k = self.selk
        if k is not None and k in ks:
            c = self.px(k.t, k.v, yr)
            txt = "%d:%05.2f   %.4g" % (int(k.t) // 60, k.t % 60, k.v)
            p.setFont(mk(theme.FONT_BODY, 11, QFont.DemiBold))
            w = QFontMetrics(p.font()).horizontalAdvance(txt) + 16
            box = QRectF(min(max(c.x() - w / 2, r.left()), r.right() - w), max(r.top(), c.y() - 38), w, 22)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 190))
            p.drawRoundedRect(box, 6, 6)
            p.setPen(QColor("#ffffff"))
            p.drawText(box, Qt.AlignCenter, txt)
        if not ks:
            p.setPen(QColor(T["text3"]))
            p.setFont(mk(theme.FONT_BODY, 12))
            p.drawText(QRectF(r.left(), r.top() + 6, r.width(), 20), Qt.AlignCenter,
                       "Kênh này chưa có key frame — nhấp đúp vào đồ thị để thêm")
        d = self.d
        if d and d["m"] == "box" and d["moved"]:
            rect = QRectF(d["p0"], d["p1"]).normalized()
            c = QColor(T["accent"])
            c.setAlpha(50)
            p.setPen(QPen(QColor(T["accent_hi"]), 1))
            p.setBrush(c)
            p.drawRect(rect)

    # ---------------------------------------------------------------- tuong tac
    def hit(self, pos):
        if not self.layer:
            return None
        if self.mode == "speed":
            return self._hit_speed(pos)
        yr = self._yr_last or self.yr()
        ps = self.param_seg()
        if ps:
            h = self.param_pt(ps[0], ps[1], yr)
            if abs(h.x() - pos.x()) < 13 and abs(h.y() - pos.y()) < 13:
                return ("p", ps[0])
        for a, b in self.bez_segments():
            h1, h2 = self.handle_pts(a, b, yr)
            for n_, h in ((1, h1), (2, h2)):
                if abs(h.x() - pos.x()) < 11 and abs(h.y() - pos.y()) < 11:
                    return ("h", a, n_)
        for k in self.keys():
            c = self.px(k.t, k.v, yr)
            if abs(c.x() - pos.x()) < 11 and abs(c.y() - pos.y()) < 11:
                return ("key", k)
        return None

    def mousePressEvent(self, e):
        self.setFocus()
        r, pos = self.plot(), QPointF(e.pos())
        if e.button() in (Qt.MiddleButton, Qt.RightButton):
            if self.vy is None:
                self.vy = self.yr()
            self.frozen = None
            self.d = dict(m="pan", last=pos)
            self.setCursor(Qt.ClosedHandCursor)
            return
        if e.button() != Qt.LeftButton or self.layer is None:
            return
        if pos.y() > r.bottom():                               # thuoc thoi gian: keo de tua
            self.d = dict(m="scrub")
            self.seek.emit(self.clampt(self.xt(pos.x())))
            return
        if self.mode == "speed":
            return self._press_speed(e, pos)
        h = self.hit(e.pos())
        add = bool(e.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier))
        if h is None:
            self.d = dict(m="box", p0=pos, p1=pos, add=add, moved=False)
            return
        self.frozen = self._yr_last or self.yr()
        if h[0] == "key":
            k = h[1]
            if add and k in self.sel:
                self.set_sel([x for x in self.sel if x is not k])
                self.frozen = None
                return
            if add:
                self.set_sel(self.sel + [k])
            elif k not in self.sel:
                self.set_sel([k])
            self.d = dict(m="key", p0=pos, snap=[(q, q.t, q.v) for q in self.sel])
        elif h[0] == "h":
            self.d = dict(m="h", key=h[1], n=h[2])
        else:
            self.d = dict(m="p", key=h[1])
        self.hot = h
        self.update()

    def mouseMoveEvent(self, e):
        d, pos, r = self.d, QPointF(e.pos()), self.plot()
        if d is None:
            h = self.hit(e.pos())
            if h != self.hot:
                self.hot = h
                self.setCursor(Qt.PointingHandCursor if h is not None else Qt.ArrowCursor)
                self.update()
            return
        m = d["m"]
        if m == "pan":
            dx, dy = pos.x() - d["last"].x(), pos.y() - d["last"].y()
            d["last"] = pos
            self.pan_t(-dx / r.width() * (self.vt1 - self.vt0))
            lo, hi = self.vy
            dv = dy / r.height() * (hi - lo)
            self.vy = (lo + dv, hi + dv)
        elif m == "scrub":
            self.seek.emit(self.clampt(self.xt(pos.x())))
        elif m == "box":
            d["p1"] = pos
            d["moved"] = d["moved"] or (pos - d["p0"]).manhattanLength() > 4
        elif m == "key":
            t0, v0 = self.unpx(d["p0"], self.frozen)
            t1, v1 = self.unpx(pos, self.frozen)
            snap = bool(e.modifiers() & Qt.ControlModifier)
            for q, qt, qv in d["snap"]:
                nt = self.clampt(qt + (t1 - t0))
                if snap:
                    nt = round(nt / 0.05) * 0.05
                q.t, q.v = round(nt, 2), qv + (v1 - v0)
            self.layer.kf[self.key].sort()
            self._queue_edit()
        elif m == "skey":
            dt = (pos.x() - d["x0"]) / r.width() * (self.vt1 - self.vt0)
            for q, qt in d["snap"]:
                nt = self.clampt(qt + dt)
                if e.modifiers() & Qt.ControlModifier:
                    nt = round(nt / 0.05) * 0.05
                q.t = round(nt, 2)
            self.layer.kf[self.key].sort()
            self._queue_edit()
        else:
            t, v = self.unpx(pos, self.frozen)
            a = d["key"]
            b = self.next_of(a)
            if b is not None:
                dt, dv = (b.t - a.t) or 1, b.v - a.v
                if m == "p":
                    a.n = float(max(1, min(WAVE_MAX, round((t - a.t) / dt * WAVE_MAX))))
                    if a.e == "noise" and abs(dv) > 1e-9:
                        a.a = max(0.0, min(1.5, (v - a.v) / dv))
                else:
                    n_ = d["n"]
                    x = max(0.0, min(1.0, (t - a.t) / dt))
                    cur = list(a.handles())
                    yy = (v - a.v) / dv if abs(dv) > 1e-9 else cur[1 if n_ == 1 else 3]
                    yy = max(-2.0, min(3.0, yy))
                    if n_ == 1:
                        cur[0], cur[1] = x, yy
                    else:
                        cur[2], cur[3] = x, yy
                    a.e, a.bz = "bezier", tuple(cur)
                self._pick = a
                self._queue_edit()
        self.update()

    def mouseReleaseEvent(self, e):
        d, pos, r = self.d, QPointF(e.pos()), self.plot()
        self.d, self.frozen = None, None
        self._flush_edit()                     # day not thay doi con cho khi tha chuot
        if d and d["m"] == "box":
            if d["moved"]:
                rect = QRectF(d["p0"], d["p1"]).normalized()
                got = [k for k in self.keys() if rect.contains(self.px(k.t, k.v))]
                base = self.sel if d["add"] else []
                self.set_sel(base + [k for k in got if k not in base])
            else:
                if not d["add"]:
                    self.set_sel([])
                if r.contains(pos):
                    self.seek.emit(self.clampt(self.xt(pos.x())))
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def mouseDoubleClickEvent(self, e):
        if e.button() != Qt.LeftButton or self.layer is None:
            return
        pos = QPointF(e.pos())
        if not self.plot().contains(pos) or self.hit(e.pos()) is not None:
            return
        t = round(self.clampt(self.xt(pos.x())), 2)
        self.layer.set(self.key, t, self.layer.get(self.key, t), True)
        new = [k for k in self.keys() if abs(k.t - t) < 0.06]
        self.set_sel(new[:1])
        self.edited.emit()

    def wheelEvent(self, e):
        f = 0.8 if e.angleDelta().y() > 0 else 1.25
        mods, pos = e.modifiers(), e.position()
        if mods & Qt.ShiftModifier:
            self.zoom_y(f, self.unpx(pos)[1])
        elif mods & Qt.ControlModifier:
            self.pan_t((self.vt1 - self.vt0) * 0.1 * (-1 if e.angleDelta().y() > 0 else 1))
        else:
            self.zoom_t(f, self.xt(pos.x()))
        e.accept()

    def delete_sel(self):
        L, lst = self.layer, self.layer.kf.get(self.key) if self.layer else None
        if not lst or not self.sel:
            return
        v = L.get(self.key, self.t)
        keep = [k for k in lst if k not in self.sel]
        if keep:
            L.kf[self.key] = keep
        else:
            L.base[self.key] = v
            del L.kf[self.key]
        self.set_sel([])
        self.edited.emit()

    def nudge(self, dt, dv):
        for k in self.sel:
            k.t = round(self.clampt(k.t + dt), 2)
            k.v += dv
        if self.layer and self.key in self.layer.kf:
            self.layer.kf[self.key].sort()
        self.sel_changed.emit()
        self.edited.emit()
        self.update()

    def keyPressEvent(self, e):
        k, big = e.key(), bool(e.modifiers() & Qt.ShiftModifier)
        lo, hi = self.yr()
        if k in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_sel()
        elif k in (Qt.Key_Home, Qt.Key_F):
            self.fit(self.sel if (k == Qt.Key_F and self.sel) else None)
        elif k == Qt.Key_A:
            self.set_sel(self.keys())
        elif k == Qt.Key_Escape:
            self.set_sel([])
        elif k == Qt.Key_Left:
            self.nudge(-0.5 if big else -0.05, 0)
        elif k == Qt.Key_Right:
            self.nudge(0.5 if big else 0.05, 0)
        elif k in (Qt.Key_Up, Qt.Key_Down) and self.mode == "speed":
            pass                      # o che do toc do khong chinh gia tri bang phim
        elif k == Qt.Key_Up:
            self.nudge(0, (hi - lo) * (0.05 if big else 0.01))
        elif k == Qt.Key_Down:
            self.nudge(0, -(hi - lo) * (0.05 if big else 0.01))
        else:
            super().keyPressEvent(e)


class GraphPanel(QWidget):
    """Do thi key frame kieu Alight Motion: thanh trai (lap, menu) | do thi + nhan kieu | cot thumbnail kieu chuyen dong."""
    seek = Signal(float)
    edited = Signal()

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
        h.setSpacing(6)
        h.addWidget(QLabel("Kênh"))
        self.combo = QComboBox()
        self._combo_sig = None
        self._rebuild_combo(None)
        self.combo.setMinimumWidth(120)
        self.combo.setToolTip("● = kênh đang có key frame")
        h.addWidget(self.combo)
        self.pt_combo = QComboBox()                      # chi hien khi chon kenh "Luoi meo": chon tung diem (💡 = da di chuyen / co key)
        self.pt_combo.setMinimumWidth(110)
        self.pt_combo.setMaxVisibleItems(18)
        self.pt_combo.setToolTip("Chọn điểm lưới.  💡 = điểm đã di chuyển hoặc có key frame")
        self.ax_x, self.ax_y = QPushButton("X"), QPushButton("Y")
        axg = QButtonGroup(self)
        for b in (self.ax_x, self.ax_y):
            b.setObjectName("SmallBtn")
            b.setCheckable(True)
            b.setFixedWidth(28)
            axg.addButton(b)
        self.ax_x.setChecked(True)
        self._pt_sig = None
        h.addWidget(self.pt_combo)
        h.addWidget(self.ax_x)
        h.addWidget(self.ax_y)
        self.pt_combo.hide(); self.ax_x.hide(); self.ax_y.hide()
        self.v_btn, self.s_btn = QPushButton("Giá trị"), QPushButton("Tốc độ")
        grp = QButtonGroup(self)
        for b, tip in ((self.v_btn, "Đồ thị giá trị theo thời gian"),
                       (self.s_btn, "Đồ thị tốc độ: độ nhanh chậm của chuyển động (chỉ xem; kéo key để đổi thời gian)")):
            b.setObjectName("SmallBtn")
            b.setCheckable(True)
            b.setToolTip(tip)
            grp.addButton(b)
            h.addWidget(b)
        self.v_btn.setChecked(True)
        self.v_btn.clicked.connect(lambda: self._mode("value"))
        self.s_btn.clicked.connect(lambda: self._mode("speed"))
        self.add_btn = QPushButton("◆＋")
        self.add_btn.setObjectName("SmallBtn")
        self.add_btn.setToolTip("Thêm key tại đầu phát (chỉ kênh này)")
        self.del_btn = QPushButton("✕ Xoá key")
        self.del_btn.setObjectName("SmallBtn")
        self.del_btn.setToolTip("Xoá các key đang chọn (Del)")
        self.fit_btn = QPushButton("⤢ Vừa khung")
        self.fit_btn.setObjectName("SmallBtn")
        self.fit_btn.setToolTip("Hiện toàn bộ key của kênh (Home). Phím F: vừa các key đang chọn")
        for b in (self.add_btn, self.del_btn, self.fit_btn):
            h.addWidget(b)
        h.addSpacing(8)
        lt, lv = QLabel("Thời gian"), QLabel("Giá trị")
        lt.setObjectName("Sub")
        lv.setObjectName("Sub")
        self.f_t = ScrubSpin("", 0.02)
        self.f_t.setRange(0, MAXT)
        self.f_t.setDecimals(2)
        self.f_t.setSuffix(" s")
        self.f_v = ScrubSpin("", 0.1)
        self.f_v.setDecimals(2)
        for w in (self.f_t, self.f_v):
            w.setFixedWidth(84)
        h.addWidget(lt)
        h.addWidget(self.f_t)
        h.addWidget(lv)
        h.addWidget(self.f_v)
        h.addStretch()
        hint = QLabel("Cuộn: zoom · chuột giữa/phải kéo: di chuyển · kéo vùng trống: chọn nhiều · nhấp đúp: thêm key")
        hint.setObjectName("Hint")
        hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        hint.setMinimumWidth(0)
        h.addWidget(hint, 1)
        v.addWidget(bar)

        body = QHBoxLayout()
        body.setSpacing(0)
        rail = QWidget()
        rail.setObjectName("Rail")
        rail.setAttribute(Qt.WA_StyledBackground, True)
        rail.setFixedWidth(56)
        rv = QVBoxLayout(rail)
        rv.setContentsMargins(6, 8, 6, 8)
        rv.setSpacing(4)
        self.loop_btn = QPushButton("⟲")
        self.loop_btn.setObjectName("Tool")
        self.loop_btn.setCheckable(True)
        self.loop_btn.setStyleSheet("font-size:20px;")
        self.loop_btn.clicked.connect(self._loop_cycle)
        self.loop_lbl = QLabel("Không lặp")
        self.loop_lbl.setObjectName("Hint")
        self.loop_lbl.setAlignment(Qt.AlignCenter)
        self.loop_lbl.setWordWrap(True)
        self.loop_lbl.setStyleSheet("font-size:9px;")
        rv.addWidget(self.loop_btn)
        rv.addWidget(self.loop_lbl)
        rv.addStretch()
        self.more = QPushButton("⋯")
        self.more.setObjectName("Tool")
        self.more.setStyleSheet("font-size:20px;")
        menu = QMenu(self.more)
        menu.addAction("Đặt key đã chọn về tuyến tính").triggered.connect(lambda _=False: self._apply("linear"))
        menu.addAction("Áp dụng kiểu của key đã chọn cho mọi key của kênh").triggered.connect(lambda _=False: self._apply_all())
        menu.addAction("Chọn tất cả key của kênh   (A)").triggered.connect(lambda _=False: self.plot.set_sel(self.plot.keys()))
        menu.addSeparator()
        menu.addAction("Xoá mọi key của kênh này").triggered.connect(lambda _=False: self._clear_channel())
        self.more.setMenu(menu)
        rv.addWidget(self.more)
        body.addWidget(rail)

        mid = QVBoxLayout()
        mid.setSpacing(0)
        self.plot = GraphPlot()
        mid.addWidget(self.plot, 1)
        foot = QWidget()
        foot.setObjectName("ViewBarBottom")
        foot.setAttribute(Qt.WA_StyledBackground, True)
        fh = QHBoxLayout(foot)
        fh.setContentsMargins(10, 4, 10, 4)
        self.prev, self.nxt = QPushButton("‹"), QPushButton("›")
        for b in (self.prev, self.nxt):
            b.setObjectName("SmallBtn")
            b.setFixedWidth(36)
        self.name_lbl = QLabel("Chưa chọn key")
        self.name_lbl.setObjectName("Title")
        self.name_lbl.setStyleSheet("font-size:13px;")
        self.name_lbl.setAlignment(Qt.AlignCenter)
        fh.addWidget(self.prev)
        fh.addWidget(self.name_lbl, 1)
        fh.addWidget(self.nxt)
        mid.addWidget(foot)
        body.addLayout(mid, 1)

        self.gal = QListWidget()
        self.gal.setViewMode(QListWidget.IconMode)
        self.gal.setIconSize(QSize(88, 56))
        self.gal.setGridSize(QSize(100, 66))
        self.gal.setResizeMode(QListWidget.Adjust)
        self.gal.setMovement(QListWidget.Static)
        self.gal.setSpacing(4)
        self.gal.setFixedWidth(224)
        for k, n in EASES:
            it = QListWidgetItem()
            it.setData(Qt.UserRole, k)
            it.setToolTip(n)
            self.gal.addItem(it)
        self._icons()
        theme.bus.changed.connect(self._icons)
        body.addWidget(self.gal)
        v.addLayout(body, 1)

        self.combo.currentIndexChanged.connect(self._channel)
        self.pt_combo.currentIndexChanged.connect(self._apply_mesh)
        self.ax_x.clicked.connect(self._apply_mesh)
        self.ax_y.clicked.connect(self._apply_mesh)
        self.gal.itemClicked.connect(lambda it: self._apply(it.data(Qt.UserRole)))
        self.prev.clicked.connect(lambda: self._step(-1))
        self.nxt.clicked.connect(lambda: self._step(1))
        self.add_btn.clicked.connect(self._add_here)
        self.del_btn.clicked.connect(self.plot.delete_sel)
        self.fit_btn.clicked.connect(lambda: self.plot.fit())
        self.f_t.valueChanged.connect(self._set_t)
        self.f_v.valueChanged.connect(self._set_v)
        self.plot.seek.connect(self.seek)
        self.plot.edited.connect(self._edited)
        self.plot.picked.connect(self._picked)
        self.plot.sel_changed.connect(self._fields)
        self._picked(None)
        self._fields()

    # ---------------------------------------------------------------- dong bo
    def _icons(self):
        for i in range(self.gal.count()):
            it = self.gal.item(i)
            it.setIcon(ease_icon(it.data(Qt.UserRole)))

    def _mode(self, m):
        pl = self.plot
        pl.mode = m
        pl.frozen = None
        pl._yr_last = None
        self.f_v.setEnabled(m == "value" and pl.selk is not None)
        pl.update()

    def _channel_list(self, L):
        """Kenh co dinh + 1 muc gop "Luoi meo" (moi diem luoi nam trong danh sach chi tiet, khong liet ke tung diem)."""
        out = list(CHANNELS)
        if L is not None and L.mesh_active():
            out.append(("mesh", "Lưới méo (%d×%d)" % (L.mesh["cols"] + 1, L.mesh["rows"] + 1)))
        return out

    def _rebuild_combo(self, L):
        sig = (L.mesh["cols"], L.mesh["rows"]) if (L is not None and L.mesh_active()) else None
        if sig == self._combo_sig and self.combo.count():
            return
        self._combo_sig = sig
        pk = self.plot.key if hasattr(self, "plot") else "pos0"
        cur = "mesh" if pk.startswith("mw") else pk
        self.combo.blockSignals(True)
        self.combo.clear()
        for k, n in self._channel_list(L):
            self.combo.addItem(n, k)
        i = self.combo.findData(cur)
        self.combo.setCurrentIndex(i if i >= 0 else 0)
        self.combo.blockSignals(False)
        if i < 0 and hasattr(self, "plot"):
            self.plot.set_key(self.combo.itemData(0))
        self._rebuild_points(L)
        self._show_points()

    def _rebuild_points(self, L):
        """Danh sach diem luoi: 💡 neu diem da bi keo lech hoac co key frame."""
        if not hasattr(self, "pt_combo"):
            return
        sig = (L.mesh["cols"], L.mesh["rows"]) if (L is not None and L.mesh_active()) else None
        n = 0 if sig is None else (sig[0] + 1) * (sig[1] + 1)
        if sig != self._pt_sig or self.pt_combo.count() != n:
            self._pt_sig = sig
            cur = self.pt_combo.currentData()
            self.pt_combo.blockSignals(True)
            self.pt_combo.clear()
            for idx in range(n):
                self.pt_combo.addItem("", idx)
            if cur is not None and 0 <= cur < n:
                self.pt_combo.setCurrentIndex(cur)
            self.pt_combo.blockSignals(False)
        for idx in range(n):
            c = sig[0] + 1
            r_, c_ = divmod(idx, c)
            used = any(L.kf.get("mw%s%d" % (a, idx)) or abs(L.base.get("mw%s%d" % (a, idx), 0.0)) > 0.01 for a in "xy")
            self.pt_combo.setItemText(idx, ("💡 " if used else "     ") + "Điểm (%d,%d)" % (c_ + 1, r_ + 1))

    def _show_points(self):
        if not hasattr(self, "pt_combo"):
            return
        on = self.combo.currentData() == "mesh"
        for w in (self.pt_combo, self.ax_x, self.ax_y):
            w.setVisible(on)

    def _mesh_key(self):
        idx = self.pt_combo.currentData()
        return "mw%s%d" % ("x" if self.ax_x.isChecked() else "y", idx if idx is not None else 0)

    def _apply_mesh(self, *_):
        if self.combo.currentData() == "mesh":
            self.plot.set_key(self._mesh_key())
            self._sync()

    def select_channel(self, key):
        """Chuyen do thi sang 1 kenh; kenh luoi (mwx12...) -> muc "Luoi meo" + dung diem do."""
        if key.startswith("mw"):
            i = self.combo.findData("mesh")
            if i < 0:
                return
            idx, ax = int(key[3:]), key[2]
            for w in (self.pt_combo, self.ax_x, self.ax_y):
                w.blockSignals(True)
            self.pt_combo.setCurrentIndex(idx)
            (self.ax_x if ax == "x" else self.ax_y).setChecked(True)
            for w in (self.pt_combo, self.ax_x, self.ax_y):
                w.blockSignals(False)
            if self.combo.currentIndex() != i:
                self.combo.setCurrentIndex(i)          # -> _channel -> _apply_mesh
            else:
                self._apply_mesh()
            return
        i = self.combo.findData(key)
        if i >= 0 and i != self.combo.currentIndex():
            self.combo.setCurrentIndex(i)

    def _mark_channels(self):
        L = self.plot.layer
        self._rebuild_combo(L)
        self._rebuild_points(L)
        for i in range(self.combo.count()):
            k = self.combo.itemData(i)
            has = bool(L and (any(L.kf.get(c) for c in L.mesh_channels()) if k == "mesh" else L.kf.get(k)))
            n = self.combo.itemText(i).lstrip("● ").strip()
            self.combo.setItemText(i, ("● " if has else "    ") + n)

    def _fields(self):
        k = self.plot.selk
        for w in (self.f_t, self.f_v):
            w.blockSignals(True)
            w.setEnabled(k is not None)
        if k is not None:
            self.f_t.setValue(k.t)
            self.f_v.setValue(k.v)
        for w in (self.f_t, self.f_v):
            w.blockSignals(False)

    def _set_t(self, val):
        k = self.plot.selk
        if k is not None and self.plot.layer is not None:
            k.t = round(float(val), 2)
            self.plot.layer.kf[self.plot.key].sort()
            self.plot.update()
            self.edited.emit()

    def _set_v(self, val):
        k = self.plot.selk
        if k is not None:
            k.v = float(val)
            self.plot.update()
            self.edited.emit()

    def _edited(self):
        self._picked(self.plot.selk)
        self._mark_channels()
        self._fields()
        self.edited.emit()

    def _channel(self, _):
        self._show_points()
        if self.combo.currentData() == "mesh":
            self._apply_mesh()
            return
        self.plot.set_key(self.combo.currentData())
        self._sync()

    def _sync(self):
        L, key = self.plot.layer, self.plot.key
        mode = L.loop.get(key, "none") if L else "none"
        self.loop_btn.setChecked(mode != "none")
        self.loop_lbl.setText(dict(LOOPS)[mode].split(" (")[0] if mode == "none" else dict(LOOPS)[mode].split("(")[1].rstrip(")"))
        self._picked(self.plot.selk)
        self._mark_channels()

    def _picked(self, k):
        self.gal.blockSignals(True)
        if k is None:
            self.gal.clearSelection()
            self.gal.setCurrentRow(-1)
            self.name_lbl.setText("Chọn một key để đổi kiểu")
        else:
            names = [e for e, _ in EASES]
            self.gal.setCurrentRow(names.index(k.e) if k.e in names else 0)
            n = len(self.plot.sel)
            self.name_lbl.setText(dict(EASES).get(k.e, k.e) + ("  ×%d" % round(k.n) if k.e in ("cyclic", "noise") else "") +
                                  ("   ·  %d key được chọn" % n if n > 1 else ""))
        self.gal.blockSignals(False)

    # ---------------------------------------------------------------- hanh dong
    def _add_here(self):
        pl = self.plot
        if pl.layer is None:
            return
        pl.layer.set(pl.key, round(pl.t, 2), pl.layer.get(pl.key, pl.t), True)
        pl.set_sel([k for k in pl.keys() if abs(k.t - pl.t) < 0.06][:1])
        self._edited()

    def _targets(self):
        pl = self.plot
        return list(pl.sel) if pl.sel else pl.keys()

    def _apply(self, e):
        pl = self.plot
        if pl.layer is None:
            return
        for k in self._targets():
            k.e = e
            k.bz = BEZ["ease_inout"] if e == "bezier" else None
        self._picked(pl.selk)
        pl.update()
        self.edited.emit()

    def _apply_all(self):
        pl = self.plot
        s = pl.selk
        if s is None:
            return
        for k in pl.keys():
            k.e, k.bz, k.n, k.a = s.e, s.bz, s.n, s.a
        pl.update()
        self.edited.emit()

    def _clear_channel(self):
        pl = self.plot
        if pl.layer is not None and pl.key in pl.layer.kf:
            pl.layer.base[pl.key] = pl.layer.get(pl.key, pl.t)
            del pl.layer.kf[pl.key]
            pl.set_sel([])
            self._mark_channels()
            self.edited.emit()

    def _step(self, d):
        pl = self.plot
        if pl.selk is None:
            return
        names = [e for e, _ in EASES]
        self._apply(names[(names.index(pl.selk.e) + d) % len(names)])

    def _loop_cycle(self):
        pl = self.plot
        if pl.layer is None:
            self.loop_btn.setChecked(False)
            return
        modes = [m for m, _ in LOOPS]
        pl.layer.loop[pl.key] = modes[(modes.index(pl.layer.loop.get(pl.key, "none")) + 1) % len(modes)]
        self._sync()
        pl.update()
        self.edited.emit()

    def set_layer(self, L):
        if L is self.plot.layer:          # cung lop: giu nguyen vung chon va muc zoom
            self.refresh()
            return
        self._rebuild_combo(L)
        self.plot.set_layer(L)
        # chon san kenh dau tien dang co key de khong phai mo ca danh sach
        if L is not None and not L.kf.get(self.plot.key):
            for i in range(self.combo.count()):
                k_ = self.combo.itemData(i)
                if (any(L.kf.get(c) for c in L.mesh_channels()) if k_ == "mesh" else L.kf.get(k_)):
                    if k_ == "mesh":
                        first = next(c for c in L.mesh_channels() if L.kf.get(c))
                        self.select_channel(first)      # nhay thang toi diem luoi dau tien co key
                    else:
                        self.combo.setCurrentIndex(i)      # -> _channel -> set_key + fit
                    break
        self._sync()

    def set_time(self, t):
        self.plot.set_time(t)

    def refresh(self):
        self._mark_channels()
        self.plot.update()
