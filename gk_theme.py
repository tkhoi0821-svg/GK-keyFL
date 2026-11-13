"""Font + he thong Theme (doi mau ca editor) + stylesheet."""
import os, math
from PySide6.QtCore import QObject, QPointF, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette, QPolygonF
import gk_settings
import gk_prefs as prefs

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DISPLAY = FONT_COND = FONT_BODY = "Sans Serif"


def init_fonts():
    """Nap font trong thu muc fonts/ (neu co) roi chon font dep nhat dang co."""
    global FONT_DISPLAY, FONT_COND, FONT_BODY
    fd = os.path.join(HERE, "fonts")
    if os.path.isdir(fd):
        for f in sorted(os.listdir(fd)):
            if f.lower().endswith((".ttf", ".otf")):
                QFontDatabase.addApplicationFont(os.path.join(fd, f))
    have = set(QFontDatabase().families())

    def pick(cands, fb):
        return next((c for c in cands if c in have), fb)

    FONT_DISPLAY = pick(["Lexend", "Lexend Deca", "Outfit", "Be Vietnam Pro", "Montserrat", "Poppins", "Noto Sans", "DejaVu Sans"], "Sans Serif")
    FONT_COND = pick(["Oswald", "Barlow Condensed", "Saira Condensed", "Roboto Condensed", "Fira Sans Condensed",
                      "Noto Sans Condensed", "DejaVu Sans Condensed"], "Sans Serif")
    FONT_BODY = pick(["Inter", "Be Vietnam Pro", "Nunito", "Noto Sans", "Cantarell", "DejaVu Sans"], "Sans Serif")


def mk(family, px, weight=QFont.Normal):
    f = QFont(family)
    f.setPixelSize(int(px))
    f.setWeight(weight)
    return f


def mixc(c1, c2, t):
    a, b = QColor(c1), QColor(c2)
    t = max(0.0, min(1.0, t))
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


def star(cx, cy, R, r, n, rot=-90):
    pts = []
    for i in range(n * 2):
        a = math.radians(rot + i * 180 / n)
        rad = R if i % 2 == 0 else r
        pts.append(QPointF(cx + rad * math.cos(a), cy + rad * math.sin(a)))
    return QPolygonF(pts)


# ------------------------------------------------------------------ themes
# bg0: nen sau cung / o nhap   bg1: panel   bg2: thanh tieu de / the   bg3: nut / hover
_BASE = dict(
    bg0="#0b0b0f", bg1="#131318", bg2="#1a1a21", bg3="#24242d", line="#2c2c36",
    text="#e8e8f0", text2="#9a9aa8", text3="#6b6b78",
    accent="#7a2bff", accent_hi="#9150ff", accent_dim="#2a1a63", on_accent="#ffffff",
    bar1="#2b2160", bar2="#43309a", on_bar="#ffffff",
    checker_a="#2a2a32", checker_b="#1e1e24", frame="#38b6ff", dark=True)

THEMES = {
    "gk": dict(_BASE, name="GK Tím (mặc định)"),
    "unity": dict(_BASE, name="Unity Xám",
                  bg0="#1e1e1e", bg1="#282828", bg2="#333333", bg3="#414141", line="#1a1a1a",
                  text="#d6d6d6", text2="#9b9b9b", text3="#727272",
                  accent="#4c8fd6", accent_hi="#6aa6e6", accent_dim="#2c5d87",
                  bar1="#3a3a3a", bar2="#3a3a3a", checker_a="#3a3a3a", checker_b="#303030", frame="#4c8fd6"),
    "blender": dict(_BASE, name="Blender Cam",
                    bg0="#1d1d1d", bg1="#303030", bg2="#3d3d3d", bg3="#4b4b4b", line="#1b1b1b",
                    text="#e6e6e6", text2="#a8a8a8", text3="#7a7a7a",
                    accent="#e87d0d", accent_hi="#ff9a2e", accent_dim="#5a3a12",
                    bar1="#3d3d3d", bar2="#3d3d3d", checker_a="#444444", checker_b="#383838", frame="#e87d0d"),
    "alight": dict(_BASE, name="Alight Đen Hồng",
                   bg0="#000000", bg1="#0d0d0d", bg2="#171717", bg3="#242424", line="#2a2a2a",
                   text="#f2f2f2", text2="#9a9a9a", text3="#666666",
                   accent="#ff2d6f", accent_hi="#ff5c90", accent_dim="#4a1228",
                   bar1="#141414", bar2="#202020", checker_a="#1c1c1c", checker_b="#121212", frame="#ff2d6f"),
    "teal": dict(_BASE, name="Teal (bản cũ)",
                 bg0="#050809", bg1="#0e1416", bg2="#17262a", bg3="#22373c", line="#2b4247",
                 text="#e6f0f1", text2="#8fb0b4", text3="#5f8085",
                 accent="#3f9ba3", accent_hi="#58b6be", accent_dim="#1f4a50",
                 bar1="#3f7a80", bar2="#3f7a80", checker_a="#ffffff", checker_b="#000000", frame="#2fb4ff"),
    "light": dict(_BASE, name="Sáng", dark=False,
                  bg0="#dcdce3", bg1="#ececf1", bg2="#f6f6fa", bg3="#e0e0e8", line="#c4c4d0",
                  text="#1b1b22", text2="#5d5d6b", text3="#8a8a98",
                  accent="#7a2bff", accent_hi="#8d4bff", accent_dim="#dccbff", on_accent="#ffffff",
                  bar1="#7a2bff", bar2="#a56bff", checker_a="#d3d3db", checker_b="#e6e6ec", frame="#7a2bff"),
}
DEFAULT_THEME = "gk"

T = {}          # theme hien tai (cap nhat tai cho, cac widget doc T[...] luc ve)
_key = DEFAULT_THEME


class _Bus(QObject):
    changed = Signal()


bus = _Bus()


def current_key():
    return _key


def _derive(t):
    t["bg3h"] = mixc(t["bg3"], t["text"], 0.10).name()
    t["line_hi"] = mixc(t["line"], t["text"], 0.25).name()
    t["track_a"] = t["bg1"]
    t["track_b"] = mixc(t["bg1"], t["bg0"], 0.45).name()
    t["playhead"] = "#ff4d5e"
    t["key"] = "#ffd23f"


QSS = """
* { font-family: "@FONT@"; font-size: @FS@px; outline: 0; }
QToolTip { background: @bg2@; color: @text@; border: 1px solid @line@; padding: 4px 6px; }
QLabel { background: transparent; }
QMainWindow, QDialog, QInputDialog { background: @bg0@; }
QMainWindow::separator { background: @bg0@; width: 4px; height: 4px; }
QMainWindow::separator:hover { background: @accent@; }

#TopBar { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 @bar1@, stop:1 @bar2@); border-bottom: 1px solid @line@; }
#TopBar QPushButton { background: transparent; color: @on_bar@; font-weight: 600; padding: 6px 11px; border: none; border-radius: 6px; }
#TopBar QPushButton:hover, #TopBar QPushButton:pressed { background: rgba(255,255,255,45); }
#TopBar QPushButton::menu-indicator { image: none; width: 0px; }
#TopBar QLabel { color: @on_bar@; font-weight: 600; }

QMenu { background: @bg2@; color: @text@; border: 1px solid @line_hi@; padding: 5px; border-radius: 8px; }
QMenu::item { padding: 6px 28px 6px 32px; border-radius: 5px; }
QMenu::item:selected { background: @accent@; color: @on_accent@; }
QMenu::indicator { width: 10px; height: 10px; left: 12px; border-radius: 5px; }
QMenu::indicator:checked { background: @accent_hi@; }
QMenu::indicator:checked:selected { background: @on_accent@; }
QMenu::item:disabled { color: @text3@; }
QMenu::separator { height: 1px; background: @line@; margin: 5px 8px; }

#DockTitle { background: @bg2@; border-bottom: 1px solid @line@; }
#DockTitle QLabel { color: @text2@; font-weight: 700; font-size: 11px; }
#DockTitle QToolButton { background: transparent; border: none; color: @text3@; padding: 2px 6px; border-radius: 4px; }
#DockTitle QToolButton:hover { background: @bg3@; color: @text@; }
QDockWidget { color: @text@; }
#Panel { background: @bg1@; }
#Rail { background: @bg2@; border-right: 1px solid @line@; }
QPushButton#Tool { background: transparent; border: none; border-radius: 8px; padding: 0; min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px; }
QPushButton#Tool:hover { background: @bg3@; }
QPushButton#Tool:checked { background: @accent@; }
#ViewBar { background: @bg2@; border-bottom: 1px solid @line@; }
#ViewBarBottom { background: @bg2@; border-top: 1px solid @line@; }

QTabBar { background: transparent; }
QTabBar::tab { background: @bg2@; color: @text2@; padding: 6px 16px; margin-right: 2px; border: none;
    border-top-left-radius: 7px; border-top-right-radius: 7px; font-weight: 600; }
QTabBar::tab:selected { background: @bg1@; color: @text@; border-top: 2px solid @accent@; }
QTabBar::tab:hover:!selected { background: @bg3@; color: @text@; }

QPushButton { background: @bg3@; color: @text@; border: 1px solid @line@; border-radius: 6px; padding: 5px 12px; }
QPushButton:hover { background: @bg3h@; border-color: @line_hi@; }
QPushButton:pressed { background: @bg2@; }
QPushButton:disabled { color: @text3@; background: @bg2@; }
QPushButton:checked { background: @accent_dim@; border-color: @accent@; }
QPushButton#Accent { background: @accent@; color: @on_accent@; border: none; font-weight: 700; padding: 6px 14px; }
QPushButton#Accent:hover { background: @accent_hi@; }
QPushButton#SmallBtn { padding: 4px 8px; font-weight: 700; }
QPushButton#Transport { background: transparent; border: none; border-radius: 15px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; padding: 0; font-size: 14px; }
QPushButton#Transport:hover { background: @bg3@; }
QPushButton#Play { background: @accent@; color: @on_accent@; border: none; border-radius: 17px; min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px; padding: 0; font-size: 14px; }
QPushButton#Play:hover { background: @accent_hi@; }
QPushButton::menu-indicator { image: none; width: 0px; }

QLineEdit, QPlainTextEdit, QDoubleSpinBox, QComboBox { background: @bg0@; color: @text@; border: 1px solid @line@; border-radius: 6px;
    padding: 4px 8px; selection-background-color: @accent@; selection-color: @on_accent@; }
QLineEdit:focus, QPlainTextEdit:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: @accent@; }
QLineEdit:disabled, QDoubleSpinBox:disabled { color: @text3@; background: @bg1@; }
QDoubleSpinBox[axis="x"] { border-left: 3px solid #e5484d; }
QDoubleSpinBox[axis="y"] { border-left: 3px solid #46a758; }
QDoubleSpinBox[axis="z"] { border-left: 3px solid #3e63dd; }
QComboBox { padding-right: 22px; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow { image: none; width: 0px; height: 0px; margin-right: 8px;
    border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid @text2@; }
QComboBox QAbstractItemView { background: @bg2@; color: @text@; border: 1px solid @line_hi@; outline: 0;
    selection-background-color: @accent@; selection-color: @on_accent@; }

QSlider::groove:horizontal { height: 4px; background: @bg3@; border-radius: 2px; }
QSlider::sub-page:horizontal { background: @accent@; border-radius: 2px; }
QSlider::handle:horizontal { background: @text@; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
QSlider::handle:horizontal:hover { background: @accent_hi@; }
QCheckBox { spacing: 8px; color: @text@; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid @line_hi@; border-radius: 4px; background: @bg0@; }
QCheckBox::indicator:checked { background: @accent@; border-color: @accent@; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: @bg3@; border-radius: 5px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: @line_hi@; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: @bg3@; border-radius: 5px; min-width: 28px; }
QScrollBar::handle:horizontal:hover { background: @line_hi@; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QScrollArea { border: none; background: transparent; }

#Section { background: @bg2@; border: 1px solid @line@; border-radius: 10px; }
#SectionHead { background: transparent; border: none; color: @text2@; font-weight: 700; text-align: left; padding: 9px 12px; }
#SectionHead:hover { color: @text@; background: transparent; }
#Title { color: @text@; font-size: 15px; font-weight: 700; }
#Sub { color: @text2@; }
#Hint { color: @text3@; }
#Timecode { color: @text@; font-weight: 700; font-size: 13px; }

QListWidget { background: @bg0@; border: none; color: @text@; }
QListWidget::item { color: @text@; border-radius: 8px; padding: 4px; }
QListWidget::item:hover { background: @bg2@; }
QListWidget::item:selected { background: @accent_dim@; color: @text@; }

QTreeWidget { background: @bg0@; border: none; color: @text@; }
QTreeWidget::item { padding: 4px 2px; border-radius: 6px; }
QTreeWidget::item:hover { background: @bg2@; }
QTreeWidget::item:selected { background: @accent_dim@; color: @text@; }
QSplitter::handle { background: @bg0@; }
QSplitter::handle:hover { background: @accent@; }
QProgressBar { background: rgba(0,0,0,70); border: none; border-radius: 5px; }
QProgressBar::chunk { background: @accent_hi@; border-radius: 5px; }
QStatusBar { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 @bar1@, stop:1 @bar2@); color: @on_bar@; }
QStatusBar::item { border: none; }
QStatusBar QLabel { color: @on_bar@; font-weight: 600; }
#Chip { background: rgba(0,0,0,70); border-radius: 9px; padding: 2px 10px; }
"""


def _palette(t):
    p = QPalette()
    C = QColor
    for role, k in ((QPalette.Window, "bg1"), (QPalette.WindowText, "text"), (QPalette.Base, "bg0"),
                    (QPalette.AlternateBase, "bg2"), (QPalette.Text, "text"), (QPalette.Button, "bg3"),
                    (QPalette.ButtonText, "text"), (QPalette.ToolTipBase, "bg2"), (QPalette.ToolTipText, "text"),
                    (QPalette.Highlight, "accent"), (QPalette.HighlightedText, "on_accent"),
                    (QPalette.PlaceholderText, "text3"), (QPalette.Link, "accent_hi")):
        p.setColor(role, C(t[k]))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, C(t["text3"]))
    return p


def set_theme(key, app=None, save=True):
    """Doi theme: cap nhat T, ap stylesheet + palette cho ca ung dung, bao cac widget ve lai."""
    global _key
    if key not in THEMES:
        key = DEFAULT_THEME
    _key = key
    t = dict(THEMES[key])
    _derive(t)
    T.clear()
    T.update(t)
    if app is None:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
    if app is not None:
        qss = QSS.replace("@FONT@", FONT_BODY).replace("@FS@", str(prefs.get("ui_font")))
        for k, v in t.items():
            if isinstance(v, str):
                qss = qss.replace("@%s@" % k, v)
        app.setStyle("Fusion")
        app.setPalette(_palette(t))
        app.setStyleSheet(qss)
    if save:
        gk_settings.put("theme", key)
    bus.changed.emit()


def apply_saved(app):
    set_theme(gk_settings.get("theme", DEFAULT_THEME), app, save=False)
