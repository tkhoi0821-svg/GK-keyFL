"""He thong Plugin cho GK KeyFL.

Plugin la 1 tep .py (hoac .gkplugin = ma Python) dat trong  <Assets>/Plugin/.
Tep phai co ham  register(api)  va (tuy chon) bien  PLUGIN = {"name": ..., "version": ..., "author": ..., "desc": ...}.
Lan dau, moi plugin phai duoc nguoi dung cho phep (nho theo ma bam SHA-256; sua tep -> hoi lai).
"""
import os, hashlib, importlib.util, importlib.machinery, traceback
import gk_settings
import gk_model
import gk_safe

EVENTS = ("seek", "play", "pause", "layer_added", "layer_removed", "layer_selected", "keys_changed",
          "project_new", "project_loaded", "project_saved", "theme_changed")

EXTS = (".py", ".gkplugin")


def plugin_dir(editor):
    d = os.path.join(editor.project.root, "Plugin")
    os.makedirs(d, exist_ok=True)
    return d


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


class PluginAPI:
    """Doi tuong duy nhat ma plugin nhin thay. Moi loi trong ham cua plugin deu duoc bat va ghi vao Console."""

    def __init__(self, host, pid):
        self._host, self._pid = host, pid
        self.actions, self.commands, self.docks, self.hooks = [], {}, [], {e: [] for e in EVENTS}
        self.tools, self.eases, self.kinds, self.themes, self.shortcuts = [], [], [], [], []

    # ---- thong tin
    @property
    def editor(self):
        return self._host.ed

    def log(self, s):
        self._host.ed.log("[%s] %s" % (self._pid, s))

    # ---- giao dien
    def add_action(self, text, fn):
        """Them muc vao menu Plugin > <ten plugin>."""
        self.actions.append((text, self._safe(fn)))

    def add_command(self, name, fn):
        """Them lenh cho o Lenh: fn(args: list[str])."""
        self.commands[name.lower()] = self._safe(fn)

    def add_panel(self, title, widget):
        """Them 1 panel dock (QWidget) canh tab Lenh."""
        self.docks.append(self._host.make_panel(self._pid, title, widget))

    def on(self, event, fn):
        """Dang ky su kien. Cac su kien (EVENTS):
        seek(t) · play() · pause() · layer_added(L) · layer_removed(L) · layer_selected(L hoac None)
        keys_changed() · project_new() · project_loaded(path) · project_saved(path) · theme_changed()"""
        if event not in EVENTS:
            self.log("Su kien khong ton tai: %s (co: %s)" % (event, ", ".join(EVENTS)))
            return
        self.hooks[event].append(self._safe(fn))

    # ---- mo rong: noi suy, loai lop, theme, phim tat, cong cu
    def add_ease(self, key, name, fn):
        """Them kieu noi suy. fn(u) nhan u trong 0..1 va tra ve tien do (0 -> 1; duoc phep vuot de nay).
        Xuat hien trong menu Tool, bang Thuoc tinh/Do thi va Tuy chon. Tra ve khoa day du."""
        full = "%s.%s" % (self._pid, key)
        gk_model.CUSTOM_EASE[full] = fn
        gk_model.EASES.append((full, name))
        self.eases.append(full)
        return full

    def add_layer_kind(self, name, painter, row=1, color="#888888", body=(0.24, 0.36), icon=None, kind=None):
        """Them loai lop moi vao nut + Add.
        painter(p, layer, rect, t): ve vao QPainter p, rect (QRectF) tam o goc toa do; phep bien doi
        (vi tri/xoay/ti le) da duoc ap san. Dung layer.extra (dict) de luu tham so rieng, no duoc luu cung du an.
        row: 0 Text, 1 Overlay, 2 Video, 3 Audio (hang tren timeline). icon(p, rect): bieu tuong nho (tuy chon)."""
        kind = "%s.%s" % (self._pid, kind or name.lower().replace(" ", "_"))
        gk_model.KINDS[name] = (kind, row, color)
        gk_model.BODY[kind] = tuple(body)
        gk_model.PAINTERS[kind] = self._once(painter, "ve loai lop '%s'" % name)
        if icon:
            gk_model.ICONS[kind] = self._once(icon, "bieu tuong '%s'" % name)
        act = self._host.ed.lp.add_menu.addAction(name)
        self.kinds.append((name, kind, act))
        return kind

    def add_theme(self, key, name, **colors):
        """Them theme. colors ghi de cac khoa trong bang mau (bg0..bg3, line, text, text2, text3, accent,
        accent_hi, accent_dim, on_accent, bar1, bar2, checker_a/b, frame, dark). Khoa khac lay tu theme mac dinh."""
        import gk_theme
        full = "%s.%s" % (self._pid, key)
        gk_theme.THEMES[full] = dict(gk_theme._BASE, name=name, **colors)
        self.themes.append(full)
        return full

    def add_shortcut(self, seq, fn):
        """Phim tat toan cua so editor, vd 'Ctrl+Alt+P'."""
        from PySide6.QtGui import QKeySequence, QShortcut
        sc = QShortcut(QKeySequence(seq), self._host.ed)
        sc.activated.connect(self._safe(fn))
        self.shortcuts.append(sc)

    def add_tool_action(self, text, fn):
        """Them muc vao menu Tool (duoi cac cong cu co san)."""
        self.tools.append((text, self._safe(fn)))

    # ---- thao tac nhanh tren key frame / phat
    def key(self, layer, channel, t, value, ease=None):
        """Dat key (channel nhu 'scl0', 'pos1', 'op'...). ease la khoa kieu noi suy (ke ca cua plugin)."""
        layer.set(channel, t, value, True)
        if ease:
            for k in layer.kf[channel]:
                if abs(k.t - round(t, 2)) < 0.05:
                    k.e = ease

    def value(self, layer, channel, t=None):
        return layer.get(channel, self._host.ed.t if t is None else t)

    def play(self):
        if not self._host.ed.playing:
            self._host.ed.toggle_play()

    def pause(self):
        self._host.ed.pause()

    def ratio(self):
        return self._host.ed.stage.ratio

    # ---- du lieu
    def time(self):
        return self._host.ed.t

    def seek(self, t):
        self._host.ed.seek(t)

    def layers(self):
        return list(self._host.ed.stage.layers)

    def selected(self):
        return self._host.ed.sel

    def add_layer(self, kind_name="Hình vuông"):
        """kind_name: 'Hình vuông', 'Văn bản', 'Hình ảnh', 'Video', 'Âm thanh'."""
        return self._host.ed.new_layer(kind_name)

    def refresh(self):
        """Goi sau khi sua Layer/key bang code de ve lai canvas, timeline, do thi."""
        self._host.ed._keys_changed()

    def get(self, key, default=None):
        return gk_settings.get("plugin_data", {}).get(self._pid, {}).get(key, default)

    def put(self, key, value):
        d = dict(gk_settings.get("plugin_data", {}))
        d[self._pid] = dict(d.get(self._pid, {}), **{key: value})
        gk_settings.put("plugin_data", d)

    def _once(self, fn, what):
        """Boc ham ve: loi chi bao 1 lan vao Console de khong dung hinh moi khung."""
        state = {"told": False}

        def run(*a):
            try:
                return fn(*a)
            except Exception:
                if not state["told"]:
                    state["told"] = True
                    self._host.ed.log("[%s] Loi %s:\n%s" % (self._pid, what, traceback.format_exc(limit=3)))
        return run

    def _safe(self, fn):
        def run(*a):
            try:
                return fn(*a)
            except Exception:
                self._host.ed.log("[%s] Lỗi:\n%s" % (self._pid, traceback.format_exc(limit=3)))
        return run


class PluginHost:
    def __init__(self, editor):
        self.ed = editor
        self.items = {}          # pid -> dict(path, meta, api, state, error)
        self.docks = []
        self.cmds = {}
        import gk_theme
        gk_theme.bus.changed.connect(lambda: self.emit("theme_changed"))

    # ---------------------------------------------------------------- cai dat
    def _cfg(self):
        c = gk_settings.get("plugins", {})
        return {"trusted": dict(c.get("trusted", {})), "disabled": list(c.get("disabled", []))}

    def _save(self, c):
        gk_settings.put("plugins", c)

    def scan(self):
        d = plugin_dir(self.ed)
        return sorted(os.path.join(d, f) for f in os.listdir(d)
                      if f.lower().endswith(EXTS) and not f.startswith("_") and os.path.isfile(os.path.join(d, f)))

    # ---------------------------------------------------------------- nap
    def load_all(self):
        self.unload_all()
        c = self._cfg()
        if gk_safe.SAFE:
            for path in self.scan():
                pid = os.path.splitext(os.path.basename(path))[0]
                self.items[pid] = dict(path=path, meta={"name": pid}, api=None, state="safe", error="")
            self.ed.log("SAFE MODE: không nạp plugin nào (%d plugin). Menu Plugin > Thoát Safe Mode để nạp lại." % len(self.items))
            return
        for path in self.scan():
            pid = os.path.splitext(os.path.basename(path))[0]
            self.items[pid] = dict(path=path, meta={"name": pid}, api=None, state="off", error="")
            if pid in c["disabled"]:
                continue
            if c["trusted"].get(pid) != _sha(path):
                self.items[pid]["state"] = "untrusted"
                continue
            self._load(pid)
        self.ed.log("Plugin: đã nạp %d / %d" % (sum(1 for i in self.items.values() if i["state"] == "on"), len(self.items)))

    def _load(self, pid):
        it = self.items[pid]
        gk_safe.mark_loading(pid)
        try:
            loader = importlib.machinery.SourceFileLoader("gkplugin_" + pid, it["path"])
            spec = importlib.util.spec_from_loader(loader.name, loader)
            mod = importlib.util.module_from_spec(spec)
            loader.exec_module(mod)
            it["meta"] = dict({"name": pid}, **getattr(mod, "PLUGIN", {}))
            api = PluginAPI(self, pid)
            mod.register(api)
            it["api"], it["state"], it["mod"] = api, "on", mod
            for k, f in api.commands.items():
                self.cmds[k] = f
        except Exception:
            it["state"], it["error"] = "error", traceback.format_exc(limit=3)
            self.ed.log("[%s] Không nạp được:\n%s" % (pid, it["error"]))
        finally:
            gk_safe.clear_loading()

    def _cleanup(self, api):
        for k in api.eases:
            gk_model.CUSTOM_EASE.pop(k, None)
            gk_model.EASES[:] = [e for e in gk_model.EASES if e[0] != k]
        for name, kind, act in api.kinds:
            gk_model.KINDS.pop(name, None)
            for d in (gk_model.BODY, gk_model.PAINTERS, gk_model.ICONS):
                d.pop(kind, None)
            self.ed.lp.add_menu.removeAction(act)
            act.deleteLater()
        if api.themes:
            import gk_theme
            for k in api.themes:
                gk_theme.THEMES.pop(k, None)
            if gk_theme.current_key() in api.themes:
                gk_theme.set_theme(gk_theme.DEFAULT_THEME)
        for sc in api.shortcuts:
            sc.setEnabled(False)
            sc.deleteLater()

    def fill_tools(self, m, act):
        """Muc do plugin them vao menu Tool."""
        rows = [(t, f) for it in self.items.values() if it.get("api") for t, f in it["api"].tools]
        if rows:
            m.addSeparator()
            for t, f in rows:
                act(m, t, f)

    def unload_all(self):
        for it in self.items.values():
            api = it.get("api")
            if api:
                self._cleanup(api)
                try:
                    fn = getattr(it["mod"], "unregister", None)
                    if fn:
                        fn(api)
                except Exception:
                    pass
        for d in self.docks:
            self.ed.removeDockWidget(d)
            d.deleteLater()
        self.docks, self.items, self.cmds = [], {}, {}

    # ---------------------------------------------------------------- panel dock
    def make_panel(self, pid, title, widget):
        from gk_panels import make_dock
        from PySide6.QtCore import Qt
        d = make_dock(self.ed, title, widget, "dock_plugin_%s_%d" % (pid, len(self.docks)))
        self.ed.addDockWidget(Qt.BottomDockWidgetArea, d)
        self.ed.tabifyDockWidget(self.ed.d_console, d)
        self.docks.append(d)
        return d

    # ---------------------------------------------------------------- su kien / lenh
    def emit(self, event, *a):
        for it in self.items.values():
            api = it.get("api")
            if api:
                for f in api.hooks.get(event, []):
                    f(*a)

    def run_command(self, name, args):
        f = self.cmds.get(name.lower())
        if f:
            f(args)
            return True
        return False

    # ---------------------------------------------------------------- cho phep / tat
    def trust(self, pid):
        from PySide6.QtWidgets import QMessageBox
        it = self.items[pid]
        r = QMessageBox.warning(
            self.ed, "Cho phép plugin?",
            "Plugin “%s” là mã Python và sẽ chạy với toàn quyền như chính ứng dụng (đọc/ghi tệp, mạng…).\n\n"
            "Chỉ cho phép nếu bạn tin nguồn của tệp:\n%s" % (it["meta"].get("name", pid), it["path"]),
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if r != QMessageBox.Yes:
            return
        c = self._cfg()
        c["trusted"][pid] = _sha(it["path"])
        c["disabled"] = [x for x in c["disabled"] if x != pid]
        self._save(c)
        self.load_all()

    def set_disabled(self, pid, off):
        c = self._cfg()
        c["disabled"] = [x for x in c["disabled"] if x != pid] + ([pid] if off else [])
        self._save(c)
        self.load_all()

    # ---------------------------------------------------------------- menu Plugin
    def fill_menu(self, m, act):
        """act = EditorPage.act (m, text, fn, checked, enabled)."""
        if not self.items:
            act(m, "Chưa có plugin nào", lambda: None, enabled=False)
        for pid, it in self.items.items():
            name = it["meta"].get("name", pid)
            ver = it["meta"].get("version", "")
            label = name + ((" " + str(ver)) if ver else "")
            if it["state"] == "safe":
                bad = pid in gk_safe.STATE["culprits"]
                act(m, ("⚠  %s — nghi gây sập, đã tắt" if bad else "⏸  %s — chưa nạp (Safe Mode)") % label,
                    lambda: None, enabled=False)
                continue
            if it["state"] == "on":
                sub = m.addMenu(label)
                for text, fn in it["api"].actions:
                    act(sub, text, fn)
                if it["api"].actions:
                    sub.addSeparator()
                desc = it["meta"].get("desc")
                if desc:
                    act(sub, desc, lambda: None, enabled=False)
                act(sub, "Tắt plugin", lambda p=pid: self.set_disabled(p, True))
            elif it["state"] == "untrusted":
                act(m, "🔒  %s — cho phép…" % label, lambda p=pid: self.trust(p))
            elif it["state"] == "error":
                act(m, "⚠  %s — lỗi (xem Console)" % label, lambda p=pid: self.ed.log(self.items[p]["error"]))
            else:
                act(m, "○  %s — bật" % label, lambda p=pid: self.set_disabled(p, False))
        m.addSeparator()
        if gk_safe.SAFE:
            act(m, "🛡  Thoát Safe Mode và nạp plugin", self.exit_safe)
        act(m, "↻  Tải lại plugin", self.load_all)
        act(m, "📂  Mở thư mục Plugin", self.open_folder)

    def exit_safe(self):
        gk_safe.SAFE = False
        self.load_all()
        self.ed.update_safe_chip()

    def open_folder(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(plugin_dir(self.ed)))
