"""Hinh hoc vector thuan Python (khong phu thuoc Qt): duong Bezier, node, cat, lam tron net ve tay, xuat SVG."""
import math

KAPPA = 0.5522847498


class Node:
    """Diem neo (x, y) + tay nam vao (ix, iy) / ra (ox, oy) tinh theo do lech so voi diem neo."""
    __slots__ = ("x", "y", "ix", "iy", "ox", "oy", "smooth")

    def __init__(self, x, y, ix=0.0, iy=0.0, ox=0.0, oy=0.0, smooth=False):
        self.x, self.y, self.ix, self.iy, self.ox, self.oy, self.smooth = x, y, ix, iy, ox, oy, smooth

    def copy(self):
        return Node(self.x, self.y, self.ix, self.iy, self.ox, self.oy, self.smooth)

    def has_in(self):
        return abs(self.ix) > 1e-9 or abs(self.iy) > 1e-9

    def has_out(self):
        return abs(self.ox) > 1e-9 or abs(self.oy) > 1e-9

    def to_list(self):
        return [self.x, self.y, self.ix, self.iy, self.ox, self.oy, int(self.smooth)]

    @staticmethod
    def from_list(v):
        return Node(*v[:6], smooth=bool(v[6]) if len(v) > 6 else False)


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def cubic_point(p0, c1, c2, p1, t):
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p1[0],
            u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p1[1])


class Path:
    """Mot duong: danh sach node, dong/ho, vai tro ('cut' = vung cat, 'draw' = net ve) va kieu to/net."""

    def __init__(self, nodes=None, closed=False, role="cut", fill="#7a2bff", stroke="#ffffff", width=2.0, name="Đường"):
        self.nodes = nodes or []
        self.closed, self.role = closed, role
        self.fill, self.stroke, self.width, self.name = fill, stroke, width, name

    def copy(self):
        return Path([n.copy() for n in self.nodes], self.closed, self.role, self.fill, self.stroke, self.width, self.name)

    # ---- phan doan Bezier bac 3
    def segments(self):
        """Tra ve [(p0, c1, c2, p1)] cho tung doan (ke ca doan khep kin neu closed)."""
        out, n = [], self.nodes
        pairs = list(zip(n, n[1:])) + ([(n[-1], n[0])] if self.closed and len(n) > 1 else [])
        for a, b in pairs:
            out.append(((a.x, a.y), (a.x + a.ox, a.y + a.oy), (b.x + b.ix, b.y + b.iy), (b.x, b.y)))
        return out

    def flatten(self, per_seg=None):
        """Da giac xap xi duong cong (danh sach (x, y))."""
        pts = []
        for i, (p0, c1, c2, p1) in enumerate(self.segments()):
            ln = math.dist(p0, c1) + math.dist(c1, c2) + math.dist(c2, p1)
            steps = per_seg or max(8, min(64, int(ln / 4)))
            for k in range(steps if i < len(self.segments()) - 1 or self.closed else steps + 1):
                pts.append(cubic_point(p0, c1, c2, p1, k / steps))
        if len(self.nodes) == 1:
            pts = [(self.nodes[0].x, self.nodes[0].y)]
        return pts

    def bbox(self):
        pts = self.flatten() + [(n.x, n.y) for n in self.nodes]
        if not pts:
            return (0, 0, 0, 0)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def contains(self, x, y):
        """Diem nam trong duong (quy tac chan le). Chi co nghia voi duong dong."""
        if not self.closed or len(self.nodes) < 3:
            return False
        inside, pts = False, self.flatten()
        j = len(pts) - 1
        for i, (xi, yi) in enumerate(pts):
            xj, yj = pts[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
                inside = not inside
            j = i
        return inside

    def nearest(self, x, y):
        """Diem gan nhat tren duong: (chi so doan, t, khoang cach) hoac None."""
        best = None
        for si, (p0, c1, c2, p1) in enumerate(self.segments()):
            for k in range(41):
                t = k / 40
                px, py = cubic_point(p0, c1, c2, p1, t)
                d = math.hypot(px - x, py - y)
                if best is None or d < best[2]:
                    best = (si, t, d)
        return best

    def insert_node(self, seg, t):
        """Chen node vao doan seg tai t bang de Casteljau (khong lam doi hinh dang). Tra ve chi so node moi."""
        n = self.nodes
        a, b = n[seg], n[(seg + 1) % len(n)]
        p0, c1, c2, p1 = (a.x, a.y), (a.x + a.ox, a.y + a.oy), (b.x + b.ix, b.y + b.iy), (b.x, b.y)
        q0, q1, q2 = _lerp(p0, c1, t), _lerp(c1, c2, t), _lerp(c2, p1, t)
        r0, r1 = _lerp(q0, q1, t), _lerp(q1, q2, t)
        s = _lerp(r0, r1, t)
        a.ox, a.oy = q0[0] - a.x, q0[1] - a.y
        b.ix, b.iy = q2[0] - b.x, q2[1] - b.y
        node = Node(s[0], s[1], r0[0] - s[0], r0[1] - s[1], r1[0] - s[0], r1[1] - s[1], smooth=True)
        n.insert(seg + 1, node)
        return seg + 1

    def auto_smooth(self, i):
        """Dat tay nam tu dong muot cho node i dua tren 2 node ke ben."""
        n = self.nodes
        if len(n) < 2:
            return
        prev = n[(i - 1) % len(n)] if (self.closed or i > 0) else None
        nxt = n[(i + 1) % len(n)] if (self.closed or i < len(n) - 1) else None
        c = n[i]
        a, b = prev or c, nxt or c
        tx, ty = b.x - a.x, b.y - a.y
        c.ix, c.iy, c.ox, c.oy = -tx / 6, -ty / 6, tx / 6, ty / 6
        if prev is None:
            c.ix = c.iy = 0.0
        if nxt is None:
            c.ox = c.oy = 0.0
        c.smooth = True

    def make_corner(self, i):
        c = self.nodes[i]
        c.ix = c.iy = c.ox = c.oy = 0.0
        c.smooth = False

    def to_svg_d(self):
        n = self.nodes
        if not n:
            return ""
        d = ["M %.2f %.2f" % (n[0].x, n[0].y)]
        for p0, c1, c2, p1 in self.segments():
            d.append("C %.2f %.2f %.2f %.2f %.2f %.2f" % (c1[0], c1[1], c2[0], c2[1], p1[0], p1[1]))
        if self.closed:
            d.append("Z")
        return " ".join(d)

    def to_dict(self):
        return dict(nodes=[n.to_list() for n in self.nodes], closed=self.closed, role=self.role, fill=self.fill,
                    stroke=self.stroke, width=self.width, name=self.name)

    @staticmethod
    def from_dict(d):
        return Path([Node.from_list(v) for v in d["nodes"]], d.get("closed", False), d.get("role", "cut"),
                    d.get("fill", "#7a2bff"), d.get("stroke", "#ffffff"), d.get("width", 2.0), d.get("name", "Đường"))


# ------------------------------------------------------------------ tao hinh co ban
def rect_path(x0, y0, x1, y1, **kw):
    x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    return Path([Node(x0, y0), Node(x1, y0), Node(x1, y1), Node(x0, y1)], True, **kw)


def ellipse_path(x0, y0, x1, y1, **kw):
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, abs(x1 - x0) / 2, abs(y1 - y0) / 2
    k = KAPPA
    return Path([Node(cx, cy - ry, -rx * k, 0, rx * k, 0, True), Node(cx + rx, cy, 0, -ry * k, 0, ry * k, True),
                 Node(cx, cy + ry, rx * k, 0, -rx * k, 0, True), Node(cx - rx, cy, 0, ry * k, 0, -ry * k, True)], True, **kw)


# ------------------------------------------------------------------ net ve tay -> Bezier muot
def rdp(pts, eps):
    """Ramer-Douglas-Peucker: giu cac diem quan trong cua net ve tay."""
    if len(pts) < 3:
        return list(pts)
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy) or 1e-12
    idx, dmax = 0, 0.0
    for i in range(1, len(pts) - 1):
        d = abs(dy * pts[i][0] - dx * pts[i][1] + x1 * y0 - y1 * x0) / ln if ln > 1e-9 else math.dist(pts[i], pts[0])
        if d > dmax:
            idx, dmax = i, d
    if dmax <= eps:
        return [pts[0], pts[-1]]
    return rdp(pts[:idx + 1], eps)[:-1] + rdp(pts[idx:], eps)


def fit_freehand(points, eps, close=False):
    """Chuyen chuoi diem cua net ve tay thanh Path Bezier muot (don gian hoa roi dat tay nam kieu Catmull-Rom)."""
    pts = [points[0]] + [p for i, p in enumerate(points[1:]) if math.dist(p, points[i]) > 0.5]
    if close and len(pts) > 2 and math.dist(pts[0], pts[-1]) < max(eps * 4, 6):
        pts = pts[:-1]
    simp = rdp(pts, eps)
    if close and len(simp) > 2 and simp[0] == simp[-1]:
        simp = simp[:-1]
    p = Path([Node(x, y) for x, y in simp], closed=close)
    if len(p.nodes) >= 3:
        for i in range(len(p.nodes)):
            p.auto_smooth(i)
    return p
