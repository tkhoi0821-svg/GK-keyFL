"""GK KeyFL - Che do 3D: bam nut 3D ben duoi thanh cong cu, canvas chuyen thang sang khong gian 3D.

Moi lop phang -> mot khoi hop (Cube neu lop vuong), mat truoc la anh lop do (chu, hinh, anh, video...).
Vi tri / xoay / ti le / do mo da key frame van chay: xoay X-Y-Z thanh xoay 3D that, Pos Z thanh do sau that.

Dieu khien (sua o KEYMAP):  A trai | D phai | W len | S xuong | Q bay toi | E lui | F zoom (Shift+F thu nho)
Chuot: keo = xoay camera, lan = tien/lui, bam = chon lop.  Giu Shift = di nhanh.  Esc / nut 3D = thoat.
"""
import math
import time
import numpy as np
from PySide6.QtCore import Qt, QObject, QTimer, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QImage, QPolygonF, QTransform, QPen, QPixmap, QIcon, QFont, QBrush, QLinearGradient
from PySide6.QtWidgets import QPushButton, QApplication
import gk_theme as theme
import gk_material
from gk_theme import T

KEYMAP = {Qt.Key_A: "left", Qt.Key_D: "right", Qt.Key_W: "up", Qt.Key_S: "down",
          Qt.Key_Q: "fwd", Qt.Key_E: "back", Qt.Key_F: "zoom"}
SHORTCUT_LETTERS = {"Q", "W", "E", "R", "Y", "T", "A", "S", "D", "F"}     # phim tat cua editor bi tam tat khi o 3D
CW = 1000.0                 # chieu rong canvas trong the gioi 3D
NEAR = 20.0
LIGHT = np.array([-0.4, 0.7, 0.6]) / np.linalg.norm([-0.4, 0.7, 0.6])


def cube_icon(col, size=28):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(col), 2.0)
    pen.setJoinStyle(Qt.RoundJoin)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    c = size / 2
    a = size * 0.36
    top = [QPointF(c, c - a), QPointF(c + a, c - a / 2), QPointF(c, c), QPointF(c - a, c - a / 2)]
    p.drawPolygon(QPolygonF(top))
    p.drawLine(QPointF(c - a, c - a / 2), QPointF(c - a, c + a / 2))
    p.drawLine(QPointF(c - a, c + a / 2), QPointF(c, c + a))
    p.drawLine(QPointF(c, c + a), QPointF(c + a, c + a / 2))
    p.drawLine(QPointF(c + a, c + a / 2), QPointF(c + a, c - a / 2))
    p.drawLine(QPointF(c, c), QPointF(c, c + a))
    p.end()
    return pm


def quad_transform(w, h, dst):
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    A, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    try:
        h8 = np.linalg.solve(np.array(A, float), np.array(b, float))
    except np.linalg.LinAlgError:
        return None
    H = np.append(h8, 1.0).reshape(3, 3)
    return QTransform(H[0, 0], H[1, 0], H[2, 0], H[0, 1], H[1, 1], H[2, 1], H[0, 2], H[1, 2], H[2, 2])


def rot_matrix(ax, ay, az):
    ax, ay, az = math.radians(ax), math.radians(ay), math.radians(az)
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rx @ Ry @ Rz


AXC = ["#e8493f", "#7bd34a", "#3d8bfd"]          # X do, Y xanh la, Z xanh duong (mau Blender)
GMODES = [("select", "Chọn", "1"), ("move", "Dời", "2"), ("rotate", "Xoay", "3"), ("scale", "Tỉ lệ", "4")]
ORIENTS = [("global", "Global"), ("local", "Local"), ("view", "View"), ("normal", "Normal")]
HALF = math.pi / 2


def rodrigues(a, th):
    a = np.asarray(a, float)
    n = float(np.linalg.norm(a))
    if n < 1e-9:
        return np.eye(3)
    a = a / n
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * (K @ K)


def euler_from(R):
    """Nguoc cua rot_matrix: tra ve (ax, ay, az) do sao cho rot_matrix(ax, ay, az) = R."""
    sy = max(-1.0, min(1.0, float(R[0, 2])))
    ay = math.asin(sy)
    if abs(sy) < 0.999999:
        ax, az = math.atan2(-R[1, 2], R[2, 2]), math.atan2(-R[0, 1], R[0, 0])
    else:
        ax, az = math.atan2(R[2, 1], R[1, 1]), 0.0
    return math.degrees(ax), math.degrees(ay), math.degrees(az)


def _sdist(p, a, b):
    ab = (b.x() - a.x(), b.y() - a.y())
    l2 = ab[0] ** 2 + ab[1] ** 2
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p.x() - a.x()) * ab[0] + (p.y() - a.y()) * ab[1]) / l2))
    return math.hypot(p.x() - (a.x() + ab[0] * t), p.y() - (a.y() + ab[1] * t))


class Scene3D(QObject):
    def __init__(self, editor):
        super().__init__(editor)
        self.ed = editor
        self.on = False
        self.keys = set()
        self.cam = np.array([0.0, 0.0, 1800.0])
        self.yaw, self.pitch, self.zoom = 0.0, 0.0, 1.0
        self._inited = False
        self._tex = {}
        self._cam_only = False
        self._cam_only_now = False
        self.faces_hit = []
        self.drag = None
        self.gmode, self.orient = "move", "global"      # gizmo: Chon / Doi / Xoay / Ti le; truc: Global / Local / View / Normal
        self._pose, self._gz, self.ghot, self.gd = {}, None, None, None
        self._hud, self._nav = [], []
        self._last = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._muted = []
        self._build_button()
        self._patch_stage()

    # ------------------------------------------------------------ nut 3D
    def _build_button(self):
        rail = self.ed.panel.rail
        self.btn = QPushButton()
        self.btn.setObjectName("Tool")
        self.btn.setCheckable(True)
        self.btn.setToolTip("Chế độ 3D  (F4)\nA/D trái-phải · W/S lên-xuống · Q/E tiến-lùi · F zoom")
        from PySide6.QtCore import QSize
        self.btn.setIconSize(QSize(28, 28))
        rail.layout().addWidget(self.btn)
        self.btn.toggled.connect(self.toggle)
        self._icons()
        theme.bus.changed.connect(self._icons)

    def _icons(self):
        ic = QIcon()
        ic.addPixmap(cube_icon(T["text"]), QIcon.Normal, QIcon.Off)
        ic.addPixmap(cube_icon(T["on_accent"]), QIcon.Normal, QIcon.On)
        self.btn.setIcon(ic)

    # ------------------------------------------------------------ bat / tat
    def toggle(self, on=None):
        want = (not self.on) if on is None else bool(on)
        if want == self.on:
            return
        self.on = want
        self.btn.blockSignals(True)
        self.btn.setChecked(want)
        self.btn.blockSignals(False)
        st = self.ed.stage
        self.keys.clear()
        if want:
            if not self._inited:
                self.reset_camera()
            st.setFocusPolicy(Qt.StrongFocus)
            st.setFocus()
            self._mute_shortcuts(True)
            self._last = time.monotonic()
            self._timer.start()
            self.ed.log("Chế độ 3D: A/D trái-phải · W/S lên-xuống · Q bay tới · E lùi · F zoom (Shift+F thu nhỏ) · kéo chuột xoay · Esc thoát")
        else:
            self._timer.stop()
            self._mute_shortcuts(False)
        self._cam_only = False
        self.gd = None
        st.update()

    def _mute_shortcuts(self, mute):
        if mute:
            self._muted = [sc for sc in getattr(self.ed, "_shortcuts", [])
                           if sc.key().toString() in SHORTCUT_LETTERS and sc.isEnabled()]
            for sc in self._muted:
                sc.setEnabled(False)
        else:
            for sc in self._muted:
                sc.setEnabled(True)
            self._muted = []

    def reset_camera(self):
        st = self.ed.stage
        self.yaw, self.pitch, self.zoom = 0.0, 0.0, 1.0
        f = self._focal(st)
        s = max(0.05, st.base_w() * st.zoom / CW)
        depth, rect = 0.0, QRectF(0, 0, CW, CW / st.ratio)
        for L in st.layers:
            if L.kind in ("bg", "audio", "camera", "light") or not L.alive(st.t):
                continue
            b = st.body(L, rect)
            depth += max(20.0, min(b.width() * L.get("scl0", st.t) / 100, b.height() * L.get("scl1", st.t) / 100)) + 40
        self.cam = np.array([0.0, 0.0, f / s + depth])      # lui ra du xa de thay ca chong khoi
        self._inited = True

    # ------------------------------------------------------------ camera
    def _focal(self, st):
        return 0.5 * st.height() / math.tan(math.radians(25)) * self.zoom

    def _basis(self):
        cy, sy, cp, sp = math.cos(self.yaw), math.sin(self.yaw), math.cos(self.pitch), math.sin(self.pitch)
        fwd = np.array([sy * cp, sp, -cy * cp])
        right = np.array([cy, 0.0, sy])
        up = np.cross(right, fwd)
        return right, up, fwd

    def _mid_z(self):
        """Do sau giua chong khoi (de xoay quanh)."""
        st, z = self.ed.stage, 0.0
        rect = QRectF(0, 0, CW, CW / st.ratio)
        for L in st.layers:
            if L.kind in ("bg", "audio", "camera", "light") or not L.alive(st.t):
                continue
            b = st.body(L, rect)
            z += max(20.0, min(b.width() * L.get("scl0", st.t) / 100, b.height() * L.get("scl1", st.t) / 100)) + 40
        return z / 2

    # ------------------------------------------------------------ anh sang 3D (nguon sang that)
    def _lights(self, st):
        out, CH, mid, t = [], CW / st.ratio, self._mid_z(), st.t
        for L in st.layers:
            if L.kind != "light" or L.extra.get("mode") != "3d" or not L.alive(t):
                continue
            I = max(0.0, min(1.0, L.get("op", t) / 100))
            pos = np.array([L.get("pos0", t) * CW / 200, L.get("pos1", t) * CH / 200, mid + L.get("pos2", t) * CW / 200])
            c = QColor(L.color)
            col = np.array([c.redF(), c.greenF(), c.blueF()])
            lt, cone = L.extra.get("lt", "sun"), None
            if lt == "ray":      # tia / den roi: huong theo goc xoay, goc mo theo Ti le
                aim = rot_matrix(L.get("rot0", t), L.get("rot1", t), -L.get("rot2", t)) @ np.array([0.0, 0.0, -1.0])
                cone = math.radians(10 + 25 * max(0.1, L.get("scl0", t) / 100))
            else:                # sun / moon: sang song song, huong tu vi tri toi tam canh
                aim = np.array([0.0, 0.0, mid]) - pos
                n = float(np.linalg.norm(aim))
                aim = aim / n if n > 1e-6 else np.array([0.0, -1.0, 0.0])
                if lt == "moon":
                    I *= 0.45
            R = rot_matrix(L.get("rot0", t), L.get("rot1", t), -L.get("rot2", t)) if lt == "ray" else np.eye(3)
            out.append(dict(pos=pos, aim=aim, col=col, I=I, type=lt, cone=cone, L=L, R=R, base=mid))
        return out

    @staticmethod
    def _face_light(n, centre, lights):
        """(do sang vo huong, mau sang theo kenh) cua 1 mat; khong co den 3D thi dung anh sang mac dinh cu."""
        if not lights:
            return max(0.0, float(n @ LIGHT)), None
        acc = np.zeros(3)
        for lg in lights:
            if lg["type"] == "ray":
                v = lg["pos"] - centre
                d = float(np.linalg.norm(v))
                if d < 1e-6:
                    continue
                l = v / d
                ca = math.cos(lg["cone"])
                cosang = float((-l) @ lg["aim"])
                if cosang <= ca:
                    continue
                f = ((cosang - ca) / (1 - ca)) ** 0.5
            else:
                l, f = -lg["aim"], 1.0
            acc += lg["I"] * f * max(0.0, float(n @ l)) * lg["col"]
        c = np.minimum(1.0, 0.22 + acc)
        return float(c.mean()), tuple(float(x) for x in c)

    @staticmethod
    def _spec(n, pt, lights, cam, ks, kp):
        """Do sang phan chieu (Blinn-Phong) tai diem pt cua mat co phap tuyen n."""
        v = cam - pt
        v = v / (float(np.linalg.norm(v)) or 1.0)
        s = 0.0
        for lg in (lights or [dict(type="sun", aim=-LIGHT, I=0.7)]):
            f = 1.0
            if lg["type"] == "ray":
                l = lg["pos"] - pt
                l = l / (float(np.linalg.norm(l)) or 1.0)
                ca = math.cos(lg["cone"])
                cosang = float((-l) @ lg["aim"])
                if cosang <= ca:
                    continue
                f = ((cosang - ca) / (1 - ca)) ** 0.5
            else:
                l = -lg["aim"]
            h = l + v
            hn = float(np.linalg.norm(h))
            if hn < 1e-6:
                continue
            s += lg["I"] * f * max(0.0, float(n @ (h / hn))) ** kp
        return min(1.0, ks * s)

    @staticmethod
    def _hull(pts):
        pts = sorted(set(pts))
        if len(pts) < 3:
            return pts
        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        lo, up = [], []
        for q in pts:
            while len(lo) >= 2 and cross(lo[-2], lo[-1], q) <= 0:
                lo.pop()
            lo.append(q)
        for q in reversed(pts):
            while len(up) >= 2 and cross(up[-2], up[-1], q) <= 0:
                up.pop()
            up.append(q)
        return lo[:-1] + up[:-1]


    # ------------------------------------------------------------ goc nhin (kieu Numpad cua Blender)
    def set_view(self, yaw, pitch):
        tgt = np.array([0.0, 0.0, self._mid_z()])
        dist = max(600.0, float(np.linalg.norm(self.cam - tgt)))
        self.yaw, self.pitch = yaw, pitch
        self.cam = tgt - self._basis()[2] * dist
        self._cam_only = True
        self.ed.stage.update()

    def view_name(self):
        for nm, y, pch in (("Trước", 0, 0), ("Sau", math.pi, 0), ("Phải", -HALF, 0), ("Trái", HALF, 0),
                           ("Trên", 0, -HALF), ("Dưới", 0, HALF)):
            if abs(math.remainder(self.yaw - y, 2 * math.pi)) < 0.02 and abs(self.pitch - pch) < 0.02:
                return nm
        return "Phối cảnh"

    # ------------------------------------------------------------ gizmo kieu Blender
    def _basis_for(self, R, right, up, fwd, local_only=False):
        o = "local" if local_only else self.orient
        if o == "local":
            return np.array(R, float)
        if o == "view":
            return np.column_stack([right, up, -fwd])
        if o == "normal":
            z = np.array(R, float)[:, 2]
            x = np.cross([0.0, 1.0, 0.0], z)
            x = np.array([1.0, 0.0, 0.0]) if np.linalg.norm(x) < 1e-6 else x / np.linalg.norm(x)
            return np.column_stack([x, np.cross(z, x), z])
        return np.eye(3)

    def _draw_gizmo(self, p, proj, st, right, up, fwd):
        self._gz = None
        L = st.sel
        pose = self._pose.get(id(L)) if L is not None else None
        if pose is None or self.gmode == "select":
            return
        pos, R, base_z, kind = pose
        if (self.gmode == "scale" and kind != "box") or (self.gmode == "rotate" and kind == "light"):
            return
        o, vz = proj(pos)
        if o is None:
            return
        B = self._basis_for(R, right, up, fwd, local_only=(self.gmode == "scale"))
        arm = vz * 110.0 / self._focal(st)
        H = []
        for i in range(3):
            a = B[:, i]
            if self.gmode == "rotate":
                u, v = B[:, (i + 1) % 3], B[:, (i + 2) % 3]
                pts = [proj(pos + (u * math.cos(2 * math.pi * k / 48) + v * math.sin(2 * math.pi * k / 48)) * arm * 0.85)[0]
                       for k in range(49)]
                H.append((i, "ring", pts))
            else:
                q, _ = proj(pos + a * arm)
                if q is not None:
                    H.append((i, self.gmode, (o, q)))
        if self.gmode in ("move", "scale"):
            H.append(("c", "center", o))
        hot = self.ghot if self.gd is None else self.gd["h"]
        p.save()
        p.setBrush(Qt.NoBrush)
        for hid, k, data in H:
            on = hid == hot
            col = QColor(AXC[hid]) if hid != "c" else QColor("#ffffff")
            if on:
                col = col.lighter(150)
            if k == "ring":
                p.setPen(QPen(col, 3.6 if on else 2.4))
                for a_, b_ in zip(data, data[1:]):
                    if a_ is not None and b_ is not None:
                        p.drawLine(a_, b_)
            elif k in ("move", "scale"):
                o_, q = data
                p.setPen(QPen(col, 3.4 if on else 2.6))
                p.drawLine(o_, q)
                dx, dy = q.x() - o_.x(), q.y() - o_.y()
                n = math.hypot(dx, dy) or 1.0
                dx, dy = dx / n, dy / n
                p.setPen(Qt.NoPen)
                p.setBrush(col)
                if k == "move":
                    p.drawPolygon(QPolygonF([q + QPointF(dx * 6, dy * 6), QPointF(q.x() - dx * 14 - dy * 6, q.y() - dy * 14 + dx * 6),
                                             QPointF(q.x() - dx * 14 + dy * 6, q.y() - dy * 14 - dx * 6)]))
                else:
                    p.drawRect(QRectF(q.x() - 6, q.y() - 6, 12, 12))
                p.setBrush(Qt.NoBrush)
            else:
                p.setPen(QPen(QColor(0, 0, 0, 200), 1.2))
                p.setBrush(QColor("#ffd54a") if on else QColor("#ffffff"))
                p.drawEllipse(data, 7, 7)
        p.restore()
        self._gz = dict(o=o, arm=arm, B=B, H=H, R=np.array(R, float), vz=vz)

    def _gz_hit(self, pos):
        gz = self._gz
        if not gz:
            return None
        best, bd = None, 1e9
        for hid, k, data in gz["H"]:
            if k == "center":
                d, thr = math.hypot(pos.x() - data.x(), pos.y() - data.y()) - 3, 10
            elif k == "ring":
                d, thr = min((_sdist(pos, a_, b_) for a_, b_ in zip(data, data[1:]) if a_ is not None and b_ is not None), default=1e9), 8
            else:
                d, thr = min(_sdist(pos, data[0], data[1]), math.hypot(pos.x() - data[1].x(), pos.y() - data[1].y()) - 5), 8
            if d < thr and d < bd:
                best, bd = hid, d
        return best

    def _gz_begin(self, h, pos):
        st, gz = self.ed.stage, self._gz
        L, t = st.sel, st.t
        right, up, fwd = self._basis()
        o = gz["o"]
        v = None
        for hid, k, data in gz["H"]:
            if hid == h and k in ("move", "scale"):
                v = (data[1].x() - data[0].x(), data[1].y() - data[0].y())
        self.gd = dict(h=h, L=L, mode=self.gmode, p0=QPointF(pos), B=gz["B"], arm=gz["arm"], R0=gz["R"], v=v, vz=gz["vz"],
                       base=[L.get(k, t) for k in ("pos0", "pos1", "pos2")], scl=[L.get("scl0", t), L.get("scl1", t)],
                       acc=0.0, last=math.atan2(pos.y() - o.y(), pos.x() - o.x()), o=o, right=right, up=up, fwd=fwd)
        return True

    def _gz_drag(self, w, e):
        st, gd = self.ed.stage, self.gd
        L, h, mode = gd["L"], gd["h"], gd["mode"]
        pos = e.position()
        dx, dy = pos.x() - gd["p0"].x(), pos.y() - gd["p0"].y()
        CH = CW / st.ratio
        ctrl = bool(e.modifiers() & Qt.ControlModifier)
        self._cam_only = True                    # noi dung lop khong doi khi keo: dung lai texture, chi ve lai khung
        if mode == "move":
            if h == "c":
                k = gd["vz"] / self._focal(st)
                wv = gd["right"] * dx * k - gd["up"] * dy * k
            else:
                v = gd["v"]
                vv = (v[0] ** 2 + v[1] ** 2) if v else 0.0
                if vv < 16:
                    return
                s = gd["arm"] * (dx * v[0] + dy * v[1]) / vv
                if ctrl:
                    s = round(s / (gd["arm"] * 0.1)) * gd["arm"] * 0.1
                wv = gd["B"][:, h] * s
            for i, (key, sc) in enumerate((("pos0", CW), ("pos1", CH), ("pos2", CW))):
                if abs(wv[i]) > 1e-9:
                    self.ed.write(L, key, gd["base"][i] + float(wv[i]) * 200 / sc)
        elif mode == "rotate":
            o = gd["o"]
            ang = math.atan2(pos.y() - o.y(), pos.x() - o.x())
            gd["acc"] += math.remainder(ang - gd["last"], 2 * math.pi)
            gd["last"] = ang
            a = gd["B"][:, h]
            th = gd["acc"] * (1.0 if float(a @ gd["fwd"]) > 0 else -1.0)
            if ctrl:
                th = round(th / math.radians(15)) * math.radians(15)
            ax, ay, az = euler_from(rodrigues(a, th) @ gd["R0"])
            self.ed.write(L, "rot0", ax)
            self.ed.write(L, "rot1", ay)
            self.ed.write(L, "rot2", -az)
        elif mode == "scale":
            if h == "c":
                f = math.exp((dx - dy) / 150.0)
            else:
                v = gd["v"]
                vv = (v[0] ** 2 + v[1] ** 2) if v else 0.0
                if vv < 16:
                    return
                f = 1 + (dx * v[0] + dy * v[1]) / vv
            f = max(0.05, f)
            if h in (0, 2, "c"):
                self.ed.write(L, "scl0", gd["scl"][0] * f)
            if h in (1, 2, "c"):
                self.ed.write(L, "scl1", gd["scl"][1] * f)

    def _hud_click(self, w, pos):
        for rc, grp, val in self._hud:
            if rc.contains(pos):
                if grp == "g":
                    self.gmode = val
                else:
                    self.orient = val
                w.update()
                return True
        for c, rad, yaw, pitch in self._nav:
            if math.hypot(pos.x() - c.x(), pos.y() - c.y()) <= rad:
                self.set_view(yaw, pitch)
                return True
        return False

    def _tick(self):
        now = time.monotonic()
        dt = min(0.1, now - self._last)
        self._last = now
        if not self.keys:
            return
        right, up, fwd = self._basis()
        mods = QApplication.keyboardModifiers()
        fast = 3.0 if mods & Qt.ShiftModifier else 1.0
        s = 0.6 * CW * dt * fast
        for k in self.keys:
            if k == "left":
                self.cam -= right * s
            elif k == "right":
                self.cam += right * s
            elif k == "up":
                self.cam += up * s
            elif k == "down":
                self.cam -= up * s
            elif k == "fwd":
                self.cam += fwd * s
            elif k == "back":
                self.cam -= fwd * s
            elif k == "zoom":
                f = 1.8 ** dt
                self.zoom = max(0.2, min(8.0, self.zoom * (1 / f if mods & Qt.ShiftModifier else f)))
        self._cam_only = True
        self.ed.stage.update()

    # ------------------------------------------------------------ su kien chuot / phim (Stage goi vao)
    def key_press(self, e):
        if e.key() == Qt.Key_Escape:
            self.toggle(False)
            return True
        key, mods = e.key(), e.modifiers()
        if mods & Qt.KeypadModifier and key in (Qt.Key_1, Qt.Key_3, Qt.Key_7, Qt.Key_5):     # goc nhin nhu Numpad Blender
            back = bool(mods & Qt.ControlModifier)
            yaw, pitch = {Qt.Key_1: (math.pi if back else 0.0, 0.0), Qt.Key_3: (HALF if back else -HALF, 0.0),
                          Qt.Key_7: (0.0, HALF if back else -HALF), Qt.Key_5: (-0.6, -0.35)}[key]
            self.set_view(yaw, pitch)
            e.accept()
            return True
        if not (mods & (Qt.ControlModifier | Qt.AltModifier | Qt.KeypadModifier)):
            gm = {Qt.Key_1: "select", Qt.Key_2: "move", Qt.Key_3: "rotate", Qt.Key_4: "scale"}.get(key)
            if gm:
                self.gmode = gm
                self.ed.stage.update()
                e.accept()
                return True
            if key == Qt.Key_O:
                names = [n for n, _ in ORIENTS]
                self.orient = names[(names.index(self.orient) + 1) % 4]
                self.ed.stage.update()
                e.accept()
                return True
        k = KEYMAP.get(e.key())
        if k and not (e.modifiers() & (Qt.ControlModifier | Qt.AltModifier)):
            self.keys.add(k)
            e.accept()
            return True
        return False

    def key_release(self, e):
        k = KEYMAP.get(e.key())
        if k and not e.isAutoRepeat():
            self.keys.discard(k)
            return True
        return False

    def mouse_press(self, w, e):
        w.setFocus()
        if e.button() == Qt.LeftButton:
            pos = e.position()
            if self._hud_click(w, pos):
                e.accept()
                return
            h = self._gz_hit(pos)
            if h is not None and self._gz_begin(h, pos):
                e.accept()
                return
        if e.button() in (Qt.LeftButton, Qt.RightButton):
            d0 = max(300.0, float((np.array([0.0, 0.0, self._mid_z()]) - self.cam) @ self._basis()[2]))
            self.drag = [e.position(), self.yaw, self.pitch, False, e.button(), self.cam + self._basis()[2] * d0, d0]
        e.accept()

    def mouse_move(self, w, e):
        if self.gd:
            self._gz_drag(w, e)
            e.accept()
            return
        d = self.drag
        if not d:
            h = self._gz_hit(e.position())
            if h != self.ghot:
                self.ghot = h
                w.setCursor(Qt.PointingHandCursor if h is not None else Qt.ArrowCursor)
                self._cam_only = True
                w.update()
        if d:
            dx, dy = e.position().x() - d[0].x(), e.position().y() - d[0].y()
            if d[3] or abs(dx) + abs(dy) > 4:
                d[3] = True
                self.yaw = d[1] + dx * 0.005
                self.pitch = max(-1.5, min(1.5, d[2] - dy * 0.005))
                self.cam = d[5] - self._basis()[2] * d[6]          # xoay quanh diem dang nhin
                self._cam_only = True
                w.update()
        e.accept()

    def mouse_release(self, w, e):
        if self.gd:
            self.gd = None
            w.update()
            e.accept()
            return
        d, self.drag = self.drag, None
        if d and not d[3] and d[4] == Qt.LeftButton:
            pos = e.position()
            for depth, poly, L in sorted(self.faces_hit, key=lambda f: f[0]):
                if poly.containsPoint(pos, Qt.OddEvenFill):
                    w.picked.emit(L)
                    break
            else:
                w.picked.emit(None)
        e.accept()

    def wheel(self, w, e):
        d = e.angleDelta().y()
        if d:
            self.cam += self._basis()[2] * (d / 120.0) * 0.08 * CW
            self._cam_only = True
            w.update()
        e.accept()

    # ------------------------------------------------------------ ve
    def _texture(self, st, L, b, pw, ph):
        key = (id(L), pw, ph)
        if self._cam_only_now and key in self._tex:
            return self._tex[key]
        img = QImage(pw, ph, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.scale(pw / b.width(), ph / b.height())
        p.translate(b.width() / 2, b.height() / 2)
        p.setOpacity(max(0.0, min(1.0, L.get("op", st.t) / 100)))
        if gk_material.mat_of(L):
            gk_material.paint(st, p, L, b)
        else:
            st.draw_full(p, L, b)
        p.end()
        if L.kind in ("shape", "text"):
            col = QColor(L.color)
        else:
            col = img.scaled(1, 1, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).pixelColor(0, 0)
            if col.alpha() < 40:
                col = QColor(L.color)
        col.setAlpha(255)
        self._tex[key] = (img, col)
        return self._tex[key]

    def paint(self, w):
        st = self.ed.stage
        if not self._cam_only:
            self._tex = {}
        cam_only, self._cam_only = self._cam_only, False
        self._cam_only_now = cam_only
        W, H = w.width(), w.height()
        p = QPainter(w)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        bg = next((QColor(L.color) for L in st.layers if L.kind == "bg" and L.alive(st.t)), QColor(T["bg0"]))
        grad_top, grad_bot = bg.darker(160), bg
        from PySide6.QtGui import QLinearGradient
        lg = QLinearGradient(0, 0, 0, H)
        lg.setColorAt(0, grad_top)
        lg.setColorAt(1, grad_bot)
        p.fillRect(w.rect(), QBrush(lg))

        right, up, fwd = self._basis()
        f = self._focal(st)
        cam = self.cam
        cx, cy = W / 2.0, H / 2.0

        def proj(P):
            d = np.asarray(P) - cam
            vz = d @ fwd
            if vz < NEAR:
                return None, vz
            return QPointF(cx + f * (d @ right) / vz, cy - f * (d @ up) / vz), vz

        CH = CW / st.ratio
        # --- san luoi + khung canvas
        gy = -CH * 0.8
        p.setPen(QPen(QColor(255, 255, 255, 28), 1))
        for i in range(-8, 9):
            for a, b2 in (((i * 250, gy, -2000), (i * 250, gy, 2000)), ((-2000, gy, i * 250), (2000, gy, i * 250))):
                pa, _ = proj(a)
                pb, _ = proj(b2)
                if pa is not None and pb is not None:
                    p.drawLine(pa, pb)
        fr = [proj((x, y, 0)) for x, y in ((-CW / 2, CH / 2), (CW / 2, CH / 2), (CW / 2, -CH / 2), (-CW / 2, -CH / 2))]
        if all(q[0] is not None for q in fr):
            p.setPen(QPen(QColor(255, 255, 255, 90), 1, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(QPolygonF([q[0] for q in fr]))

        # --- cac khoi
        faces, z_run = [], 0.0
        rect = QRectF(0, 0, CW, CH)
        lights, boxes = self._lights(st), []
        self._pose = {}
        for lg in lights:
            self._pose[id(lg["L"])] = (lg["pos"], lg["R"], lg["base"], "ray" if lg["type"] == "ray" else "light")
        for L in st.layers:
            if L.kind in ("bg", "audio", "camera", "light") or not L.alive(st.t):
                continue
            b = st.body(L, rect)
            sw = max(8.0, b.width() * L.get("scl0", st.t) / 100)
            sh = max(8.0, b.height() * L.get("scl1", st.t) / 100)
            d = max(20.0, min(sw, sh))
            k = min(1.0, 800.0 / max(b.width(), b.height(), 1.0))
            pw, ph = max(2, int(b.width() * k)), max(2, int(b.height() * k))
            img, side = self._texture(st, L, b, pw, ph)
            R = rot_matrix(L.get("rot0", st.t), L.get("rot1", st.t), -L.get("rot2", st.t))
            z_run += d / 2
            pos = np.array([L.get("pos0", st.t) * CW / 200, L.get("pos1", st.t) * CH / 200,
                            z_run + L.get("pos2", st.t) * CW / 200])
            z_run += d / 2 + 40
            hx, hy, hz = sw / 2, sh / 2, d / 2
            boxes.append((R, pos, hx, hy, hz))
            self._pose[id(L)] = (pos.copy(), R, float(pos[2]) - L.get("pos2", st.t) * CW / 200, "box")
            local = {
                "front": [(-hx, hy, hz), (hx, hy, hz), (hx, -hy, hz), (-hx, -hy, hz)],
                "back": [(hx, hy, -hz), (-hx, hy, -hz), (-hx, -hy, -hz), (hx, -hy, -hz)],
                "right": [(hx, hy, hz), (hx, hy, -hz), (hx, -hy, -hz), (hx, -hy, hz)],
                "left": [(-hx, hy, -hz), (-hx, hy, hz), (-hx, -hy, hz), (-hx, -hy, -hz)],
                "top": [(-hx, hy, -hz), (hx, hy, -hz), (hx, hy, hz), (-hx, hy, hz)],
                "bottom": [(-hx, -hy, hz), (hx, -hy, hz), (hx, -hy, -hz), (-hx, -hy, -hz)],
            }
            normals = {"front": (0, 0, 1), "back": (0, 0, -1), "right": (1, 0, 0), "left": (-1, 0, 0),
                       "top": (0, 1, 0), "bottom": (0, -1, 0)}
            op = max(0.0, min(1.0, L.get("op", st.t) / 100))
            mt = gk_material.mat_of(L)
            ks, kp = (gk_material.SPEC[mt[0]][0] * mt[1], gk_material.SPEC[mt[0]][1]) if mt else (0.0, 1)
            if mt and mt[0] == "glass":
                op *= gk_material.glass_alpha(mt[1])
            if mt and mt[0] in gk_material.SIDE:
                c_ = gk_material.SIDE[mt[0]]
                side = QColor(c_[0], c_[1], c_[2])
            for name, verts in local.items():
                n = R @ np.array(normals[name], float)
                wv = [R @ np.array(v, float) + pos for v in verts]
                centre = sum(wv) / 4.0
                if n @ (centre - cam) >= 0:                    # mat quay lung camera
                    continue
                pts, depth, ok = [], 0.0, True
                for v in wv:
                    q, vz = proj(v)
                    if q is None:
                        ok = False
                        break
                    pts.append(q)
                    depth += vz / 4.0
                if not ok:
                    continue
                lit, tint = self._face_light(n, centre, lights)
                spec = None
                if ks > 0.01:
                    spec = (self._spec(n, wv[0], lights, cam, ks, kp), self._spec(n, centre, lights, cam, ks, kp),
                            self._spec(n, wv[2], lights, cam, ks, kp))
                faces.append((depth, name, QPolygonF(pts), pts, L, img, side, lit, op, pw, ph, tint, spec))

        faces.sort(key=lambda t: -t[0])
        # --- bong do len san (moi den 3D that chieu vao tung khoi)
        if lights:
            p.setPen(Qt.NoPen)
            for lg in lights:
                p.setBrush(QColor(0, 0, 0, int(120 * min(1.0, lg["I"] + 0.15))))
                for R_, pos_, hx_, hy_, hz_ in boxes:
                    gp = []
                    for sx in (-1, 1):
                        for sy in (-1, 1):
                            for sz in (-1, 1):
                                V = R_ @ np.array([sx * hx_, sy * hy_, sz * hz_]) + pos_
                                if V[1] <= gy:
                                    continue
                                if lg["type"] == "ray":
                                    if lg["pos"][1] <= V[1]:
                                        continue
                                    P = lg["pos"] + (V - lg["pos"]) * ((lg["pos"][1] - gy) / (lg["pos"][1] - V[1]))
                                else:
                                    if lg["aim"][1] >= -1e-3:
                                        continue
                                    P = V + lg["aim"] * ((gy - V[1]) / lg["aim"][1])
                                gp.append((float(P[0]), float(P[2])))
                    hull = self._hull(gp)
                    if len(hull) < 3:
                        continue
                    qs = [proj((x, gy, z))[0] for x, z in hull]
                    if all(q is not None for q in qs):
                        p.drawPolygon(QPolygonF(qs))
        self.faces_hit = []
        sel = st.sel
        for depth, name, poly, pts, L, img, side, lit, op, pw, ph, tint, spec in faces:
            self.faces_hit.append((depth, poly, L))
            textured = name in ("front", "back")
            p.save()
            p.setOpacity(op if not textured else 1.0)
            if textured:
                order = pts if name == "front" else pts
                tr = quad_transform(pw, ph, [(q.x(), q.y()) for q in order])
                if tr is not None:
                    p.setTransform(tr, False)
                    p.drawImage(0, 0, img)
                    p.resetTransform()
                shade = (0.72 + 0.28 * lit if tint is None else min(1.0, 0.25 + 0.9 * lit)) if name == "front" else 0.55
                if shade < 1.0:
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(0, 0, 0, int(255 * (1 - shade) * (op if name == "back" else 0.9))))
                    p.drawPolygon(poly)
            else:
                shade = 0.40 + 0.60 * lit
                if tint is None:
                    c = QColor(int(side.red() * shade), int(side.green() * shade), int(side.blue() * shade))
                else:
                    c = QColor(int(side.red() * tint[0]), int(side.green() * tint[1]), int(side.blue() * tint[2]))
                p.setBrush(c)
                p.setPen(Qt.NoPen)
                p.drawPolygon(poly)
            if spec is not None and max(spec) > 0.02 and name != "back":      # diem sang phan chieu cua chat lieu
                g = QLinearGradient(pts[0], pts[2])
                for pos_, s_ in zip((0.0, 0.5, 1.0), spec):
                    g.setColorAt(pos_, QColor(255, 255, 255, int(255 * min(1.0, s_) * 0.85)))
                p.setOpacity(1.0 if name == "front" else op)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(g))
                p.drawPolygon(poly)
            p.setBrush(Qt.NoBrush)
            if L is sel:
                p.setPen(QPen(QColor(T["accent"]), 2.2))
            else:
                p.setPen(QPen(QColor(0, 0, 0, 80), 1))
            p.drawPolygon(poly)
            p.restore()

        # --- dau hieu nguon sang
        for lg in lights:
            q, lg_vz = proj(lg["pos"])
            if q is None:
                continue
            c = QColor(int(lg["col"][0] * 255), int(lg["col"][1] * 255), int(lg["col"][2] * 255))
            p.setBrush(c)
            p.setPen(QPen(QColor(0, 0, 0, 160), 1))
            p.drawEllipse(q, 8, 8)
            self.faces_hit.append((lg_vz - 100.0, QPolygonF([QPointF(q.x() + 11 * math.cos(i * 0.785), q.y() + 11 * math.sin(i * 0.785)) for i in range(8)]), lg["L"]))
            if lg["L"] is sel:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(T["accent"]), 2.2))
                p.drawEllipse(q, 12, 12)
            if lg["type"] == "ray":
                q2, _ = proj(lg["pos"] + lg["aim"] * 400)
                if q2 is not None:
                    p.setPen(QPen(c, 1.5, Qt.DashLine))
                    p.drawLine(q, q2)
            p.setPen(QColor(255, 255, 255, 220))
            p.drawText(QPointF(q.x() + 12, q.y() + 4), lg["type"].upper())
        # --- gizmo + HUD
        p.setOpacity(1.0)
        self._draw_gizmo(p, proj, st, right, up, fwd)
        p.setFont(QFont(theme.FONT_BODY, 9))
        self._hud = []
        for row, (grp, items, cur) in enumerate((("g", [(k, "%s %s" % (n, key)) for k, n, key in GMODES], self.gmode),
                                                 ("o", ORIENTS, self.orient))):
            x = 12.0
            for val, label in items:
                rc = QRectF(x, 12 + row * 30, 74, 24)
                on = val == cur
                p.setPen(QPen(QColor(255, 255, 255, 60), 1))
                p.setBrush(QColor(T["accent"]) if on else QColor(0, 0, 0, 140))
                p.drawRoundedRect(rc, 6, 6)
                p.setPen(QColor(T["on_accent"]) if on else QColor(255, 255, 255, 220))
                p.drawText(rc, Qt.AlignCenter, label)
                self._hud.append((rc, grp, val))
                x += 78
        # --- hinh truc goc tren phai (bam de doi goc nhin)
        self._nav = []
        c0, Rn = QPointF(W - 62, 74), 40.0
        balls = []
        for i in range(3):
            for sgn in (1, -1):
                a = np.eye(3)[i] * sgn
                balls.append((float(a @ fwd), i, sgn, QPointF(c0.x() + Rn * float(a @ right), c0.y() - Rn * float(a @ up))))
        balls.sort(key=lambda b: -b[0])
        views = {(0, 1): (-HALF, 0.0), (0, -1): (HALF, 0.0), (1, 1): (0.0, -HALF), (1, -1): (0.0, HALF),
                 (2, 1): (0.0, 0.0), (2, -1): (math.pi, 0.0)}
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawEllipse(c0, Rn + 16, Rn + 16)
        for dep, i, sgn, q in balls:
            col = QColor(AXC[i])
            if sgn < 0:
                col.setAlpha(150)
            p.setPen(QPen(col, 2) if sgn > 0 else Qt.NoPen)
            p.drawLine(c0, q) if sgn > 0 else None
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            rad = 9.0 if sgn > 0 else 6.5
            p.drawEllipse(q, rad, rad)
            if sgn > 0:
                p.setPen(QColor(0, 0, 0, 230))
                p.drawText(QRectF(q.x() - 9, q.y() - 9, 18, 18), Qt.AlignCenter, "XYZ"[i])
            self._nav.append((q, rad + 2, *views[(i, sgn)]))
        p.setPen(QColor(255, 255, 255, 220))
        p.drawText(QRectF(W - 130, 128, 136, 18), Qt.AlignRight | Qt.AlignVCenter, self.view_name())
        lines = ["3D   A/D trái-phải · W/S lên-xuống · Q tới · E lùi · F zoom (Shift+F thu nhỏ)",
                 "Kéo chuột: xoay · Lăn: tiến/lùi · Bấm: chọn lớp · Shift: nhanh · Esc: thoát",
                 "1-4: công cụ · O: đổi hệ trục · Numpad 1/3/7/5: Trước/Phải/Trên/Phối cảnh (Ctrl: ngược lại) · Ctrl khi kéo: bám bước"]
        for i, s in enumerate(lines):
            r = QRectF(12, H - 64 + i * 18, W - 24, 18)
            p.setPen(QColor(0, 0, 0, 160))
            p.drawText(r.translated(1, 1), Qt.AlignLeft | Qt.AlignVCenter, s)
            p.setPen(QColor(255, 255, 255, 220))
            p.drawText(r, Qt.AlignLeft | Qt.AlignVCenter, s)
        p.end()

    # ------------------------------------------------------------ gan vao Stage
    def _patch_stage(self):
        import gk_panels
        St = gk_panels.Stage
        if getattr(St, "_s3_patched", False):
            St._s3 = self
            return
        o_paint, o_press, o_move, o_rel = St.paintEvent, St.mousePressEvent, St.mouseMoveEvent, St.mouseReleaseEvent
        o_wheel, o_dbl, o_kp, o_kr = St.wheelEvent, St.mouseDoubleClickEvent, St.keyPressEvent, St.keyReleaseEvent
        o_focus = St.focusOutEvent

        def on():
            s = getattr(St, "_s3", None)
            return s if (s is not None and s.on) else None

        def paint(w, e):
            s = on()
            s.paint(w) if s else o_paint(w, e)

        def press(w, e):
            s = on()
            s.mouse_press(w, e) if s else o_press(w, e)

        def move(w, e):
            s = on()
            s.mouse_move(w, e) if s else o_move(w, e)

        def rel(w, e):
            s = on()
            s.mouse_release(w, e) if s else o_rel(w, e)

        def wheel(w, e):
            s = on()
            s.wheel(w, e) if s else o_wheel(w, e)

        def dbl(w, e):
            if not on():
                o_dbl(w, e)

        def kp(w, e):
            s = on()
            if not (s and s.key_press(e)):
                o_kp(w, e)

        def kr(w, e):
            s = on()
            if not (s and s.key_release(e)):
                o_kr(w, e)

        def focus(w, e):
            s = getattr(St, "_s3", None)
            if s:
                s.keys.clear()
            o_focus(w, e)

        St.paintEvent, St.mousePressEvent, St.mouseMoveEvent, St.mouseReleaseEvent = paint, press, move, rel
        St.wheelEvent, St.mouseDoubleClickEvent, St.keyPressEvent, St.keyReleaseEvent = wheel, dbl, kp, kr
        St.focusOutEvent = focus
        St._s3_patched = True
        St._s3 = self


def attach(editor):
    return Scene3D(editor)
