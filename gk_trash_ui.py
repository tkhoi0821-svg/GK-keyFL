"""Panel Thung rac (muc 52): dang dock nhu cac panel khac, xem danh sach da xoa, khoi phuc / xoa han.
Doc lap: chi phat tin hieu, EditorPage tu quyet dinh cach khoi phuc (dung lai _insert_layer() /
add_layer_clip() cua ong), giong cach Vector Editor / Matte Dialog da lam."""
import datetime
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem
import gk_trash as T


def _fmt(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")


class TrashPanel(QWidget):
    """Danh sach cac muc da xoa trong phien lam viec. restore_requested phat ra 1 TrashItem,
    EditorPage tu lay item.kind / item.payload ra de dung lai ham chen lop / chen clip co san."""
    restore_requested = Signal(object)     # TrashItem
    purge_requested = Signal(object)       # TrashItem - nguoi dung chon xoa han 1 muc (khong con lay lai duoc)

    def __init__(self, trash):
        super().__init__()
        self.setObjectName("Panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.trash = trash
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(8)

        head = QHBoxLayout()
        self.count_lbl = QLabel("Thùng rác trống")
        self.count_lbl.setObjectName("Hint")
        head.addWidget(self.count_lbl, 1)
        self.empty_btn = QPushButton("Dọn sạch")
        self.empty_btn.setObjectName("SmallBtn")
        self.empty_btn.setToolTip("Xoá hẳn mọi mục trong thùng rác (không thể lấy lại)")
        head.addWidget(self.empty_btn)
        v.addLayout(head)

        self.list = QListWidget()
        v.addWidget(self.list, 1)

        row = QHBoxLayout()
        self.restore_btn = QPushButton("↩  Khôi phục")
        self.restore_btn.setObjectName("Accent")
        self.restore_btn.setEnabled(False)
        self.purge_btn = QPushButton("✕  Xoá hẳn")
        self.purge_btn.setObjectName("SmallBtn")
        self.purge_btn.setEnabled(False)
        row.addWidget(self.restore_btn, 1)
        row.addWidget(self.purge_btn)
        v.addLayout(row)

        hint = QLabel("Lớp và clip đã xoá trong phiên làm việc này nằm ở đây. Đóng chương trình sẽ "
                      "dọn sạch thùng rác (không lưu lại qua các lần mở app khác nhau).")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        v.addWidget(hint)

        self.list.itemSelectionChanged.connect(self._sync_buttons)
        self.list.itemDoubleClicked.connect(lambda _it: self._restore())
        self.restore_btn.clicked.connect(self._restore)
        self.purge_btn.clicked.connect(self._purge)
        self.empty_btn.clicked.connect(self._empty_all)
        self.refresh()

    def _sync_buttons(self):
        has = bool(self.list.selectedItems())
        self.restore_btn.setEnabled(has)
        self.purge_btn.setEnabled(has)

    def _selected_item(self):
        its = self.list.selectedItems()
        return its[0].data(Qt.UserRole) if its else None

    def _restore(self):
        it = self._selected_item()
        if it is not None:
            self.restore_requested.emit(it)

    def _purge(self):
        it = self._selected_item()
        if it is not None:
            self.purge_requested.emit(it)

    def _empty_all(self):
        for it in list(self.trash.items):
            self.purge_requested.emit(it)

    def refresh(self):
        self.list.clear()
        icon = {"layer": "▦", "clip": "▭"}
        for it in reversed(self.trash.items):      # moi xoa gan day nhat len dau danh sach
            qi = QListWidgetItem("%s  %s  ·  %s" % (icon.get(it.kind, "•"), it.label, _fmt(it.ts)))
            qi.setData(Qt.UserRole, it)
            self.list.addItem(qi)
        n = len(self.trash)
        self.count_lbl.setText("Trống" if n == 0 else ("%d mục đã xoá" % n))
        self.empty_btn.setEnabled(n > 0)
        self._sync_buttons()
