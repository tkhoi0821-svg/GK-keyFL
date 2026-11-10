import sys, os
from PyQt5.QtCore import Qt, QTimer, QRectF, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPixmap, QIcon, QLinearGradient
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


class ThumbCard(QWidget):
    clicked = pyqtSignal()

    def __init__(self, title, w, h, c1, c2, sub="", badge="", icon="", below=False):
        super().__init__()
        self.t, self.sub, self.c1, self.c2, self.badge, self.icon = title, sub, c1, c2, badge, icon
        self.th, self.below, self.hover = h, below, False
        self.setFixedSize(w, h + (46 if below else 0))
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, th = self.width(), self.th
        r = QRectF(2, 2, w - 4, th - 4)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(self.c1))
        g.setColorAt(1, QColor(self.c2))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor("#a56bff"), 2) if self.hover else Qt.NoPen)
        p.drawRoundedRect(r, 14, 14)
        if self.icon:
            p.setPen(QColor(255, 255, 255, 230))
            p.setFont(QFont("Arial", int(th / 4), QFont.Bold))
            p.drawText(r, Qt.AlignCenter, self.icon)
        if self.badge:
            pill = QRectF(r.right() - 56, r.bottom() - 26, 48, 18)
            p.setBrush(QColor(0, 0, 0, 150))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(pill, 9, 9)
            p.setPen(QColor("#fff"))
            p.setFont(QFont("Arial", 8))
            p.drawText(pill, Qt.AlignCenter, self.badge)
        p.setPen(QColor("#ffffff"))
        if self.below:
            p.setFont(QFont("Arial", 10, QFont.Bold))
            p.drawText(QRectF(4, th + 6, w - 8, 18), Qt.AlignLeft | Qt.AlignVCenter, self.t)
            p.setPen(QColor("#8a8a96"))
            p.setFont(QFont("Arial", 8))
            p.drawText(QRectF(4, th + 24, w - 8, 16), Qt.AlignLeft | Qt.AlignVCenter, self.sub)
        else:
            p.setFont(QFont("Arial", 11, QFont.Bold))
            p.drawText(r.adjusted(14, 0, -14, -12), Qt.AlignLeft | Qt.AlignBottom, self.t)
            if self.sub:
                p.setPen(QColor(255, 255, 255, 170))
                p.setFont(QFont("Arial", 8))
                p.drawText(r.adjusted(14, 0, -14, -30), Qt.AlignLeft | Qt.AlignBottom, self.sub)


class HomePage(QWidget):
    new_project = pyqtSignal(str, float)
    open_recent = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- sidebar (icon + label, kieu CapCut) ----
        side = QWidget()
        side.setFixedWidth(84)
        side.setStyleSheet("background:#141418;")
        sv = QVBoxLayout(side)
        sv.setContentsMargins(10, 14, 10, 14)
        sv.setSpacing(4)
        img = QLabel()
        img.setPixmap(QPixmap(LOGO).scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        img.setAlignment(Qt.AlignCenter)
        img.setFixedSize(60, 52)
        img.setStyleSheet("background:#ffffff;border-radius:12px;")
        sv.addWidget(img, 0, Qt.AlignHCenter)
        sv.addSpacing(14)
        grp = QButtonGroup(self)
        for i, (ic, t) in enumerate([("⌂", "Home"), ("▦", "Templates"), ("✦", "Assets"),
                                     ("▤", "Projects"), ("⚙", "Settings")]):
            b = QPushButton(f"{ic}\n{t}")
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setFixedSize(62, 58)
            b.setStyleSheet("QPushButton{background:transparent;border-radius:10px;font-size:11px;color:#9a9aa6;}"
                            "QPushButton:hover{background:#1f1f26;}"
                            "QPushButton:checked{background:#26262f;color:#ffffff;}")
            grp.addButton(b)
            sv.addWidget(b, 0, Qt.AlignHCenter)
        sv.addStretch()
        root.addWidget(side)

        # ---- noi dung ----
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(34, 20, 34, 28)
        v.setSpacing(12)

        top = QHBoxLayout()
        search = QLineEdit()
        search.setPlaceholderText("🔍  Search projects, templates...")
        search.setFixedSize(340, 36)
        search.setStyleSheet("QLineEdit{background:#24242b;border:none;border-radius:18px;padding:0 16px;}"
                             "QLineEdit:focus{border:1px solid #7a2bff;}")
        sign = QPushButton("Sign in")
        sign.setStyleSheet("QPushButton{background:#24242b;border-radius:18px;padding:8px 20px;}"
                           "QPushButton:hover{background:#30303a;}")
        top.addWidget(search)
        top.addStretch()
        top.addWidget(sign)
        v.addLayout(top)

        def title(t):
            l = QLabel(t)
            l.setStyleSheet("font-size:16px;font-weight:bold;margin-top:14px;")
            return l

        hero = QHBoxLayout()
        hero.setSpacing(16)
        nb = ThumbCard("New project", 330, 180, "#7a2bff", "#3a0fb0", "Start a blank canvas", icon="＋")
        nb.clicked.connect(lambda: self.new_project.emit("Untitled", 16 / 9))
        hero.addWidget(nb)
        for t, sub, ic, c1, c2 in [("Keyframe animation", "Move, scale, rotate with curves", "◆", "#2a3f8f", "#16204d"),
                                   ("Auto captions", "Speech to subtitles", "Aa", "#8f2a6a", "#4d1638"),
                                   ("Templates", "Start from a ready design", "▦", "#1f7a6a", "#0f3f37")]:
            c = ThumbCard(t, 210, 180, c1, c2, sub, icon=ic)
            c.clicked.connect(lambda t=t: self.new_project.emit(t, 9 / 16))
            hero.addWidget(c)
        hero.addStretch()
        v.addLayout(hero)

        chips = QHBoxLayout()
        chips.addWidget(QLabel("Canvas:"))
        for txt, r in [("16:9  YouTube", 16 / 9), ("9:16  TikTok / Reels", 9 / 16),
                       ("1:1  Square", 1.0), ("4:5  Instagram", 4 / 5)]:
            b = QPushButton(txt)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("QPushButton{background:#24242b;border-radius:15px;padding:7px 14px;}"
                            "QPushButton:hover{background:#7a2bff;}")
            b.clicked.connect(lambda _, t=txt, r=r: self.new_project.emit("Untitled " + t.split()[0], r))
            chips.addWidget(b)
        chips.addStretch()
        v.addLayout(chips)

        v.addWidget(title("Local drafts"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(14)
        drafts = [("Intro vlog", "Edited 2 hours ago", "00:42", "#2a5a8f", "#142a47"),
                  ("Edit TikTok", "Edited yesterday", "00:15", "#8f4a2a", "#47200f"),
                  ("Motion logo", "Edited 3 days ago", "00:08", "#5a2a8f", "#2a1447"),
                  ("Game trailer", "Edited last week", "01:20", "#2a8f5a", "#14472a"),
                  ("Lyric video", "Edited last week", "03:05", "#8f2a4a", "#47142a"),
                  ("Product promo", "Edited 2 weeks ago", "00:30", "#7a7a2a", "#3a3a14")]
        for i, (n, sub, dur, c1, c2) in enumerate(drafts):
            c = ThumbCard(n, 230, 130, c1, c2, sub, badge=dur, icon="▶", below=True)
            c.clicked.connect(lambda n=n: self.open_recent.emit(n))
            grid.addWidget(c, i // 4, i % 4)
        grid.setColumnStretch(4, 1)
        v.addLayout(grid)

        v.addWidget(title("Trending templates"))
        tp = QHBoxLayout()
        tp.setSpacing(16)
        for n, uses, c1, c2 in [("Glitch intro", "12.4K uses", "#6a2aa8", "#1b1b1f"),
                                ("Lyric video", "9.8K uses", "#a82a5a", "#1b1b1f"),
                                ("Slideshow", "8.1K uses", "#2a78a8", "#1b1b1f"),
                                ("Typography", "6.3K uses", "#a8782a", "#1b1b1f"),
                                ("Beat sync", "5.7K uses", "#2aa870", "#1b1b1f")]:
            c = ThumbCard(n, 150, 230, c1, c2, uses)
            c.clicked.connect(lambda n=n: self.new_project.emit(n, 9 / 16))
            tp.addWidget(c)
        tp.addStretch()
        v.addLayout(tp)
        v.addStretch()

        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setWidget(page)
        sa.setFrameShape(QFrame.NoFrame)
        root.addWidget(sa, 1)


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
                it.setSizeHint(lw.gridSize().expandedTo(self.size().boundedTo(self.size())) if False else __import__("PyQt5.QtCore", fromlist=["QSize"]).QSize(90, 64))
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
        self.home = HomePage()
        self.home.new_project.connect(self.open_editor)
        self.home.open_recent.connect(lambda n: self.open_editor(n, 16 / 9))
        self.stack = QStackedWidget()
        self.stack.addWidget(self.home)
        self.stack.addWidget(root)
        self.setCentralWidget(self.stack)

        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.tick)

    def open_editor(self, name, ratio):
        self.preview.ratio = ratio
        self.preview.update()
        self.title.setText(f"GK KeyFL — {name}")
        self.seek(0)
        self.stack.setCurrentIndex(1)

    def go_home(self):
        if self.playing:
            self.toggle_play()
        self.stack.setCurrentIndex(0)

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
    w = Main()
    w.show()
    sys.exit(app.exec_())
