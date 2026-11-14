"""Cua so 'Cubic Bezier Easing' (rieng, khong dung chung voi Do thi key frame).
He toa do chuan hoa 0..1: P0(0,0) va P3(1,1) co dinh, keo 2 tay cam P1(x1,y1), P2(x2,y2).
x1, x2 bi kep trong [0,1] (de duong cong luon la ham so); y1, y2 duoc phep vuot ra ngoai de tao hieu ung nay (overshoot)."""
import re, time
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPainterPath, QPixmap, QIcon
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
                               QDoubleSpinBox, QLineEdit, QListWidget, QListWidgetItem, QApplication)
import gk_theme as theme
from gk_theme import T, mk
from gk_model import CHANNELS, BEZ, EASES, bezier_y

GREEN = "#3ddc84"
YMIN, YMAX = -2.0, 3.0


def _presets():
    out = [(k, n, BEZ[k], True) for k, n in EASES if k in BEZ]       # kieu co ten san trong mo hinh
    extra = [("sine_in", "Sine In", (0.12, 0, 0.39, 0)), ("sine_out", "Sine Out", (0.61, 1, 0.88, 1)),
             ("sine_io", "Sine In-Out", (0.37, 0, 0.63, 1)),
             ("quad_in", "Quad In", (0.11, 0, 0.5, 0)), ("quad_out", "Quad Out", (0.5, 1, 0.89, 1)),
             ("quad_io", "Quad In-Out", (0.45, 0, 0.55, 1)),
             ("cubic_in", "Cubic In", (0.32, 0, 0.67, 0)), ("cubic_out", "Cubic Out", (0.33, 1, 0.68, 1)),
             ("cubic_io", "Cubic In-Out", (0.65, 0, 0.35, 1)),
             ("quart_in", "Quart In", (0.5, 0, 0.75, 0)), ("quart_out", "Quart Out", (0.25, 1, 0.5, 1)),
             ("quart_io", "Quart In-Out", (0.76, 0, 0.24, 1)),
             ("expo_in", "Expo In", (0.7, 0, 0.84, 0)), ("expo_out", "Expo Out", (0.16, 1, 0.3, 1)),
             ("expo_io", "Expo In-Out", (0.87, 0, 0.13, 1)),
             ("circ_in", "Circ In", (0.55, 0, 1, 0.45)), ("circ_out", "Circ Out", (0, 0.55, 0.45, 1)),
             ("circ_io", "Circ In-Out", (0.85, 0, 0.15, 1)),
             ("back_in", "Back In", (0.36, 0, 0.66, -0.56)), ("back_out", "Back Out", (0.34, 1.56, 0.64, 1)),
             ("back_io", "Back In-Out", (0.68, -0.6, 0.32, 1.6)),
             ("s_sharp", "S gắt", (0.95, 0.05, 0.05, 0.95))]
    out += [(k, n, p, False) for k, n, p in extra]
    return out


PRESETS = _presets()


def clamp_params(p):
    return [max(0.0, min(1.0, p[0])), max(YMIN, min(YMAX, p[1])), max(0.0, min(1.0, p[2])), max(YMIN, min(YMAX, p[3]))]


def parse_css(txt):
    nums = re.findall(r"-?\d*\.?\d+", txt or "")
    if len(nums) < 4:
        return None
    return clamp_params([float(x) for x in nums[:4]])


def css_text(p):
    return "cubic-bezier(%s)" % ", ".join(("%.3f" % v).rstrip("0").rstrip(".") or "0" for v in p)


def bez_points(p, n=80):
    """Cac diem (x, y) cua duong cong theo tham so t (khong can giai nguoc)."""
    x1, y1, x2, y2 = p
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c = 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * x1 + b * x2 + c, a * y1 + b * y2 + c))
    return out


def curve_icon(p, w=64, h=46):
    pm = QPixmap(w, h)
    pm.fill(Qt.transparent)
    q = QPainter(pm)
    q.setRenderHint(QPainter.Antialiasing)
    q.setPen(Qt.NoPen)
    q.setBrush(QColor(T["bg2"]))
    q.drawRoundedRect(QRectF(0, 0, w, h), 8, 8)
    pts = bez_points(p, 40)
    lo, hi = min(0.0, min(y for _, y in pts)), max(1.0, max(y for _, y in pts))
    pad = 10.0
    path = QPainterPath()
    for i, (x, y) in enumerate(pts):
        X = pad + (w - 2 * pad) * x
        Y = h - pad - (h - 2 * pad) * (y - lo) / ((hi - lo) or 1)
        path.moveTo(X, Y) if i == 0 else path.lineTo(X, Y)
    q.setPen(QPen(QColor(GREEN), 2.0))
    q.setBrush(Qt.NoBrush)
    q.drawPath(path)
    q.end()
    return QIcon(pm)


# ====================================================================== khung ve duong cong
class BezPlot(QWidget):
    changed = Signal()          # dang keo
    released = Signal()         # tha chuot
    ML, MR, MT, MB = 28, 28, 16, 30

    def __init__(self):
        super().__init__()
        self.p = list(BEZ["ease_inout"])
        self.u = None            # vi tri xem thu (0..1) hoac None
        self.hot, self.drag, self.frozen = None, None, None
        self.editable = True
        self.setMouseTracking(True)
        self.setMinimumSize(280, 240)
        theme.bus.changed.connect(self.update)

    def area(self):
        return QRectF(self.ML, self.MT, max(10, self.width() - self.ML - self.MR), max(10, self.height() - self.MT - self.MB))

    def yr(self):
        if self.frozen is not None:
            return self.frozen
        return (min(-0.25, min(self.p[1], self.p[3]) - 0.15), max(1.25, max(self.p[1], self.p[3]) + 0.15))

    def pt(self, x, y, yr=None):
        a, yr = self.area(), yr or self.yr()
        return QPointF(a.left() + x * a.width(), a.bottom() - (y - yr[0]) / ((yr[1] - yr[0]) or 1) * a.height())

    def unpt(self, pos):
        a, yr = self.area(), self.yr()
        return (pos.x() - a.left()) / a.width(), yr[0] + (a.bottom() - pos.y()) / a.height() * (yr[1] - yr[0])

    def handles(self):
        return self.pt(self.p[0], self.p[1]), self.pt(self.p[2], self.p[3])

    def paintEvent(self, _):
        q = QPainter(self)
        q.setRenderHint(QPainter.Antialiasing)
        q.fillRect(self.rect(), QColor(T["bg0"]))
        a, yr = self.area(), self.yr()
        # luoi
        q.setFont(mk(theme.FONT_BODY, 10))
        for i in range(5):
            x = a.left() + a.width() * i / 4
            q.setPen(QPen(QColor(T["line"]), 1))
            q.drawLine(QPointF(x, a.top()), QPointF(x, a.bottom()))
            q.setPen(QColor(T["text3"]))
            q.drawText(QRectF(x - 20, a.bottom() + 5, 40, 16), Qt.AlignCenter, ("%g" % (i / 4)) if i in (0, 2, 4) else "")
        v = 0.0
        step = 0.25
        k = int(yr[0] / step) - 1
        while k * step <= yr[1]:
            y = k * step
            if yr[0] <= y <= yr[1]:
                py = self.pt(0, y, yr).y()
                strong = abs(y) < 1e-9 or abs(y - 1) < 1e-9
                q.setPen(QPen(QColor(T["line_hi"] if strong else T["line"]), 1.4 if strong else 1,
                              Qt.DashLine if strong else Qt.SolidLine))
                q.drawLine(QPointF(a.left(), py), QPointF(a.right(), py))
                if abs(y * 2 - round(y * 2)) < 1e-9:
                    q.setPen(QColor(T["text3"]))
                    q.drawText(QRectF(0, py - 8, self.ML - 6, 16), Qt.AlignRight | Qt.AlignVCenter, "%g" % y)
            k += 1
        q.setPen(QColor(T["text3"]))
        q.setFont(mk(theme.FONT_BODY, 10, QFont.DemiBold))
        q.drawText(QRectF(a.left(), a.bottom() + 12, a.width(), 16), Qt.AlignCenter, "")
        # duong cong
        path = QPainterPath()
        for i, (x, y) in enumerate(bez_points(self.p, 100)):
            P = self.pt(x, y, yr)
            path.moveTo(P) if i == 0 else path.lineTo(P)
        q.setPen(QPen(QColor(GREEN), 3.6))
        q.setBrush(Qt.NoBrush)
        q.drawPath(path)
        # tay cam
        p0, p3 = self.pt(0, 0, yr), self.pt(1, 1, yr)
        h1, h2 = self.handles()
        q.setPen(QPen(QColor("#ffffff"), 2.6))
        q.drawLine(p0, h1)
        q.drawLine(p3, h2)
        q.setPen(Qt.NoPen)
        q.setBrush(QColor(GREEN))
        for P in (p0, p3):
            q.drawEllipse(P, 5, 5)
        if self.u is not None:                                     # cham chay theo duong cong
            y = bezier_y(*self.p, self.u)
            q.setBrush(QColor(T["playhead"]))
            q.drawEllipse(self.pt(self.u, y, yr), 6, 6)
        for i, h in enumerate((h1, h2)):
            hot = self.hot == i or self.drag == i
            q.setPen(QPen(QColor("#000000"), 1))
            q.setBrush(QColor("#ffffff") if self.editable else QColor("#8a8a96"))
            q.drawEllipse(h, 12.5 if hot else 11, 12.5 if hot else 11)
        q.setPen(QColor(T["text3"]))
        q.setFont(mk(theme.FONT_BODY, 10, QFont.DemiBold))
        q.drawText(QRectF(a.left(), self.height() - 20, a.width(), 16), Qt.AlignCenter, "CUBIC BEZIER EASING")

    def hit(self, pos):
        for i, h in enumerate(self.handles()):
            if abs(h.x() - pos.x()) < 17 and abs(h.y() - pos.y()) < 17:
                return i
        return None

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton or not self.editable:
            return
        i = self.hit(QPointF(e.position()))
        if i is not None:
            self.frozen = self.yr()          # khoa truc doc khi keo de khung khong "troi"
            self.drag = i
            self.update()

    def mouseMoveEvent(self, e):
        pos = QPointF(e.position())
        if self.drag is None:
            h = self.hit(pos) if self.editable else None
            if h != self.hot:
                self.hot = h
                self.setCursor(Qt.PointingHandCursor if h is not None else Qt.ArrowCursor)
                self.update()
            return
        x, y = self.unpt(pos)
        if e.modifiers() & Qt.ShiftModifier:
            x, y = round(x * 20) / 20, round(y * 20) / 20
        x, y = max(0.0, min(1.0, x)), max(YMIN, min(YMAX, y))
        if self.drag == 0:
            self.p[0], self.p[1] = x, y
        else:
            self.p[2], self.p[3] = x, y
        self.changed.emit()
        self.update()

    def leaveEvent(self, e):
        self.hot = None
        self.update()

    def mouseReleaseEvent(self, e):
        if self.drag is not None:
            self.drag, self.frozen = None, None
            self.released.emit()
            self.update()


class PreviewStrip(QWidget):
    """Thanh xem thu: cham chay tu trai sang phai theo duong cong dang chinh."""

    def __init__(self):
        super().__init__()
        self.y = 0.0
        self.setFixedHeight(46)
        theme.bus.changed.connect(self.update)

    def paintEvent(self, _):
        q = QPainter(self)
        q.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        q.setPen(Qt.NoPen)
        q.setBrush(QColor(T["bg2"]))
        q.drawRoundedRect(QRectF(0, 0, w, h), 10, 10)
        x0, x1 = 26.0, w - 26.0
        q.setPen(QPen(QColor(T["line_hi"]), 2))
        q.drawLine(QPointF(x0, h / 2), QPointF(x1, h / 2))
        q.setPen(Qt.NoPen)
        q.setBrush(QColor(T["text3"]))
        for x in (x0, x1):
            q.drawEllipse(QPointF(x, h / 2), 4, 4)
        q.setBrush(QColor(GREEN))
        q.drawEllipse(QPointF(x0 + (x1 - x0) * self.y, h / 2), 9, 9)


# ====================================================================== cua so
class BezierDialog(QDialog):
    changed = Signal()      # key da bi sua -> editor ve lai (gom toi da 1 lan / ~16ms)

    def __init__(self, ed):
        super().__init__(ed)
        self.setWindowFlag(Qt.Tool, True)
        self.setWindowTitle("Cubic Bézier Easing")
        self.resize(860, 540)
        self.ed = ed
        self.targets, self._chans, self.chan, self._lock = [], None, None, False
        self._dirty = False
        self._et = QTimer(self)
        self._et.setSingleShot(True)
        self._et.setInterval(16)
        self._et.timeout.connect(self._flush)
        self._pt = QTimer(self)
        self._pt.setInterval(16)
        self._pt.timeout.connect(self._tick)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)
        top = QHBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("Title")
        self.title.setStyleSheet("font-size:13px;")
        self.combo = QComboBox()
        self.combo.setMinimumWidth(170)
        self.combo.setToolTip("Chọn kênh cần áp dụng (mặc định: mọi kênh có key tại đầu phát)")
        self.combo.currentIndexChanged.connect(self._chan_changed)
        top.addWidget(self.title, 1)
        top.addWidget(QLabel("Kênh"))
        top.addWidget(self.combo)
        root.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(10)
        self.gal = QListWidget()
        self.gal.setViewMode(QListWidget.IconMode)
        self.gal.setIconSize(QSize(64, 46))
        self.gal.setGridSize(QSize(76, 62))
        self.gal.setResizeMode(QListWidget.Adjust)
        self.gal.setMovement(QListWidget.Static)
        self.gal.setSpacing(2)
        self.gal.setFixedWidth(172)
        for key, name, params, named in PRESETS:
            it = QListWidgetItem()
            it.setData(Qt.UserRole, key)
            it.setToolTip("%s\n%s" % (name, css_text(params)))
            self.gal.addItem(it)
        self._icons()
        theme.bus.changed.connect(self._icons)
        self.gal.itemClicked.connect(lambda it: self._preset(it.data(Qt.UserRole)))
        body.addWidget(self.gal)

        mid = QVBoxLayout()
        mid.setSpacing(8)
        self.plot = BezPlot()
        self.plot.changed.connect(self._plot_changed)
        self.plot.released.connect(self._flush)
        mid.addWidget(self.plot, 1)
        nav = QHBoxLayout()
        self.prev, self.nxt = QPushButton("‹"), QPushButton("›")
        for b, d in ((self.prev, -1), (self.nxt, 1)):
            b.setObjectName("SmallBtn")
            b.setFixedWidth(36)
            b.clicked.connect(lambda _=False, d=d: self._step(d))
        self.name_lbl = QLabel("")
        self.name_lbl.setAlignment(Qt.AlignCenter)
        self.name_lbl.setObjectName("Sub")
        nav.addWidget(self.prev)
        nav.addWidget(self.name_lbl, 1)
        nav.addWidget(self.nxt)
        mid.addLayout(nav)
        body.addLayout(mid, 1)
        root.addLayout(body, 1)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.sp = []
        for lab, lo, hi in (("x1", 0, 1), ("y1", YMIN, YMAX), ("x2", 0, 1), ("y2", YMIN, YMAX)):
            l = QLabel(lab)
            l.setObjectName("Sub")
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setDecimals(3)
            s.setSingleStep(0.01)
            s.setFixedWidth(82)
            s.valueChanged.connect(self._spin)
            row.addWidget(l)
            row.addWidget(s)
            self.sp.append(s)
        self.txt = QLineEdit()
        self.txt.setMinimumWidth(200)
        self.txt.setToolTip("Dán cubic-bezier(x1, y1, x2, y2) từ CSS / After Effects rồi Enter")
        self.txt.editingFinished.connect(self._text)
        row.addWidget(self.txt, 1)
        for label, tip, fn in (("⇄", "Đảo ngược đường cong", self._reverse), ("↺", "Đặt lại (Ease In-Out)", self._reset),
                               ("⎘", "Sao chép cubic-bezier(...)", self._copy)):
            b = QPushButton(label)
            b.setObjectName("SmallBtn")
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, f=fn: f())
            row.addWidget(b)
        root.addLayout(row)
        self.strip = PreviewStrip()
        root.addWidget(self.strip)
        hint = QLabel("Kéo 2 chấm trắng (giữ Shift: bám lưới 0.05). Trục ngang là thời gian giữa 2 key, trục dọc là tiến độ giá trị: "
                      "kéo y vượt ngoài 0..1 để tạo hiệu ứng bật nảy (overshoot). Thay đổi áp dụng ngay cho key tại đầu phát.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        root.addWidget(hint)
        self._load_params(list(BEZ["ease_inout"]))
        self.refresh()

    # ---------------------------------------------------------------- hien thi
    def _icons(self):
        for i, (key, name, params, named) in enumerate(PRESETS):
            self.gal.item(i).setIcon(curve_icon(params))

    def showEvent(self, e):
        super().showEvent(e)
        self._t0 = time.monotonic()
        self._pt.start()
        self.refresh()

    def hideEvent(self, e):
        self._pt.stop()
        super().hideEvent(e)

    def _tick(self):
        ph = ((time.monotonic() - self._t0) % 2.0) / 2.0          # 2 giay / vong: dung - chay - dung
        u = max(0.0, min(1.0, (ph - 0.12) / 0.62))
        self.plot.u = u
        self.strip.y = bezier_y(*self.plot.p, u)
        self.plot.update()
        self.strip.update()

    def _load_params(self, p):
        self._lock = True
        self.plot.p = list(p)
        for s, v in zip(self.sp, p):
            s.setValue(v)
        self.txt.setText(css_text(p))
        self._lock = False
        self.plot.update()

    # ---------------------------------------------------------------- moi lien he voi key dang chon
    @staticmethod
    def _collect(L, t):
        out = []
        if L is None or L.kind in ("bg", "audio"):
            return out
        for ch, _ in CHANNELS:
            ks = sorted(L.kf.get(ch, []))
            for k, nxt in zip(ks, ks[1:]):                           # key cuoi khong co doan tiep theo
                if abs(k.t - t) < 0.05:
                    out.append((ch, k))
        return out

    def refresh(self):
        L, t = self.ed.sel, self.ed.t
        allt = self._collect(L, t)
        chans = tuple(ch for ch, _ in allt)
        if chans != self._chans:
            self._chans = chans
            names = dict(CHANNELS)
            keep = self.chan if self.chan in chans else None
            self.combo.blockSignals(True)
            self.combo.clear()
            self.combo.addItem("Tất cả kênh có key", None)
            for ch in chans:
                self.combo.addItem(names[ch], ch)
            self.combo.setCurrentIndex(0 if keep is None else chans.index(keep) + 1)
            self.combo.blockSignals(False)
            self.chan = keep
        self.targets = [(ch, k) for ch, k in allt if self.chan in (None, ch)]
        ok = bool(self.targets)
        self.plot.editable = ok
        for w in self.sp + [self.txt, self.gal, self.prev, self.nxt, self.combo]:
            w.setEnabled(ok)
        if not ok:
            self.title.setText("Đặt đầu phát đúng vào một key frame (không phải key cuối) của lớp đang chọn · phím K để thêm key")
            self.name_lbl.setText("")
            self.plot.update()
            return
        k = self.targets[0][1]
        self.title.setText("Lớp: %s · key tại %d:%05.2f · %d kênh" % (L.name, int(k.t) // 60, k.t % 60, len(self.targets)))
        h = k.handles()
        self.name_lbl.setText(("Tuỳ chỉnh (Bezier)" if k.e == "bezier" else dict(EASES).get(k.e, k.e)) +
                              ("" if h else "  ·  kiểu này không phải Bézier: chọn mẫu hoặc kéo tay cầm để chuyển"))
        p = list(h) if h else list(BEZ["ease_inout"])
        if self.plot.drag is None and any(abs(a - b) > 5e-4 for a, b in zip(p, self.plot.p)):
            self._load_params(p)
        self.plot.update()

    def _chan_changed(self, _):
        self.chan = self.combo.currentData()
        self.refresh()

    # ---------------------------------------------------------------- ap dung len key
    def _apply(self, p, named=None):
        for ch, k in self.targets:
            if named:
                k.e, k.bz = named, None
            else:
                k.e, k.bz = "bezier", tuple(round(v, 4) for v in p)
        self._dirty = True
        if not self._et.isActive():
            self._et.start()

    def _flush(self):
        self._et.stop()
        if self._dirty:
            self._dirty = False
            self.changed.emit()

    def _plot_changed(self):
        p = clamp_params(self.plot.p)
        self._lock = True
        for s, v in zip(self.sp, p):
            s.setValue(v)
        self.txt.setText(css_text(p))
        self._lock = False
        self._apply(p)

    def _spin(self, _):
        if self._lock:
            return
        p = clamp_params([s.value() for s in self.sp])
        self.plot.p = p
        self.txt.setText(css_text(p))
        self.plot.update()
        self._apply(p)

    def _text(self):
        p = parse_css(self.txt.text())
        if p is None:
            self.txt.setText(css_text(self.plot.p))
            return
        self._load_params(p)
        self._apply(p)
        self._flush()

    def _preset(self, key):
        for k, name, params, named in PRESETS:
            if k == key:
                self._load_params(list(params))
                self._apply(list(params), key if named else None)
                self._flush()
                self.name_lbl.setText(name)
                return

    def _step(self, d):
        keys = [k for k, *_ in PRESETS]
        cur = self.gal.currentRow()
        row = (cur + d) % len(keys) if cur >= 0 else (0 if d > 0 else len(keys) - 1)
        self.gal.setCurrentRow(row)
        self._preset(keys[row])

    def _reverse(self):
        x1, y1, x2, y2 = self.plot.p
        p = clamp_params([1 - x2, 1 - y2, 1 - x1, 1 - y1])
        self._load_params(p)
        self._apply(p)
        self._flush()

    def _reset(self):
        self._preset("ease_inout")

    def _copy(self):
        QApplication.clipboard().setText(css_text(self.plot.p))
