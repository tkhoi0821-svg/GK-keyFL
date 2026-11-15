"""Hang so + mo hinh du lieu (Layer) dung chung."""
import os, math
from PySide6.QtGui import QPixmap

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "gk_keyfl_logo.png")
MAXT = 3600.0          # gioi han tren khi keo clip (giay)
DURATION = 5.0         # het noi dung du an (giay) - tu dong theo clip, xem fit_duration()
PAD = 2.0              # khoang trong sau clip cuoi tren timeline


def total():
    """Chieu dai vung timeline dang hien (noi dung + khoang trong)."""
    return DURATION + PAD


def fit_duration(clips):
    """Tinh lai DURATION tu clip cuoi cung (clips: moi phan tu co .start, .dur). Tra ve True neu doi."""
    global DURATION
    end = max((c.start + c.dur for c in clips), default=0.0)
    new = 5.0 if end <= 0 else max(1.0, math.ceil(end * 10 - 1e-6) / 10)
    if abs(new - DURATION) < 1e-6:
        return False
    DURATION = new
    return True


TRACK_H, RULER_H = 44, 26
TRACKS = ["Text", "Overlay", "Video", "Audio"]
COLORS = {"Text": "#e0a526", "Overlay": "#9b59d0", "Video": "#2f8fe0", "Audio": "#2fb37a"}

KINDS = {"Hình vuông": ("shape", 1, "#7a2bff"), "Văn bản": ("text", 0, "#ffffff"),
         "Hình ảnh": ("image", 1, "#2f8fe0"), "Video": ("video", 2, "#2f8fe0"), "Âm thanh": ("audio", 3, "#2fb37a")}
# cac hinh co ban: kind van la "shape", dang hinh nam o Layer.extra["form"] (rect mac dinh). Ve bang gk_panels.form_path
FORM_GROUPS = [
    ("Cơ bản", [("Hình vuông", "rect"), ("Vuông bo tròn", "rrect"), ("Viên thuốc", "pill"), ("Hình elip", "ellipse"),
                ("Tam giác", "triangle"), ("Tam giác vuông", "rtri"), ("Tam giác ngược", "dtri"), ("Hình thoi", "diamond"),
                ("Hình thang", "trapezoid"), ("Hình bình hành", "parallelogram"), ("Bán nguyệt", "semicircle"),
                ("Cung phần tư", "quarter"), ("Quạt tròn", "pie"), ("Vòng tròn", "ring"), ("Khung vuông", "frame"),
                ("Cổng vòm", "arch")]),
    ("Đa giác", [("Đa giác", "polygon"), ("Ngũ giác", "pentagon"), ("Lục giác", "hexagon"), ("Thất giác", "heptagon"),
                 ("Bát giác", "octagon"), ("Thập giác", "decagon"), ("Kim cương", "gem")]),
    ("Sao & tia", [("Ngôi sao", "star"), ("Sao 4 cánh", "star4"), ("Sao 6 cánh", "star6"), ("Sao 8 cánh", "star8"),
                   ("Lấp lánh", "sparkle"), ("Huy hiệu răng cưa", "seal"), ("Tia nhọn", "burst"), ("Bánh răng", "gear"),
                   ("Bông hoa", "flower"), ("Tia sét", "bolt")]),
    ("Mũi tên", [("Mũi tên", "arrow"), ("Mũi tên trái", "arrow_l"), ("Mũi tên lên", "arrow_u"), ("Mũi tên xuống", "arrow_d"),
                 ("Mũi tên hai chiều ngang", "arrow_lr"), ("Mũi tên hai chiều dọc", "arrow_ud"), ("Chữ V phải", "chevron_r"),
                 ("Chữ V trái", "chevron_l"), ("Mũi tên ngũ giác", "homeplate"), ("Nút phát", "play")]),
    ("Khung thoại", [("Khung thoại tròn", "bubble_round"), ("Khung thoại elip", "bubble_oval"),
                     ("Chú thích vuông", "callout"), ("Khung thoại gai (hét)", "bubble_spike"),
                     ("Khung suy nghĩ", "bubble_think")]),
    ("Ký hiệu & khác", [("Trái tim", "heart"), ("Dấu cộng", "plus"), ("Dấu nhân", "cross"), ("Dấu trừ", "minus"),
                        ("Dấu tích", "check"), ("Đám mây", "cloud"), ("Trăng lưỡi liềm", "crescent"),
                        ("Giọt nước", "drop"), ("Chiếc lá", "leaf"), ("Khiên", "shield"), ("Ngôi nhà", "house"),
                        ("Dấu trang", "bookmark"), ("Mặt cười", "smiley"), ("Chữ L", "letter_l"), ("Chữ T", "letter_t"),
                        ("Bậc thang", "stairs")]),
]
FORMS = {n: k for _, items in FORM_GROUPS for n, k in items}                  # ten trong menu Add -> dang hinh
FORM_NAMES = [(k, n) for _, items in FORM_GROUPS for n, k in items]           # (dang hinh, ten) cho o chon trong Thuoc tinh
for _n in list(FORMS)[1:]:
    KINDS[_n] = ("shape", 1, "#7a2bff")
BODY = {"shape": (.24, .36), "text": (.40, .14), "image": (.36, .24), "video": (.36, .24)}
# ---- cho plugin (gk_plugins.PluginAPI dang ky vao day)
CUSTOM_EASE = {}   # khoa -> ham(u) tra tien do
PAINTERS = {}      # kind -> ham(p, layer, rect, t) ve lop
ICONS = {}         # kind -> ham(p, rect) ve bieu tuong lop
PKEYS = ["pos0", "pos1", "pos2", "rot0", "rot1", "rot2", "scl0", "scl1", "scl2", "skw0", "skw1"]
CHANNELS = [("pos0", "Vị trí X"), ("pos1", "Vị trí Y"), ("pos2", "Vị trí Z"),
            ("rot0", "Xoay X"), ("rot1", "Xoay Y"), ("rot2", "Xoay Z"),
            ("scl0", "Tỉ lệ X"), ("scl1", "Tỉ lệ Y"), ("skw0", "Nghiêng X"), ("skw1", "Nghiêng Y"),
            ("op", "Độ mờ")]


# ====================================================================== noi suy / easing
EASES = [("linear", "Tuyến tính"), ("hold", "Dừng (Hold)"), ("ease", "Ease"), ("ease_in", "Ease In"),
         ("ease_out", "Ease Out"), ("ease_inout", "Ease In-Out"), ("back", "Vượt (Back)"),
         ("bounce", "Nảy (Bounce)"), ("elastic", "Đàn hồi (Elastic)"), ("cyclic", "Cyclic (sóng lặp)"),
         ("noise", "Rung (Noise)"), ("bezier", "Tuỳ chỉnh (Bezier)"),
         ("smooth", "Mượt liền mạch (Spline)")]
LOOPS = [("none", "Không lặp"), ("cycle", "Lặp lại (Cyclic)"), ("pingpong", "Qua lại (Ping-pong)")]
# cubic-bezier(x1, y1, x2, y2) giong CSS / After Effects
BEZ = {"linear": (0.33, 0.33, 0.67, 0.67), "ease": (0.25, 0.1, 0.25, 1.0), "ease_in": (0.42, 0.0, 1.0, 1.0),
       "ease_out": (0.0, 0.0, 0.58, 1.0), "ease_inout": (0.42, 0.0, 0.58, 1.0), "back": (0.34, 1.56, 0.64, 1.0)}


def bezier_y(x1, y1, x2, y2, u):
    if u <= 0:
        return 0.0
    if u >= 1:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(24):
        m = (lo + hi) / 2
        x = 3 * (1 - m) ** 2 * m * x1 + 3 * (1 - m) * m * m * x2 + m ** 3
        if x < u:
            lo = m
        else:
            hi = m
    m = (lo + hi) / 2
    return 3 * (1 - m) ** 2 * m * y1 + 3 * (1 - m) * m * m * y2 + m ** 3


def _bounce(u):
    n, d = 7.5625, 2.75
    if u < 1 / d:
        return n * u * u
    if u < 2 / d:
        u -= 1.5 / d
        return n * u * u + 0.75
    if u < 2.5 / d:
        u -= 2.25 / d
        return n * u * u + 0.9375
    u -= 2.625 / d
    return n * u * u + 0.984375


def _elastic(u):
    if u <= 0:
        return 0.0
    if u >= 1:
        return 1.0
    return 2 ** (-10 * u) * math.sin((u * 10 - 0.75) * (2 * math.pi / 3)) + 1


def _hash(i):
    n = (i * 1103515245 + 12345) & 0x7FFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0x7FFFFFFF
    return (n % 2000) / 1000.0 - 1.0


def _vnoise(x):
    i = math.floor(x)
    f = x - i
    f = f * f * (3 - 2 * f)
    return _hash(i) * (1 - f) + _hash(i + 1) * f


def _spline(k, i, u):
    """Noi suy Hermite don dieu (kieu PCHIP) cho doan k[i]->k[i+1]: toc do LIEN TUC qua tung key (khong khung / khong
    dung lai o moi key nhu ease) va khong vuot qua gia tri key (khong overshoot)."""
    a, b = k[i], k[i + 1]
    h = (b.t - a.t) or 1.0
    d = (b.v - a.v) / h

    def tangent(d0, d1):
        if d0 * d1 <= 0:
            return 0.0
        return 2 * d0 * d1 / (d0 + d1)

    if i > 0:
        p = k[i - 1]
        ma = tangent((a.v - p.v) / ((a.t - p.t) or 1.0), d)
    else:
        ma = d
    if i + 2 < len(k):
        n = k[i + 2]
        mb = tangent(d, (n.v - b.v) / ((n.t - b.t) or 1.0))
    else:
        mb = d
    u2, u3 = u * u, u * u * u
    return ((2 * u3 - 3 * u2 + 1) * a.v + (u3 - 2 * u2 + u) * h * ma +
            (-2 * u3 + 3 * u2) * b.v + (u3 - u2) * h * mb)


def ease_u(k, u):
    """Bien u (0..1 trong doan tu key k den key ke tiep) thanh tien do 0..1 theo kieu noi suy cua k."""
    if u >= 1:
        return 1.0
    e = k.e
    fn = CUSTOM_EASE.get(e)
    if fn is not None:                      # kieu noi suy do plugin them
        try:
            return float(fn(max(0.0, u)))
        except Exception:
            return max(0.0, u)
    if e == "linear":
        return max(0.0, u)
    if e == "hold":
        return 0.0
    if e == "bounce":
        return _bounce(max(0.0, u))
    if e == "elastic":
        return _elastic(max(0.0, u))
    if e == "cyclic":      # k.n dinh song, bat dau o v0 va ket thuc o v1
        return 0.5 - 0.5 * math.cos(math.pi * (2 * max(1, round(k.n)) - 1) * max(0.0, u))
    if e == "noise":       # rung quanh duong thang, bien do k.a, ket thuc dung v1
        u = max(0.0, u)
        return u + k.a * 0.5 * _vnoise(u * max(1.0, k.n)) * math.sin(math.pi * u)
    h = k.handles()
    if h is None:                           # kieu la (vd plugin da bi tat): quay ve tuyen tinh
        return max(0.0, u)
    return bezier_y(*h, u)


DEFAULT_EASE = "linear"      # dat tu Tuy chon


class Key:
    """Mot key frame: thoi gian t, gia tri v, kieu noi suy e cho doan tu key nay den key ke tiep.
    bz: cubic-bezier tuy chinh. n: so song (cyclic) / tan so rung (noise). a: bien do rung (noise)."""
    __slots__ = ("t", "v", "e", "bz", "n", "a")

    def __init__(self, t, v, e="linear", bz=None, n=4.0, a=0.5):
        self.t, self.v, self.e, self.bz, self.n, self.a = t, v, e, bz, n, a

    def __lt__(self, o):
        return self.t < o.t

    def handles(self):
        """Tham so cubic-bezier (x1,y1,x2,y2) hoac None (hold/bounce/elastic/cyclic/noise khong co tay nam bezier)."""
        if self.e == "bezier":
            return self.bz or BEZ["ease_inout"]
        return BEZ.get(self.e)

    def to_list(self):
        return [self.t, self.v, self.e, list(self.bz) if self.bz else None, self.n, self.a]

    @staticmethod
    def from_list(x):
        if len(x) >= 3:
            return Key(x[0], x[1], x[2], tuple(x[3]) if len(x) > 3 and x[3] else None,
                       x[4] if len(x) > 4 else 4.0, x[5] if len(x) > 5 else 0.5)
        return Key(x[0], x[1])


class Layer:
    """Mot lop: thuoc tinh co so + key frame (noi suy tuyen tinh) + cac clip tren timeline."""

    def __init__(self, name, kind="shape", color="#7a2bff"):
        self.name, self.kind, self.color, self.text = name, kind, color, name
        self.visible, self.timed, self.path, self.pix = True, True, None, None
        self.vid = None            # MediaSource (video / am thanh), khong luu vao file du an
        self.wfrac = 0.4           # chieu rong anh/video so voi canvas (cat anh dat de giu dung ti le)
        self.base = {"pos0": 0.0, "pos1": 0.0, "pos2": 0.0, "rot0": 0.0, "rot1": 0.0, "rot2": 0.0,
                     "scl0": 100.0, "scl1": 100.0, "scl2": 100.0, "skw0": 0.0, "skw1": 0.0, "op": 100.0}
        self.kf, self.clips, self.loop = {}, [], {}
        self.mesh = {"on": False, "cols": 3, "rows": 3}   # luoi meo (Mesh Warp); diem la kenh mwx<i>/mwy<i> (% kich thuoc)
        self.extra = {}            # tham so rieng cua loai lop do plugin them (duoc luu cung du an)

    def _wrap(self, key, k, t):
        m = self.loop.get(key, "none")
        t0, t1 = k[0].t, k[-1].t
        s = t1 - t0
        if m == "none" or s <= 0 or t0 <= t <= t1:
            return t
        if m == "cycle":
            return t0 + (t - t0) % s
        r = (t - t0) % (2 * s)
        return t0 + (r if r <= s else 2 * s - r)

    def get(self, key, t):
        k = self.kf.get(key)
        if not k:
            return self.base.get(key, 0.0)
        k = sorted(k)
        if len(k) >= 2:
            t = self._wrap(key, k, t)
        if t <= k[0].t:
            return k[0].v
        if t >= k[-1].t:
            return k[-1].v
        for i, (a, b) in enumerate(zip(k, k[1:])):
            if a.t <= t <= b.t:
                u = (t - a.t) / ((b.t - a.t) or 1)
                if a.e == "smooth":
                    return _spline(k, i, u)
                return a.v + (b.v - a.v) * ease_u(a, u)
        return k[-1].v

    def set(self, key, t, v, auto):
        if auto or key in self.kf:
            lst = self.kf.setdefault(key, [])
            for k in lst:
                if abs(k.t - t) < 0.05:
                    k.v = v
                    return
            lst.append(Key(round(t, 2), v, DEFAULT_EASE))
            lst.sort()
        else:
            self.base[key] = v

    # ---- tien ich key frame (theo thoi diem, ap dung cho moi kenh)
    def key_times(self):
        return sorted({round(k.t, 2) for v in self.kf.values() for k in v})

    def keys_at(self, t, tol=0.05):
        return [k for v in self.kf.values() for k in v if abs(k.t - t) < tol]

    # ---- luoi meo
    def mesh_channels(self):
        n = (self.mesh["cols"] + 1) * (self.mesh["rows"] + 1)
        return ["mw%s%d" % (a, i) for i in range(n) for a in "xy"]

    def mesh_off(self, i, j, t):
        """Do lech (% rong, % cao cua than lop) cua diem luoi (cot i, hang j)."""
        idx = j * (self.mesh["cols"] + 1) + i
        return self.get("mwx%d" % idx, t), self.get("mwy%d" % idx, t)

    def mesh_has_key(self, idx, t=None):
        """Diem luoi idx co key khong (t=None: o bat ky thoi diem nao; co t: dung tai t)."""
        for ch in ("mwx%d" % idx, "mwy%d" % idx):
            for k in self.kf.get(ch, []):
                if t is None or abs(k.t - t) < 0.05:
                    return True
        return False

    def toggle_keys(self, channels, t):
        """Co key tai t o moi kenh -> xoa; chua -> them (giu nguyen gia tri hien tai). Tra ve True neu vua THEM."""
        had = any(abs(k.t - t) < 0.05 for ch in channels for k in self.kf.get(ch, []))
        for ch in channels:
            if had:
                v = self.get(ch, t)
                rest = [k for k in self.kf.get(ch, []) if abs(k.t - t) >= 0.05]
                if rest:
                    self.kf[ch] = rest
                elif ch in self.kf:
                    self.base[ch] = v
                    del self.kf[ch]
            else:
                self.set(ch, t, self.get(ch, t), True)
        return not had

    def mesh_clear(self):
        for ch in [k for k in list(self.kf) + list(self.base) if k.startswith("mw")]:
            self.kf.pop(ch, None)
            self.loop.pop(ch, None)
            self.base.pop(ch, None)

    def mesh_active(self):
        return bool(self.mesh.get("on"))

    def _key_channels(self):
        return PKEYS + ["op"] + (self.mesh_channels() if self.mesh_active() else [])

    def add_keys(self, t):
        for ch in self._key_channels():
            self.set(ch, t, self.get(ch, t), True)

    def del_keys_at(self, t):
        for ch in list(self.kf):
            v = self.get(ch, t)
            rest = [k for k in self.kf[ch] if abs(k.t - t) >= 0.05]
            if rest:
                self.kf[ch] = rest
            else:
                self.base[ch] = v
                del self.kf[ch]

    def move_keys(self, t_old, t_new):
        for lst in self.kf.values():
            for k in lst:
                if abs(k.t - t_old) < 0.05:
                    k.t = t_new
            lst.sort()

    def set_ease_at(self, t, e):
        for k in self.keys_at(t):
            k.e = e
            k.bz = BEZ["ease_inout"] if e == "bezier" else None

    def set_ease_all(self, e):
        """Dat kieu noi suy cho MOI key cua lop (vd. lam muot toan bo chuyen dong)."""
        for lst in self.kf.values():
            for k in lst:
                k.e = e
                k.bz = BEZ["ease_inout"] if e == "bezier" else None

    def set_loop_all(self, mode):
        for ch in self._key_channels():
            self.loop[ch] = mode

    def clip_at(self, t):
        for c in self.clips:
            if c.start <= t <= c.start + c.dur:
                return c
        return None

    def alive(self, t):
        if not self.visible:
            return False
        if not self.timed:
            return True
        return any(c.start <= t <= c.start + c.dur for c in self.clips)

    def to_dict(self):
        return dict(name=self.name, kind=self.kind, color=self.color, text=self.text, visible=self.visible,
                    timed=self.timed, path=self.path, base=self.base, wfrac=self.wfrac, extra=self.extra, mesh=self.mesh,
                    kf={k: [x.to_list() for x in v] for k, v in self.kf.items()}, loop=self.loop,
                    clips=[[c.row, c.start, c.dur, getattr(c, "src_off", 0.0)] for c in self.clips])

    @staticmethod
    def from_dict(d):
        L = Layer(d["name"], d["kind"], d["color"])
        L.text, L.visible, L.timed, L.path = d.get("text", L.name), d.get("visible", True), d.get("timed", True), d.get("path")
        L.base.update(d.get("base", {}))
        L.wfrac = float(d.get("wfrac", 0.4))
        L.extra = dict(d.get("extra", {}))
        L.mesh = {"on": False, "cols": 3, "rows": 3, **d.get("mesh", {})}
        L.kf = {k: sorted(Key.from_list(x) for x in v) for k, v in d.get("kf", {}).items()}
        L.loop = dict(d.get("loop", {}))
        if L.path and L.kind == "image" and os.path.exists(L.path):
            L.pix = QPixmap(L.path)
        return L
