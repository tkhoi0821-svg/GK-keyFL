"""GK KeyFL - Safe Mode + tu luu phuc hoi du an.

* Moi lan chay: tao  session.lock  (xoa khi thoat binh thuong). Con lai o lan sau = lan truoc bi dong dot ngot.
* faulthandler ghi dau vet khi sap cung (segfault...) -> tim ra plugin nao nam trong dau vet.
* Truoc khi nap tung plugin ghi  loading.txt  -> sap luc nap thi biet chinh xac plugin nao.
* Lan sau mo len: hoi vao Safe Mode (khong nap plugin nao, tat plugin nghi ngo). Co the ep bang  --safe.
* Du an tu luu moi 60 giay; sau khi sap se hoi khoi phuc.
"""
import os
import re
import sys
import hashlib
import faulthandler

DIR = os.path.join(os.path.expanduser("~"), ".config", "gk_keyfl")
SESSION = os.path.join(DIR, "session.lock")
LOADING = os.path.join(DIR, "loading.txt")
FAULT = os.path.join(DIR, "crash_trace.log")
REC_DIR = os.path.join(DIR, "recovery")
RECOVERY = os.path.join(REC_DIR, "autosave.gkproj")
SAVED = os.path.join(REC_DIR, "last_crash.gkproj")

SAFE = False
STATE = {"unclean": False, "culprits": [], "recovery": None}
_fp = None
_last_sig = None


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def begin():
    """Goi 1 lan, truoc khi tao QApplication."""
    global _fp
    os.makedirs(REC_DIR, exist_ok=True)
    unclean = os.path.exists(SESSION)
    STATE["unclean"] = unclean
    cul = []
    if unclean:
        pid = _read(LOADING).strip()
        if pid:
            cul.append(pid)
        for m in re.finditer(r'[/\\]Plugin[/\\]([^/\\"]+?)\.(?:py|gkplugin)"', _read(FAULT)):
            if m.group(1) not in cul:
                cul.append(m.group(1))
        if os.path.exists(RECOVERY):                       # giu ban tu luu de timer khong ghi de len no
            try:
                os.replace(RECOVERY, SAVED)
            except Exception:
                pass
        if os.path.exists(SAVED):
            STATE["recovery"] = SAVED
    STATE["culprits"] = cul
    for p in (LOADING,):
        try:
            os.remove(p)
        except Exception:
            pass
    try:
        with open(SESSION, "w") as f:
            f.write(str(os.getpid()))
        _fp = open(FAULT, "w")
        faulthandler.enable(file=_fp, all_threads=True)
    except Exception:
        pass


def end():
    """Thoat binh thuong: xoa dau hieu 'bi sap'."""
    for p in (SESSION, LOADING, RECOVERY):
        try:
            os.remove(p)
        except Exception:
            pass
    try:
        faulthandler.disable()
        if _fp:
            _fp.close()
        os.remove(FAULT)
    except Exception:
        pass


def mark_loading(pid):
    try:
        with open(LOADING, "w", encoding="utf-8") as f:
            f.write(pid)
    except Exception:
        pass


def clear_loading():
    try:
        os.remove(LOADING)
    except Exception:
        pass


def _has_plugins():
    import gk_settings
    root = gk_settings.get("assets_root") or os.path.join(os.path.expanduser("~"), "GKKeyFL", "Assets")
    d = os.path.join(root, "Plugin")
    try:
        return any(f.lower().endswith((".py", ".gkplugin")) and not f.startswith("_") for f in os.listdir(d))
    except Exception:
        return False


def _disable(pids):
    import gk_settings
    c = gk_settings.get("plugins", {})
    c = {"trusted": dict(c.get("trusted", {})), "disabled": list(c.get("disabled", []))}
    for p in pids:
        if p not in c["disabled"]:
            c["disabled"].append(p)
    gk_settings.put("plugins", c)


def startup_prompt():
    """Hoi vao Safe Mode neu lan truoc sap (hoac co --safe). Goi sau khi co QApplication."""
    global SAFE
    cul = STATE["culprits"]
    if "--safe" in sys.argv:
        SAFE = True
        _disable(cul)
        return
    if not STATE["unclean"] or not (cul or _has_plugins()):
        return
    from PySide6.QtWidgets import QMessageBox
    if cul:
        why = "Lần chạy trước ứng dụng bị đóng đột ngột, nghi do plugin: %s." % ", ".join(cul)
    else:
        why = "Lần chạy trước ứng dụng bị đóng đột ngột (chưa rõ nguyên nhân) và bạn đang có plugin."
    box = QMessageBox(QMessageBox.Warning, "Mở Safe Mode?",
                      why + "\n\nSafe Mode không nạp plugin nào%s. Dự án tự lưu (nếu có) vẫn được khôi phục."
                      % (" và tắt plugin nghi ngờ" if cul else ""))
    b_safe = box.addButton("Mở Safe Mode", QMessageBox.AcceptRole)
    box.addButton("Chạy bình thường", QMessageBox.RejectRole)
    box.setDefaultButton(b_safe)
    box.exec()
    if box.clickedButton() is b_safe:
        SAFE = True
        _disable(cul)


def pending_recovery():
    p = STATE["recovery"]
    return p if p and os.path.exists(p) else None


def discard_recovery():
    try:
        os.remove(SAVED)
    except Exception:
        pass
    STATE["recovery"] = None


def write_recovery(text):
    """Ghi ban tu luu (nguyen tu, chi ghi khi noi dung doi)."""
    global _last_sig
    sig = hashlib.sha1(text.encode("utf-8")).hexdigest()
    if sig == _last_sig:
        return
    os.makedirs(REC_DIR, exist_ok=True)
    tmp = RECOVERY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, RECOVERY)
    _last_sig = sig
