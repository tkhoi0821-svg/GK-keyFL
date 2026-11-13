"""Gia tri tuy chon (Preferences): doc/ghi + phat tin hieu khi doi. Luu cung file ui.json."""
from PySide6.QtCore import QObject, Signal
import gk_settings

DEFAULTS = dict(
    ui_font=12,             # co chu giao dien (px)
    gizmo_scale=1.0,        # ti le kich thuoc gizmo
    snap_move=5.0,          # buoc nhay khi giu Ctrl: di chuyen / xoay (do) / ti le (%)
    snap_rot=15.0,
    snap_scl=10.0,
    guides=False,           # hien luoi canvas mac dinh
    fps=30,                 # toc do lam moi khi phat
    loop=True,              # lap lai khi phat het
    autokey=False,          # tu dong key frame
    default_ease="linear",  # kieu noi suy cua key moi
    restore_layout=True,    # mo lai layout lan truoc khi khoi dong
)


class _Bus(QObject):
    changed = Signal(str)       # ten khoa, hoac "*" khi dat lai tat ca


bus = _Bus()


def get(key):
    d = DEFAULTS[key]
    v = gk_settings.get("prefs", {}).get(key, d)
    try:
        return bool(v) if isinstance(d, bool) else type(d)(v)
    except (TypeError, ValueError):
        return d


def put(key, value):
    d = dict(gk_settings.get("prefs", {}))
    d[key] = value
    gk_settings.put("prefs", d)
    bus.changed.emit(key)


def reset():
    gk_settings.put("prefs", {})
    bus.changed.emit("*")
