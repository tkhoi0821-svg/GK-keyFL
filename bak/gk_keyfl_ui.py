"""GK KeyFL - diem vao cua ung dung (dang nhap -> trang chu -> editor)."""
import sys
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget
import gk_theme as theme
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
        self.home.open_recent.connect(lambda n: self.open_editor(n, 16 / 9))
        self.home.sign_out.connect(self.on_sign_out)
        self.editor = EditorPage()
        self.editor.home_requested.connect(self.go_home)
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

    def go_home(self):
        self.editor.pause()
        self.stack.setCurrentIndex(1)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(LOGO))
    theme.init_fonts()
    theme.apply_saved(app)
    w = Main()
    w.show()
    sys.exit(app.exec_())
