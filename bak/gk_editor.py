"""Trang Editor: cac panel dock duoc (keo tha / tach cua so), Theme, Workspace luu-khoi phuc layout."""
import os, json, time
from PySide6.QtCore import Qt, QTimer, QByteArray, Signal
from PySide6.QtGui import QPixmap, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QLabel, QPushButton, QMenu, QStatusBar,
                             QProgressBar, QFileDialog, QColorDialog, QInputDialog, QTabWidget)
import gk_theme as theme
import gk_settings
import gk_prefs as prefs
import gk_model
import gk_panels
from gk_model import Layer, KINDS, PKEYS, TOTAL
from gk_timeline import LTimeline, LayerClip, TimelinePanel, GraphPanel
from gk_panels import styled, make_dock, LogoTile, Avatar, StagePanel, LayerPanel, Inspector, ConsolePanel
from gk_project import ProjectPanel
from gk_assets import kind_of
from gk_media import MediaSource, AudioEngine
from gk_vector_ui import make_vector_dock
from gk_matte_ui import MatteDialog
from gk_prefs_ui import SettingsDialog

DEFAULT_WS = "Mặc định"


class EditorPage(QMainWindow):
    home_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Widget)           # nhung vao QStackedWidget nhung van co dock
        self.setDockNestingEnabled(True)
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)
        self.playing, self.t, self.sel = False, 0.0, None
        self._ticking = False
        self.audio = AudioEngine()
        self._need_size = False
        self.ws_current = DEFAULT_WS

        # ---------------- panel
        self.panel = StagePanel(self)
        self.stage = self.panel.stage
        self.stage.picked.connect(lambda L: self.select_layer(L))
        self.setCentralWidget(self.panel)

        self.lp = LayerPanel()
        self.llist = self.lp.llist
        self.llist.picked.connect(lambda L: self.select_layer(L))
        self.llist.toggled.connect(self.toggle_eye)
        self.lp.up.clicked.connect(lambda: self.move_layer(1))
        self.lp.down.clicked.connect(lambda: self.move_layer(-1))
        self.lp.rm.clicked.connect(self.delete_layer)
        self.lp.add_menu.triggered.connect(lambda a: self.new_layer(a.text()))

        self.insp = Inspector()
        self.insp.pill_changed.connect(self.on_pill)
        self.insp.opacity_changed.connect(lambda v: self.on_pill("op", v))
        self.insp.name_edited.connect(self.on_name)
        self.insp.color_clicked.connect(self.pick_color)
        self.insp.key_add.connect(self.add_key)
        self.insp.key_del.connect(self.del_key)
        self.insp.matte_clicked.connect(self.open_matte)
        self.insp.vector_clicked.connect(self.open_vector)
        self.insp.key_nav.connect(self.key_nav)
        self.insp.ease_chosen.connect(self.on_ease)
        self.insp.loop_chosen.connect(self.on_loop)

        self.tl = LTimeline()
        self.tl.seek.connect(self.seek)
        self.tl.sc.selectionChanged.connect(self.on_clip_sel)
        self.tl.key_picked.connect(self.seek)
        self.tl.keys_edited.connect(self._keys_changed)
        self.tlp = TimelinePanel(self.tl)
        self.tlp.key_add.connect(self.add_key)
        self.tlp.key_del.connect(self.del_key)
        self.tlp.key_prev.connect(lambda: self.key_nav(-1))
        self.tlp.key_next.connect(lambda: self.key_nav(1))
        self.graph = GraphPanel()
        self.graph.seek.connect(self.seek)
        self.graph.edited.connect(self.on_graph_edit)

        self.project = ProjectPanel()
        self.project.open_asset.connect(lambda p: self.add_asset(p))
        self.project.message.connect(self.log)
        self.stage.asset_dropped.connect(lambda p, x, y: self.add_asset(p, x=x, y=y))
        self.tl.asset_dropped.connect(lambda p, t: self.add_asset(p, t=t))
        self.console = ConsolePanel()
        self.console.command.connect(self.run_cmd)

        self.panel.prev.clicked.connect(lambda: self.seek(0))
        self.panel.nxt.clicked.connect(lambda: self.seek(TOTAL))
        self.panel.play.clicked.connect(self.toggle_play)
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.toggle_play).setContext(Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings).setContext(Qt.WidgetWithChildrenShortcut)
        for key, mode in ((Qt.Key_Q, "select"), (Qt.Key_W, "move"), (Qt.Key_E, "rotate"), (Qt.Key_R, "scale")):
            QShortcut(QKeySequence(key), self, activated=lambda m=mode: self.panel.set_mode(m)).setContext(Qt.WidgetWithChildrenShortcut)

        # ---------------- dock
        self.d_vector, self.vecwin = make_vector_dock(self, self.on_vector_cut)
        self.d_layers = make_dock(self, "Lớp", self.lp, "dock_layers")
        self.d_inspector = make_dock(self, "Thuộc tính", self.insp, "dock_inspector")
        self.d_project = make_dock(self, "Assets", self.project, "dock_project")
        self.d_console = make_dock(self, "Lệnh", self.console, "dock_console")
        self.d_timeline = make_dock(self, "Timeline", self.tlp, "dock_timeline")
        self.d_graph = make_dock(self, "Đồ thị key frame", self.graph, "dock_graph")
        self.docks = [self.d_layers, self.d_inspector, self.d_project, self.d_timeline, self.d_graph, self.d_console,
                     self.d_vector]
        self.d_layers.widget().setMinimumWidth(200)
        self.d_inspector.widget().setMinimumWidth(260)

        # ---------------- thanh tren + thanh trang thai
        self.setMenuWidget(self.build_topbar())
        self.build_statusbar()

        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.tick)
        self.stats = QTimer(self)
        self.stats.setInterval(1500)
        self.stats.timeout.connect(self.update_stats)
        self.stats.start()
        prefs.bus.changed.connect(self.apply_prefs)
        self.apply_prefs("*")
        self.insp.autokey.toggled.connect(lambda v: prefs.put("autokey", bool(v)))

        self.apply_default_layout()
        cur = gk_settings.get("workspace_current", DEFAULT_WS) if prefs.get("restore_layout") else DEFAULT_WS
        if cur != DEFAULT_WS:
            self.load_workspace(cur)
        else:
            self.update_chips()
        theme.bus.changed.connect(self.update_chips)
        self.reset_project(16 / 9)

    # ================= thanh tren =================
    def build_topbar(self):
        bar = styled(QWidget(), "TopBar")
        bar.setFixedHeight(52)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 0, 14, 0)
        bl.setSpacing(2)
        bl.addWidget(LogoTile())
        bl.addSpacing(18)

        def stub(label):
            return lambda m: self.act(m, label, lambda: None, enabled=False)

        for name, fill in (("File", self.fill_file), ("Edit", self.fill_edit), ("View", self.fill_view),
                           ("Workspace", self.fill_workspace), ("Theme", self.fill_theme),
                           ("Setting", self.fill_setting), ("Tool", stub("Công cụ (chưa có)")),
                           ("Plugin", stub("Plugin (chưa có)"))):
            b = QPushButton(name)
            m = QMenu(b)
            m.aboutToShow.connect(lambda m=m, f=fill: self.refill(m, f))
            b.setMenu(m)
            bl.addWidget(b)
        bl.addStretch()
        self.greet = QLabel("Xin chào\nKhách")
        self.greet.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.avatar = Avatar()
        bl.addWidget(self.greet)
        bl.addSpacing(8)
        bl.addWidget(self.avatar)
        return bar

    def build_statusbar(self):
        sb = QStatusBar()
        sb.setSizeGripEnabled(False)
        self.setStatusBar(sb)
        self.prog = QProgressBar()
        self.prog.setRange(0, 100)
        self.prog.setValue(0)
        self.prog.setTextVisible(False)
        self.prog.setFixedSize(160, 10)
        sb.addWidget(self.prog)
        self.task = QLabel("Sẵn sàng")
        sb.addWidget(self.task, 1)
        self.ws_chip, self.theme_chip = QLabel(""), QLabel("")
        self.cpu, self.ram = QLabel("CPU: --"), QLabel("RAM: --")
        for w in (self.ws_chip, self.theme_chip, self.cpu, self.ram):
            w.setObjectName("Chip")
            sb.addPermanentWidget(w)

    def update_chips(self):
        self.ws_chip.setText("Layout: %s" % self.ws_current)
        self.theme_chip.setText("Theme: %s" % theme.THEMES[theme.current_key()]["name"])

    # ================= menu =================
    def refill(self, m, fill):
        m.clear()
        fill(m)

    @staticmethod
    def act(m, text, fn, checked=None, enabled=True):
        a = m.addAction(text)
        if checked is not None:
            a.setCheckable(True)
            a.setChecked(checked)
        a.setEnabled(enabled)
        a.triggered.connect(lambda _=False, f=fn: f())
        return a

    def fill_setting(self, m):
        self.act(m, "⚙  Tuỳ chọn…", self.open_settings)

    def open_settings(self):
        d = getattr(self, "_dlg", None)
        if d is None:
            d = self._dlg = SettingsDialog(self, self)
        d.show()
        d.raise_()
        d.activateWindow()

    def apply_prefs(self, key="*"):
        a = key == "*"
        if a or key == "gizmo_scale":
            s = prefs.get("gizmo_scale")
            gk_panels.ARM, gk_panels.RING = 84.0 * s, 72.0 * s
            self.stage.update()
        if a or key == "guides":
            self.panel.guide_btn.setChecked(prefs.get("guides"))
        if a or key == "fps":
            self.timer.setInterval(max(1, int(1000 / prefs.get("fps"))))
        if a or key == "autokey":
            self.insp.autokey.setChecked(prefs.get("autokey"))
        if a or key == "default_ease":
            gk_model.DEFAULT_EASE = prefs.get("default_ease")
        if key in ("ui_font", "*"):
            theme.set_theme(theme.current_key())

    def fill_file(self, m):
        self.act(m, "Lưu dự án…", self.save_project)
        self.act(m, "Mở dự án…", self.load_project)
        self.act(m, "Đổi thư mục Assets…", self.project.choose_root)
        m.addSeparator()
        self.act(m, "‹ Về trang chủ", self.home_requested.emit)

    def fill_edit(self, m):
        self.act(m, "✂  Cắt clip", self.tl.split)
        self.act(m, "🗑  Xoá clip", self.tl.delete)
        self.act(m, "🗑  Xoá lớp", self.delete_layer)
        m.addSeparator()
        self.act(m, "✂  Vector Editor (cắt ảnh)…", self.open_vector)
        self.act(m, "◐  Tách nền…", self.open_matte)

    def fill_view(self, m):
        for d in self.docks:
            m.addAction(d.toggleViewAction())
        m.addSeparator()
        self.act(m, "Lưới canvas", lambda: self.panel.guide_btn.toggle(), checked=self.panel.guide_btn.isChecked())

    def fill_theme(self, m):
        for key, th in theme.THEMES.items():
            self.act(m, th["name"], lambda k=key: theme.set_theme(k), checked=(key == theme.current_key()))

    def fill_workspace(self, m):
        items = gk_settings.get("workspaces", {})
        self.act(m, DEFAULT_WS, lambda: self.load_workspace(DEFAULT_WS), checked=(self.ws_current == DEFAULT_WS))
        for n in sorted(items):
            self.act(m, n, lambda n=n: self.load_workspace(n), checked=(self.ws_current == n))
        m.addSeparator()
        self.act(m, "＋  Lưu layout hiện tại…", self.save_workspace_dialog)
        if items:
            sub = m.addMenu("Xoá layout")
            for n in sorted(items):
                self.act(sub, n, lambda n=n: self.delete_workspace(n))

    # ================= workspace (bo cuc panel) =================
    def apply_default_layout(self):
        for d in self.docks:
            if d is self.d_vector:
                continue
            d.setFloating(False)
            self.removeDockWidget(d)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.d_layers)
        self.addDockWidget(Qt.RightDockWidgetArea, self.d_inspector)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.d_project)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.d_timeline, Qt.Horizontal)
        self.tabifyDockWidget(self.d_project, self.d_console)
        self.tabifyDockWidget(self.d_timeline, self.d_graph)
        for d in self.docks:
            if d is not self.d_vector:
                d.show()
        self.d_project.raise_()
        self.d_timeline.raise_()
        self.d_vector.hide()
        self._need_size = True
        QTimer.singleShot(0, self._size_docks)

    def _size_docks(self):
        if not self.isVisible():
            return                                  # se chay lai o showEvent
        self.resizeDocks([self.d_layers, self.d_inspector], [250, 340], Qt.Horizontal)
        self.resizeDocks([self.d_project, self.d_timeline], [380, 980], Qt.Horizontal)
        self.resizeDocks([self.d_timeline], [280], Qt.Vertical)
        self._need_size = False

    def showEvent(self, e):
        super().showEvent(e)
        if self._need_size:
            QTimer.singleShot(0, self._size_docks)

    def save_workspace(self, name):
        data = gk_settings.get("workspaces", {})
        data[name] = bytes(self.saveState(1).toBase64()).decode("ascii")
        gk_settings.put("workspaces", data)
        self.ws_current = name
        gk_settings.put("workspace_current", name)
        self.update_chips()
        self.log("Đã lưu layout '%s'." % name)

    def save_workspace_dialog(self):
        name, ok = QInputDialog.getText(self, "Lưu layout", "Tên layout:")
        name = name.strip()
        if ok and name:
            self.save_workspace(DEFAULT_WS + " 2" if name == DEFAULT_WS else name)

    def load_workspace(self, name):
        ok = False
        if name != DEFAULT_WS:
            s = gk_settings.get("workspaces", {}).get(name)
            if s:
                ok = self.restoreState(QByteArray.fromBase64(s.encode("ascii")), 1)
            if not ok:
                self.log("Không khôi phục được layout '%s', dùng bố cục mặc định." % name)
        if name == DEFAULT_WS or not ok:
            self.apply_default_layout()
            name = DEFAULT_WS
        self.ws_current = name
        gk_settings.put("workspace_current", name)
        self.update_chips()

    def delete_workspace(self, name):
        data = gk_settings.get("workspaces", {})
        data.pop(name, None)
        gk_settings.put("workspaces", data)
        if self.ws_current == name:
            self.load_workspace(DEFAULT_WS)

    # ================= du an / lop =================
    def reset_project(self, ratio):
        self.clear_project()
        self.panel.set_ratio(ratio)
        bg = Layer("Nền", "bg", "#000000")
        bg.timed = False
        self.stage.layers.append(bg)
        self.new_layer("Hình vuông", start=0, dur=TOTAL)
        self.seek(0)

    def clear_project(self):
        self.tl.clear()
        self.stage.layers.clear()
        self.sel = self.stage.sel = None
        self.audio.players.clear()

    def new_layer(self, kn, path=None, start=None, dur=5.0):
        kind, row, col = KINDS[kn]
        n = sum(1 for x in self.stage.layers if x.kind == kind) + 1
        L = Layer(os.path.basename(path) if path else "%s %d" % (kn, n), kind, col)
        L.path = path
        if path and kind == "image":
            L.pix = QPixmap(path)
        self.stage.layers.append(L)
        s = min(self.t, TOTAL - 2) if start is None else start
        self.tl.add_layer_clip(L, row, s, min(dur, TOTAL - s))
        self.tl.refresh()
        self.select_layer(L)
        self.rebuild_tree()
        return L

    def delete_layer(self):
        L = self.sel
        if not L or L.kind == "bg":
            return
        for c in list(L.clips):
            self.tl.remove_clip(c)
        if getattr(L, "vid", None) is not None:
            self.audio.players.pop(id(L), None)
        self.stage.layers.remove(L)
        self.select_layer(None)
        self.rebuild_tree()

    def move_layer(self, d):
        L, ls = self.sel, self.stage.layers
        if not L or L.kind == "bg":
            return
        j = ls.index(L) + d
        if 1 <= j < len(ls):
            ls[j - d], ls[j] = ls[j], ls[j - d]
            self.rebuild_tree()
            self.stage.update()

    def rebuild_tree(self):
        self.llist.set_layers(self.stage.layers, self.sel)

    def toggle_eye(self, L):
        L.visible = not L.visible
        self.llist.update()
        self.stage.update()

    def on_clip_sel(self):
        for c in self.tl.sc.selectedItems():
            if isinstance(c, LayerClip):
                self.select_layer(c.layer)
                break

    def select_layer(self, L):
        self.sel = self.stage.sel = L
        self.llist.sel = L
        self.llist.update()
        self.stage.update()
        self.graph.set_layer(L)
        self.sync_props()

    # ================= thuoc tinh / key frame =================
    def sync_props(self):
        self.insp.load(self.sel, self.t)

    def write(self, L, key, v):
        L.set(key, self.t, v, self.insp.autokey.isChecked())
        self.stage.update()
        self.sync_props()
        self.tl.viewport().update()
        self.graph.refresh()

    def on_graph_edit(self):
        self._keys_changed()

    def _keys_changed(self):
        self.stage.update()
        self.sync_props()
        self.tl.viewport().update()
        self.graph.refresh()

    def on_pill(self, key, v):
        if self.sel:
            self.write(self.sel, key, float(v))

    def on_name(self, txt):
        L = self.sel
        if not L or not txt:
            return
        L.name = txt
        if L.kind == "text":
            L.text = txt
        for c in L.clips:
            c.name = txt
        self.rebuild_tree()
        self.stage.update()
        self.tl.viewport().update()
        self.insp.title.setText(txt)

    def pick_color(self):
        L = self.sel
        if L:
            c = QColorDialog.getColor(QColor(L.color), self)
            if c.isValid():
                L.color = c.name()
                self.stage.update()
                self.llist.update()

    def add_key(self):
        L = self.sel
        if L and L.kind not in ("bg", "audio"):
            L.add_keys(self.t)
            self._keys_changed()

    def del_key(self):
        if self.sel:
            self.sel.del_keys_at(self.t)
            self._keys_changed()

    def key_nav(self, d):
        L = self.sel
        if not L:
            return
        c = [x for x in L.key_times() if (x < self.t - 0.01 if d < 0 else x > self.t + 0.01)]
        if c:
            self.seek(max(c) if d < 0 else min(c))

    def on_ease(self, e):
        if self.sel:
            self.sel.set_ease_at(self.t, e)
            self._keys_changed()

    def on_loop(self, m):
        if self.sel:
            self.sel.set_loop_all(m)
            self._keys_changed()

    # ================= tach nen / cat vector =================
    def open_matte(self):
        L = self.sel
        if not (L and L.kind == "image" and L.pix is not None and not L.pix.isNull()):
            return
        d = getattr(self, "_matte_dlg", None)
        if d is None:
            d = self._matte_dlg = MatteDialog(self)
            d.applied.connect(lambda: (self.stage.update(), self.llist.update()))
        d.set_layer(L)
        d.show()
        d.raise_()
        d.activateWindow()

    def open_vector(self):
        L = self.sel
        if L and L.kind == "image" and L.path and os.path.exists(L.path):
            self.vecwin.load_image(L.path)
        elif L and L.pix is not None and not L.pix.isNull():
            self.vecwin.canvas.set_bg(L.pix)
        self.d_vector.show()
        self.d_vector.raise_()
        self.d_vector.activateWindow()

    def on_vector_cut(self, mask_qimage, path):
        """Nhan mat na tu Vector Editor: cat vung do ra khoi anh nguon thanh 1 lop moi (vi du: cat rieng cai dau)."""
        src = self.vecwin.canvas.bg
        if src is None or src.isNull():
            self.log("Chưa có ảnh nền trong Vector Editor để cắt.")
            return
        import numpy as np
        from PySide6.QtGui import QImage
        import gk_matting as M
        base = M.qimage_to_rgba(src.toImage())
        m = mask_qimage.convertToFormat(QImage.Format_Grayscale8)
        ptr = m.constBits()
        ptr.setsize(m.height() * m.bytesPerLine())
        alpha = np.frombuffer(ptr, np.uint8).reshape(m.height(), m.bytesPerLine())[:, :m.width()].astype(np.float32) / 255.0
        out = M.apply_alpha(base, alpha, multiply=True)
        xs = np.where(alpha.max(0) > 0.02)[0]
        ys = np.where(alpha.max(1) > 0.02)[0]
        if len(xs) == 0 or len(ys) == 0:
            self.log("Vùng cắt rỗng, không có gì để tách.")
            return
        x0, x1, y0, y1 = int(xs[0]), int(xs[-1]) + 1, int(ys[0]), int(ys[-1]) + 1
        crop = out[y0:y1, x0:x1]
        pm = QPixmap.fromImage(M.rgba_to_qimage(crop))
        L = self.new_layer("Hình ảnh", path=None, start=self.t)
        L.name = "Cắt từ " + os.path.basename(getattr(self.vecwin.canvas, "src_path", "ảnh"))
        L.pix, L.path = pm, None
        L.wfrac = self.sel.wfrac if self.sel else 0.3
        self.rebuild_tree()
        self.select_layer(L)
        self.stage.update()
        self.log("Đã cắt vùng chọn thành lớp '%s'." % L.name)

    # ================= tep / lenh / luu =================
    def log(self, s):
        self.console.log(s)

    def make_media(self, L):
        """Gan nguon media (ffmpeg) cho lop video / am thanh. Tra ve MediaSource hoac None."""
        if L.kind not in ("video", "audio") or not L.path or not os.path.exists(L.path):
            return None
        src = MediaSource(L.path)
        if not src.info:
            self.log("Không đọc được '%s'. Cần ffmpeg (đóng gói kèm hoặc cài trong hệ thống)." % os.path.basename(L.path))
            return None
        L.vid = src
        src.updated.connect(self.stage.update)
        src.start()
        return src

    def add_asset(self, path, x=None, y=None, t=None):
        """Dua 1 tep trong Assets (hoac tep tu may) len timeline thanh lop moi."""
        path = self.project.ingest(path)
        names = {"image": "Hình ảnh", "video": "Video", "audio": "Âm thanh"}
        k = kind_of(path)
        if k not in names:
            self.log("Chưa hỗ trợ loại '%s': %s" % (k, os.path.basename(path)))
            return
        dur = 5.0
        if k in ("video", "audio"):
            from gk_ffmpeg import probe
            info = probe(path)
            if info and info["duration"] > 0:
                dur = info["duration"]
        L = self.new_layer(names[k], path, start=t, dur=dur)
        if k in ("video", "audio"):
            src = self.make_media(L)
            if src is not None:
                self.log("Đang tạo khung xem trước cho %s (%.1fs)…" % (os.path.basename(path), src.duration))
        if x is not None:
            L.base["pos0"], L.base["pos1"] = float(x), float(y)
            self.stage.update()
            self.sync_props()
        self.log("Đã thêm " + os.path.basename(path))

    def run_cmd(self, txt):
        self.log("> " + txt)
        a = txt.lower().split()
        c = a[0]
        names = {"shape": "Hình vuông", "text": "Văn bản", "image": "Hình ảnh", "video": "Video", "audio": "Âm thanh"}
        try:
            if c == "help":
                self.log("help | play | pause | seek <giây> | add <shape|text|image|video|audio> | del | "
                         "ratio <16:9|9:16|1:1|4:5> | theme <gk|unity|blender|alight|teal|light> | save | load")
            elif c in ("play", "pause"):
                if (c == "play") != self.playing:
                    self.toggle_play()
            elif c == "seek":
                self.seek(max(0.0, min(TOTAL, float(a[1]))))
            elif c == "add" and a[1] in names:
                self.new_layer(names[a[1]])
            elif c == "del":
                self.delete_layer()
            elif c == "ratio":
                w, h = a[1].split(":")
                self.panel.set_ratio(float(w) / float(h))
            elif c == "theme" and a[1] in theme.THEMES:
                theme.set_theme(a[1])
            elif c == "save":
                self.save_project()
            elif c == "load":
                self.load_project()
            else:
                self.log("Lệnh không hợp lệ. Gõ help.")
        except Exception as ex:
            self.log("Lỗi: %s" % ex)

    def save_project(self):
        f, _ = QFileDialog.getSaveFileName(self, "Lưu dự án", "", "GK KeyFL (*.gkproj)")
        if not f:
            return
        if not f.endswith(".gkproj"):
            f += ".gkproj"
        try:
            with open(f, "w", encoding="utf-8") as fp:
                json.dump({"ratio": self.stage.ratio, "layers": [L.to_dict() for L in self.stage.layers]}, fp,
                          ensure_ascii=False)
            self.log("Đã lưu " + f)
        except Exception as ex:
            self.log("Lỗi lưu: %s" % ex)

    def load_project(self):
        f, _ = QFileDialog.getOpenFileName(self, "Mở dự án", "", "GK KeyFL (*.gkproj)")
        if not f:
            return
        try:
            with open(f, encoding="utf-8") as fp:
                d = json.load(fp)
            self.clear_project()
            self.panel.set_ratio(d.get("ratio", 16 / 9))
            for ld in d["layers"]:
                L = Layer.from_dict(ld)
                self.stage.layers.append(L)
                for cl in ld.get("clips", []):
                    c = self.tl.add_layer_clip(L, cl[0], cl[1], cl[2])
                    if len(cl) > 3:
                        c.src_off = cl[3]
                self.make_media(L)
            self.tl.refresh()
            self.select_layer(None)
            self.rebuild_tree()
            self.seek(0)
            self.log("Đã mở " + f)
        except Exception as ex:
            self.log("Lỗi mở: %s" % ex)

    # ================= nguoi dung / phat =================
    def set_user(self, name):
        self.greet.setText("Xin chào\n%s" % (name or "Khách"))
        self.avatar.set_name(name)

    def update_stats(self):
        try:
            import psutil
            self.cpu.setText("CPU: %d%%" % psutil.cpu_percent())
            self.ram.setText("RAM: %d%%" % psutil.virtual_memory().percent)
        except Exception:
            pass

    def open_project(self, name, ratio):
        self.pause()
        self.reset_project(ratio)

    def pause(self):
        if self.playing:
            self.toggle_play()

    def seek(self, t):
        self.t = t
        self.tl.set_time(t)
        self.stage.set_time(t)
        self.graph.set_time(t)
        self.sync_props()
        txt = f"{int(t) // 60:02d}:{t % 60:04.1f} / 00:{TOTAL:04.1f}"
        self.panel.timelbl.setText(txt)
        self.tlp.timelbl.setText(txt)
        self.prog.setValue(int(t / TOTAL * 100))
        if self.playing and not self._ticking:
            self.audio.sync(self.stage.layers, t, True, force=True)

    def tick(self):
        now = time.monotonic()
        dt = min(0.1, now - self._last)
        self._last = now
        t = self.t + dt
        if t >= TOTAL:
            if prefs.get("loop"):
                t = 0.0
            else:
                self.seek(TOTAL)
                self.toggle_play()
                return
        self._ticking = True
        self.seek(t)
        self._ticking = False
        self.audio.sync(self.stage.layers, self.t, True, force=(t == 0.0))

    def toggle_play(self):
        self.playing = not self.playing
        self.panel.play.setText("⏸" if self.playing else "▶")
        self.task.setText("Đang phát" if self.playing else "Sẵn sàng")
        if self.playing:
            self._last = time.monotonic()
            self.timer.start()
            self.audio.sync(self.stage.layers, self.t, True, force=True)
        else:
            self.timer.stop()
            self.audio.stop_all()
