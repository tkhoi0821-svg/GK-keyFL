"""Hang so + mo hinh du lieu (Layer) dung chung."""
import os, math
from PySide6.QtGui import QPixmap

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "gk_keyfl_logo.png")
TOTAL = 30.0
TRACK_H, RULER_H = 44, 26
TRACKS = ["Text", "Overlay", "Video", "Audio"]
COLORS = {"Text": "#e0a526", "Overlay": "#9b59d0", "Video": "#2f8fe0", "Audio": "#2fb37a"}

KINDS = {"Hình vuông": ("shape", 1, "#7a2bff"), "Văn bản": ("text", 0, "#ffffff"),
         "Hình ảnh": ("image", 1, "#2f8fe0"), "Video": ("video", 2, "#2f8fe0"), "Âm thanh": ("audio", 3, "#2fb37a")}
BODY = {"shape": (.24, .36), "text": (.40, .14), "image": (.36, .24), "video": (.36, .24)}
PKEYS = ["pos0", "pos1", "pos2", "rot0", "rot1", "rot2", "scl0", "scl1", "scl2"]
CHANNELS = [("pos0", "Vị trí X"), ("pos1", "Vị trí Y"), ("pos2", "Vị trí Z"),
            ("rot0", "Xoay X"), ("rot1", "Xoay Y"), ("rot2", "Xoay Z"),
            ("scl0", "Tỉ lệ X"), ("scl1", "Tỉ lệ Y"), ("op", "Độ mờ")]


# ====================================================================== noi suy / easing
EASES = [("linear", "Tuyến tính"), ("hold", "Dừng (Hold)"), ("ease", "Ease"), ("ease_in", "Ease In"),
         ("ease_out", "Ease Out"), ("ease_inout", "Ease In-Out"), ("back", "Vượt (Back)"),
         ("bounce", "Nảy (Bounce)"), ("elastic", "Đàn hồi (Elastic)"), ("cyclic", "Cyclic (sóng lặp)"),
         ("noise", "Rung (Noise)"), ("bezier", "Tuỳ chỉnh (Bezier)")]
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


def ease_u(k, u):
    """Bien u (0..1 trong doan tu key k den key ke tiep) thanh tien do 0..1 theo kieu noi suy cua k."""
    if u >= 1:
        return 1.0
    e = k.e
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
    return bezier_y(*k.handles(), u)


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
                     "scl0": 100.0, "scl1": 100.0, "scl2": 100.0, "op": 100.0}
        self.kf, self.clips, self.loop = {}, [], {}

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
            return self.base[key]
        k = sorted(k)
        if len(k) >= 2:
            t = self._wrap(key, k, t)
        if t <= k[0].t:
            return k[0].v
        if t >= k[-1].t:
            return k[-1].v
        for a, b in zip(k, k[1:]):
            if a.t <= t <= b.t:
                u = (t - a.t) / ((b.t - a.t) or 1)
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

    def add_keys(self, t):
        for ch in PKEYS + ["op"]:
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

    def set_loop_all(self, mode):
        for ch in PKEYS + ["op"]:
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
                    timed=self.timed, path=self.path, base=self.base, wfrac=self.wfrac,
                    kf={k: [x.to_list() for x in v] for k, v in self.kf.items()}, loop=self.loop,
                    clips=[[c.row, c.start, c.dur, getattr(c, "src_off", 0.0)] for c in self.clips])

    @staticmethod
    def from_dict(d):
        L = Layer(d["name"], d["kind"], d["color"])
        L.text, L.visible, L.timed, L.path = d.get("text", L.name), d.get("visible", True), d.get("timed", True), d.get("path")
        L.base.update(d.get("base", {}))
        L.wfrac = float(d.get("wfrac", 0.4))
        L.kf = {k: sorted(Key.from_list(x) for x in v) for k, v in d.get("kf", {}).items()}
        L.loop = dict(d.get("loop", {}))
        if L.path and L.kind == "image" and os.path.exists(L.path):
            L.pix = QPixmap(L.path)
        return L
