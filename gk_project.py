"""Panel Assets kieu Unity: cay thu muc | luoi tep co thumbnail | keo tha, doi ten, xoa, tim kiem."""
import os
from PySide6.QtCore import Qt, QSize, QRectF, QUrl, QMimeData, QFile, QFileSystemWatcher, Signal
from PySide6.QtGui import (QColor, QPainter, QPen, QBrush, QFont, QPixmap, QIcon, QImageReader, QDrag,
                         QDesktopServices, QKeySequence)
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QLineEdit, QSplitter,
                             QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem, QAbstractItemView, QMenu,
                             QMessageBox, QInputDialog, QFileDialog)
import gk_theme as theme
import gk_settings
import gk_assets as A
from gk_theme import T, mk
from gk_panels import styled, folder_icon

KIND_COL = {"video": "#2f8fe0", "audio": "#2fb37a", "model": "#9b59d0", "plugin": "#e0a526", "image": "#2f8fe0",
            "file": "#7a7a88"}
UR, UK = Qt.UserRole, Qt.UserRole + 1     # du lieu item: duong dan, loai


def file_icon(kind, ext, size):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    w, h = size * 0.62, size * 0.8
    x, y = (size - w) / 2, (size - h) / 2
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#f2f2f6"))
    p.drawRoundedRect(QRectF(x, y, w, h), 6, 6)
    col = QColor(KIND_COL.get(kind, KIND_COL["file"]))
    p.setBrush(col)
    p.drawRoundedRect(QRectF(x, y + h * 0.58, w, h * 0.42), 6, 6)
    p.drawRect(QRectF(x, y + h * 0.58, w, 8))
    p.setPen(QColor("#ffffff"))
    p.setFont(mk(theme.FONT_BODY, max(9, int(size * 0.13)), QFont.Bold))
    p.drawText(QRectF(x, y + h * 0.58, w, h * 0.42), Qt.AlignCenter, (ext or "").lstrip(".").upper()[:4])
    p.end()
    return QIcon(pm)


class AssetList(QListWidget):
    """Luoi tep: keo ra (de tha len canvas / timeline / thu muc khac) va nhan tha vao (tep tu may hoac noi bo)."""
    dropped = Signal(list, str, bool)     # duong dan, thu muc dich, la keo noi bo?

    def __init__(self):
        super().__init__()
        self.cur = ""
        self._hot = None
        self.setViewMode(QListWidget.IconMode)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setWordWrap(True)
        self.setUniformItemSizes(True)
        self.setSpacing(4)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

    def startDrag(self, actions):
        items = self.selectedItems()
        if not items:
            return
        paths = [it.data(UR) for it in items]
        md = QMimeData()
        md.setUrls([QUrl.fromLocalFile(p) for p in paths])
        md.setData(A.MIME, "\n".join(paths).encode("utf-8"))
        md.setData(A.MIME_INT, b"1")
        d = QDrag(self)
        d.setMimeData(md)
        d.setPixmap(items[0].icon().pixmap(48, 48))
        d.exec_(Qt.CopyAction | Qt.MoveAction, Qt.CopyAction)

    def _folder_at(self, pos):
        it = self.itemAt(pos)
        return it if (it is not None and it.data(UK) == "dir") else None

    def _hl(self, it):
        if self._hot is not None:
            self._hot.setBackground(QBrush())
        self._hot = it
        if it is not None:
            it.setBackground(QColor(T["accent_dim"]))

    def dragEnterEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() or md.hasFormat(A.MIME):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() or md.hasFormat(A.MIME):
            self._hl(self._folder_at(e.pos()))
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self._hl(None)

    def dropEvent(self, e):
        md = e.mimeData()
        paths = A.mime_paths(md)
        tgt = self._folder_at(e.pos())
        dest = tgt.data(UR) if tgt is not None else self.cur
        internal = md.hasFormat(A.MIME_INT) and e.source() is self
        self._hl(None)
        e.acceptProposedAction()
        if paths and dest:
            self.dropped.emit(paths, dest, internal)


class ProjectPanel(QWidget):
    open_asset = Signal(str)       # nhap dup tep -> dua vao timeline
    message = Signal(str)

    def __init__(self, root=None):
        super().__init__()
        styled(self, "Panel")
        self.root = root or gk_settings.get("assets_root") or A.default_root()
        self.cur, self.hist, self.size, self.cache = self.root, [], 80, {}
        try:
            A.ensure_root(self.root)
        except OSError as ex:
            self.root = self.cur = os.path.expanduser("~")
            self.message.emit("Không tạo được thư mục Assets: %s" % ex)
        self.watch = QFileSystemWatcher(self)
        self.watch.directoryChanged.connect(lambda _: self.refresh())

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        bar = styled(QWidget(), "ViewBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(8, 5, 8, 5)
        h.setSpacing(6)
        self.back, self.up = QPushButton("‹"), QPushButton("↑")
        for b, tip in ((self.back, "Quay lại"), (self.up, "Lên thư mục cha")):
            b.setObjectName("SmallBtn")
            b.setFixedWidth(30)
            b.setToolTip(tip)
            h.addWidget(b)
        self.crumb_w = QWidget()
        self.crumb_l = QHBoxLayout(self.crumb_w)
        self.crumb_l.setContentsMargins(4, 0, 0, 0)
        self.crumb_l.setSpacing(0)
        h.addWidget(self.crumb_w, 1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm trong thư mục…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(150)
        h.addWidget(self.search)
        self.newf = QPushButton("＋ Thư mục")
        self.newf.setObjectName("SmallBtn")
        self.imp = QPushButton("⇪ Nhập…")
        self.imp.setObjectName("Accent")
        h.addWidget(self.newf)
        h.addWidget(self.imp)
        self.zoom = QSlider(Qt.Horizontal)
        self.zoom.setRange(48, 128)
        self.zoom.setValue(self.size)
        self.zoom.setFixedWidth(80)
        self.zoom.setToolTip("Cỡ biểu tượng")
        h.addWidget(self.zoom)
        v.addWidget(bar)

        sp = QSplitter(Qt.Horizontal)
        sp.setChildrenCollapsible(False)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(110)
        self.list = AssetList()
        sp.addWidget(self.tree)
        sp.addWidget(self.list)
        sp.setStretchFactor(1, 1)
        sp.setSizes([150, 600])
        v.addWidget(sp, 1)
        foot = styled(QWidget(), "ViewBarBottom")
        fh = QHBoxLayout(foot)
        fh.setContentsMargins(10, 3, 10, 3)
        self.status = QLabel("")
        self.status.setObjectName("Hint")
        fh.addWidget(self.status)
        v.addWidget(foot)

        self.back.clicked.connect(self.go_back)
        self.up.clicked.connect(self.go_up)
        self.search.textChanged.connect(lambda _: self.refresh())
        self.newf.clicked.connect(self.new_folder)
        self.imp.clicked.connect(self.import_files)
        self.zoom.valueChanged.connect(self._zoom)
        self.tree.itemClicked.connect(lambda it, _c=0: self.go(it.data(0, UR)))
        self.list.itemDoubleClicked.connect(self._open)
        self.list.dropped.connect(self.on_dropped)
        self.list.customContextMenuRequested.connect(self.menu)
        QShortcut(QKeySequence(Qt.Key_F2), self.list, activated=self.rename_sel).setContext(Qt.WidgetShortcut)
        QShortcut(QKeySequence(Qt.Key_Delete), self.list, activated=self.delete_sel).setContext(Qt.WidgetShortcut)
        theme.bus.changed.connect(self._theme)
        self.go(self.cur, push=False)

    # ------------------------------------------------------------ dieu huong
    def go(self, path, push=True):
        if not path or not os.path.isdir(path) or not A.inside(self.root, path):
            return
        if push and path != self.cur:
            self.hist.append(self.cur)
        old = self.watch.directories()
        if old:
            self.watch.removePaths(old)
        self.cur = path
        self.list.cur = path
        self.watch.addPath(path)
        self.refresh()

    def go_back(self):
        if self.hist:
            self.go(self.hist.pop(), push=False)

    def go_up(self):
        if os.path.realpath(self.cur) != os.path.realpath(self.root):
            self.go(os.path.dirname(self.cur))

    def _zoom(self, v):
        self.size = v
        self.refresh()

    def _theme(self):
        self.cache.clear()
        self.refresh()

    def _open(self, it):
        p = it.data(UR)
        if it.data(UK) == "dir":
            self.go(p)
        else:
            self.open_asset.emit(p)

    # ------------------------------------------------------------ ve lai
    def rel(self, p):
        r = os.path.relpath(p, self.root)
        return [] if r == "." else r.split(os.sep)

    def build_crumbs(self):
        while self.crumb_l.count():
            w = self.crumb_l.takeAt(0).widget()
            if w:
                w.deleteLater()
        parts, path = ["Assets"] + self.rel(self.cur), self.root
        for i, name in enumerate(parts):
            if i:
                path = os.path.join(path, name)
                sep = QLabel("›")
                sep.setObjectName("Hint")
                self.crumb_l.addWidget(sep)
            b = QPushButton(name)
            b.setFlat(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("QPushButton{border:none;background:transparent;padding:3px 6px;font-weight:%s;}"
                            "QPushButton:hover{background:%s;border-radius:5px;}" %
                            ("700" if i == len(parts) - 1 else "500", T["bg3"]))
            b.clicked.connect(lambda _=False, p=path: self.go(p))
            self.crumb_l.addWidget(b)
        self.crumb_l.addStretch()

    def build_tree(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        cur_item = [None]

        def add(parent, path, depth):
            try:
                names = sorted((n for n in os.listdir(path) if os.path.isdir(os.path.join(path, n)) and not n.startswith(".")),
                               key=str.lower)
            except OSError:
                return
            for n in names:
                p = os.path.join(path, n)
                it = QTreeWidgetItem(parent, [n])
                it.setData(0, UR, p)
                if os.path.realpath(p) == os.path.realpath(self.cur):
                    cur_item[0] = it
                if depth < 6:
                    add(it, p, depth + 1)

        root_it = QTreeWidgetItem(self.tree, ["Assets"])
        root_it.setData(0, UR, self.root)
        if os.path.realpath(self.root) == os.path.realpath(self.cur):
            cur_item[0] = root_it
        add(root_it, self.root, 0)
        self.tree.expandToDepth(1)
        if cur_item[0] is not None:
            self.tree.setCurrentItem(cur_item[0])
        self.tree.blockSignals(False)

    def thumb(self, path):
        try:
            key = (path, os.path.getmtime(path), self.size)
        except OSError:
            return None
        if key in self.cache:
            return self.cache[key]
        ic = None
        rd = QImageReader(path)
        rd.setAutoTransform(True)
        sz = rd.size()
        if sz.isValid():
            rd.setScaledSize(sz.scaled(self.size - 8, self.size - 8, Qt.KeepAspectRatio))
            img = rd.read()
            if not img.isNull():
                pm = QPixmap(self.size, self.size)
                pm.fill(Qt.transparent)
                p = QPainter(pm)
                p.setRenderHint(QPainter.Antialiasing)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(T["bg2"]))
                p.drawRoundedRect(QRectF(0, 0, self.size, self.size), 8, 8)
                t = QPixmap.fromImage(img)
                p.drawPixmap((self.size - t.width()) // 2, (self.size - t.height()) // 2, t)
                p.end()
                ic = QIcon(pm)
        self.cache[key] = ic
        return ic

    def refresh(self):
        self.build_crumbs()
        self.build_tree()
        self.list.setIconSize(QSize(self.size, self.size))
        self.list.setGridSize(QSize(self.size + 30, self.size + 46))
        self.list.clear()
        q = self.search.text().strip().lower()
        try:
            names = sorted(os.listdir(self.cur), key=lambda n: (not os.path.isdir(os.path.join(self.cur, n)), n.lower()))
        except OSError:
            names = []
        n = 0
        for name in names:
            if name.startswith(".") or (q and q not in name.lower()):
                continue
            p = os.path.join(self.cur, name)
            k = A.kind_of(p)
            if k == "dir":
                ic = folder_icon(A.FOLDER_KEY.get(name.lower(), ""), self.size)
            elif k == "image":
                ic = self.thumb(p) or file_icon("image", os.path.splitext(name)[1], self.size)
            else:
                ic = file_icon(k, os.path.splitext(name)[1], self.size)
            it = QListWidgetItem(ic, name)
            it.setData(UR, p)
            it.setData(UK, k)
            it.setToolTip(p)
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.list.addItem(it)
            n += 1
        self.status.setText("%d mục  ·  kéo tệp từ máy vào đây, hoặc kéo tệp lên canvas / timeline để dùng" % n)
        self.back.setEnabled(bool(self.hist))
        self.up.setEnabled(os.path.realpath(self.cur) != os.path.realpath(self.root))

    # ------------------------------------------------------------ thao tac tep
    def selected(self):
        return [it.data(UR) for it in self.list.selectedItems()]

    def new_folder(self):
        name, ok = QInputDialog.getText(self, "Thư mục mới", "Tên thư mục:")
        name = A.valid_name(name) if ok else None
        if name:
            try:
                os.makedirs(A.unique_path(self.cur, name))
            except OSError as ex:
                self.message.emit("Không tạo được thư mục: %s" % ex)
            self.refresh()

    def import_files(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Nhập tệp vào Assets", "", "Tất cả tệp (*)")
        if fs:
            self.on_dropped(fs, self.cur, False)

    def on_dropped(self, paths, dest, internal):
        done = 0
        for p in paths:
            try:
                r = A.move_into(self.root, p, dest) if internal else A.copy_into(self.root, p, dest)
            except OSError as ex:
                self.message.emit("Lỗi: %s" % ex)
                r = None
            done += 1 if r else 0
        self.refresh()
        if done:
            self.message.emit("Đã %s %d mục vào %s" % ("chuyển" if internal else "nhập", done, os.path.basename(dest) or "Assets"))

    def rename_sel(self):
        s = self.selected()
        if len(s) != 1:
            return
        old = s[0]
        name, ok = QInputDialog.getText(self, "Đổi tên", "Tên mới:", text=os.path.basename(old))
        name = A.valid_name(name) if ok else None
        if not name or name == os.path.basename(old):
            return
        new = os.path.join(os.path.dirname(old), name)
        if os.path.exists(new):
            self.message.emit("Đã có '%s' trong thư mục này." % name)
            return
        try:
            os.rename(old, new)
        except OSError as ex:
            self.message.emit("Không đổi tên được: %s" % ex)
        self.refresh()

    def delete_sel(self):
        s = [p for p in self.selected() if A.inside(self.root, p)]
        if not s:
            return
        msg = "Chuyển %d mục vào thùng rác?" % len(s)
        if QMessageBox.question(self, "Xoá", msg) != QMessageBox.Yes:
            return
        for p in s:
            ok = False
            try:
                r = QFile.moveToTrash(p)
                ok = r[0] if isinstance(r, tuple) else bool(r)
            except AttributeError:
                ok = False
            if not ok:
                self.message.emit("Không chuyển được '%s' vào thùng rác nên không xoá." % os.path.basename(p))
        self.refresh()

    def reveal(self, path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path if os.path.isdir(path) else os.path.dirname(path)))

    def choose_root(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục Assets", self.root)
        if d:
            self.root = self.cur = d
            A.ensure_root(d)
            gk_settings.put("assets_root", d)
            self.hist.clear()
            self.cache.clear()
            self.go(d, push=False)
            self.message.emit("Thư mục Assets: " + d)

    def ingest(self, path):
        r = A.ingest(self.root, path)
        self.refresh()
        return r

    def menu(self, pos):
        m = QMenu(self)
        it = self.list.itemAt(pos)

        def act(text, fn, enabled=True):
            a = m.addAction(text)
            a.setEnabled(enabled)
            a.triggered.connect(lambda _=False, f=fn: f())

        if it is not None:
            if not it.isSelected():
                self.list.clearSelection()
                it.setSelected(True)
            p = it.data(UR)
            if it.data(UK) == "dir":
                act("Mở thư mục", lambda: self.go(p))
            else:
                act("Thêm vào timeline", lambda: self.open_asset.emit(p))
            m.addSeparator()
            act("Đổi tên…   (F2)", self.rename_sel, len(self.selected()) == 1)
            act("Xoá (vào thùng rác)   (Del)", self.delete_sel)
            m.addSeparator()
            act("Mở vị trí trong trình quản lý tệp", lambda: self.reveal(p))
        else:
            act("＋ Thư mục mới…", self.new_folder)
            act("⇪ Nhập tệp…", self.import_files)
            m.addSeparator()
            act("Làm mới", self.refresh)
            act("Mở thư mục này trong trình quản lý tệp", lambda: self.reveal(self.cur))
        m.exec_(self.list.mapToGlobal(pos))
