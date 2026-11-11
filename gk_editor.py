"""Trang Editor: cac panel dock duoc (keo tha / tach cua so), Theme, Workspace luu-khoi phuc layout."""
import os, json
from PyQt5.QtCore import Qt, QTimer, QByteArray, pyqtSignal
from PyQt5.QtGui import QPixmap, QColor, QKeySequence
from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QLabel, QPushButton, QMenu, QStatusBar,
                             QProgressBar, QFileDialog, QColorDialog, QInputDialog, QTabWidget, QShortcut)
import gk_theme as theme
import gk_settings
from gk_model import Layer, KINDS, PKEYS, TOTAL
from gk_timeline import LTimeline, LayerClip, TimelinePanel, GraphPanel
from gk_panels import (styled, make_dock, LogoTile, Avatar, StagePanel, LayerPanel, Inspector, ProjectPanel,
                       ConsolePanel)

DEFAULT_WS = "Mặc định"


class EditorPage(QMainWindow):
    home_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Widget)           # nhung vao QStackedWidget nhung van co dock
        self.setDockNestingEnabled(True)
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)
        self.playing, self.t, self.sel = False, 0.0, None
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

        self.tl = LTimeline()
        self.tl.seek.connect(self.seek)
        self.tl.sc.selectionChanged.connect(self.on_clip_sel)
        self.tlp = TimelinePanel(self.tl)
        self.graph = GraphPanel()
        self.graph.seek.connect(self.seek)
        self.graph.edited.connect(self.on_graph_edit)

        self.project = ProjectPanel()
        self.project.opened.connect(self.import_file)
        self.console = ConsolePanel()
        self.console.command.connect(self.run_cmd)

        self.panel.prev.clicked.connect(lambda: self.seek(0))
        self.panel.nxt.clicked.connect(lambda: self.seek(TOTAL))
        self.panel.play.clicked.connect(self.toggle_play)
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.toggle_play).setContext(Qt.WidgetWithChildrenShortcut)

        # ---------------- dock
        self.d_layers = make_dock(self, "Lớp", self.lp, "dock_layers")
        self.d_inspector = make_dock(self, "Thuộc tính", self.insp, "dock_inspector")
        self.d_project = make_dock(self, "Assets", self.project, "dock_project")
        self.d_console = make_dock(self, "Lệnh", self.console, "dock_console")
        self.d_timeline = make_dock(self, "Timeline", self.tlp, "dock_timeline")
        self.d_graph = make_dock(self, "Đồ thị key frame", self.graph, "dock_graph")
        self.docks = [self.d_layers, self.d_inspector, self.d_project, self.d_timeline, self.d_graph, self.d_console]
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

        self.apply_default_layout()
        cur = gk_settings.get("workspace_current", DEFAULT_WS)
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
                           ("Setting", stub("Tuỳ chọn (chưa có)")), ("Tool", stub("Công cụ (chưa có)")),
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

    def fill_file(self, m):
        self.act(m, "Lưu dự án…", self.save_project)
        self.act(m, "Mở dự án…", self.load_project)
        m.addSeparator()
        self.act(m, "‹ Về trang chủ", self.home_requested.emit)

    def fill_edit(self, m):
        self.act(m, "✂  Cắt clip", self.tl.split)
        self.act(m, "🗑  Xoá clip", self.tl.delete)
        self.act(m, "🗑  Xoá lớp", self.delete_layer)

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
            d.setFloating(False)
            self.removeDockWidget(d)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.d_layers)
        self.addDockWidget(Qt.RightDockWidgetArea, self.d_inspector)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.d_project)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.d_timeline, Qt.Horizontal)
        self.tabifyDockWidget(self.d_project, self.d_console)
        self.tabifyDockWidget(self.d_timeline, self.d_graph)
        for d in self.docks:
            d.show()
        self.d_project.raise_()
        self.d_timeline.raise_()
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
        self.stage.update()
        self.sync_props()
        self.tl.viewport().update()

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
            for k in list(PKEYS) + ["op"]:
                L.set(k, self.t, L.get(k, self.t), True)
            self.tl.viewport().update()
            self.graph.refresh()

    def del_key(self):
        L = self.sel
        if not L:
            return
        for k in list(L.kf):
            v = L.get(k, self.t)
            rest = [x for x in L.kf[k] if abs(x[0] - self.t) >= 0.05]
            if rest:
                L.kf[k] = rest
            else:
                L.base[k] = v
                del L.kf[k]
        self.stage.update()
        self.tl.viewport().update()
        self.graph.refresh()

    # ================= tep / lenh / luu =================
    def log(self, s):
        self.console.log(s)

    def import_file(self, which):
        if which == "image":
            f, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh", "", "Ảnh (*.png *.jpg *.jpeg *.bmp *.webp)")
            kn = "Hình ảnh"
        elif which == "video":
            f, _ = QFileDialog.getOpenFileName(self, "Chọn video", "", "Video (*.mp4 *.mov *.mkv *.avi *.webm)")
            kn = "Video"
        else:
            self.log("%s: chưa hỗ trợ." % which)
            return
        if f:
            self.new_layer(kn, f)
            self.log("Đã nhập " + f + (" (video chỉ hiện khung, chưa giải mã)" if which == "video" else ""))

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
                for row, s, du in ld.get("clips", []):
                    self.tl.add_layer_clip(L, row, s, du)
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

    def tick(self):
        t = self.t + 0.033
        if t >= TOTAL:
            t = 0
        self.seek(t)

    def toggle_play(self):
        self.playing = not self.playing
        self.panel.play.setText("⏸" if self.playing else "▶")
        self.task.setText("Đang phát" if self.playing else "Sẵn sàng")
        self.timer.start() if self.playing else self.timer.stop()
