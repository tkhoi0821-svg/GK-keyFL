"""Logic tep cho panel Assets (thu muc that tren dia, giong Unity): phan loai, copy/move an toan, mime keo tha."""
import os, shutil

MIME = "application/x-gk-asset"            # danh sach duong dan, ngan cach bang xuong dong
MIME_INT = "application/x-gk-asset-internal"  # keo noi bo trong panel Assets (de di chuyen thay vi sao chep)

EXT = {
    "image": {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"},
    "video": {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"},
    "audio": {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"},
    "model": {".obj", ".gltf", ".glb", ".fbx", ".stl", ".dae"},
    "plugin": {".py", ".gkplugin"},
}
# ten thu muc chuan -> khoa icon / noi mac dinh cua loai tep
STD_DIRS = {"video": "video", "image": "image", "audio": "audio", "model": "Model", "plugin": "Plugin"}
FOLDER_KEY = {"video": "video", "image": "image", "audio": "audio", "model": "Model", "plugin": "Plugin"}


def default_root():
    return os.path.join(os.path.expanduser("~"), "GKKeyFL", "Assets")


def ensure_root(root):
    os.makedirs(root, exist_ok=True)
    for d in STD_DIRS.values():
        os.makedirs(os.path.join(root, d), exist_ok=True)


def kind_of(path):
    if os.path.isdir(path):
        return "dir"
    ext = os.path.splitext(path)[1].lower()
    for k, s in EXT.items():
        if ext in s:
            return k
    return "file"


def inside(root, p):
    rp, rr = os.path.realpath(p), os.path.realpath(root)
    return rp == rr or rp.startswith(rr + os.sep)


def unique_path(folder, name):
    base, ext = os.path.splitext(name)
    p, n = os.path.join(folder, name), 1
    while os.path.exists(p):
        p = os.path.join(folder, "%s (%d)%s" % (base, n, ext))
        n += 1
    return p


def valid_name(name):
    name = (name or "").strip()
    if not name or name in (".", "..") or "/" in name or "\\" in name or "\0" in name:
        return None
    return name


def copy_into(root, src, dest_dir):
    """Sao chep tep/thu muc vao dest_dir (phai nam trong root). Tra ve duong dan moi hoac None."""
    if not os.path.exists(src) or not inside(root, dest_dir):
        return None
    dst = unique_path(dest_dir, os.path.basename(src.rstrip(os.sep)))
    if os.path.isdir(src):
        if inside(src, dest_dir):
            return None                      # khong chep thu muc vao chinh no
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return dst


def move_into(root, src, dest_dir):
    """Di chuyen noi bo trong root. Tra ve duong dan moi hoac None."""
    if not (os.path.exists(src) and inside(root, src) and inside(root, dest_dir)):
        return None
    if os.path.realpath(src) == os.path.realpath(root):
        return None
    if os.path.dirname(os.path.realpath(src)) == os.path.realpath(dest_dir):
        return None                          # da o san trong thu muc do
    if os.path.isdir(src) and inside(src, dest_dir):
        return None                          # khong chuyen thu muc vao chinh no
    dst = unique_path(dest_dir, os.path.basename(src.rstrip(os.sep)))
    shutil.move(src, dst)
    return dst


def ingest(root, src):
    """Dam bao tep nam trong Assets: neu o ngoai thi sao chep vao thu muc chuan theo loai."""
    if inside(root, src):
        return src
    sub = STD_DIRS.get(kind_of(src), "")
    folder = os.path.join(root, sub) if sub else root
    os.makedirs(folder, exist_ok=True)
    return copy_into(root, src, folder) or src


def mime_paths(md):
    """Lay danh sach duong dan tu QMimeData (keo noi bo hoac keo tep tu trinh quan ly tep)."""
    if md.hasFormat(MIME):
        ps = bytes(md.data(MIME)).decode("utf-8").split("\n")
    elif md.hasUrls():
        ps = [u.toLocalFile() for u in md.urls() if u.isLocalFile()]
    else:
        ps = []
    return [p for p in ps if p and os.path.exists(p)]
