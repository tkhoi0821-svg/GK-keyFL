"""GK KeyFL - Debug Mod: FPS that, RAM/CPU, bat loi tu dong, lop phu tren Stage.

F3        : vao / thoat che do Debug (co canh bao truoc khi vao): khung xem thanh DEN TRANG, nen XANH
Alt+F3    : bat / tat bang thong so (FPS, RAM, CPU, loi) o goc man hinh
Lenh      : debug [on|off|stats|log|test]
Loi chua xu ly -> tu dong vao Console + ghi ~/.config/gk_keyfl/debug.log
"""
import os
import sys
import time
import threading
import traceback
from collections import deque
from PySide6.QtCore import QObject, QTimer, Signal, QRectF, Qt
from PySide6.QtGui import QPainter, QColor, QFont, QImage
from PySide6.QtWidgets import QMessageBox
import numpy as np

DEBUG_BG = (10, 70, 200)      # mau nen xanh cua che do Debug (R, G, B) - doi o day neu muon xanh la
LOGFILE = os.path.join(os.path.expanduser("~"), ".config", "gk_keyfl", "debug.log")


class _Hub(QObject):
    """Cau noi an toan luong: thread nao bao loi cung chuyen ve luong GUI qua signal."""
    line = Signal(str)


HUB = _Hub()
ERRORS = deque(maxlen=50)


def _record(kind, etype, value, tb):
    txt = "".join(traceback.format_exception(etype, value, tb))
    ERRORS.append(txt)
    try:
        os.makedirs(os.path.dirname(LOGFILE), exist_ok=True)
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), kind, txt))
    except Exception:
        pass
    last = txt.strip().splitlines()[-1] if txt.strip() else "?"
    HUB.line.emit("[LỖI] %s (chi tiết: gõ `debug log`)" % last)


def install_hooks():
    """Goi 1 lan khi khoi dong: bat loi o main thread va thread phu."""
    old = sys.excepthook

    def hook(et, ev, tb):
        _record("main", et, ev, tb)
        old(et, ev, tb)

    sys.excepthook = hook

    def thook(args):
        _record("thread:%s" % getattr(args.thread, "name", "?"), args.exc_type, args.exc_value, args.exc_traceback)

    threading.excepthook = thook


class Debug(QObject):
    def __init__(self, editor):
        super().__init__(editor)
        self.ed = editor
        self.mode = False          # che do Debug (den trang / nen xanh)
        self.stats = False         # bang thong so goc man hinh
        self._busy = False
        self._ticks, self._paints = deque(maxlen=240), deque(maxlen=240)
        self.paint_ms = 0.0
        self.ram_mb, self.cpu = 0.0, 0.0
        self._proc = None
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._sample)
        HUB.line.connect(editor.log)
        self._patch_stage()

    # ---- do dac
    def on_tick(self):
        self._ticks.append(time.monotonic())

    def note_paint(self, ms):
        self._paints.append(time.monotonic())
        self.paint_ms = ms

    @staticmethod
    def _rate(dq):
        now = time.monotonic()
        return sum(1 for t in dq if now - t <= 1.0)

    def _sample(self):
        try:
            import psutil
            if self._proc is None:
                self._proc = psutil.Process()
                self._proc.cpu_percent(None)
            self.ram_mb = self._proc.memory_info().rss / 1048576.0
            self.cpu = self._proc.cpu_percent(None)
        except Exception:
            self.ram_mb, self.cpu = -1.0, -1.0
        self.ed.stage.update()

    # ---- bat / tat
    def toggle_stats(self, on=None):
        self.stats = (not self.stats) if on is None else bool(on)
        if self.stats:
            self._sample()
            self._timer.start()
        else:
            self._timer.stop()
        self.ed.stage.update()

    def toggle_mode(self, on=None):
        want = (not self.mode) if on is None else bool(on)
        if want == self.mode:
            return
        if want:
            ans = QMessageBox.warning(
                self.ed, "Chế độ Debug",
                "Chế độ Debug chỉ dùng để kiểm tra lỗi.\n\n"
                "• Khung xem sẽ chuyển sang ĐEN TRẮNG, nền xanh (chữ, ảnh, hình đều mất màu).\n"
                "• Tốn thêm CPU nên có thể giật khi phát.\n"
                "• Không ảnh hưởng tới dự án đã lưu.\n\n"
                "Thoát bằng F3. Vào chế độ Debug?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ans != QMessageBox.Yes:
                return
        self.mode = want
        self.ed.stage.update()
        self.ed.log("Chế độ Debug: %s" % ("BẬT (F3 để thoát, Alt+F3 hiện thông số)" if want else "TẮT"))

    def command(self, args):
        a = args[0] if args else ""
        if a in ("", "on", "off"):
            self.toggle_mode(None if a == "" else a == "on")
        elif a == "stats":
            self.toggle_stats()
        elif a == "log":
            if not ERRORS:
                self.ed.log("Chưa có lỗi nào được ghi.")
            for t in list(ERRORS)[-3:]:
                self.ed.log(t.rstrip())
            self.ed.log("File log: " + LOGFILE)
        elif a == "test":
            raise RuntimeError("Lỗi thử nghiệm từ `debug test`")
        else:
            self.ed.log("debug [on|off|stats|log|test]")

    # ---- che do den trang / nen xanh
    def bw_frame(self, w, orig, e):
        """Ve Stage vao QImage (goi paintEvent goc qua render), doi sang xam, o ban co -> xanh."""
        import gk_panels
        dpr = w.devicePixelRatioF()
        img = QImage(int(w.width() * dpr), int(w.height() * dpr), QImage.Format_ARGB32)
        img.setDevicePixelRatio(dpr)
        img.fill(0)
        self._busy = True
        try:
            w.render(img)
        finally:
            self._busy = False
        W, H, bpl = img.width(), img.height(), img.bytesPerLine()
        a = np.frombuffer(img.constBits(), np.uint8).reshape(H, bpl // 4, 4)[:, :W].astype(np.int16)
        gray = (a[..., 0] * 29 + a[..., 1] * 150 + a[..., 2] * 77) >> 8        # B, G, R
        bg = np.zeros((H, W), bool)
        for k in ("checker_a", "checker_b"):
            c = QColor(gk_panels.T[k])
            bg |= (np.abs(a[..., 2] - c.red()) <= 6) & (np.abs(a[..., 1] - c.green()) <= 6) & (np.abs(a[..., 0] - c.blue()) <= 6)
        out = np.empty((H, W, 4), np.uint8)
        out[..., 0] = out[..., 1] = out[..., 2] = gray.astype(np.uint8)
        out[..., 3] = 255
        out[bg] = (DEBUG_BG[2], DEBUG_BG[1], DEBUG_BG[0], 255)                  # BGRA
        res = QImage(out.data, W, H, W * 4, QImage.Format_ARGB32)
        res.setDevicePixelRatio(dpr)
        p = QPainter(w)
        p.drawImage(0, 0, res)
        p.end()

    # ---- lop phu
    def draw(self, w):
        ps = self.ed.playing
        lines = [
            "FPS phát : %d%s" % (self._rate(self._ticks), "" if ps else "  (đang dừng)"),
            "FPS vẽ   : %d   (%.1f ms/khung)" % (self._rate(self._paints), self.paint_ms),
            "RAM app  : %s" % ("%.0f MB" % self.ram_mb if self.ram_mb >= 0 else "cần psutil"),
            "CPU app  : %s" % ("%.0f%%" % self.cpu if self.cpu >= 0 else "cần psutil"),
            "Lỗi      : %d" % len(ERRORS),
        ]
        p = QPainter(w)
        f = QFont("monospace", 9)
        f.setStyleHint(QFont.Monospace)
        p.setFont(f)
        h = 16 * len(lines) + 12
        r = QRectF(10, 10, 230, h)
        p.fillRect(r, QColor(0, 0, 0, 170))
        for i, s in enumerate(lines):
            bad = (i == 4 and ERRORS)
            p.setPen(QColor("#ff6b6b") if bad else QColor("#7CFC9A"))
            p.drawText(QRectF(18, 16 + i * 16, 220, 16), Qt.AlignLeft | Qt.AlignVCenter, s)
        p.end()

    def _patch_stage(self):
        import gk_panels
        St = gk_panels.Stage
        if getattr(St, "_dbg_patched", False):
            St._dbg = self
            return
        orig = St.paintEvent

        def paint(w, e):
            t0 = time.perf_counter()
            d = getattr(St, "_dbg", None)
            if d is not None and d.mode and not d._busy:
                d.bw_frame(w, orig, e)
            else:
                orig(w, e)
            if d is not None and not d._busy:
                d.note_paint((time.perf_counter() - t0) * 1000.0)
                if d.stats:
                    d.draw(w)

        St.paintEvent = paint
        St._dbg_patched = True
        St._dbg = self


def attach(editor):
    return Debug(editor)
