"""Luu cai dat giao dien (theme, layout/workspace) vao ~/.config/gk_keyfl/ui.json"""
import os, json

PATH = os.path.join(os.path.expanduser("~"), ".config", "gk_keyfl", "ui.json")
_data = None


def _load():
    global _data
    if _data is None:
        try:
            with open(PATH, encoding="utf-8") as f:
                _data = json.load(f)
        except Exception:
            _data = {}
    return _data


def get(key, default=None):
    return _load().get(key, default)


def put(key, value):
    d = _load()
    d[key] = value
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass
