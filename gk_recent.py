"""Danh sach du an gan day (luu trong ui.json, khoa "recent") + anh xem truoc (thumbnail)."""
import os, json, hashlib
import gk_settings

MAX = 24
THUMB_DIR = os.path.join(os.path.expanduser("~"), ".config", "gk_keyfl", "thumbs")


def _all():
    return [d for d in gk_settings.get("recent", []) if isinstance(d, dict) and d.get("path")]


def items():
    """Du an gan day nhat truoc, bo qua tep da bi xoa."""
    return [d for d in _all() if os.path.isfile(d["path"])]


def _info(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    dur = 0.0
    for L in d.get("layers", []):
        for c in L.get("clips", []):
            dur = max(dur, float(c[1]) + float(c[2]))
    return float(d.get("ratio", 16 / 9)), dur


def add(path):
    path = os.path.abspath(path)
    try:
        ratio, dur = _info(path)
    except Exception:
        ratio, dur = 16 / 9, 0.0
    lst = [d for d in _all() if d["path"] != path]
    lst.insert(0, dict(name=os.path.splitext(os.path.basename(path))[0], path=path, ratio=ratio, dur=dur))
    gk_settings.put("recent", lst[:MAX])


def remove(path, delete_thumb=False):
    gk_settings.put("recent", [d for d in _all() if d["path"] != path])
    if delete_thumb:
        try:
            os.remove(thumb_path(path))
        except OSError:
            pass


def rename(old, new):
    """Doi duong dan trong danh sach (tep da duoc doi ten tren dia)."""
    new = os.path.abspath(new)
    lst = _all()
    for d in lst:
        if d["path"] == old:
            d["path"], d["name"] = new, os.path.splitext(os.path.basename(new))[0]
    gk_settings.put("recent", lst)
    try:
        os.replace(thumb_path(old), thumb_path(new))
    except OSError:
        pass


def fmt_dur(s):
    s = int(round(s))
    return "%d:%02d" % (s // 60, s % 60)


def thumb_path(path):
    return os.path.join(THUMB_DIR, hashlib.sha1(os.path.abspath(path).encode("utf-8")).hexdigest() + ".png")


def save_thumb(path, pixmap):
    """Luu anh xem truoc (toi da 480px) cho du an."""
    try:
        from PySide6.QtCore import Qt
        os.makedirs(THUMB_DIR, exist_ok=True)
        pixmap.scaled(480, 480, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation).save(thumb_path(path), "PNG")
    except Exception:
        pass
