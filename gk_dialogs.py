"""Hop thoai dung chung: Tai khoan, Cap nhat, Kiem tra he thong, Thong tin."""
import sys, platform, webbrowser
import PySide6
from PySide6.QtCore import Qt, Signal, qVersion
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox,
                             QGridLayout, QWidget)
import gk_update
import gk_diag
import gk_theme as theme

COL = {"ok": "#46a758", "warn": "#e0a526", "bad": "#e5484d"}
ICON = {"ok": "✓", "warn": "⚠", "bad": "✗"}


# ------------------------------------------------------------------ tai khoan
class AccountDialog(QDialog):
    changed = Signal(str, str)
    sign_out = Signal()

    def __init__(self, name, email, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tài khoản — GK KeyFL")
        self.setMinimumWidth(420)
        self.email = email
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 16)
        v.setSpacing(10)
        t = QLabel("Tài khoản")
        t.setObjectName("Title")
        v.addWidget(t)
        guest = not email
        s = QLabel("Bạn đang dùng chế độ khách. Đăng nhập để đồng bộ dự án." if guest else "Đã đăng nhập.")
        s.setObjectName("Hint")
        v.addWidget(s)
        v.addSpacing(6)
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(10)
        self.name = QLineEdit(name)
        self.name.setMaxLength(40)
        for r, (lab, w) in enumerate((("Tên hiển thị", self.name), ("Email", QLabel(email or "—")))):
            l = QLabel(lab)
            l.setObjectName("Sub")
            g.addWidget(l, r, 0)
            g.addWidget(w, r, 1)
        g.setColumnStretch(1, 1)
        v.addLayout(g)
        v.addSpacing(8)
        h = QHBoxLayout()
        so = QPushButton("Đăng nhập" if guest else "Đăng xuất")
        so.clicked.connect(lambda: (self.sign_out.emit(), self.close()))
        h.addWidget(so)
        h.addStretch()
        cl = QPushButton("Đóng")
        cl.clicked.connect(self.close)
        sv = QPushButton("Lưu tên")
        sv.setObjectName("Accent")
        sv.clicked.connect(self.save)
        sv.setDefault(True)
        h.addWidget(cl)
        h.addWidget(sv)
        v.addLayout(h)

    def save(self):
        n = self.name.text().strip()
        if n:
            self.changed.emit(n, self.email)
            self.close()


def open_account(parent, name, email, on_changed, on_sign_out):
    d = AccountDialog(name, email, parent)
    d.changed.connect(on_changed)
    d.sign_out.connect(on_sign_out)
    d.exec()


# ------------------------------------------------------------------ cap nhat
def check_updates(parent, silent=False, on_result=None):
    """silent=True: chi bao khi co ban moi (dung khi khoi dong)."""
    ck = gk_update.Checker(parent)
    parent._upd_checker = ck           # giu tham chieu

    def done(r):
        if on_result:
            on_result(r)
        if not r["ok"]:
            if not silent:
                QMessageBox.information(parent, "Cập nhật", "Không kiểm tra được bản cập nhật.\n\n%s\n\nMáy chủ: %s"
                                        % (r["error"], r["source"]))
        elif r["newer"]:
            if silent:
                return
            m = QMessageBox(parent)
            m.setWindowTitle("Có bản cập nhật")
            m.setText("Có bản mới %s (bạn đang dùng %s)." % (r["latest"], r["current"]))
            m.setInformativeText(r["notes"] or "")
            go = m.addButton("Tải về" if r["url"] else "OK", QMessageBox.ButtonRole.AcceptRole)
            m.addButton("Để sau", QMessageBox.ButtonRole.RejectRole)
            m.exec()
            if m.clickedButton() is go and r["url"]:
                webbrowser.open(r["url"])
        elif not silent:
            QMessageBox.information(parent, "Cập nhật", "Bạn đang dùng bản mới nhất (%s)." % r["current"])
    ck.done.connect(done, Qt.ConnectionType.QueuedConnection)
    ck.start()


# ------------------------------------------------------------------ kiem tra he thong
class DiagDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kiểm tra hệ thống — GK KeyFL")
        self.resize(640, 440)
        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(20, 18, 20, 16)
        self.v.setSpacing(8)
        t = QLabel("Kiểm tra hệ thống")
        t.setObjectName("Title")
        self.sum = QLabel()
        self.sum.setObjectName("Hint")
        self.v.addWidget(t)
        self.v.addWidget(self.sum)
        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        self.v.addLayout(self.body)
        self.v.addStretch()
        h = QHBoxLayout()
        again = QPushButton("Chạy lại")
        again.clicked.connect(self.run)
        cp = QPushButton("Sao chép báo cáo")
        cp.clicked.connect(lambda: QGuiApplication.clipboard().setText(gk_diag.report_text(self.res)))
        cl = QPushButton("Đóng")
        cl.setObjectName("Accent")
        cl.clicked.connect(self.close)
        h.addWidget(again)
        h.addWidget(cp)
        h.addStretch()
        h.addWidget(cl)
        self.v.addLayout(h)
        self.run()

    def run(self):
        while self.body.count():
            w = self.body.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.res = gk_diag.run_checks()
        for st, name, det in self.res:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            ic = QLabel(ICON[st])
            ic.setFixedWidth(22)
            ic.setStyleSheet("color:%s;font-weight:700;font-size:15px" % COL[st])
            n = QLabel(name)
            n.setFixedWidth(130)
            n.setStyleSheet("font-weight:700")
            d = QLabel(det)
            d.setObjectName("Sub")
            d.setWordWrap(True)
            h.addWidget(ic)
            h.addWidget(n)
            h.addWidget(d, 1)
            self.body.addWidget(row)
        bad = sum(1 for r in self.res if r[0] == "bad")
        warn = sum(1 for r in self.res if r[0] == "warn")
        self.sum.setText("Mọi thứ ổn." if not (bad or warn) else "%d lỗi, %d cảnh báo." % (bad, warn))


def run_diag(parent):
    DiagDialog(parent).exec()


# ------------------------------------------------------------------ thong tin
def show_about(parent):
    QMessageBox.about(parent, "Thông tin GK KeyFL",
                      "<h3>GK KeyFL %s</h3>"
                      "<p>Trình chỉnh sửa key frame nhẹ, nhiều panel kéo thả, hỗ trợ plugin.</p>"
                      "<p>Python %s · Qt %s · PySide6 %s<br>%s %s</p>"
                      "<p>© GrayKazu</p>" % (gk_update.VERSION, platform.python_version(), qVersion(),
                                              PySide6.__version__, platform.system(), platform.release()))
