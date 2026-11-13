"""Cua so Vector Editor: dock rieng, keo tha duoc, co cong cu ve (But, Chon, Node, Hinh co ban) + tach nen.
Dung de 'cat anh vector': ve mot duong bao quanh dau/tay..., phan trong duong tach thanh lop rieng de chinh."""
import os
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal
from PySide6.QtGui import (QColor, QPainter, QPen, QBrush, QFont, QPixmap, QImage, QPainterPath, QPolygonF,
                         QImageReader, QIcon)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QComboBox,
                             QColorDialog, QFileDialog, QScrollArea, QFrame, QMenu, QMessageBox, QButtonGroup,
                             QDockWidget)
import gk_theme as theme
from gk_theme import T, mk
from gk_panels import styled, DockTitle, Section, ScrubSpin
from gk_vector import Path, Node, rect_path, ellipse_path, fit_freehand

TOOLS = (("select", "Chọn  (V)"), ("node", "Node  (A)"), ("pen", "Bút  (P)"), ("brush", "Vẽ tay  (B)"),
         ("rect", "Hình chữ nhật  (M)"), ("oval", "Hình tròn  (O)"))


class VectorCanvas(QWidget):
    """Mat phang ve: anh nen (neu dang cat tu 1 anh) + danh sach Path. Toa do Path la pixel cua anh nen."""
    changed = Signal()
    path_picked = Signal(object)

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.bg = None                 # QPixmap lam nen (anh dang cat), co the None (ve tu do)
        self.paths = []
        self.sel = None                # Path dang chon
        self.node_i = None             # chi so node dang chon (cong cu Node)
        self.tool = "select"
        self.zoom, self.off = 1.0, QPointF(0, 0)
        self.drag = None
        self.fill_col, self.stroke_col = "#7a2bff", "#ffffff"
        theme.bus.changed.connect(self.update)

    # ---------------------------------------------------------------- toa do
    def to_img(self, pos):
        return ((pos.x() - self.off.x()) / self.zoom, (pos.y() - self.off.y()) / self.zoom)

    def to_scr(self, x, y):
        return QPointF(x * self.zoom + self.off.x(), y * self.zoom + self.off.y())

    def fit(self):
        if self.bg is None:
            self.zoom, self.off = 1.0, QPointF(40, 40)
            return
        w, h = self.bg.width(), self.bg.height()
        self.zoom = max(0.05, min((self.width() - 60) / max(1, w), (self.height() - 60) / max(1, h), 4.0))
        self.off = QPointF((self.width() - w * self.zoom) / 2, (self.height() - h * self.zoom) / 2)
        self.update()

    def set_bg(self, pm):
        self.bg = pm
        self.fit()

    def set_tool(self, t):
        self.tool, self.node_i, self.drag = t, None, None
        self.setCursor(Qt.CrossCursor if t in ("pen", "brush", "rect", "oval") else Qt.ArrowCursor)
        self.update()

    def set_sel(self, p):
        self.sel, self.node_i = p, None
        self.path_picked.emit(p)
        self.update()

    # ---------------------------------------------------------------- ve
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(T["bg0"]))
        s = 18
        for i in range(self.width() // s + 1):
            for j in range(self.height() // s + 1):
                p.fillRect(i * s, j * s, s, s, QColor(T["checker_a"] if (i + j) % 2 else T["checker_b"]))
        if self.bg is not None:
            w, h = self.bg.width() * self.zoom, self.bg.height() * self.zoom
            p.drawPixmap(QRectF(self.off, QSize(int(w), int(h))), self.bg, QRectF(self.bg.rect()))
            p.setPen(QPen(QColor(T["line_hi"]), 1))
            p.drawRect(QRectF(self.off, QSize(int(w), int(h))))
        for path in self.paths:
            self.draw_path(p, path, path is self.sel)
        if self.drag and self.drag.get("tmp"):
            self.draw_path(p, self.drag["tmp"], True, dashed=True)
        if self.sel is not None and self.tool == "node":
            self.draw_handles(p, self.sel)

    def qpath(self, path):
        qp = QPainterPath()
        segs = path.segments()
        if not segs:
            if path.nodes:
                qp.addEllipse(self.to_scr(path.nodes[0].x, path.nodes[0].y), 2, 2)
            return qp
        qp.moveTo(self.to_scr(*segs[0][0]))
        for p0, c1, c2, p1 in segs:
            qp.cubicTo(self.to_scr(*c1), self.to_scr(*c2), self.to_scr(*p1))
        if path.closed:
            qp.closeSubpath()
        return qp

    def draw_path(self, p, path, sel, dashed=False):
        qp = self.qpath(path)
        if path.role == "cut":
            col = QColor("#ffb020" if sel else "#ffd23f")
            pen = QPen(col, 2 if sel else 1.4, Qt.DashLine if (dashed or not sel) else Qt.SolidLine)
            p.setPen(pen)
            p.setBrush(QColor(255, 178, 32, 40) if sel else Qt.NoBrush)
        else:
            p.setPen(QPen(QColor(path.stroke), max(1.0, path.width * self.zoom)) if path.width > 0 else Qt.NoPen)
            p.setBrush(QColor(path.fill)) if (path.closed and path.fill not in (None, "none")) else p.setBrush(Qt.NoBrush)
            if sel:
                p.setPen(QPen(QColor("#38b6ff"), max(1.0, path.width * self.zoom) + 1.2))
        p.drawPath(qp)
        if sel and path.role == "draw":
            p.setPen(QPen(QColor("#38b6ff"), 1, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            b = path.bbox()
            p.drawRect(QRectF(self.to_scr(b[0], b[1]), self.to_scr(b[2], b[3])))

    def draw_handles(self, p, path):
        for i, n in enumerate(path.nodes):
            c = self.to_scr(n.x, n.y)
            if n.has_in():
                hi = self.to_scr(n.x + n.ix, n.y + n.iy)
                p.setPen(QPen(QColor("#9a9aa8"), 1))
                p.drawLine(c, hi)
                p.setPen(QPen(QColor("#000"), 1))
                p.setBrush(QColor("#38b6ff"))
                p.drawEllipse(hi, 4, 4)
            if n.has_out():
                ho = self.to_scr(n.x + n.ox, n.y + n.oy)
                p.setPen(QPen(QColor("#9a9aa8"), 1))
                p.drawLine(c, ho)
                p.setPen(QPen(QColor("#000"), 1))
                p.setBrush(QColor("#38b6ff"))
                p.drawEllipse(ho, 4, 4)
        for i, n in enumerate(path.nodes):
            c = self.to_scr(n.x, n.y)
            hot = i == self.node_i
            p.setPen(QPen(QColor("#000"), 1))
            p.setBrush(QColor("#ffffff") if hot else QColor("#ffd23f"))
            if n.smooth:
                p.drawEllipse(c, 6 if hot else 5, 6 if hot else 5)
            else:
                p.drawRect(QRectF(c.x() - 5, c.y() - 5, 10, 10))

    # ---------------------------------------------------------------- tuong tac
    def hit_node(self, path, pos):
        for i, n in enumerate(path.nodes):
            if (self.to_scr(n.x, n.y) - pos).manhattanLength() < 10:
                return i
        return None

    def hit_path(self, pos):
        x, y = self.to_img(pos)
        for path in reversed(self.paths):
            if path.closed and path.contains(x, y):
                return path
            near = path.nearest(x, y)
            if near and near[2] * self.zoom < 8:
                return path
        return None

    def mousePressEvent(self, e):
        self.setFocus()
        pos = QPointF(e.pos())
        if e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton and e.modifiers() & Qt.AltModifier):
            self.drag = dict(m="pan", last=pos)
            self.setCursor(Qt.ClosedHandCursor)
            return
        if e.button() != Qt.LeftButton:
            return
        t = self.tool
        if t == "select":
            hp = self.hit_path(pos)
            self.set_sel(hp)
            if hp is not None:
                self.drag = dict(m="move", last=pos, path=hp)
        elif t == "node":
            if self.sel is not None:
                i = self.hit_node(self.sel, pos)
                if i is not None:
                    self.node_i = i
                    self.drag = dict(m="node", last=pos)
                    self.update()
                    return
                hi = self.hit_in_out(self.sel, pos)
                if hi is not None:
                    self.node_i = hi[0]
                    self.drag = dict(m="handle", last=pos, which=hi[1])
                    return
                near = self.sel.nearest(*self.to_img(pos))
                if near and near[2] * self.zoom < 10:
                    idx = self.sel.insert_node(near[0], near[1])
                    self.node_i = idx
                    self.changed.emit()
                    self.update()
                    return
            hp = self.hit_path(pos)
            self.set_sel(hp)
        elif t == "pen":
            self.pen_click(pos)
        elif t == "brush":
            self.drag = dict(m="brush", pts=[self.to_img(pos)])
        elif t in ("rect", "oval"):
            self.drag = dict(m=t, p0=self.to_img(pos))

    def hit_in_out(self, path, pos):
        for i, n in enumerate(path.nodes):
            if n.has_in() and (self.to_scr(n.x + n.ix, n.y + n.iy) - pos).manhattanLength() < 9:
                return (i, "i")
            if n.has_out() and (self.to_scr(n.x + n.ox, n.y + n.oy) - pos).manhattanLength() < 9:
                return (i, "o")
        return None

    def pen_click(self, pos):
        d = self.drag
        x, y = self.to_img(pos)
        if d and d.get("m") == "pen":
            n0 = d["tmp"].nodes[0]
            if len(d["tmp"].nodes) > 2 and (self.to_scr(n0.x, n0.y) - pos).manhattanLength() < 10:
                d["tmp"].closed = True
                self.finish_draw(d["tmp"])
                return
            d["tmp"].nodes.append(Node(x, y))
            self.update()
            return
        p = Path([Node(x, y)], False, role="draw", fill=self.fill_col, stroke=self.stroke_col)
        self.drag = dict(m="pen", tmp=p)
        self.update()

    def mouseDoubleClickEvent(self, e):
        if self.tool == "pen" and self.drag and self.drag.get("m") == "pen":
            self.finish_draw(self.drag["tmp"])
        elif self.tool == "node" and self.sel is not None and self.node_i is not None:
            n = self.sel.nodes[self.node_i]
            self.sel.make_corner(self.node_i) if n.smooth else self.sel.auto_smooth(self.node_i)
            self.changed.emit()
            self.update()

    def mouseMoveEvent(self, e):
        d, pos = self.drag, QPointF(e.pos())
        if d is None:
            return
        m = d["m"]
        if m == "pan":
            self.off += pos - d["last"]
            d["last"] = pos
        elif m == "move" and self.sel is not None:
            dx, dy = (pos - d["last"]) / self.zoom
            for n in self.sel.nodes:
                n.x += dx.x() if hasattr(dx, "x") else dx
            d["last"] = pos
        elif m == "node" and self.sel is not None and self.node_i is not None:
            n = self.sel.nodes[self.node_i]
            n.x, n.y = self.to_img(pos)
        elif m == "handle" and self.sel is not None and self.node_i is not None:
            n = self.sel.nodes[self.node_i]
            x, y = self.to_img(pos)
            if d["which"] == "i":
                n.ix, n.iy = x - n.x, y - n.y
                if n.smooth:
                    r = (n.ox ** 2 + n.oy ** 2) ** 0.5
                    il = (n.ix ** 2 + n.iy ** 2) ** 0.5 or 1
                    n.ox, n.oy = -n.ix / il * r, -n.iy / il * r
            else:
                n.ox, n.oy = x - n.x, y - n.y
                if n.smooth:
                    r = (n.ix ** 2 + n.iy ** 2) ** 0.5
                    ol = (n.ox ** 2 + n.oy ** 2) ** 0.5 or 1
                    n.ix, n.iy = -n.ox / ol * r, -n.oy / ol * r
        elif m == "brush":
            d["pts"].append(self.to_img(pos))
        elif m in ("rect", "oval"):
            x1, y1 = self.to_img(pos)
            maker = rect_path if m == "rect" else ellipse_path
            d["tmp"] = maker(d["p0"][0], d["p0"][1], x1, y1, role="draw", fill=self.fill_col, stroke=self.stroke_col)
        self.update()

    def mouseReleaseEvent(self, e):
        d = self.drag
        if d and d["m"] == "brush" and len(d["pts"]) > 1:
            close = d["pts"][0] != d["pts"][-1] and (abs(d["pts"][0][0] - d["pts"][-1][0]) < 14 / self.zoom and
                                                      abs(d["pts"][0][1] - d["pts"][-1][1]) < 14 / self.zoom)
            p = fit_freehand(d["pts"], 2.5 / self.zoom, close=close)
            p.role, p.fill, p.stroke = ("draw" if close else "draw"), self.fill_col, self.stroke_col
            self.finish_draw(p)
        elif d and d["m"] in ("rect", "oval") and d.get("tmp") is not None:
            self.finish_draw(d["tmp"])
        elif d and d["m"] in ("move", "node", "handle"):
            self.changed.emit()
        if not (d and d["m"] == "pen"):
            self.drag = None
        self.setCursor(Qt.CrossCursor if self.tool in ("pen", "brush", "rect", "oval") else Qt.ArrowCursor)
        self.update()

    def finish_draw(self, path):
        self.paths.append(path)
        self.drag = None
        self.set_sel(path)
        self.changed.emit()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.sel is not None:
            self.paths.remove(self.sel)
            self.set_sel(None)
            self.changed.emit()
        elif e.key() == Qt.Key_Escape:
            if self.drag and self.drag.get("m") == "pen" and len(self.drag["tmp"].nodes) > 1:
                self.finish_draw(self.drag["tmp"])
            else:
                self.drag = None
                self.set_sel(None)
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter) and self.drag and self.drag.get("m") == "pen":
            self.finish_draw(self.drag["tmp"])
        elif e.key() == Qt.Key_Home:
            self.fit()
        else:
            super().keyPressEvent(e)

    def wheelEvent(self, e):
        f = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        anchor = QPointF(e.pos())
        img_before = self.to_img(anchor)
        self.zoom = max(0.05, min(8.0, self.zoom * f))
        new_scr = self.to_scr(*img_before)
        self.off += anchor - new_scr
        self.update()

    # ---------------------------------------------------------------- cat vung tu anh nen
    def cut_mask_image(self, path):
        """Ve duong 'cut' da chon thanh anh mat na trang/den (kich thuoc = anh nen), dung alpha cho lop moi."""
        if self.bg is None:
            return None
        img = QImage(self.bg.width(), self.bg.height(), QImage.Format_Grayscale8)
        img.fill(0)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        qp = QPainterPath()
        segs = path.segments()
        if segs:
            qp.moveTo(QPointF(*segs[0][0]))
            for p0, c1, c2, p1 in segs:
                qp.cubicTo(QPointF(*c1), QPointF(*c2), QPointF(*p1))
            qp.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawPath(qp)
        p.end()
        return img


class VectorWindow(QWidget):
    """Toan bo cua so Vector Editor: thanh cong cu doc | canvas | bang thuoc tinh duong.
    Dat trong QDockWidget rieng nen keo tha, tach cua so nhu moi panel khac."""
    cut_requested = Signal(object, object)      # (QImage mat_na, Path) -> Editor tao lop moi tu vung cat

    def __init__(self):
        super().__init__()
        styled(self, "Panel")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = styled(QWidget(), "ViewBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(10, 5, 10, 5)
        h.setSpacing(6)
        self.open_btn = QPushButton("⇪ Mở ảnh…")
        self.open_btn.setObjectName("SmallBtn")
        self.fit_btn = QPushButton("⤢ Vừa khung")
        self.fit_btn.setObjectName("SmallBtn")
        for b in (self.open_btn, self.fit_btn):
            h.addWidget(b)
        h.addStretch()
        self.hint = QLabel("Bút: nhấp từng điểm quanh phần cần cắt, Enter hoặc nhấp lại điểm đầu để đóng")
        self.hint.setObjectName("Hint")
        h.addWidget(self.hint)
        root.addWidget(bar)

        body = QHBoxLayout()
        body.setSpacing(0)
        rail = styled(QWidget(), "Rail")
        rail.setFixedWidth(48)
        rv = QVBoxLayout(rail)
        rv.setContentsMargins(6, 8, 6, 8)
        rv.setSpacing(4)
        self.grp = QButtonGroup(self)
        self.btns = {}
        for key, tip in TOOLS:
            b = QPushButton(TOOL_GLYPH.get(key, "?"))
            b.setObjectName("Tool")
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setStyleSheet("font-size:16px;")
            self.grp.addButton(b)
            rv.addWidget(b)
            self.btns[key] = b
            b.clicked.connect(lambda _=False, k=key: self.set_tool(k))
        self.btns["select"].setChecked(True)
        rv.addStretch()
        body.addWidget(rail)

        self.canvas = VectorCanvas()
        body.addWidget(self.canvas, 1)

        side = QScrollArea()
        side.setWidgetResizable(True)
        side.setFixedWidth(230)
        side.setFrameShape(QFrame.NoFrame)
        pane = styled(QWidget(), "Panel")
        pv = QVBoxLayout(pane)
        pv.setContentsMargins(10, 10, 10, 10)
        pv.setSpacing(10)

        s1 = Section("Màu")
        row = QHBoxLayout()
        self.fill_btn, self.stroke_btn = QPushButton("Tô màu"), QPushButton("Viền")
        self.fill_btn.setObjectName("SmallBtn")
        self.stroke_btn.setObjectName("SmallBtn")
        row.addWidget(self.fill_btn)
        row.addWidget(self.stroke_btn)
        s1.bl.addLayout(row)
        self.width_sp = ScrubSpin("", 0.2)
        self.width_sp.setRange(0, 40)
        self.width_sp.setSuffix(" px")
        wr = QHBoxLayout()
        wl = QLabel("Độ dày viền")
        wl.setObjectName("Sub")
        wr.addWidget(wl)
        wr.addWidget(self.width_sp)
        s1.bl.addLayout(wr)
        pv.addWidget(s1)

        s2 = Section("Vùng cắt (để tách lớp)")
        self.role_cb = QComboBox()
        self.role_cb.addItem("Vùng cắt (ẩn trong ảnh gốc)", "cut")
        self.role_cb.addItem("Nét vẽ (hiện khi xuất)", "draw")
        s2.bl.addWidget(self.role_cb)
        self.cut_btn = QPushButton("✂  Cắt thành lớp mới")
        self.cut_btn.setObjectName("Accent")
        self.cut_btn.setToolTip("Phần bên trong đường đang chọn sẽ thành một lớp riêng để chỉnh/di chuyển")
        s2.bl.addWidget(self.cut_btn)
        hint2 = QLabel("Vẽ đường bao quanh đầu, tay… rồi bấm Cắt. Lớp gốc giữ nguyên; lớp mới chỉ chứa phần trong đường.")
        hint2.setObjectName("Hint")
        hint2.setWordWrap(True)
        s2.bl.addWidget(hint2)
        pv.addWidget(s2)

        s3 = Section("Danh sách đường")
        self.list_lbl = QLabel("Chưa có đường nào")
        self.list_lbl.setObjectName("Hint")
        self.list_lbl.setWordWrap(True)
        s3.bl.addWidget(self.list_lbl)
        delrow = QHBoxLayout()
        self.del_btn = QPushButton("✕ Xoá đường đã chọn")
        self.del_btn.setObjectName("SmallBtn")
        self.clear_btn = QPushButton("Xoá hết")
        self.clear_btn.setObjectName("SmallBtn")
        delrow.addWidget(self.del_btn)
        delrow.addWidget(self.clear_btn)
        s3.bl.addLayout(delrow)
        pv.addWidget(s3)
        pv.addStretch()
        side.setWidget(pane)
        body.addWidget(side)
        root.addLayout(body, 1)

        self.open_btn.clicked.connect(self.open_image)
        self.fit_btn.clicked.connect(self.canvas.fit)
        self.fill_btn.clicked.connect(self.pick_fill)
        self.stroke_btn.clicked.connect(self.pick_stroke)
        self.width_sp.valueChanged.connect(self._width)
        self.role_cb.activated.connect(self._role)
        self.cut_btn.clicked.connect(self.do_cut)
        self.del_btn.clicked.connect(self.del_sel)
        self.clear_btn.clicked.connect(self.clear_all)
        self.canvas.changed.connect(self._refresh_list)
        self.canvas.path_picked.connect(self._sync_sel)
        self._swatches()
        self._refresh_list()

    def _swatches(self):
        for b, col in ((self.fill_btn, self.canvas.fill_col), (self.stroke_btn, self.canvas.stroke_col)):
            b.setStyleSheet("QPushButton{background:%s;color:%s;}" % (col, "#fff" if QColor(col).lightness() < 150 else "#000"))

    def set_tool(self, k):
        self.canvas.set_tool(k)
        self.hint.setText({"select": "Nhấp để chọn đường, kéo để di chuyển cả đường",
                           "node": "Nhấp đúp 1 node để đổi góc nhọn / bo tròn · nhấp đúp trên đường để thêm node",
                           "pen": "Bút: nhấp từng điểm quanh phần cần cắt, Enter hoặc nhấp lại điểm đầu để đóng",
                           "brush": "Vẽ tay: giữ chuột và kéo quanh phần cần cắt, thả ra để tự làm mượt",
                           "rect": "Kéo để vẽ hình chữ nhật", "oval": "Kéo để vẽ hình tròn / bầu dục"}[k])

    def open_image(self):
        f, _ = QFileDialog.getOpenFileName(self, "Mở ảnh để cắt vector", "", "Ảnh (*.png *.jpg *.jpeg *.bmp *.webp)")
        if f:
            self.load_image(f)

    def load_image(self, path):
        rd = QImageReader(path)
        rd.setAutoTransform(True)
        pm = QPixmap.fromImageReader(rd)
        if pm.isNull():
            QMessageBox.warning(self, "Lỗi", "Không mở được ảnh:\n" + path)
            return
        self.canvas.set_bg(pm)
        self.canvas.src_path = path

    def pick_fill(self):
        c = QColorDialog.getColor(QColor(self.canvas.fill_col), self)
        if c.isValid():
            self.canvas.fill_col = c.name()
            self._apply_sel()

    def pick_stroke(self):
        c = QColorDialog.getColor(QColor(self.canvas.stroke_col), self)
        if c.isValid():
            self.canvas.stroke_col = c.name()
            self._apply_sel()

    def _apply_sel(self):
        p = self.canvas.sel
        if p is not None and p.role == "draw":
            p.fill, p.stroke = self.canvas.fill_col, self.canvas.stroke_col
            self.canvas.changed.emit()
        self._swatches()
        self.canvas.update()

    def _width(self, v):
        p = self.canvas.sel
        if p is not None:
            p.width = float(v)
            self.canvas.changed.emit()
            self.canvas.update()

    def _role(self, _):
        p = self.canvas.sel
        if p is not None:
            p.role = self.role_cb.currentData()
            self.canvas.changed.emit()
            self.canvas.update()

    def _sync_sel(self, p):
        has = p is not None
        self.width_sp.setEnabled(has)
        self.role_cb.setEnabled(has)
        self.cut_btn.setEnabled(has and p.closed)
        if has:
            self.width_sp.blockSignals(True)
            self.width_sp.setValue(p.width)
            self.width_sp.blockSignals(False)
            self.role_cb.blockSignals(True)
            self.role_cb.setCurrentIndex(self.role_cb.findData(p.role))
            self.role_cb.blockSignals(False)
            self.canvas.fill_col, self.canvas.stroke_col = p.fill, p.stroke
            self._swatches()
        self._refresh_list()

    def _refresh_list(self):
        n = len(self.canvas.paths)
        cuts = sum(1 for p in self.canvas.paths if p.role == "cut")
        if n == 0:
            self.list_lbl.setText("Chưa có đường nào")
        else:
            self.list_lbl.setText("%d đường (%d vùng cắt)%s" % (n, cuts, "  ·  đang chọn 1" if self.canvas.sel else ""))

    def del_sel(self):
        if self.canvas.sel is not None:
            self.canvas.paths.remove(self.canvas.sel)
            self.canvas.set_sel(None)
            self.canvas.changed.emit()

    def clear_all(self):
        if self.canvas.paths and QMessageBox.question(self, "Xoá hết", "Xoá toàn bộ %d đường?" % len(self.canvas.paths)) == QMessageBox.Yes:
            self.canvas.paths.clear()
            self.canvas.set_sel(None)
            self.canvas.changed.emit()

    def do_cut(self):
        p = self.canvas.sel
        if p is None or not p.closed or self.canvas.bg is None:
            QMessageBox.information(self, "Cắt ảnh vector", "Hãy mở một ảnh, vẽ một đường khép kín quanh phần cần "
                                     "cắt (Bút hoặc Vẽ tay), chọn đường đó rồi bấm Cắt.")
            return
        mask = self.canvas.cut_mask_image(p)
        if mask is not None:
            self.cut_requested.emit(mask, p)


TOOL_GLYPH = {"select": "↖", "node": "✛", "pen": "✒", "brush": "✎", "rect": "▭", "oval": "◯"}


def make_vector_dock(win, on_cut):
    vw = VectorWindow()
    vw.cut_requested.connect(on_cut)
    d = QDockWidget("Vector Editor", win)
    d.setObjectName("dock_vector")
    d.setWidget(vw)
    d.setTitleBarWidget(DockTitle(d))
    d.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
    d.setFloating(True)
    d.resize(980, 620)
    return d, vw
