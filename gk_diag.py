"""Kiem tra he thong ("check engine"): moi muc tra ve (trang thai, ten, chi tiet). Trang thai: ok | warn | bad."""
import os, sys, shutil, platform
import gk_settings
import gk_assets as A


def _writable(d):
    try:
        os.makedirs(d, exist_ok=True)
        t = os.path.join(d, ".gk_test")
        with open(t, "w") as f:
            f.write("x")
        os.remove(t)
        return True
    except OSError:
        return False


def run_checks():
    import PySide6
    from PySide6.QtCore import qVersion
    import gk_theme as theme
    import gk_model
    R = []
    v = sys.version_info
    R.append(("ok" if v >= (3, 8) else "bad", "Python", "%d.%d.%d" % v[:3] + ("" if v >= (3, 8) else " — cần 3.8 trở lên")))
    R.append(("ok", "Qt / PySide6", "Qt %s · PySide6 %s" % (qVersion(), PySide6.__version__)))
    R.append(("ok", "Hệ điều hành", "%s %s (%s)" % (platform.system(), platform.release(), platform.machine())))
    fonts_ok = theme.FONT_BODY != "Sans Serif" and theme.FONT_DISPLAY != "Sans Serif"
    R.append(("ok" if fonts_ok else "warn", "Phông chữ",
              "%s / %s" % (theme.FONT_DISPLAY, theme.FONT_BODY) if fonts_ok
              else "Chưa có Lexend/Inter, đang dùng phông dự phòng. Đặt .ttf vào thư mục fonts/."))
    R.append(("ok" if os.path.isfile(gk_model.LOGO) else "warn", "Logo", gk_model.LOGO if os.path.isfile(gk_model.LOGO)
              else "Thiếu gk_keyfl_logo.png cạnh mã nguồn"))
    try:
        import psutil  # noqa
        R.append(("ok", "psutil", "Hiện CPU/RAM ở thanh trạng thái"))
    except ImportError:
        R.append(("warn", "psutil", "Chưa cài (pip install psutil) — thanh trạng thái không hiện CPU/RAM"))
    cfg = os.path.dirname(gk_settings.PATH)
    R.append(("ok" if _writable(cfg) else "bad", "Thư mục cấu hình", cfg if _writable(cfg) else "Không ghi được: " + cfg))
    root = gk_settings.get("assets_root") or (A.default_root() if hasattr(A, "default_root") else os.path.join(os.path.expanduser("~"), "GKKeyFL"))
    if _writable(root):
        free = shutil.disk_usage(root).free / 2 ** 30
        R.append(("ok" if free >= 1 else "warn", "Thư mục Assets", "%s · còn trống %.1f GB" % (root, free)))
        pd = os.path.join(root, "Plugin")
        n = len([f for f in os.listdir(pd) if f.lower().endswith(tuple(getattr(A, "EXT", {}).get("plugin", (".py", ".gkplugin"))))]) if os.path.isdir(pd) else 0
        R.append(("ok", "Plugin", "%d tệp trong Assets/Plugin" % n))
    else:
        R.append(("bad", "Thư mục Assets", "Không ghi được: " + root))
    ff = shutil.which("ffmpeg")
    R.append(("ok" if ff else "warn", "ffmpeg", ff or "Chưa thấy trong PATH — cần khi làm phát video/âm thanh và xuất file"))
    return R


def report_text(res):
    mark = {"ok": "[OK]  ", "warn": "[CẢNH BÁO]  ", "bad": "[LỖI]  "}
    return "\n".join("%s%s: %s" % (mark[s], n, d) for s, n, d in res)
