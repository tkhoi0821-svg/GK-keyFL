"""GK KeyFL - diem vao cua ung dung (dang nhap -> trang chu -> editor)."""
import sys
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget
import gk_theme as theme
import gk_recent
import gk_debug
import gk_safe
from PySide6.QtWidgets import QMessageBox
from gk_model import LOGO
from gk_auth import load_user, save_user, clear_user
from gk_pages import LoginPage, HomePage
from gk_editor import EditorPage


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GK KeyFL")
        self.resize(1360, 820)
        self.login = LoginPage()
        self.login.entered.connect(self.on_login)
        self.home = HomePage()
        self.home.new_project.connect(self.open_editor)
        self.home.open_file.connect(self.open_path)
        self.home.sign_out.connect(self.on_sign_out)
        self.editor = EditorPage()
        self.editor.home_requested.connect(self.go_home)
        self.home.new_template.connect(self.open_template)
        self.home.settings_requested.connect(self.editor.open_settings)
        self.home.account_changed.connect(self.on_account)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.login)    # 0
        self.stack.addWidget(self.home)     # 1
        self.stack.addWidget(self.editor)   # 2
        self.setCentralWidget(self.stack)
        u = load_user()
        if u:
            self.set_user(*u)
            self.stack.setCurrentIndex(1)

    def set_user(self, name, email):
        self.home.set_user(name, email)
        self.editor.set_user(name)

    def on_login(self, name, email):
        save_user(name, email)
        self.set_user(name, email)
        self.stack.setCurrentIndex(1)

    def on_sign_out(self):
        clear_user()
        self.stack.setCurrentIndex(0)

    def open_editor(self, name, ratio):
        self.editor.open_project(name, ratio)
        self.stack.setCurrentIndex(2)

    def open_template(self, key, ratio):
        self.editor.open_project("Untitled", ratio)
        self.editor.apply_template(key)
        self.stack.setCurrentIndex(2)

    def on_account(self, name, email):
        save_user(name, email)
        self.set_user(name, email)

    def open_path(self, path):
        self.editor.pause()
        if self.editor.load_path(path):
            self.stack.setCurrentIndex(2)
        else:
            gk_recent.remove(path)
            self.home.refresh()
            self.home.notify("Không mở được dự án — đã gỡ khỏi danh sách")

    def maybe_recover(self):
        p = gk_safe.pending_recovery()
        if not p:
            return
        r = QMessageBox.question(self, "Khôi phục dự án?",
                                 "Lần trước ứng dụng bị đóng đột ngột. Có bản tự lưu của dự án bạn đang làm.\n\nKhôi phục nó?",
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if r == QMessageBox.Yes:
            self.editor.pause()
            if self.editor.load_path(p):
                gk_recent.remove(p)
                self.stack.setCurrentIndex(2)
                self.editor.log("Đã khôi phục bản tự lưu. Nhấn Ctrl+S để lưu thành tệp .gkproj.")
        gk_safe.discard_recovery()

    def go_home(self):
        self.editor.pause()
        self.stack.setCurrentIndex(1)


if __name__ == "__main__":
    gk_debug.install_hooks()
    gk_safe.begin()
    app = QApplication(sys.argv)
    app.aboutToQuit.connect(gk_safe.end)
    app.setWindowIcon(QIcon(LOGO))
    theme.init_fonts()
    theme.apply_saved(app)
    gk_safe.startup_prompt()
    w = Main()
    w.show()
    w.maybe_recover()
    sys.exit(app.exec())
