"""Chat lieu cho lop (2D va 3D): nhua, kim loai, vang, kinh, vai, go.
2D: ve lop vao anh tam roi phu hieu ung len dung phan co noi dung (SourceAtop), luu cache theo noi dung lop.
3D: gk_3d dung lai anh nay cho mat truoc, them diem sang phan chieu (specular) theo den va mau canh theo chat lieu."""
import json
import math
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (QColor, QImage, QPainter, QPen, QBrush, QPixmap, QLinearGradient, QRadialGradient,
                           QPolygonF)

MATS = [("none", "Không"), ("plastic", "Nhựa"), ("metal", "Kim loại"), ("gold", "Vàng"), ("glass", "Kính"),
        ("fabric", "Vải"), ("wood", "Gỗ")]
SPEC = {"plastic": (0.55, 40), "metal": (1.0, 24), "gold": (1.0, 24), "glass": (0.9, 90), "fabric": (0.05, 4),
        "wood": (0.12, 10)}                                   # (he so phan chieu, do bong)
SIDE = {"metal": (172, 174, 182), "gold": (214, 172, 62), "wood": (140, 92, 50), "glass": (176, 208, 232)}   # mau canh khoi 3D
KINDS = ("shape", "text", "image", "video")


def mat_of(L):
    """(loai, cuong do 0..1) hoac None."""
    m = L.extra.get("mat") if L.kind in KINDS else None
    if not m or m.get("type", "none") == "none":
        return None
    return m["type"], max(0.0, min(1.0, m.get("amt", 70) / 100.0))


def glass_alpha(amt):
    return 1.0 - 0.6 * amt


def _c(rgb, a):
    return QColor(rgb[0], rgb[1], rgb[2], max(0, min(255, int(a * 255))))


def _bands(w, h, stops, a):
    g = QLinearGradient(0, 0, w, h)
    for pos, rgb, al in stops:
        g.setColorAt(pos, _c(rgb, al * a))
    return g


def apply(img, typ, amt):
    """Phu hieu ung chat lieu len anh (ARGB premultiplied) tai cho, chi o vung co noi dung."""
    w, h = img.width(), img.height()
    q = QPainter(img)
    q.setRenderHint(QPainter.Antialiasing)
    q.setPen(Qt.NoPen)
    rect = QRectF(0, 0, w, h)
    if typ == "glass":
        q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        q.fillRect(rect, QColor(255, 255, 255, int(255 * glass_alpha(amt))))
    q.setCompositionMode(QPainter.CompositionMode_SourceAtop)
    a = amt
    if typ == "plastic":
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, _c((255, 255, 255), 0.30 * a))
        g.setColorAt(0.45, _c((255, 255, 255), 0.0))
        g.setColorAt(0.55, _c((0, 0, 0), 0.0))
        g.setColorAt(1, _c((0, 0, 0), 0.38 * a))
        q.fillRect(rect, g)
        r = max(w, h) * 0.45
        rg = QRadialGradient(QPointF(w * 0.3, h * 0.25), r)
        rg.setColorAt(0, _c((255, 255, 255), 0.6 * a))
        rg.setColorAt(1, _c((255, 255, 255), 0.0))
        q.fillRect(rect, rg)
    elif typ in ("metal", "gold"):
        if typ == "metal":
            st = [(0, (236, 236, 242), 0.85), (0.22, (92, 94, 102), 0.72), (0.45, (248, 249, 252), 0.86),
                  (0.7, (72, 74, 82), 0.72), (1, (212, 214, 222), 0.82)]
        else:
            st = [(0, (255, 238, 156), 0.88), (0.22, (150, 106, 22), 0.75), (0.45, (255, 246, 196), 0.88),
                  (0.7, (122, 82, 12), 0.75), (1, (242, 202, 92), 0.85)]
        q.fillRect(rect, _bands(w, h, st, a))
    elif typ == "glass":
        q.fillRect(rect, QColor(190, 225, 255, int(40 * a)))
        for x0, x1, al in ((0.15, 0.40, 0.34), (0.50, 0.58, 0.22)):
            q.setBrush(_c((255, 255, 255), al * a))
            q.drawPolygon(QPolygonF([QPointF(w * x0, 0), QPointF(w * x1, 0), QPointF(w * (x1 - 0.30), h), QPointF(w * (x0 - 0.30), h)]))
    elif typ == "fabric":
        tile = QPixmap(6, 6)
        tile.fill(Qt.transparent)
        t = QPainter(tile)
        t.setPen(QPen(_c((0, 0, 0), 0.30 * a), 1))
        t.drawLine(0, 1, 6, 1)
        t.drawLine(4, 0, 4, 6)
        t.setPen(QPen(_c((255, 255, 255), 0.22 * a), 1))
        t.drawLine(0, 4, 6, 4)
        t.drawLine(1, 0, 1, 6)
        t.end()
        q.fillRect(rect, QBrush(tile))
        vg = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.75)
        vg.setColorAt(0.5, _c((0, 0, 0), 0.0))
        vg.setColorAt(1, _c((0, 0, 0), 0.30 * a))
        q.fillRect(rect, vg)
    elif typ == "wood":
        q.fillRect(rect, _c((150, 100, 55), 0.78 * a))
        q.setBrush(Qt.NoBrush)
        q.setPen(QPen(_c((60, 35, 15), 0.38 * a), 1.2))
        step = max(4, int(h / 28))
        for k, y in enumerate(range(0, int(h) + step, step)):
            pts = [QPointF(x, y + 3.5 * math.sin(x / 38.0 + k * 1.7) + 2 * math.sin(x / 11.0 + k)) for x in range(0, int(w) + 12, 12)]
            q.drawPolyline(QPolygonF(pts))
        sh = QLinearGradient(0, 0, 0, h)
        sh.setColorAt(0, _c((255, 230, 190), 0.12 * a))
        sh.setColorAt(1, _c((0, 0, 0), 0.18 * a))
        q.setPen(Qt.NoPen)
        q.fillRect(rect, sh)
    q.end()


def paint(st, p, L, b):
    """Ve lop L (hop b, toa do cua than lop) co chat lieu len painter p."""
    typ, amt = mat_of(L)
    iw, ih = int(math.ceil(b.width())) + 4, int(math.ceil(b.height())) + 4
    cache = st.__dict__.setdefault("_matcache", {})
    key = None
    if L.kind != "video":                       # video doi moi khung: khong cache
        pm = getattr(L, "pix", None)
        key = (typ, round(amt, 2), L.color, L.text, iw, ih, L.kind, bool(L.mesh.get("on")),
               json.dumps(L.extra, sort_keys=True, default=str), pm.cacheKey() if pm is not None and not pm.isNull() else 0)
    hit = cache.get(id(L))
    if key is not None and hit and hit[0] == key:
        img = hit[1]
    else:
        img = QImage(iw, ih, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        ip = QPainter(img)
        ip.setRenderHint(QPainter.Antialiasing)
        ip.setRenderHint(QPainter.SmoothPixmapTransform)
        ip.translate(iw / 2.0, ih / 2.0)
        st.draw_full(ip, L, b)
        ip.end()
        apply(img, typ, amt)
        if key is not None:
            cache[id(L)] = (key, img)
    p.drawImage(QRectF(-iw / 2.0, -ih / 2.0, iw, ih), img)
