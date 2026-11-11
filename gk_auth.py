"""Dang nhap qua trinh duyet + luu nguoi dung."""
import os, json, time, secrets, threading, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, urlencode
from PyQt5.QtCore import Qt, QTimer, QRect, QRectF, QPointF, QSize, QObject, pyqtSignal
from PyQt5.QtGui import (QColor, QPainter, QPen, QBrush, QFont, QPixmap, QIcon, QLinearGradient,
                         QPainterPath, QPolygonF, QFontDatabase, QFontMetrics, QRadialGradient, QTransform)
from PyQt5.QtWidgets import (QWidget, QApplication)


AUTH_BASE = os.environ.get("GK_AUTH_URL", "https://graykazu.graykazuvn.workers.dev/acc/gkkeyfl")
DEV = bool(os.environ.get("GK_DEV"))
CFG = os.path.join(os.path.expanduser("~"), ".config", "gk_keyfl", "user.json")
OK_HTML = ("<!doctype html><meta charset='utf-8'><title>GK KeyFL</title>"
           "<body style='margin:0;height:100vh;display:grid;place-items:center;background:#0b0b0f;color:#fff;"
           "font-family:system-ui,sans-serif'><div style='text-align:center'><h2>Đăng nhập thành công</h2>"
           "<p style='color:#9a9aa6'>Bạn có thể đóng tab này và quay lại GK KeyFL.</p></div>")


def load_user():
    try:
        with open(CFG, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("name", ""), d.get("email", "")
    except Exception:
        return None


def save_user(name, email):
    try:
        os.makedirs(os.path.dirname(CFG), exist_ok=True)
        with open(CFG, "w", encoding="utf-8") as f:
            json.dump({"name": name, "email": email}, f)
    except Exception:
        pass


def clear_user():
    try:
        os.remove(CFG)
    except Exception:
        pass



# ------------------------------------------------------------------ icons
def draw_brand_icon(p, r):
    p.save()
    p.setBrush(Qt.NoBrush)
    for i, col in enumerate(["#7a2bff", "#a56bff", "#111111"]):
        pen = QPen(QColor(col), r.width() * 0.13)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)
        x = r.left() + r.width() * (0.10 + i * 0.26)
        p.drawLine(QPointF(x, r.bottom()), QPointF(x + r.width() * 0.42, r.top()))
    p.restore()


def draw_google(p, r):
    p.save()
    s = r.width()
    w = s * 0.24
    ring = QRectF(r.left() + w / 2, r.top() + w / 2, s - w, s - w)
    p.setBrush(Qt.NoBrush)
    for col, start, span in [("#ea4335", 45, 95), ("#fbbc05", 140, 85), ("#34a853", 225, 90), ("#4285f4", 315, 45)]:
        pen = QPen(QColor(col), w)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)
        p.drawArc(ring, int(start * 16), int(span * 16))
    pen = QPen(QColor("#4285f4"), w * 0.9)
    pen.setCapStyle(Qt.FlatCap)
    p.setPen(pen)
    p.drawLine(QPointF(r.center().x(), r.center().y()), QPointF(r.right(), r.center().y()))
    p.restore()




# ------------------------------------------------------------------ dang nhap qua trinh duyet
class AuthBridge(QObject):
    """Mo trinh duyet toi trang dang nhap cua worker, cho no goi lai http://127.0.0.1:<port>/cb."""
    done = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.url = ""
        self._stop = threading.Event()

    def start(self, google=False):
        self.cancel()
        state = secrets.token_urlsafe(18)
        stop = self._stop = threading.Event()
        bridge = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if u.path != "/cb" or q.get("state", [""])[0] != state:
                    self.send_response(404)
                    self.end_headers()
                    return
                name = q.get("name", [""])[0][:60]
                email = q.get("email", [""])[0][:120]
                body = OK_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                stop.set()
                bridge.done.emit(name, email)

        srv = HTTPServer(("127.0.0.1", 0), H)
        srv.timeout = 1
        port = srv.server_address[1]

        def run():
            t0 = time.monotonic()
            while not stop.is_set() and time.monotonic() - t0 < 300:
                srv.handle_request()
            srv.server_close()
            if not stop.is_set():
                stop.set()
                bridge.failed.emit("Hết thời gian chờ đăng nhập.")

        threading.Thread(target=run, daemon=True).start()
        self.url = AUTH_BASE + "?" + urlencode({"app": "gkkeyfl", "port": port, "state": state,
                                                "via": "google" if google else "account"})
        self.reopen()

    def reopen(self):
        try:
            webbrowser.open(self.url)
        except Exception:
            self.failed.emit("Không mở được trình duyệt.")

    def cancel(self):
        self._stop.set()


