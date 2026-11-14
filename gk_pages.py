"""Man hinh Dang nhap + Trang chu (giu nguyen tu ban cu)."""
import os, math, time, random, datetime
from PySide6.QtCore import Qt, QTimer, QUrl, QPoint, QRect, QRectF, QPointF, QSize, QObject, Signal
from PySide6.QtGui import (QDesktopServices, QKeySequence, QShortcut, QColor, QPainter, QPen, QBrush, QFont, QPixmap, QIcon, QLinearGradient,
                         QPainterPath, QPolygonF, QFontDatabase, QFontMetrics, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QWidget, QApplication, QLineEdit, QFileDialog, QMenu,
                             QInputDialog, QMessageBox)
import gk_recent
import gk_dialogs as dlg
from gk_templates import TEMPLATES
import gk_theme as theme
from gk_theme import mk, mixc, star
from gk_model import LOGO
from gk_auth import AuthBridge, DEV, draw_brand_icon, draw_google


class _Theme(dict):
    """Bang mau theme hien tai; tu tinh bg3h / line_hi neu gk_theme khong co san."""
    def __missing__(self, k):
        if k == "bg3h":
            return mixc(self["bg3"], self["text"], 0.10).name()
        if k == "line_hi":
            return mixc(self["line"], self["text"], 0.25).name()
        raise KeyError(k)


def cur_theme():
    base = getattr(theme, "T", None)
    if not base:
        base = theme.THEMES.get(theme.current_key(), {})
    return _Theme(base)



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
    entered = Signal(str, str)

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
        self.f_head = mk(theme.FONT_DISPLAY, 30, QFont.Black)
        self.f_sub = mk(theme.FONT_BODY, 14)
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
        p.setFont(mk(theme.FONT_DISPLAY, 18, QFont.Bold))
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
            p.setFont(mk(theme.FONT_BODY, 15, QFont.DemiBold))
            p.drawText(QRectF(area.left() + 64, area.top() + 18, inner - 80, 22), Qt.AlignLeft | Qt.AlignVCenter,
                       "Đang chờ đăng nhập…")
            p.setPen(QColor("#8d8d9a"))
            p.setFont(mk(theme.FONT_BODY, 13))
            p.drawText(QRectF(area.left() + 64, area.top() + 42, inner - 80, 20), Qt.AlignLeft | Qt.AlignVCenter,
                       "Hoàn tất ở tab trình duyệt vừa mở.")
            for name, txt, rx in (("reopen", "Mở lại trình duyệt", area.left() + 24), ("cancel", "Huỷ", area.right() - 70)):
                r = QRectF(rx, area.bottom() - 40, 150 if name == "reopen" else 46, 26)
                p.setPen(QColor("#c9a8ff" if self.hot == name else "#a56bff"))
                p.setFont(mk(theme.FONT_BODY, 13, QFont.DemiBold))
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
                p.setFont(mk(theme.FONT_BODY, 16, QFont.DemiBold))
                p.drawText(r.adjusted(34, 0, 0, 0), Qt.AlignCenter, label)
                self.hits.append((name, r))
        p.setFont(mk(theme.FONT_BODY, 12))
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
    p.setFont(mk(theme.FONT_COND, 24, QFont.Normal))
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


def ca(h, a):
    c = QColor(h)
    c.setAlpha(a)
    return c


class HomePage(QWidget):
    new_project = Signal(str, float)
    new_template = Signal(str, float)
    open_recent = Signal(str)       # (khong con dung, giu cho tuong thich)
    open_file = Signal(str)
    sign_out = Signal()
    settings_requested = Signal()
    account_changed = Signal(str, str)
    RATIOS = [("16:9", "YouTube", 16 / 9), ("9:16", "TikTok", 9 / 16), ("1:1", "Vuông", 1.0), ("4:5", "Instagram", 4 / 5)]
    SORTS = ["Mới nhất", "Tên A–Z"]
    BAR, TW, TH = 72, 196, 150

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.logo = QPixmap(LOGO)
        self.user = ("Khách", "")
        self.ratio_i = 0
        self.sort_i = 0
        self.scroll = 0
        self.content_h = 0
        self.hits, self.hot = [], None
        self.recent, self._shown, self._tc = [], [], {}
        self.toast = ("", 0.0)
        self.update_info = None
        self._checked = False
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Tìm dự án…  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedSize(230, 32)
        self.search.hide()
        self.search.textChanged.connect(lambda _: self.update())
        theme.bus.changed.connect(self.update)
        for key, fn in (("Ctrl+N", self.new_default), ("Ctrl+O", self.pick_file),
                        ("Ctrl+F", lambda: self.search.setFocus())):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)

    # ---- du lieu
    def showEvent(self, e):
        self.refresh()
        if not self._checked:                      # kiem tra cap nhat im lang 1 lan moi lan chay
            self._checked = True
            QTimer.singleShot(1500, lambda: dlg.check_updates(self, True, self._on_update))

    def _on_update(self, r):
        if r.get("ok") and r.get("newer"):
            self.update_info = r
            self.notify("Có bản cập nhật mới %s — mở menu ⚙ để tải" % r["latest"])
        self.update()

    def refresh(self):
        self.recent = gk_recent.items()
        self.update()

    def set_user(self, name, email):
        self.user = (name or "Khách", email)
        self.update()

    def shown(self):
        q = self.search.text().strip().lower()
        xs = [d for d in self.recent if q in d["name"].lower()]
        if self.sort_i == 1:
            xs.sort(key=lambda d: d["name"].lower())
        return xs

    def notify(self, text):
        self.toast = (text, time.monotonic() + 3.0)
        QTimer.singleShot(3100, self.update)
        self.update()

    def new_default(self):
        self.new_project.emit("Untitled", self.RATIOS[self.ratio_i][2])

    def pick_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Mở dự án", "", "GK KeyFL (*.gkproj)")
        if f:
            self.open_file.emit(f)

    def _thumb(self, path):
        tp = gk_recent.thumb_path(path)
        try:
            m = os.path.getmtime(tp)
        except OSError:
            return None
        c = self._tc.get(path)
        if not c or c[0] != m:
            pm = QPixmap(tp)
            c = self._tc[path] = (m, None if pm.isNull() else pm)
        return c[1]

    # ---- hanh dong tren du an
    def rename_project(self, d):
        old = d["path"]
        name, ok = QInputDialog.getText(self, "Đổi tên dự án", "Tên mới:", text=d["name"])
        name = name.strip()
        if not ok or not name or name == d["name"]:
            return
        if any(c in name for c in '/\\:*?"<>|\0') or name in (".", ".."):
            self.notify("Tên không hợp lệ")
            return
        new = os.path.join(os.path.dirname(old), name + ".gkproj")
        if os.path.exists(new):
            self.notify("Đã có tệp trùng tên")
            return
        try:
            os.rename(old, new)
        except OSError as ex:
            self.notify("Không đổi tên được: %s" % ex.strerror)
            return
        gk_recent.rename(old, new)
        self.refresh()
        self.notify("Đã đổi tên thành “%s”" % name)

    def delete_project(self, d):
        r = QMessageBox.warning(self, "Xoá dự án", "Xoá hẳn tệp “%s” khỏi ổ đĩa?\nKhông thể hoàn tác." % d["name"],
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                QMessageBox.StandardButton.Cancel)
        if r != QMessageBox.StandardButton.Yes:
            return
        try:
            os.remove(d["path"])
        except OSError as ex:
            self.notify("Không xoá được: %s" % ex.strerror)
            return
        gk_recent.remove(d["path"], True)
        self.refresh()
        self.notify("Đã xoá “%s”" % d["name"])

    def unlist_project(self, d):
        gk_recent.remove(d["path"])
        self.refresh()
        self.notify("Đã gỡ khỏi danh sách (tệp vẫn còn trên đĩa)")

    def show_folder(self, d):
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(d["path"])))

    def card_menu(self, d, gpos):
        m = QMenu(self)
        m.addAction("Mở").triggered.connect(lambda: self.open_file.emit(d["path"]))
        m.addAction("Đổi tên…").triggered.connect(lambda: self.rename_project(d))
        m.addAction("Hiện trong thư mục").triggered.connect(lambda: self.show_folder(d))
        m.addSeparator()
        m.addAction("Gỡ khỏi danh sách").triggered.connect(lambda: self.unlist_project(d))
        m.addAction("Xoá tệp…").triggered.connect(lambda: self.delete_project(d))
        m.exec(gpos)

    def gear_menu(self, gpos):
        m = QMenu(self)
        m.addAction("⚙  Cài đặt…").triggered.connect(self.settings_requested.emit)
        m.addAction("👤  Tài khoản…").triggered.connect(self.open_account)
        m.addSeparator()
        up = self.update_info
        a = m.addAction("⟳  Có bản mới %s — tải về…" % up["latest"] if up else "⟳  Kiểm tra cập nhật…")
        a.triggered.connect(lambda: dlg.check_updates(self, False, self._on_update))
        m.addAction("🩺  Kiểm tra hệ thống…").triggered.connect(lambda: dlg.run_diag(self))
        m.addAction("ⓘ  Thông tin GK KeyFL").triggered.connect(lambda: dlg.show_about(self))
        m.addSeparator()
        m.addAction("Đăng xuất").triggered.connect(self.sign_out.emit)
        m.exec(gpos)

    def open_account(self):
        dlg.open_account(self, self.user[0], self.user[1], self.account_changed.emit, self.sign_out.emit)

    # ---- chuot
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

    def contextMenuEvent(self, e):
        h = self.hit(e.pos())
        if h and h.startswith("card") and int(h[4:]) < len(self._shown):
            self.card_menu(self._shown[int(h[4:])], e.globalPos())

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        h = self.hit(e.pos())
        if not h:
            self.search.clearFocus()
            return
        if h in ("hero", "newcard"):
            self.new_default()
        elif h == "open":
            self.pick_file()
        elif h == "signout":
            self.sign_out.emit()
        elif h == "account":
            self.open_account()
        elif h == "gear":
            r = [r for n, r in self.hits if n == "gear"][0]
            self.gear_menu(self.mapToGlobal(QPoint(int(r.left()), int(r.bottom()) + 6)))
        elif h == "sort":
            self.sort_i = (self.sort_i + 1) % len(self.SORTS)
            self.update()
        elif h.startswith("ratio"):
            self.ratio_i = int(h[5:])
            self.update()
        elif h.startswith("tpl"):
            self.new_template.emit(TEMPLATES[int(h[3:])][0], self.RATIOS[self.ratio_i][2])
        elif h.startswith("card"):
            i = int(h[4:])
            if i < len(self._shown):
                self.open_file.emit(self._shown[i]["path"])
        elif h.startswith("del"):
            i = int(h[3:])
            if i < len(self._shown):
                self.unlist_project(self._shown[i])

    # ---- ve
    def greeting(self):
        h = datetime.datetime.now().hour
        part = "buổi sáng" if h < 11 else "buổi trưa" if h < 14 else "buổi chiều" if h < 18 else "buổi tối"
        return "Chào %s, %s" % (part, self.user[0])

    def draw_tpl(self, p, r, key, hov):
        """Hinh xem truoc nho cua mau du an."""
        T = cur_theme()
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(r, 16, 16)
        p.setClipPath(clip)
        p.fillRect(r, QColor(T["bg2"]))
        c, ac = r.center(), QColor(T["accent_hi"])
        p.setPen(Qt.NoPen)
        if key == "blank":
            pen = QPen(ca(T["text"], 110), 2)
            pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(40, 26, -40, -26), 8, 8)
            p.setPen(Qt.NoPen)
            p.setBrush(ac)
            p.drawRoundedRect(QRectF(c.x() - 12, c.y() - 2, 24, 4), 2, 2)
            p.drawRoundedRect(QRectF(c.x() - 2, c.y() - 12, 4, 24), 2, 2)
        elif key == "title":
            p.setBrush(QColor(T["text"]))
            p.drawRoundedRect(QRectF(c.x() - 52, c.y() - 20, 104, 18), 5, 5)
            p.setBrush(ac)
            p.drawRoundedRect(QRectF(c.x() - 40, c.y() + 10, 80, 6), 3, 3)
        elif key == "lower":
            p.setBrush(ac)
            p.drawRoundedRect(QRectF(r.left() + 16, r.bottom() - 46, 100, 22), 5, 5)
            p.setBrush(ca(T["text"], 200))
            p.drawRoundedRect(QRectF(r.left() + 26, r.bottom() - 40, 56, 5), 2, 2)
            p.drawRoundedRect(QRectF(r.left() + 26, r.bottom() - 32, 36, 4), 2, 2)
        elif key == "logo":
            p.save()
            p.translate(c)
            p.rotate(35)
            p.setBrush(ac)
            p.drawRoundedRect(QRectF(-24, -24, 48, 48), 10, 10)
            p.restore()
            p.setBrush(ca(T["text"], 200))
            p.drawRoundedRect(QRectF(c.x() - 30, c.y() + 34, 60, 5), 2, 2)
        elif key == "slides":
            for i, col in enumerate(("#7a2bff", "#e0457b", "#2f8fe0")):
                p.setBrush(QColor(col))
                p.drawRoundedRect(QRectF(r.left() + 22 + i * 40, c.y() - 22 + i * 4, 56, 44), 7, 7)
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(T["accent_hi"]) if hov else QColor(T["line"]), 2 if hov else 1))
        p.drawRoundedRect(r, 16, 16)

    def paintEvent(self, _):
        T = cur_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        W, H = self.width(), self.height()
        p.fillRect(self.rect(), QColor(T["bg0"]))
        g = QRadialGradient(W * 0.75, 0, max(W, H) * 0.7)
        g.setColorAt(0, ca(T["accent"], 46))
        g.setColorAt(1, ca(T["accent"], 0))
        p.fillRect(self.rect(), QBrush(g))
        self.hits = []
        M = max(28, min(56, W * 0.04))
        sc = self.scroll = max(0, min(self.scroll, max(0, self.content_h - H)))
        shown = self._shown = self.shown()

        p.save()
        p.setClipRect(QRectF(0, self.BAR, W, H - self.BAR))
        # --- loi chao
        gy = self.BAR + 22 - sc
        p.setPen(QColor(T["text"]))
        p.setFont(mk(theme.FONT_DISPLAY, 24, QFont.Bold))
        p.drawText(QRectF(M, gy, W - 2 * M, 36), Qt.AlignLeft | Qt.AlignVCenter, self.greeting())
        p.setPen(QColor(T["text2"]))
        p.setFont(mk(theme.FONT_BODY, 14))
        n = len(self.recent)
        p.drawText(QRectF(M, gy + 36, W - 2 * M, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   "Bạn có %d dự án gần đây." % n if n else "Chưa có dự án nào — hãy tạo dự án đầu tiên của bạn.")

        # --- hero "Tao du an moi"
        hero = QRectF(M, gy + 76, W - 2 * M, 150)
        g = QLinearGradient(hero.left(), hero.top(), hero.right(), hero.bottom())
        g.setColorAt(0, QColor("#ff5e5b"))
        g.setColorAt(0.55, mixc("#ff5e5b", T["accent"], 0.7))
        g.setColorAt(1, QColor(T["accent_hi"]))
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
        p.setFont(mk(theme.FONT_DISPLAY, 34, QFont.Black))
        p.drawText(QRectF(hero.left() + 40, hero.top() + 28, hero.width() - 200, 48), Qt.AlignLeft | Qt.AlignVCenter, "Tạo dự án mới")
        c = QPointF(hero.right() - 80, hero.center().y())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(c, 34, 34)
        p.setBrush(QColor("#111111"))
        p.drawRoundedRect(QRectF(c.x() - 15, c.y() - 4, 30, 8), 3, 3)
        p.drawRoundedRect(QRectF(c.x() - 4, c.y() - 15, 8, 30), 3, 3)
        self.hits.append(("hero", hero))

        fm = QFontMetrics(mk(theme.FONT_BODY, 14, QFont.DemiBold))
        ow = fm.horizontalAdvance("Mở dự án…") + 36
        if hero.width() > ow + 560:
            orr = QRectF(c.x() - 34 - 22 - ow, c.y() - 19, ow, 38)
            p.setPen(QPen(QColor(255, 255, 255, 120), 1))
            p.setBrush(QColor(255, 255, 255, 60 if self.hot == "open" else 28))
            p.drawRoundedRect(orr, 19, 19)
            p.setPen(QColor("#ffffff"))
            p.setFont(mk(theme.FONT_BODY, 14, QFont.DemiBold))
            p.drawText(orr, Qt.AlignCenter, "Mở dự án…")
            self.hits.append(("open", orr))

        fm = QFontMetrics(mk(theme.FONT_BODY, 13, QFont.DemiBold))
        x = hero.left() + 40
        for i, (lab, sub, _r) in enumerate(self.RATIOS):
            txt = "%s  %s" % (lab, sub)
            cw = fm.horizontalAdvance(txt) + 28
            r = QRectF(x, hero.top() + 96, cw, 30)
            sel = i == self.ratio_i
            p.setPen(Qt.NoPen if sel else QPen(QColor(255, 255, 255, 90), 1))
            p.setBrush(QColor("#ffffff") if sel else QColor(255, 255, 255, 60 if self.hot == "ratio%d" % i else 24))
            p.drawRoundedRect(r, 15, 15)
            p.setPen(QColor("#1b1b22" if sel else "#ffffff"))
            p.setFont(mk(theme.FONT_BODY, 13, QFont.DemiBold))
            p.drawText(r, Qt.AlignCenter, txt)
            self.hits.append(("ratio%d" % i, r))
            x += cw + 8

        # --- mau du an
        ty = hero.bottom() + 32
        p.setPen(QColor(T["text"]))
        p.setFont(mk(theme.FONT_DISPLAY, 20, QFont.Bold))
        p.drawText(QRectF(M, ty, 300, 34), Qt.AlignLeft | Qt.AlignVCenter, "Bắt đầu từ mẫu")
        tg = 16
        tcols = max(1, int((W - 2 * M + tg) // (self.TW + tg)))
        tt = ty + 46
        for i, (key, nm, desc) in enumerate(TEMPLATES):
            tx = M + (i % tcols) * (self.TW + tg)
            tyy = tt + (i // tcols) * (self.TH + 18 + tg)
            hov = self.hot == "tpl%d" % i
            self.draw_tpl(p, QRectF(tx, tyy - (3 if hov else 0), self.TW, 112), key, hov)
            p.setPen(QColor(T["text"]))
            p.setFont(mk(theme.FONT_BODY, 14, QFont.DemiBold))
            p.drawText(QRectF(tx + 4, tyy + 118, self.TW - 8, 20), Qt.AlignLeft | Qt.AlignVCenter, nm)
            p.setPen(QColor(T["text3"]))
            p.setFont(mk(theme.FONT_BODY, 12))
            p.drawText(QRectF(tx + 4, tyy + 138, self.TW - 8, 18), Qt.AlignLeft | Qt.AlignVCenter, desc)
            self.hits.append(("tpl%d" % i, QRectF(tx, tyy, self.TW, self.TH + 8)))
        trows = (len(TEMPLATES) + tcols - 1) // tcols

        # --- tieu de + tim kiem + sap xep
        ry = tt + trows * (self.TH + 18 + tg) + 8
        p.setPen(QColor(T["text"]))
        p.setFont(mk(theme.FONT_DISPLAY, 20, QFont.Bold))
        p.drawText(QRectF(M, ry, 300, 34), Qt.AlignLeft | Qt.AlignVCenter, "Dự án gần đây")
        fm = QFontMetrics(mk(theme.FONT_BODY, 13, QFont.DemiBold))
        lab = "⇅  " + self.SORTS[self.sort_i]
        sw = fm.horizontalAdvance(lab) + 28
        sr = QRectF(W - M - sw, ry + 2, sw, 30)
        p.setPen(QPen(QColor(T["line_hi"]), 1))
        p.setBrush(QColor(T["bg3h"] if self.hot == "sort" else T["bg2"]))
        p.drawRoundedRect(sr, 15, 15)
        p.setPen(QColor(T["text2"]))
        p.setFont(mk(theme.FONT_BODY, 13, QFont.DemiBold))
        p.drawText(sr, Qt.AlignCenter, lab)
        self.hits.append(("sort", sr))
        sx, sy = sr.left() - 12 - self.search.width(), ry + 1
        if sx > M + 200 and sy > self.BAR and sy < H and (self.recent or self.search.text()):
            self.search.move(int(sx), int(sy))
            self.search.show()
        else:
            self.search.hide()

        # --- luoi project
        gap = 24
        cols = max(1, int((W - 2 * M + gap) // (CARD_W + gap)))
        top = ry + 52
        items = list(range(len(shown))) + [-1]
        for k, it in enumerate(items):
            col, row = k % cols, k // cols
            x0 = M + col * (CARD_W + gap)
            y0 = top + row * (CARD_H + gap)
            name = "newcard" if it < 0 else "card%d" % it
            hov = self.hot in (name, "del%d" % it)
            p.save()
            p.translate(x0, y0 - (5 if hov else 0))
            p.scale(CARD_K, CARD_K)
            if it < 0:
                self.draw_new(p, hov)
            else:
                d = shown[it]
                try:
                    date = time.strftime("%d/%m/%Y", time.localtime(os.path.getmtime(d["path"])))
                except OSError:
                    date = ""
                rl = min(self.RATIOS, key=lambda q: abs(q[2] - d.get("ratio", 16 / 9)))[0]
                self.draw_card(p, d["name"], d["name"].upper(), 30, rl, gk_recent.fmt_dur(d.get("dur", 0)), date, hov,
                               self._thumb(d["path"]))
            p.restore()
            self.hits.append((name, QRectF(x0, y0, CARD_W, CARD_H)))
            if it >= 0 and hov:
                dr = QRectF(x0 + CARD_W - 36, y0 + 5, 26, 26)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("#e5484d") if self.hot == "del%d" % it else QColor(0, 0, 0, 170))
                p.drawEllipse(dr)
                p.setPen(QColor("#ffffff"))
                p.setFont(mk(theme.FONT_BODY, 13, QFont.Bold))
                p.drawText(dr, Qt.AlignCenter, "✕")
                self.hits.append(("del%d" % it, dr))
        if not shown and self.search.text() and cols > 1:
            p.setPen(QColor(T["text2"]))
            p.setFont(mk(theme.FONT_BODY, 15))
            p.drawText(QRectF(M + CARD_W + gap + 10, top, 360, CARD_H), Qt.AlignLeft | Qt.AlignVCenter,
                       "Không có dự án nào khớp “%s”." % self.search.text().strip())
        rows = (len(items) + cols - 1) // cols
        self.content_h = top + sc + rows * (CARD_H + gap) + 20
        p.restore()

        # --- thanh tren cung
        p.setPen(Qt.NoPen)
        p.setBrush(ca(T["bg0"], 238))
        p.drawRect(QRectF(0, 0, W, self.BAR))
        p.setPen(QPen(QColor(T["line"]), 1))
        p.drawLine(0, self.BAR, W, self.BAR)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(M, 18, 36, 36), 10, 10)
        p.drawPixmap(QRectF(M + 4, 22, 28, 28), self.logo, QRectF(self.logo.rect()))
        p.setPen(QColor(T["text"]))
        p.setFont(mk(theme.FONT_DISPLAY, 18, QFont.Bold))
        p.drawText(QRectF(M + 48, 18, 200, 36), Qt.AlignVCenter | Qt.AlignLeft, "GK KeyFL")
        fm = QFontMetrics(mk(theme.FONT_BODY, 13, QFont.DemiBold))
        bw = fm.horizontalAdvance("Đăng xuất") + 28
        br = QRectF(W - M - bw, 20, bw, 32)
        p.setPen(QPen(QColor(T["line_hi"]), 1))
        p.setBrush(QColor(T["bg3h"] if self.hot == "signout" else T["bg2"]))
        p.drawRoundedRect(br, 16, 16)
        p.setPen(QColor(T["text"]))
        p.setFont(mk(theme.FONT_BODY, 13, QFont.DemiBold))
        p.drawText(br, Qt.AlignCenter, "Đăng xuất")
        nm = self.user[0]
        nw = QFontMetrics(mk(theme.FONT_BODY, 14, QFont.DemiBold)).horizontalAdvance(nm)
        nx = br.left() - 16 - nw
        p.setFont(mk(theme.FONT_BODY, 14, QFont.DemiBold))
        p.drawText(QRectF(nx, 18, nw + 4, 36), Qt.AlignVCenter | Qt.AlignLeft, nm)
        av = QRectF(nx - 46, 18, 36, 36)
        ag = QLinearGradient(av.topLeft(), av.bottomRight())
        ag.setColorAt(0, QColor("#ff5e5b"))
        ag.setColorAt(1, QColor(T["accent"]))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(ag))
        p.drawEllipse(av)
        p.setPen(QColor("#ffffff"))
        p.setFont(mk(theme.FONT_DISPLAY, 16, QFont.Bold))
        p.drawText(av, Qt.AlignCenter, nm[:1].upper())
        # banh rang (cai dat / tai khoan / cap nhat / he thong)
        gr = QRectF(av.left() - 14 - 36, 18, 36, 36)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T["bg3h"] if self.hot == "gear" else T["bg2"]))
        p.drawEllipse(gr)
        p.setPen(QColor(T["text"]))
        p.setFont(mk(theme.FONT_BODY, 18))
        p.drawText(gr, Qt.AlignCenter, "⚙")
        if self.update_info:
            p.setPen(QPen(QColor(T["bg0"]), 2))
            p.setBrush(QColor("#e5484d"))
            p.drawEllipse(QPointF(gr.right() - 6, gr.top() + 7), 5, 5)
        self.hits.append(("bar", QRectF(0, 0, W, self.BAR)))
        self.hits.append(("signout", br))
        self.hits.append(("account", QRectF(av.left(), 18, br.left() - av.left() - 8, 36)))
        self.hits.append(("gear", gr))

        # --- thong bao nho
        if time.monotonic() < self.toast[1]:
            fm = QFontMetrics(mk(theme.FONT_BODY, 14, QFont.DemiBold))
            tw = fm.horizontalAdvance(self.toast[0]) + 40
            tr = QRectF((W - tw) / 2, H - 70, tw, 40)
            p.setPen(QPen(QColor(T["line_hi"]), 1))
            p.setBrush(ca(T["bg2"], 245))
            p.drawRoundedRect(tr, 20, 20)
            p.setPen(QColor(T["text"]))
            p.setFont(mk(theme.FONT_BODY, 14, QFont.DemiBold))
            p.drawText(tr, Qt.AlignCenter, self.toast[0])

    def draw_card(self, p, name, title, fps, ratio, dur, date, hover, thumb=None):
        w, h = 324, 454
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 42, 42)
        p.setClipPath(clip)
        p.fillRect(QRectF(0, 0, w, h), QColor("#050505"))
        art = QRectF(0, 0, w, 319)
        p.save()
        p.setClipRect(art, Qt.IntersectClip)
        if thumb is not None:
            p.fillRect(art, QColor("#0a0a0e"))
            sw = art.width()
            sh = sw * thumb.height() / max(1, thumb.width())
            if sh > art.height():
                sh = art.height()
                sw = sh * thumb.width() / max(1, thumb.height())
            p.drawPixmap(QRectF(art.center().x() - sw / 2, art.center().y() - sh / 2, sw, sh), thumb, QRectF(thumb.rect()))
        else:
            draw_art(p, art, title)
        p.restore()
        p.setPen(QColor("#ffffff"))
        p.setFont(mk(theme.FONT_BODY, 32, QFont.DemiBold))
        p.drawText(QRectF(14, 326, w - 28, 44), Qt.AlignRight | Qt.AlignVCenter, name)
        p.setPen(QColor("#7a7a86"))
        p.setFont(mk(theme.FONT_BODY, 18))
        for i, t in enumerate(["fps : %d" % fps, ratio, dur]):
            p.drawText(QRectF(18, 332 + i * 30, 140, 28), Qt.AlignLeft | Qt.AlignVCenter, t)
        p.drawText(QRectF(150, 392, w - 168, 28), Qt.AlignRight | Qt.AlignVCenter, date)
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(cur_theme()["accent_hi"]) if hover else QColor(cur_theme()["line_hi"]), 5 if hover else 2))
        p.drawRoundedRect(QRectF(2.5, 2.5, w - 5, h - 5), 40, 40)

    def draw_new(self, p, hover):
        T = cur_theme()
        w, h = 324, 454
        p.setBrush(QColor(T["bg2"] if hover else T["bg1"]))
        pen = QPen(QColor(T["accent_hi"]) if hover else QColor(T["line_hi"]), 4)
        pen.setStyle(Qt.CustomDashLine)
        pen.setDashPattern([4, 3.5])
        p.setPen(pen)
        p.drawRoundedRect(QRectF(3, 3, w - 6, h - 6), 40, 40)
        c = QPointF(w / 2, h / 2 - 16)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T["accent"] if hover else T["bg3"]))
        p.drawEllipse(c, 62, 62)
        p.setBrush(QColor(T["on_accent"] if hover else T["text"]))
        p.drawRoundedRect(QRectF(c.x() - 28, c.y() - 7, 56, 14), 5, 5)
        p.drawRoundedRect(QRectF(c.x() - 7, c.y() - 28, 14, 56), 5, 5)
        p.setPen(QColor(T["text"]))
        p.setFont(mk(theme.FONT_BODY, 26, QFont.DemiBold))
        p.drawText(QRectF(0, c.y() + 84, w, 40), Qt.AlignCenter, "Dự án mới")
