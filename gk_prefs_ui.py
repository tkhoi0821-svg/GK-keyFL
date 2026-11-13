"""Hop thoai Tuy chon: thay doi ap dung ngay va duoc nho."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QListWidget, QStackedWidget, QLabel,
                             QComboBox, QCheckBox, QSlider, QPushButton, QWidget)
import gk_prefs as prefs
import gk_theme as theme
from gk_model import EASES
from gk_panels import ScrubSpin

FONTS = [10, 11, 12, 13, 14, 15, 16]
FPS = [24, 25, 30, 50, 60]


class SettingsDialog(QDialog):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.ed = editor
        self.setWindowTitle("Tuỳ chọn — GK KeyFL")
        self.resize(780, 520)
        self.sync = []                       # cac ham dat lai gia tri widget tu prefs
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)
        body = QHBoxLayout()
        body.setSpacing(14)
        self.cats = QListWidget()
        self.cats.setFixedWidth(176)
        self.cats.setSpacing(2)
        self.pages = QStackedWidget()
        body.addWidget(self.cats)
        body.addWidget(self.pages, 1)
        root.addLayout(body, 1)

        self.page("Giao diện", "Màu sắc và cỡ chữ của toàn bộ editor.", self.build_ui)
        self.page("Canvas & Gizmo", "Tay nắm kéo trục và bước nhảy khi giữ Ctrl.", self.build_canvas)
        self.page("Phát & Timeline", "Cách phát lại dòng thời gian.", self.build_play)
        self.page("Key frame", "Mặc định cho key frame.", self.build_key)
        self.page("Bố cục", "Các panel kéo thả và Workspace.", self.build_layout)
        self.cats.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.cats.setCurrentRow(0)

        foot = QHBoxLayout()
        hint = QLabel("Thay đổi được áp dụng và lưu ngay.")
        hint.setObjectName("Hint")
        foot.addWidget(hint)
        foot.addStretch()
        rb = QPushButton("Khôi phục mặc định")
        rb.clicked.connect(self.reset)
        cb = QPushButton("Đóng")
        cb.setObjectName("Accent")
        cb.clicked.connect(self.close)
        foot.addWidget(rb)
        foot.addWidget(cb)
        root.addLayout(foot)
        theme.bus.changed.connect(self.load_values)
        self.load_values()

    # ---------------------------------------------------------------- khung trang
    def page(self, name, sub, builder):
        self.cats.addItem(name)
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 0, 4, 0)
        v.setSpacing(6)
        t = QLabel(name)
        t.setObjectName("Title")
        s = QLabel(sub)
        s.setObjectName("Hint")
        v.addWidget(t)
        v.addWidget(s)
        v.addSpacing(8)
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(12)
        g.setColumnStretch(1, 1)
        v.addLayout(g)
        v.addStretch()
        builder(g)
        self.pages.addWidget(w)

    @staticmethod
    def row(g, label, widget, hint=None):
        r = g.rowCount()
        lab = QLabel(label)
        lab.setObjectName("Sub")
        g.addWidget(lab, r, 0, Qt.AlignTop | Qt.AlignLeft)
        g.addWidget(widget, r, 1, Qt.AlignLeft)
        if hint:
            h = QLabel(hint)
            h.setObjectName("Hint")
            h.setWordWrap(True)
            g.addWidget(h, r + 1, 1)

    def check(self, g, key, text, hint=None):
        c = QCheckBox(text)
        c.toggled.connect(lambda v: prefs.put(key, bool(v)))
        self.sync.append(lambda: self._set(c, prefs.get(key)))
        self.row(g, "", c, hint)

    def combo(self, g, key, label, items, hint=None, cast=lambda x: x):
        cb = QComboBox()
        for text, data in items:
            cb.addItem(text, data)
        cb.activated.connect(lambda _: prefs.put(key, cast(cb.currentData())))
        self.sync.append(lambda: self._set(cb, prefs.get(key)))
        self.row(g, label, cb, hint)
        return cb

    def scrub(self, g, key, label, lo, hi, step, suffix, hint=None):
        sp = ScrubSpin("", step)
        sp.setRange(lo, hi)
        sp.setSuffix(suffix)
        sp.setFixedWidth(100)
        sp.valueChanged.connect(lambda v: prefs.put(key, float(v)))
        self.sync.append(lambda: self._set(sp, prefs.get(key)))
        self.row(g, label, sp, hint)

    @staticmethod
    def _set(w, v):
        w.blockSignals(True)
        if isinstance(w, QCheckBox):
            w.setChecked(bool(v))
        elif isinstance(w, QComboBox):
            w.setCurrentIndex(max(0, w.findData(v)))
        elif isinstance(w, QSlider):
            w.setValue(int(round(float(v) * 100)))
        else:
            w.setValue(v)
        w.blockSignals(False)

    # ---------------------------------------------------------------- cac trang
    def build_ui(self, g):
        cb = QComboBox()
        for k, th in theme.THEMES.items():
            cb.addItem(th["name"], k)
        cb.activated.connect(lambda _: theme.set_theme(cb.currentData()))
        self.sync.append(lambda: self._set(cb, theme.current_key()))
        self.row(g, "Theme", cb, "Cũng đổi được ở menu Theme.")
        self.combo(g, "ui_font", "Cỡ chữ giao diện", [("%d px" % f, f) for f in FONTS],
                   "Áp dụng cho menu, nút, ô nhập. Chữ vẽ trên canvas và timeline giữ nguyên.", cast=int)
        b = QPushButton("Đổi thư mục Assets…")
        b.clicked.connect(self.ed.project.choose_root)
        self.row(g, "Thư mục Assets", b, "Nơi lưu video, ảnh, âm thanh, model, plugin của bạn.")

    def build_canvas(self, g):
        sl = QSlider(Qt.Horizontal)
        sl.setRange(60, 180)
        sl.setFixedWidth(220)
        lab = QLabel("100%")
        lab.setFixedWidth(46)
        sl.valueChanged.connect(lambda v: (lab.setText("%d%%" % v), prefs.put("gizmo_scale", v / 100.0)))
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(sl)
        h.addWidget(lab)
        self.sync.append(lambda: (self._set(sl, prefs.get("gizmo_scale")), lab.setText("%d%%" % sl.value())))
        self.row(g, "Kích thước gizmo", box, "Tay nắm di chuyển / xoay / kích thước trên canvas.")
        self.scrub(g, "snap_move", "Bước nhảy di chuyển", 0.5, 50, 0.1, "", "Giữ Ctrl khi kéo mũi tên.")
        self.scrub(g, "snap_rot", "Bước nhảy xoay", 1, 90, 0.2, "°", "Giữ Ctrl khi kéo vòng xoay.")
        self.scrub(g, "snap_scl", "Bước nhảy kích thước", 1, 100, 0.2, "%", "Giữ Ctrl khi kéo ô co giãn.")
        self.check(g, "guides", "Hiện lưới canvas khi mở", "Đường chia ba và tâm khung.")

    def build_play(self, g):
        self.combo(g, "fps", "Tốc độ làm mới", [("%d fps" % f, f) for f in FPS],
                   "Thời gian vẫn chạy đúng tốc độ thật; chỉ đổi số lần vẽ lại mỗi giây.", cast=int)
        self.check(g, "loop", "Lặp lại khi phát hết", "Tắt thì dừng ở cuối dòng thời gian.")

    def build_key(self, g):
        self.check(g, "autokey", "Tự động key frame khi chỉnh", "Cũng là ô trong bảng Thuộc tính.")
        self.combo(g, "default_ease", "Kiểu nội suy của key mới", [(n, k) for k, n in EASES],
                   "Chỉ áp dụng cho key tạo sau này, không đổi key đã có.")

    def build_layout(self, g):
        self.check(g, "restore_layout", "Mở lại bố cục lần trước khi khởi động",
                   "Tắt thì luôn bắt đầu bằng bố cục Mặc định.")
        b = QPushButton("Đặt lại bố cục mặc định")
        b.clicked.connect(lambda: self.ed.load_workspace("Mặc định"))
        self.row(g, "Bố cục hiện tại", b, "Lưu và chuyển nhiều bố cục ở menu Workspace.")

    # ---------------------------------------------------------------- dong bo / dat lai
    def load_values(self):
        for f in self.sync:
            f()

    def reset(self):
        prefs.reset()
        theme.set_theme(theme.DEFAULT_THEME)
        self.load_values()
