"""Hang so + mo hinh du lieu (Layer) dung chung."""
import os
from PyQt5.QtGui import QPixmap

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


class Layer:
    """Mot lop: thuoc tinh co so + key frame (noi suy tuyen tinh) + cac clip tren timeline."""

    def __init__(self, name, kind="shape", color="#7a2bff"):
        self.name, self.kind, self.color, self.text = name, kind, color, name
        self.visible, self.timed, self.path, self.pix = True, True, None, None
        self.base = {"pos0": 0.0, "pos1": 0.0, "pos2": 0.0, "rot0": 0.0, "rot1": 0.0, "rot2": 0.0,
                     "scl0": 100.0, "scl1": 100.0, "scl2": 100.0, "op": 100.0}
        self.kf, self.clips = {}, []

    def get(self, key, t):
        k = sorted(self.kf.get(key, []))
        if not k:
            return self.base[key]
        if t <= k[0][0]:
            return k[0][1]
        if t >= k[-1][0]:
            return k[-1][1]
        for (t0, v0), (t1, v1) in zip(k, k[1:]):
            if t0 <= t <= t1:
                return v0 + (v1 - v0) * (t - t0) / ((t1 - t0) or 1)
        return k[-1][1]

    def set(self, key, t, v, auto):
        if auto or key in self.kf:
            lst = self.kf.setdefault(key, [])
            for i, (tt, _) in enumerate(lst):
                if abs(tt - t) < 0.05:
                    lst[i] = (tt, v)
                    return
            lst.append((round(t, 2), v))
        else:
            self.base[key] = v

    def alive(self, t):
        if not self.visible:
            return False
        if not self.timed:
            return True
        return any(c.start <= t <= c.start + c.dur for c in self.clips)

    def to_dict(self):
        return dict(name=self.name, kind=self.kind, color=self.color, text=self.text, visible=self.visible,
                    timed=self.timed, path=self.path, base=self.base,
                    kf={k: [list(x) for x in v] for k, v in self.kf.items()},
                    clips=[[c.row, c.start, c.dur] for c in self.clips])

    @staticmethod
    def from_dict(d):
        L = Layer(d["name"], d["kind"], d["color"])
        L.text, L.visible, L.timed, L.path = d.get("text", L.name), d.get("visible", True), d.get("timed", True), d.get("path")
        L.base.update(d.get("base", {}))
        L.kf = {k: [tuple(x) for x in v] for k, v in d.get("kf", {}).items()}
        if L.path and L.kind == "image" and os.path.exists(L.path):
            L.pix = QPixmap(L.path)
        return L
