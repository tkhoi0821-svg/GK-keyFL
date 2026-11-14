"""Kiem tra ban cap nhat. May chu tra ve JSON: {"version": "1.1.0", "url": "https://...", "notes": "..."}.
Dia chi mac dinh: <goc cua may chu dang nhap>/api/keyfl/version  (doi bang bien moi truong GK_UPDATE_URL)."""
import os, json, threading, urllib.request
from urllib.parse import urlparse
from PySide6.QtCore import QObject, Signal

VERSION = "1.0.0"


def update_url():
    env = os.environ.get("GK_UPDATE_URL")
    if env:
        return env
    from gk_auth import AUTH_BASE
    u = urlparse(AUTH_BASE)
    return "%s://%s/api/keyfl/version" % (u.scheme, u.netloc)


def _tuple(v):
    out = []
    for x in str(v).strip().lstrip("vV").split("."):
        n = "".join(c for c in x if c.isdigit())
        out.append(int(n) if n else 0)
    return tuple(out)


def fetch():
    url = update_url()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GKKeyFL/" + VERSION})
        with urllib.request.urlopen(req, timeout=6) as r:
            d = json.loads(r.read().decode("utf-8"))
        latest = str(d["version"])
        return dict(ok=True, current=VERSION, latest=latest, newer=_tuple(latest) > _tuple(VERSION),
                    url=d.get("url", ""), notes=d.get("notes", ""), source=url)
    except Exception as ex:
        return dict(ok=False, current=VERSION, error=str(ex) or ex.__class__.__name__, source=url)


class Checker(QObject):
    done = Signal(dict)

    def start(self):
        threading.Thread(target=lambda: self.done.emit(fetch()), daemon=True).start()
