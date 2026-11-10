import sys, os, math, datetime, json, time, random, secrets, threading, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, urlencode
from PyQt5.QtCore import Qt, QTimer, QRect, QRectF, QPointF, QSize, QObject, pyqtSignal
from PyQt5.QtGui import (QColor, QPainter, QPen, QBrush, QFont, QPixmap, QIcon, QLinearGradient,
                         QPainterPath, QPolygonF, QFontDatabase, QFontMetrics, QRadialGradient)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QListWidget, QListWidgetItem, QPushButton, QLabel, QSlider,
    QDoubleSpinBox, QComboBox, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsLineItem, QGroupBox, QScrollArea, QFrame, QStackedWidget, QLineEdit, QGridLayout, QButtonGroup)

LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gk_keyfl_logo.png")
TOTAL = 30.0
TRACK_H, RULER_H = 44, 26
TRACKS = ["Text", "Overlay", "Video", "Audio"]
COLORS = {"Text": "#e0a526", "Overlay": "#9b59d0", "Video": "#2f8fe0", "Audio": "#2fb37a"}

STYLE = """
* { color: #dcdcdc; font-size: 12px; }
QMainWindow, QWidget { background: #1b1b1f; }
QTabWidget::pane { border: 1px solid #2c2c33; }
QTabBar::tab { background: #24242a; padding: 6px 12px; }
QTabBar::tab:selected { background: #34343c; color: #fff; }
QListWidget { background: #202026; border: none; }
QGroupBox { border: 1px solid #2c2c33; margin-top: 10px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; color: #8a8a96; }
QPushButton { background: #2d2d35; border: none; border-radius: 4px; padding: 6px 10px; }
QPushButton:hover { background: #3a3a44; }
QPushButton:checked { background: #e0a526; color: #000; }
QPushButton#accent { background: #7a2bff; color: #ffffff; font-weight: bold; }
QSlider::groove:horizontal { height: 4px; background: #33333c; }
QSlider::handle:horizontal { background: #7a2bff; width: 12px; margin: -5px 0; border-radius: 6px; }
QDoubleSpinBox, QComboBox { background: #26262d; border: 1px solid #33333c; padding: 2px 4px; }
QSplitter::handle { background: #121215; }
"""


class Preview(QWidget):
    """Canvas 16:9 voi 1 layer mau, nhan transform tu panel thuoc tinh."""
    def __init__(self):
        super().__init__()
        self.t = 0.0
        self.tf = dict(x=0, y=0, scale=100, rot=0, opacity=100)
        self.ratio = 16 / 9
        self.setMinimumSize(320, 180)

    def set_tf(self, k, v):
        self.tf[k] = v
        self.update()

    def set_time(self, t):
        self.t = t
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101013"))
        w = min(self.width() - 20, (self.height() - 20) * self.ratio)
        h = w / self.ratio
        r = QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)
        s = 12
        for i in range(int(w // s) + 1):
            for j in range(int(h // s) + 1):
                c = "#2a2a30" if (i + j) % 2 else "#222228"
                p.fillRect(QRectF(r.x() + i * s, r.y() + j * s, min(s, w - i * s), min(s, h - j * s)), QColor(c))
        p.setClipRect(r)
        p.translate(r.center().x() + self.tf["x"] * w / 200, r.center().y() + self.tf["y"] * h / 200)
        p.rotate(self.tf["rot"])
        p.scale(self.tf["scale"] / 100, self.tf["scale"] / 100)
        p.setOpacity(self.tf["opacity"] / 100)
        p.setBrush(QBrush(QColor("#7a2bff")))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(-w * .15, -h * .15, w * .3, h * .3), 14, 14)
        p.setPen(QColor("#ffffff"))
        f = QFont("Arial", max(8, int(w / 28)), QFont.Bold)
        p.setFont(f)
        p.drawText(QRectF(-w * .15, -h * .15, w * .3, h * .3), Qt.AlignCenter, "GrayKazu")


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
        c = self.color.lighter(130) if self.isSelected() else self.color
        p.setBrush(c)
        p.setPen(QPen(QColor("#fff"), 2) if self.isSelected() else Qt.NoPen)
        p.drawRoundedRect(self.rect(), 5, 5)
        p.setPen(QColor("#fff"))
        p.drawText(self.rect().adjusted(8, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, self.name)


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
        self.head = QGraphicsLineItem()
        self.head.setPen(QPen(QColor("#ff4d5e"), 2))
        self.head.setZValue(100)
        self.sc.addItem(self.head)
        self.clips = []
        self.t = 0.0
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
        x = t * self.pps
        self.head.setLine(x, 0, x, self.sc.height())

    def drawBackground(self, p, rect):
        p.fillRect(rect, QColor("#1b1b1f"))
        for i in range(len(TRACKS)):
            y = RULER_H + i * TRACK_H
            p.fillRect(QRectF(rect.left(), y, rect.width(), TRACK_H), QColor("#212127" if i % 2 else "#1d1d22"))
        p.fillRect(QRectF(rect.left(), 0, rect.width(), RULER_H), QColor("#26262d"))
        p.setPen(QColor("#8a8a96"))
        for s in range(int(TOTAL) + 1):
            x = s * self.pps
            p.drawLine(int(x), RULER_H - (12 if s % 5 == 0 else 6), int(x), RULER_H)
            if s % 5 == 0:
                p.drawText(int(x) + 3, 14, f"{s // 60:02d}:{s % 60:02d}")

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


def prop_row(grid, label, lo, hi, val, cb, suffix=""):
    row = QHBoxLayout()
    lab = QLabel(label)
    lab.setFixedWidth(58)
    sl = QSlider(Qt.Horizontal)
    sl.setRange(int(lo), int(hi))
    sl.setValue(int(val))
    sp = QDoubleSpinBox()
    sp.setRange(lo, hi)
    sp.setValue(val)
    sp.setSuffix(suffix)
    sp.setFixedWidth(74)
    kf = QPushButton("◆")
    kf.setCheckable(True)
    kf.setFixedWidth(26)
    kf.setToolTip("Keyframe")
    sl.valueChanged.connect(lambda v: sp.setValue(v))
    sp.valueChanged.connect(lambda v: (sl.blockSignals(True), sl.setValue(int(v)), sl.blockSignals(False), cb(v)))
    for w in (lab, sl, sp, kf):
        row.addWidget(w)
    grid.addLayout(row)


FONT_DISPLAY = FONT_COND = FONT_BODY = "Sans Serif"
AUTH_BASE = os.environ.get("GK_AUTH_URL", "https://graykazu.graykazuvn.workers.dev/acc/gkkeyfl")
DEV = bool(os.environ.get("GK_DEV"))
CFG = os.path.join(os.path.expanduser("~"), ".config", "gk_keyfl", "user.json")
OK_HTML = ("<!doctype html><meta charset='utf-8'><title>GK KeyFL</title>"
           "<body style='margin:0;height:100vh;display:grid;place-items:center;background:#0b0b0f;color:#fff;"
           "font-family:system-ui,sans-serif'><div style='text-align:center'><h2>Đăng nhập thành công</h2>"
           "<p style='color:#9a9aa6'>Bạn có thể đóng tab này và quay lại GK KeyFL.</p></div>")


def load_user():
    try:
        with open(CFG, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("name", ""), d.get("email", "")
    except Exception:
        return None


def save_user(name, email):
    try:
        os.makedirs(os.path.dirname(CFG), exist_ok=True)
        with open(CFG, "w", encoding="utf-8") as f:
            json.dump({"name": name, "email": email}, f)
    except Exception:
        pass


def clear_user():
    try:
        os.remove(CFG)
    except Exception:
        pass


def init_fonts():
    """Nap font trong thu muc fonts/ (neu co) roi chon font dep nhat dang co."""
    global FONT_DISPLAY, FONT_COND, FONT_BODY
    fd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    if os.path.isdir(fd):
        for f in sorted(os.listdir(fd)):
            if f.lower().endswith((".ttf", ".otf")):
                QFontDatabase.addApplicationFont(os.path.join(fd, f))
    have = set(QFontDatabase().families())

    def pick(cands, fb):
        return next((c for c in cands if c in have), fb)

    FONT_DISPLAY = pick(["Lexend", "Lexend Deca", "Outfit", "Be Vietnam Pro", "Montserrat", "Poppins", "Noto Sans", "DejaVu Sans"], "Sans Serif")
    FONT_COND = pick(["Oswald", "Barlow Condensed", "Saira Condensed", "Roboto Condensed", "Fira Sans Condensed",
                      "Noto Sans Condensed", "DejaVu Sans Condensed"], "Sans Serif")
    FONT_BODY = pick(["Inter", "Be Vietnam Pro", "Nunito", "Noto Sans", "Cantarell", "DejaVu Sans"], "Sans Serif")


def mk(family, px, weight=QFont.Normal):
    f = QFont(family)
    f.setPixelSize(int(px))
    f.setWeight(weight)
    return f


def mixc(c1, c2, t):
    a, b = QColor(c1), QColor(c2)
    t = max(0.0, min(1.0, t))
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


def star(cx, cy, R, r, n, rot=-90):
    pts = []
    for i in range(n * 2):
        a = math.radians(rot + i * 180 / n)
        rad = R if i % 2 == 0 else r
        pts.append(QPointF(cx + rad * math.cos(a), cy + rad * math.sin(a)))
    return QPolygonF(pts)


# ------------------------------------------------------------------ icons
def draw_brand_icon(p, r):
    p.save()
    p.setBrush(Qt.NoBrush)
    for i, col in enumerate(["#7a2bff", "#a56bff", "#111111"]):
        pen = QPen(QColor(col), r.width() * 0.13)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)
        x = r.left() + r.width() * (0.10 + i * 0.26)
        p.drawLine(QPointF(x, r.bottom()), QPointF(x + r.width() * 0.42, r.top()))
    p.restore()


def draw_google(p, r):
    p.save()
    s = r.width()
    w = s * 0.24
    ring = QRectF(r.left() + w / 2, r.top() + w / 2, s - w, s - w)
    p.setBrush(Qt.NoBrush)
    for col, start, span in [("#ea4335", 45, 95), ("#fbbc05", 140, 85), ("#34a853", 225, 90), ("#4285f4", 315, 45)]:
        pen = QPen(QColor(col), w)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)
        p.drawArc(ring, int(start * 16), int(span * 16))
    pen = QPen(QColor("#4285f4"), w * 0.9)
    pen.setCapStyle(Qt.FlatCap)
    p.setPen(pen)
    p.drawLine(QPointF(r.center().x(), r.center().y()), QPointF(r.right(), r.center().y()))
    p.restore()


# ------------------------------------------------------------------ dang nhap qua trinh duyet
class AuthBridge(QObject):
    """Mo trinh duyet toi trang dang nhap cua worker, cho no goi lai http://127.0.0.1:<port>/cb."""
    done = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.url = ""
        self._stop = threading.Event()

    def start(self, google=False):
        self.cancel()
        state = secrets.token_urlsafe(18)
        stop = self._stop = threading.Event()
        bridge = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if u.path != "/cb" or q.get("state", [""])[0] != state:
                    self.send_response(404)
                    self.end_headers()
                    return
                name = q.get("name", [""])[0][:60]
                email = q.get("email", [""])[0][:120]
                body = OK_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                stop.set()
                bridge.done.emit(name, email)

        srv = HTTPServer(("127.0.0.1", 0), H)
        srv.timeout = 1
        port = srv.server_address[1]

        def run():
            t0 = time.monotonic()
            while not stop.is_set() and time.monotonic() - t0 < 300:
                srv.handle_request()
            srv.server_close()
            if not stop.is_set():
                stop.set()
                bridge.failed.emit("Hết thời gian chờ đăng nhập.")

        threading.Thread(target=run, daemon=True).start()
        self.url = AUTH_BASE + "?" + urlencode({"app": "gkkeyfl", "port": port, "state": state,
                                                "via": "google" if google else "account"})
        self.reopen()

    def reopen(self):
        try:
            webbrowser.open(self.url)
        except Exception:
            self.failed.emit("Không mở được trình duyệt.")

    def cancel(self):
        self._stop.set()


# ------------------------------------------------------------------ cube 3D
CUBE_FACES = [((1, 0, 0), (0, 1, 0), (0, 0, 1)), ((-1, 0, 0), (0, 1, 0), (0, 0, 1)),
              ((0, 1, 0), (1, 0, 0), (0, 0, 1)), ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
              ((0, 0, 1), (1, 0, 0), (0, 1, 0)), ((0, 0, -1), (1, 0, 0), (0, 1, 0))]
_LN = math.sqrt(0.4 ** 2 + 0.6 ** 2 + 0.7 ** 2)
LIGHT = (-0.4 / _LN, -0.6 / _LN, -0.7 / _LN)


def rot3(v, ax, ay, az):
    x, y, z = v
    c, s = math.cos(ay), math.sin(ay)
    x, z = x * c + z * s, -x * s + z * c
    c, s = math.cos(ax), math.sin(ax)
    y, z = y * c - z * s, y * s + z * c
    c, s = math.cos(az), math.sin(az)
    x, y = x * c - y * s, x * s + y * c
    return x, y, z


def draw_cube(p, cx, cy, unit, t, mx=0.5, my=0.5):
    ax = t * 0.45 + 0.55 + (my - 0.5) * 0.6
    ay = t * 0.62 + (mx - 0.5) * 0.6
    az = math.sin(t * 0.35) * 0.22
    D = 4.6
    f = unit * D
    cy += math.sin(t * 1.3) * unit * 0.10
    # hao quang + bong
    g = QRadialGradient(cx, cy, unit * 3.6)
    g.setColorAt(0, QColor(124, 58, 237, 110))
    g.setColorAt(0.5, QColor(168, 85, 247, 40))
    g.setColorAt(1, QColor(124, 58, 237, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(cx, cy), unit * 3.6, unit * 3.6)
    sy = cy + unit * 2.5
    g = QRadialGradient(cx, sy, unit * 1.6)
    g.setColorAt(0, QColor(0, 0, 0, 130))
    g.setColorAt(1, QColor(0, 0, 0, 0))
    p.setBrush(QBrush(g))
    p.save()
    p.translate(cx, sy)
    p.scale(1, 0.18)
    p.translate(-cx, -sy)
    p.drawEllipse(QPointF(cx, sy), unit * 1.6, unit * 1.6)
    p.restore()
    # cac mat
    for n, u, v in CUBE_FACES:
        rn = rot3(n, ax, ay, az)
        if rn[2] >= -1 / D:
            continue
        pts = []
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            q = rot3(tuple(n[i] + su * u[i] + sv * v[i] for i in range(3)), ax, ay, az)
            s = f / (q[2] + D)
            pts.append(QPointF(cx + q[0] * s, cy + q[1] * s))
        lam = max(0.0, rn[0] * LIGHT[0] + rn[1] * LIGHT[1] + rn[2] * LIGHT[2])
        col = mixc("#33208a", "#e3d9ff", 0.12 + 0.88 * lam ** 0.85)
        gr = QLinearGradient(pts[0], pts[2])
        gr.setColorAt(0, col.lighter(118))
        gr.setColorAt(1, col)
        p.setPen(QPen(col, unit * 0.10, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QBrush(gr))
        p.drawPolygon(QPolygonF(pts))
        p.setPen(QPen(QColor(255, 255, 255, 38), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(QPolygonF(pts))


# ------------------------------------------------------------------ man hinh dang nhap
HEAD = "SỰ ĐƠN GIẢN TẠO NÊN SÁNG TẠO"
SUB = "Đăng nhập để mở trình chỉnh sửa và đồng bộ dự án của bạn."


class LoginPage(QWidget):
    entered = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.t0 = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.update)
        self.logo = QPixmap(LOGO)
        self.hits, self.hot = [], None
        self.status, self.msg = "", ""
        self.mx = self.my = 0.5
        self._mx = self._my = 0.5
        rnd = random.Random(7)
        self.parts = [(rnd.random(), rnd.random(), rnd.uniform(.01, .04), rnd.uniform(1, 2.6), rnd.uniform(0, 6.28))
                      for _ in range(46)]
        self.auth = AuthBridge(self)
        self.auth.done.connect(self.on_done)
        self.auth.failed.connect(self.on_fail)

    def showEvent(self, e):
        self.timer.start()

    def hideEvent(self, e):
        self.timer.stop()

    # ---- hanh dong
    def begin(self, google):
        self.status, self.msg = "waiting", ""
        self.auth.start(google)

    def on_done(self, name, email):
        self.status = ""
        self.entered.emit(name or (email.split("@")[0] if email else "Bạn"), email)

    def on_fail(self, msg):
        self.status, self.msg = "error", msg

    def hit(self, pos):
        pt = QPointF(pos)
        for name, rect in self.hits:
            if rect.contains(pt):
                return name
        return None

    def mouseMoveEvent(self, e):
        self.mx, self.my = e.x() / max(1, self.width()), e.y() / max(1, self.height())
        h = self.hit(e.pos())
        if h != self.hot:
            self.hot = h
            self.setCursor(Qt.PointingHandCursor if h else Qt.ArrowCursor)

    def leaveEvent(self, e):
        self.hot = None

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        h = self.hit(e.pos())
        if h in ("btn1", "btn2"):
            self.begin(h == "btn2")
        elif h == "cancel":
            self.auth.cancel()
            self.status = ""
        elif h == "reopen":
            self.auth.reopen()
        elif h == "skip":
            self.entered.emit("Khách", "")

    # ---- ve
    def compute(self):
        w, h = self.width(), self.height()
        cw = max(360, min(500, w * 0.46))
        ml = max(28, min(w * 0.07, 110))
        if w < 760:
            ml = (w - cw) / 2
        inner = cw - 80
        fl = Qt.TextWordWrap | Qt.AlignLeft
        self.f_head = mk(FONT_DISPLAY, 30, QFont.Black)
        self.f_sub = mk(FONT_BODY, 14)
        hh = QFontMetrics(self.f_head).boundingRect(QRect(0, 0, int(inner), 2000), fl, HEAD).height()
        sh = QFontMetrics(self.f_sub).boundingRect(QRect(0, 0, int(inner), 2000), fl, SUB).height()
        y, L = 40, {}
        L["logo"] = y
        y += 44 + 26
        L["head"] = (y, hh)
        y += hh + 12
        L["sub"] = (y, sh)
        y += sh + 30
        L["btn1"] = y
        y += 56 + 14
        L["btn2"] = y
        y += 56 + 24
        L["foot"] = y
        y += 18
        if DEV:
            L["skip"] = y + 8
            y += 30
        ch = y + 34
        self.card = QRectF(ml, max(20, (h - ch) / 2), cw, ch)
        self.L, self.inner = L, inner

    def paintEvent(self, _):
        t = time.monotonic() - self.t0
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        full = QRectF(0, 0, w, h)
        p.fillRect(full, QColor("#07070b"))
        # nen: cac vet mau troi cham
        for cx, cy, r, col, sx, sy, ph in [(.22, .30, .55, (124, 58, 237), .21, .17, 0.0),
                                           (.82, .25, .50, (219, 39, 119), .16, .23, 1.7),
                                           (.70, .88, .60, (37, 99, 235), .19, .14, 3.1),
                                           (.10, .95, .45, (168, 85, 247), .13, .20, 4.6)]:
            x = w * (cx + 0.07 * math.sin(t * sx + ph))
            y = h * (cy + 0.07 * math.cos(t * sy + ph))
            R = max(w, h) * r
            g = QRadialGradient(x, y, R)
            g.setColorAt(0, QColor(col[0], col[1], col[2], 120))
            g.setColorAt(1, QColor(col[0], col[1], col[2], 0))
            p.fillRect(full, QBrush(g))
        # hat bui sang
        p.setPen(Qt.NoPen)
        for fx, fy, sp, sz, ph in self.parts:
            x = (fx * w + t * sp * w * 0.6) % w
            y = (fy * h - t * sp * h * 0.9) % h
            p.setBrush(QColor(255, 255, 255, int(40 + 60 * (0.5 + 0.5 * math.sin(t * 1.4 + ph)))))
            p.drawEllipse(QPointF(x, y), sz, sz)
        g = QRadialGradient(w / 2, h / 2, max(w, h) * 0.78)
        g.setColorAt(0.55, QColor(0, 0, 0, 0))
        g.setColorAt(1, QColor(0, 0, 0, 170))
        p.fillRect(full, QBrush(g))

        self.compute()
        c, L, inner = self.card, self.L, self.inner
        self._mx += (self.mx - self._mx) * 0.06
        self._my += (self.my - self._my) * 0.06

        # cube
        right0 = c.right() + 30
        avail = w - right0
        if avail > 220:
            draw_cube(p, right0 + avail / 2, h / 2, min(avail * 0.16, h * 0.16), t, self._mx, self._my)

        # the den
        for i, a in enumerate((10, 8, 6)):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(124, 58, 237, a))
            p.drawRoundedRect(c.adjusted(-6 - i * 8, -6 - i * 8, 6 + i * 8, 6 + i * 8), 34 + i * 8, 34 + i * 8)
        p.setBrush(QColor(10, 10, 14, 250))
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        p.drawRoundedRect(c, 28, 28)

        x0, y0 = c.x() + 40, c.y()
        # logo trong o trang
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(x0, y0 + L["logo"], 44, 44), 12, 12)
        p.drawPixmap(QRectF(x0 + 6, y0 + L["logo"] + 6, 32, 32), self.logo, QRectF(self.logo.rect()))
        p.setPen(QColor("#ffffff"))
        p.setFont(mk(FONT_DISPLAY, 18, QFont.Bold))
        p.drawText(QRectF(x0 + 56, y0 + L["logo"], 200, 44), Qt.AlignVCenter | Qt.AlignLeft, "GK KeyFL")
        fl = Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop
        p.setFont(self.f_head)
        p.drawText(QRectF(x0, y0 + L["head"][0], inner, L["head"][1] + 4), fl, HEAD)
        p.setPen(QColor("#8d8d9a"))
        p.setFont(self.f_sub)
        p.drawText(QRectF(x0, y0 + L["sub"][0], inner, L["sub"][1] + 4), fl, SUB)

        self.hits = []
        b1 = QRectF(x0, y0 + L["btn1"], inner, 56)
        b2 = QRectF(x0, y0 + L["btn2"], inner, 56)
        if self.status == "waiting":
            area = QRectF(x0, b1.top(), inner, b2.bottom() - b1.top())
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#14141a"))
            p.drawRoundedRect(area, 20, 20)
            sp = QRectF(area.left() + 24, area.top() + 24, 26, 26)
            p.setBrush(Qt.NoBrush)
            pen = QPen(QColor("#a56bff"), 3)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(sp, int(-t * 320 * 16), 110 * 16)
            p.setPen(QColor("#ffffff"))
            p.setFont(mk(FONT_BODY, 15, QFont.DemiBold))
            p.drawText(QRectF(area.left() + 64, area.top() + 18, inner - 80, 22), Qt.AlignLeft | Qt.AlignVCenter,
                       "Đang chờ đăng nhập…")
            p.setPen(QColor("#8d8d9a"))
            p.setFont(mk(FONT_BODY, 13))
            p.drawText(QRectF(area.left() + 64, area.top() + 42, inner - 80, 20), Qt.AlignLeft | Qt.AlignVCenter,
                       "Hoàn tất ở tab trình duyệt vừa mở.")
            for name, txt, rx in (("reopen", "Mở lại trình duyệt", area.left() + 24), ("cancel", "Huỷ", area.right() - 70)):
                r = QRectF(rx, area.bottom() - 40, 150 if name == "reopen" else 46, 26)
                p.setPen(QColor("#c9a8ff" if self.hot == name else "#a56bff"))
                p.setFont(mk(FONT_BODY, 13, QFont.DemiBold))
                p.drawText(r, Qt.AlignLeft | Qt.AlignVCenter, txt)
                self.hits.append((name, r))
        else:
            for name, r, label, icon in (("btn1", b1, "Tiếp tục bằng tài khoản", draw_brand_icon),
                                         ("btn2", b2, "Tiếp tục bằng Google", draw_google)):
                hov = self.hot == name
                primary = name == "btn1"
                p.setPen(Qt.NoPen if primary else QPen(QColor(255, 255, 255, 46), 1))
                p.setBrush(QColor("#ececf6" if hov else "#ffffff") if primary else QColor("#1d1d25" if hov else "#15151b"))
                p.drawRoundedRect(r, 28, 28)
                if icon is draw_google:
                    icon(p, QRectF(r.left() + 22, r.center().y() - 11, 22, 22))
                else:
                    icon(p, QRectF(r.left() + 22, r.center().y() - 11, 22, 22))
                p.setPen(QColor("#0b0b0f" if primary else "#ffffff"))
                p.setFont(mk(FONT_BODY, 16, QFont.DemiBold))
                p.drawText(r.adjusted(34, 0, 0, 0), Qt.AlignCenter, label)
                self.hits.append((name, r))
        p.setFont(mk(FONT_BODY, 12))
        if self.status == "error":
            p.setPen(QColor("#ff7a8a"))
            txt = self.msg
        else:
            p.setPen(QColor("#6b6b78"))
            txt = "Bằng việc tiếp tục, bạn đồng ý với Điều khoản sử dụng."
        p.drawText(QRectF(x0, y0 + L["foot"], inner, 18), Qt.AlignLeft | Qt.AlignVCenter, txt)
        if DEV:
            r = QRectF(x0, y0 + L["skip"], 220, 22)
            p.setPen(QColor("#a56bff"))
            p.drawText(r, Qt.AlignLeft | Qt.AlignVCenter, "Dùng thử (chế độ dev)")
            self.hits.append(("skip", r))


# ------------------------------------------------------------------ man hinh Home
def draw_art(p, r, title):
    """Hinh minh hoa thumbnail project."""
    W, H = r.width(), r.height()

    def P(fx, fy):
        return QPointF(r.x() + fx * W, r.y() + fy * H)

    p.fillRect(r, QColor("#ffffff"))
    pen = QPen(QColor("#a9b6bd"), 5)
    pen.setJoinStyle(Qt.RoundJoin)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    path = QPainterPath(P(.19, .12))
    path.lineTo(P(.19, .09))
    path.quadTo(P(.19, .03), P(.25, .03))
    path.lineTo(P(.88, .03))
    path.quadTo(P(.94, .03), P(.94, .09))
    path.lineTo(P(.94, .80))
    path.quadTo(P(.94, .86), P(.88, .86))
    path.lineTo(P(.80, .86))
    p.drawPath(path)
    p.drawLine(P(.165, .095), P(.19, .13))
    p.drawLine(P(.215, .095), P(.19, .13))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#5c5c5c"))
    p.drawEllipse(P(.19, .245), .114 * W, .114 * W)
    p.setBrush(QColor("#000000"))
    p.drawEllipse(P(.80, .715), .074 * W, .074 * W)
    p.save()
    p.translate(P(.52, .49))
    p.rotate(-35)
    bw, bh = W * 0.9, W * 0.33
    g = QLinearGradient(-bw / 2, 0, bw / 2, 0)
    g.setColorAt(0, QColor("#050505"))
    g.setColorAt(1, QColor("#ffffff"))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawRoundedRect(QRectF(-bw / 2, -bh / 2, bw, bh), bh * .25, bh * .25)
    p.setPen(QColor("#000000"))
    p.setFont(mk(FONT_COND, 24, QFont.Normal))
    p.drawText(QRectF(-bw / 2, -bh / 2, bw, bh), Qt.AlignCenter, title)
    p.restore()
    p.setPen(Qt.NoPen)
    for fx, fy, R, col in [(.45, .107, .045, "#2b2b2b"), (.54, .14, .045, "#4fe0e8"),
                           (.47, .21, .045, "#8e7fc8"), (.37, .295, .042, "#a9d8f0")]:
        c = P(fx, fy)
        p.setBrush(QColor(col))
        p.drawPolygon(star(c.x(), c.y(), R * W, R * W * .45, 5))
    c = P(.59, .85)
    p.setBrush(QColor("#c05ae0"))
    p.drawPolygon(star(c.x(), c.y(), .09 * W, .09 * W * .42, 5))
    c = P(.13, .875)
    p.setBrush(QColor("#6a1bff"))
    p.drawPolygon(star(c.x(), c.y(), .10 * W, .10 * W * .86, 14))
    c = P(.93, .935)
    p.setBrush(QColor("#4fe0e8"))
    p.drawPolygon(star(c.x(), c.y(), .045 * W, .045 * W * .3, 4))


CARD_W, CARD_H, CARD_K = 216, 303, 216 / 324


class HomePage(QWidget):
    new_project = pyqtSignal(str, float)
    open_recent = pyqtSignal(str)
    sign_out = pyqtSignal()
    RATIOS = [("16:9", "YouTube", 16 / 9), ("9:16", "TikTok", 9 / 16), ("1:1", "Vuông", 1.0), ("4:5", "Instagram", 4 / 5)]
    BAR = 72

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.logo = QPixmap(LOGO)
        self.user = ("Khách", "")
        self.ratio_i = 0
        self.scroll = 0
        self.content_h = 0
        self.hits, self.hot = [], None
        today = datetime.date.today()
        d = lambda n: (today - datetime.timedelta(days=n)).strftime("%d/%m/%Y")
        self.drafts = [("My File", "WHAT NEW APP", 30, "16:9", "0:04", d(1)),
                       ("Intro vlog", "INTRO VLOG", 30, "16:9", "0:42", d(2)),
                       ("Edit TikTok", "EDIT TIKTOK", 60, "9:16", "0:15", d(3))]

    def set_user(self, name, email):
        self.user = (name or "Khách", email)
        self.update()

    def hit(self, pos):
        pt = QPointF(pos)
        for name, rect in reversed(self.hits):
            if rect.contains(pt):
                return name
        return None

    def mouseMoveEvent(self, e):
        h = self.hit(e.pos())
        if h != self.hot:
            self.hot = h
            self.setCursor(Qt.PointingHandCursor if h and h != "bar" else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, e):
        self.hot = None
        self.update()

    def wheelEvent(self, e):
        self.scroll = max(0, min(max(0, self.content_h - self.height()), self.scroll - e.angleDelta().y() * 0.6))
        self.update()

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        h = self.hit(e.pos())
        if not h:
            return
        if h in ("hero", "newcard"):
            self.new_project.emit("Untitled", self.RATIOS[self.ratio_i][2])
        elif h == "signout":
            self.sign_out.emit()
        elif h.startswith("ratio"):
            self.ratio_i = int(h[5:])
            self.update()
        elif h.startswith("card"):
            self.open_recent.emit(self.drafts[int(h[4:])][0])

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        W, H = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#0d0d11"))
        g = QRadialGradient(W * 0.75, 0, max(W, H) * 0.7)
        g.setColorAt(0, QColor(124, 58, 237, 46))
        g.setColorAt(1, QColor(124, 58, 237, 0))
        p.fillRect(self.rect(), QBrush(g))
        self.hits = []
        M = max(28, min(56, W * 0.04))
        sc = self.scroll = max(0, min(self.scroll, max(0, self.content_h - H)))

        p.save()
        p.setClipRect(QRectF(0, self.BAR, W, H - self.BAR))
        # --- hero "Tao du an moi"
        hero = QRectF(M, self.BAR + 16 - sc, W - 2 * M, 150)
        g = QLinearGradient(hero.left(), hero.top(), hero.right(), hero.bottom())
        g.setColorAt(0, QColor("#ff5e5b"))
        g.setColorAt(0.55, QColor("#c3419f"))
        g.setColorAt(1, QColor("#7b4dff"))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(hero, 28, 28)
        hp = QPainterPath()
        hp.addRoundedRect(hero, 28, 28)
        p.save()
        p.setClipPath(hp)
        p.setBrush(QColor(255, 255, 255, 22))
        p.drawEllipse(QPointF(hero.right() - 60, hero.top() - 20), 150, 150)
        p.drawEllipse(QPointF(hero.right() - 260, hero.bottom() + 30), 110, 110)
        if self.hot == "hero":
            p.setBrush(QColor(255, 255, 255, 26))
            p.drawRoundedRect(hero, 28, 28)
        p.restore()
        p.setPen(QColor("#ffffff"))
        p.setFont(mk(FONT_DISPLAY, 34, QFont.Black))
        p.drawText(QRectF(hero.left() + 40, hero.top() + 34, hero.width() - 200, 48), Qt.AlignLeft | Qt.AlignVCenter, "Tạo dự án mới")
        p.setPen(QColor(255, 255, 255, 215))
        p.setFont(mk(FONT_BODY, 15))
        rl = self.RATIOS[self.ratio_i]
        p.drawText(QRectF(hero.left() + 40, hero.top() + 86, hero.width() - 200, 24), Qt.AlignLeft | Qt.AlignVCenter,
                   "Canvas trống · %s %s" % (rl[0], rl[1]))
        c = QPointF(hero.right() - 80, hero.center().y())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(c, 34, 34)
        p.setBrush(QColor("#111111"))
        p.drawRoundedRect(QRectF(c.x() - 15, c.y() - 4, 30, 8), 3, 3)
        p.drawRoundedRect(QRectF(c.x() - 4, c.y() - 15, 8, 30), 3, 3)
        self.hits.append(("hero", hero))

        # --- tieu de + chon ti le
        ry = hero.bottom() + 34
        p.setPen(QColor("#ffffff"))
        p.setFont(mk(FONT_DISPLAY, 20, QFont.Bold))
        p.drawText(QRectF(M, ry, 300, 34), Qt.AlignLeft | Qt.AlignVCenter, "Dự án gần đây")
        fm = QFontMetrics(mk(FONT_BODY, 13, QFont.DemiBold))
        x = W - M
        for i in range(len(self.RATIOS) - 1, -1, -1):
            lab = self.RATIOS[i][0]
            cw = fm.horizontalAdvance(lab) + 28
            r = QRectF(x - cw, ry + 2, cw, 30)
            sel = i == self.ratio_i
            p.setPen(Qt.NoPen if sel else QPen(QColor(255, 255, 255, 36), 1))
            p.setBrush(QColor("#7a2bff") if sel else QColor(255, 255, 255, 26 if self.hot == "ratio%d" % i else 8))
            p.drawRoundedRect(r, 15, 15)
            p.setPen(QColor("#ffffff" if sel else "#b4b4c0"))
            p.setFont(mk(FONT_BODY, 13, QFont.DemiBold))
            p.drawText(r, Qt.AlignCenter, lab)
            self.hits.append(("ratio%d" % i, r))
            x -= cw + 8

        # --- luoi project
        gap = 24
        cols = max(1, int((W - 2 * M + gap) // (CARD_W + gap)))
        top = ry + 52
        items = list(range(len(self.drafts))) + [-1]
        for k, it in enumerate(items):
            col, row = k % cols, k // cols
            x0 = M + col * (CARD_W + gap)
            y0 = top + row * (CARD_H + gap)
            name = "newcard" if it < 0 else "card%d" % it
            hov = self.hot == name
            p.save()
            p.translate(x0, y0 - (5 if hov else 0))
            p.scale(CARD_K, CARD_K)
            if it < 0:
                self.draw_new(p, hov)
            else:
                dr = self.drafts[it]
                self.draw_card(p, dr[0], dr[1], dr[2], dr[3], dr[4], dr[5], hov)
            p.restore()
            self.hits.append((name, QRectF(x0, y0, CARD_W, CARD_H)))
        rows = (len(items) + cols - 1) // cols
        self.content_h = top + sc + rows * (CARD_H + gap) + 20
        p.restore()

        # --- thanh tren cung
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(13, 13, 17, 238))
        p.drawRect(QRectF(0, 0, W, self.BAR))
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.drawLine(0, self.BAR, W, self.BAR)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(M, 18, 36, 36), 10, 10)
        p.drawPixmap(QRectF(M + 4, 22, 28, 28), self.logo, QRectF(self.logo.rect()))
        p.setPen(QColor("#ffffff"))
        p.setFont(mk(FONT_DISPLAY, 18, QFont.Bold))
        p.drawText(QRectF(M + 48, 18, 200, 36), Qt.AlignVCenter | Qt.AlignLeft, "GK KeyFL")
        # nguoi dung + dang xuat
        fm = QFontMetrics(mk(FONT_BODY, 13, QFont.DemiBold))
        bw = fm.horizontalAdvance("Đăng xuất") + 28
        br = QRectF(W - M - bw, 20, bw, 32)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.setBrush(QColor(255, 255, 255, 24 if self.hot == "signout" else 8))
        p.drawRoundedRect(br, 16, 16)
        p.setPen(QColor("#ffffff"))
        p.setFont(mk(FONT_BODY, 13, QFont.DemiBold))
        p.drawText(br, Qt.AlignCenter, "Đăng xuất")
        nm = self.user[0]
        nw = QFontMetrics(mk(FONT_BODY, 14, QFont.DemiBold)).horizontalAdvance(nm)
        nx = br.left() - 16 - nw
        p.setFont(mk(FONT_BODY, 14, QFont.DemiBold))
        p.drawText(QRectF(nx, 18, nw + 4, 36), Qt.AlignVCenter | Qt.AlignLeft, nm)
        av = QRectF(nx - 46, 18, 36, 36)
        ag = QLinearGradient(av.topLeft(), av.bottomRight())
        ag.setColorAt(0, QColor("#ff5e5b"))
        ag.setColorAt(1, QColor("#7a2bff"))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(ag))
        p.drawEllipse(av)
        p.setPen(QColor("#ffffff"))
        p.setFont(mk(FONT_DISPLAY, 16, QFont.Bold))
        p.drawText(av, Qt.AlignCenter, nm[:1].upper())
        self.hits.append(("bar", QRectF(0, 0, W, self.BAR)))
        self.hits.append(("signout", br))

    def draw_card(self, p, name, title, fps, ratio, dur, date, hover):
        w, h = 324, 454
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 42, 42)
        p.setClipPath(clip)
        p.fillRect(QRectF(0, 0, w, h), QColor("#050505"))
        art = QRectF(0, 0, w, 319)
        p.save()
        p.setClipRect(art, Qt.IntersectClip)
        draw_art(p, art, title)
        p.restore()
        p.setPen(QColor("#ffffff"))
        p.setFont(mk(FONT_BODY, 32, QFont.DemiBold))
        p.drawText(QRectF(14, 326, w - 28, 44), Qt.AlignRight | Qt.AlignVCenter, name)
        p.setPen(QColor("#7a7a86"))
        p.setFont(mk(FONT_BODY, 18))
        for i, t in enumerate(["fps : %d" % fps, ratio, dur]):
            p.drawText(QRectF(18, 332 + i * 30, 140, 28), Qt.AlignLeft | Qt.AlignVCenter, t)
        p.drawText(QRectF(150, 392, w - 168, 28), Qt.AlignRight | Qt.AlignVCenter, date)
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#a56bff") if hover else QColor(255, 255, 255, 30), 5 if hover else 2))
        p.drawRoundedRect(QRectF(2.5, 2.5, w - 5, h - 5), 40, 40)

    def draw_new(self, p, hover):
        w, h = 324, 454
        p.setBrush(QColor("#15151b" if not hover else "#1c1c26"))
        pen = QPen(QColor("#a56bff") if hover else QColor(255, 255, 255, 70), 4)
        pen.setStyle(Qt.CustomDashLine)
        pen.setDashPattern([4, 3.5])
        p.setPen(pen)
        p.drawRoundedRect(QRectF(3, 3, w - 6, h - 6), 40, 40)
        c = QPointF(w / 2, h / 2 - 16)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#7a2bff" if hover else "#2a2a35"))
        p.drawEllipse(c, 62, 62)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(c.x() - 28, c.y() - 7, 56, 14), 5, 5)
        p.drawRoundedRect(QRectF(c.x() - 7, c.y() - 28, 14, 56), 5, 5)
        p.setPen(QColor("#d6d6e0"))
        p.setFont(mk(FONT_BODY, 26, QFont.DemiBold))
        p.drawText(QRectF(0, c.y() + 84, w, 40), Qt.AlignCenter, "Dự án mới")


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GK KeyFL")
        self.resize(1360, 820)
        self.playing = False
        self.t = 0.0

        # ---- left: library ----
        tabs = QTabWidget()
        for name, items in [("Media", ["clip1.mp4", "clip2.mp4", "photo.jpg", "music.mp3"]),
                            ("Text", ["Title", "Subtitle", "Lower third", "Auto captions"]),
                            ("Shapes", ["Rectangle", "Circle", "Line", "Star"]),
                            ("Effects", ["Blur", "Glitch", "Shake", "Color grade"])]:
            lw = QListWidget()
            lw.setViewMode(QListWidget.IconMode)
            lw.setSpacing(6)
            for i in items:
                it = QListWidgetItem(i)
                it.setSizeHint(QSize(90, 64))
                lw.addItem(it)
            tabs.addTab(lw, name)
        imp = QPushButton("＋ Import")
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(imp)
        lv.addWidget(tabs)

        # ---- center: preview + transport ----
        self.preview = Preview()
        self.timelbl = QLabel("00:00.0 / 00:30.0")
        self.timelbl.setAlignment(Qt.AlignCenter)
        self.play_btn = QPushButton("▶")
        prev, nxt = QPushButton("⏮"), QPushButton("⏭")
        prev.clicked.connect(lambda: self.seek(0))
        nxt.clicked.connect(lambda: self.seek(TOTAL))
        self.play_btn.clicked.connect(self.toggle_play)
        bar = QHBoxLayout()
        bar.addStretch()
        for w in (prev, self.play_btn, nxt):
            bar.addWidget(w)
        bar.addWidget(self.timelbl)
        bar.addStretch()
        center = QWidget()
        cv = QVBoxLayout(center)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.addWidget(self.preview, 1)
        cv.addLayout(bar)

        # ---- right: properties ----
        props = QWidget()
        pv = QVBoxLayout(props)
        g = QGroupBox("Transform")
        gl = QVBoxLayout(g)
        for lab, lo, hi, v, key, suf in [("X", -100, 100, 0, "x", ""), ("Y", -100, 100, 0, "y", ""),
                                         ("Scale", 10, 300, 100, "scale", "%"), ("Rotate", -180, 180, 0, "rot", "°"),
                                         ("Opacity", 0, 100, 100, "opacity", "%")]:
            prop_row(gl, lab, lo, hi, v, lambda x, k=key: self.preview.set_tf(k, x), suf)
        pv.addWidget(g)
        g2 = QGroupBox("Blend & Easing")
        g2l = QVBoxLayout(g2)
        blend = QComboBox()
        blend.addItems(["Normal", "Multiply", "Screen", "Overlay", "Add", "Difference"])
        ease = QComboBox()
        ease.addItems(["Linear", "Ease In", "Ease Out", "Ease In-Out", "Bounce", "Custom curve…"])
        g2l.addWidget(QLabel("Blend mode"))
        g2l.addWidget(blend)
        g2l.addWidget(QLabel("Easing"))
        g2l.addWidget(ease)
        pv.addWidget(g2)
        pv.addStretch()
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setWidget(props)
        sa.setFrameShape(QFrame.NoFrame)

        top = QSplitter(Qt.Horizontal)
        top.addWidget(left)
        top.addWidget(center)
        top.addWidget(sa)
        top.setSizes([280, 760, 320])

        # ---- bottom: timeline ----
        self.tl = Timeline()
        self.tl.seek.connect(self.seek)
        for n, r, s, d in [("clip1.mp4", 2, 0, 6), ("clip2.mp4", 2, 6, 6), ("Title", 0, 1, 3),
                           ("Shape", 1, 2, 4), ("music.mp3", 3, 0, 12)]:
            self.tl.add_clip(n, r, s, d)
        tools = QHBoxLayout()
        for txt, fn in [("✂ Split", self.tl.split), ("🗑 Delete", self.tl.delete)]:
            b = QPushButton(txt)
            b.clicked.connect(fn)
            tools.addWidget(b)
        tools.addStretch()
        tools.addWidget(QLabel("Zoom"))
        z = QSlider(Qt.Horizontal)
        z.setRange(20, 200)
        z.setValue(60)
        z.setFixedWidth(140)
        z.valueChanged.connect(lambda v: (setattr(self.tl, "pps", float(v)), self.tl.refresh()))
        tools.addWidget(z)
        labels = QVBoxLayout()
        labels.setSpacing(0)
        labels.setContentsMargins(0, RULER_H, 0, 0)
        for n in TRACKS:
            l = QLabel(n)
            l.setFixedSize(64, TRACK_H)
            l.setAlignment(Qt.AlignCenter)
            labels.addWidget(l)
        labels.addStretch()
        trow = QHBoxLayout()
        trow.setSpacing(0)
        trow.addLayout(labels)
        trow.addWidget(self.tl, 1)
        bottom = QWidget()
        bv = QVBoxLayout(bottom)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.addLayout(tools)
        bv.addLayout(trow)

        main = QSplitter(Qt.Vertical)
        main.addWidget(top)
        main.addWidget(bottom)
        main.setSizes([520, 280])

        # ---- header ----
        head = QHBoxLayout()
        back = QPushButton("‹ Home")
        back.clicked.connect(self.go_home)
        self.title = QLabel("GK KeyFL")
        self.title.setStyleSheet("font-size:15px;font-weight:bold;")
        exp = QPushButton("Export")
        exp.setObjectName("accent")
        head.addWidget(back)
        head.addWidget(self.title)
        head.addStretch()
        head.addWidget(exp)
        root = QWidget()
        rv = QVBoxLayout(root)
        rv.addLayout(head)
        rv.addWidget(main, 1)
        self.login = LoginPage()
        self.login.entered.connect(self.on_login)
        self.home = HomePage()
        self.home.new_project.connect(self.open_editor)
        self.home.open_recent.connect(lambda n: self.open_editor(n, 16 / 9))
        self.home.sign_out.connect(self.on_sign_out)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.login)   # 0
        self.stack.addWidget(self.home)    # 1
        self.stack.addWidget(root)         # 2
        self.setCentralWidget(self.stack)
        u = load_user()
        if u:
            self.home.set_user(*u)
            self.stack.setCurrentIndex(1)

        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.tick)

    def on_login(self, name, email):
        save_user(name, email)
        self.home.set_user(name, email)
        self.stack.setCurrentIndex(1)

    def on_sign_out(self):
        clear_user()
        self.stack.setCurrentIndex(0)

    def open_editor(self, name, ratio):
        self.preview.ratio = ratio
        self.preview.update()
        self.title.setText(f"GK KeyFL — {name}")
        self.seek(0)
        self.stack.setCurrentIndex(2)

    def go_home(self):
        if self.playing:
            self.toggle_play()
        self.stack.setCurrentIndex(1)

    def seek(self, t):
        self.t = t
        self.tl.set_time(t)
        self.preview.set_time(t)
        self.timelbl.setText(f"{int(t) // 60:02d}:{t % 60:04.1f} / 00:{TOTAL:04.1f}")

    def tick(self):
        t = self.t + 0.033
        if t >= TOTAL:
            t = 0
        self.seek(t)

    def toggle_play(self):
        self.playing = not self.playing
        self.play_btn.setText("⏸" if self.playing else "▶")
        self.timer.start() if self.playing else self.timer.stop()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    app.setWindowIcon(QIcon(LOGO))
    init_fonts()
    w = Main()
    w.show()
    sys.exit(app.exec_())
