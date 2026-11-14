"""Plugin mau 'Extras': minh hoa API mo rong - kieu noi suy moi, loai lop moi, theme moi, phim tat, su kien."""
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPen
import math

PLUGIN = {"name": "Extras", "version": "1.0", "author": "GK",
          "desc": "Thêm kiểu nội suy, lớp Hình tròn / Thanh tiến trình, theme Dracula"}


# ---- kieu noi suy: ham nhan u (0..1), tra tien do
def steps5(u):
    return min(1.0, math.floor(u * 5) / 4.0)                  # 5 bac thang

def smoother(u):
    return u * u * u * (u * (u * 6 - 15) + 10)                # smootherstep, muot hon ease thuong

def overshoot(u):
    c = 2.2
    return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2       # vuot qua dich roi ve


# ---- loai lop: ve vao rect b (da co vi tri/xoay/ti le)
def paint_circle(p, L, b, t):
    s = min(b.width(), b.height())
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(L.color))
    p.drawEllipse(QPointF(0, 0), s / 2, s / 2)

def icon_circle(p, r):
    p.drawEllipse(r.center(), 6, 6)

def paint_bar(p, L, b, t):
    """Thanh tien do: do day = L.extra['value'] (0..100), mac dinh 60."""
    v = max(0.0, min(100.0, float(L.extra.get("value", 60)))) / 100.0
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 50))
    p.drawRoundedRect(b, b.height() / 2, b.height() / 2)
    p.setBrush(QColor(L.color))
    p.drawRoundedRect(QRectF(b.left(), b.top(), max(b.height(), b.width() * v), b.height()), b.height() / 2, b.height() / 2)

def icon_bar(p, r):
    c = r.center()
    p.drawLine(QPointF(c.x() - 7, c.y()), QPointF(c.x() + 7, c.y()))


def register(api):
    api.add_ease("steps5", "Bậc thang (5 bước)", steps5)
    api.add_ease("smoother", "Siêu mượt (Smootherstep)", smoother)
    api.add_ease("overshoot", "Vượt rồi về (Overshoot)", overshoot)

    api.add_layer_kind("Hình tròn", paint_circle, row=1, color="#e0457b", body=(0.2, 0.36), icon=icon_circle)
    api.add_layer_kind("Thanh tiến trình", paint_bar, row=1, color="#2fb37a", body=(0.5, 0.06), icon=icon_bar)

    api.add_theme("dracula", "Dracula", bg0="#191a21", bg1="#21222c", bg2="#282a36", bg3="#343746", line="#3a3d4d",
                  text="#f8f8f2", text2="#b0b4c8", text3="#7a7f98",
                  accent="#bd93f9", accent_hi="#d0adff", accent_dim="#44356b",
                  bar1="#282a36", bar2="#44356b", frame="#ff79c6")

    def count():
        n = sum(1 for L in api.layers() if L.kind != "bg")
        api.log("Dự án đang có %d lớp." % n)
    api.add_shortcut("Ctrl+Alt+L", count)
    api.add_tool_action("Đếm số lớp (Ctrl+Alt+L)", count)

    # su kien: ghi log khi them lop
    api.on("layer_added", lambda L: api.log("Đã thêm lớp '%s' (loại %s)" % (L.name, L.kind)))
