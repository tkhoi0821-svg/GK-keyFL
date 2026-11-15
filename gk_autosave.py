"""Auto-save + Version: tu luu moi 5 giay + giu lich su cac ban truoc de khoi phuc.
Module doc lap, khong dung toi Undo/Redo. EditorPage chi can goi 4 ham o cuoi file nay.

Co che:
- Moi project co 1 thu muc rieng trong ~/.config/gk_keyfl/autosave/<slug>-<hash8>/
- File 'current.gkproj.json' la ban auto-save moi nhat (ghi de lien tuc).
- Thu muc 'versions/' giu toi da VERSION_MAX ban cu, dat ten theo thoi gian (epoch giay),
  chi tao ban version moi khi noi dung THAY DOI that (so sanh hash) va da qua VERSION_EVERY giay
  ke tu ban version gan nhat -> tranh sinh hang tram ban giong het nhau.
- Ghi file theo kieu "ghi vao tmp roi os.replace()" de khong bao gio hong file (mat dien, sap may
  giua chung thi file .gkproj cu/cu hon van con nguyen, khong bao gio con 1 file dang ghi do).
"""
import os, re, json, time, hashlib, glob

AUTOSAVE_DIR = os.path.join(os.path.expanduser("~"), ".config", "gk_keyfl", "autosave")
SAVE_INTERVAL = 5.0          # giay - tan suat auto-save (muc 6 trong danh sach)
VERSION_EVERY = 600.0        # giay - toi thieu 10 phut giua 2 ban version (muc 6: "quay lai ban 10 phut truoc")
VERSION_MAX = 48             # gioi han so ban version giu lai moi project (~8 tieng neu moi 10 phut/ban)


def _slug(name):
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", (name or "untitled").strip().lower()).strip("-")
    return s[:40] or "untitled"


def project_dir(project_key):
    """project_key: duong dan file .gkproj that (neu da luu) hoac ten tam (du an chua luu lan nao).
    Dung hash cua duong dan/ten de moi project co 1 thu muc rieng, on dinh qua cac lan mo lai."""
    h = hashlib.sha1(str(project_key).encode("utf-8")).hexdigest()[:8]
    d = os.path.join(AUTOSAVE_DIR, "%s-%s" % (_slug(os.path.basename(str(project_key))), h))
    os.makedirs(os.path.join(d, "versions"), exist_ok=True)
    return d


def _atomic_write(path, data_bytes):
    tmp = path + ".tmp-%d" % os.getpid()
    with open(tmp, "wb") as f:
        f.write(data_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)      # os.replace la atomic tren cung 1 filesystem: khong bao gio co file nua voi nua


def _hash_bytes(b):
    return hashlib.sha1(b).hexdigest()


class AutoSaver:
    """Theo doi 1 du an dang mo. get_state_fn() phai tra ve dict giong Layer.to_dict() gop lai
    (vi du {"ratio": .., "layers": [...]})  -  cung dinh dang voi file .gkproj hien co, nen ban
    auto-save/version co the mo lai bang y het ham load_project cu, khong can doi gi khac."""

    def __init__(self, project_key, get_state_fn):
        self.dir = project_dir(project_key)
        self.get_state = get_state_fn
        self.last_hash = None
        self.last_save_t = -1e18     # rat xa trong qua khu: lan tick() dau tien luon duoc ghi, bat ke now la gi
        self.dirty_since_version = False
        meta = self._read_meta()
        # neu chua tung co version nao, dat moc "lan truoc" rat xa trong qua khu de ban DAU TIEN
        # luon duoc tao ngay (khong phai cho du VERSION_EVERY giay moi co ban version dau tien)
        self.last_version_t = meta.get("last_version_t", -1e18)

    # ---------------------------------------------------------------- duong dan
    def _meta_path(self):
        return os.path.join(self.dir, "meta.json")

    def _read_meta(self):
        try:
            with open(self._meta_path(), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_meta(self, **kw):
        meta = self._read_meta()
        meta.update(kw)
        try:
            _atomic_write(self._meta_path(), json.dumps(meta, ensure_ascii=False).encode("utf-8"))
        except OSError:
            pass

    def current_path(self):
        return os.path.join(self.dir, "current.gkproj.json")

    def versions(self):
        """Danh sach ban version, moi cai la (duong_dan, epoch_giay), moi nhat truoc.
        Ten file la '<epoch>.gkproj.json' hoac '<epoch>-<n>.gkproj.json' khi 2 ban trung giay."""
        vs = []
        for p in glob.glob(os.path.join(self.dir, "versions", "*.gkproj.json")):
            stem = os.path.basename(p).split(".")[0]      # "<epoch>" hoac "<epoch>-<n>"
            try:
                ts = int(stem.split("-")[0])
            except ValueError:
                continue
            vs.append((p, ts))
        # cung epoch thi ban tao sau (mtime lon hon) duoc coi la moi hon, de thu tu hien thi dung
        return sorted(vs, key=lambda x: (-x[1], -os.path.getmtime(x[0])))

    # ---------------------------------------------------------------- tick dinh ky
    def tick(self, now=None):
        """Goi dinh ky (vi du moi 1 giay tu 1 QTimer co san). Tu quyet dinh co can luu khong.
        Tra ve True neu vua ghi auto-save (de UI co the chop nhay 1 chu 'Da luu' neu muon)."""
        now = now if now is not None else time.monotonic()
        if now - self.last_save_t < SAVE_INTERVAL:
            return False
        self.last_save_t = now
        try:
            state = self.get_state()
            data = json.dumps(state, ensure_ascii=False).encode("utf-8")
        except Exception:
            return False          # du an dang o trang thai khong serialize duoc (hiem, vd lop loi) -> bo qua lan nay
        h = _hash_bytes(data)
        if h == self.last_hash:
            return False          # khong co gi thay doi -> khong ghi de, do mon dia va tranh version rong
        self.last_hash = h
        self.dirty_since_version = True
        try:
            _atomic_write(self.current_path(), data)
        except OSError:
            return False
        self._maybe_snapshot(now, data)
        self._write_meta(saved_at=time.time())
        return True

    def _maybe_snapshot(self, now, data):
        if not self.dirty_since_version or (now - self.last_version_t) < VERSION_EVERY:
            return
        ts = int(time.time())
        path = os.path.join(self.dir, "versions", "%d.gkproj.json" % ts)
        n = 0
        while os.path.exists(path):           # ten trung giay (2 ban rat gan nhau) -> them hau to de khong de nhau
            n += 1
            path = os.path.join(self.dir, "versions", "%d-%d.gkproj.json" % (ts, n))
        try:
            _atomic_write(path, data)
        except OSError:
            return
        self.last_version_t = now
        self.dirty_since_version = False
        self._write_meta(last_version_t = now)
        self._prune()

    def _prune(self):
        vs = self.versions()
        for path, _ts in vs[VERSION_MAX:]:
            try:
                os.remove(path)
            except OSError:
                pass

    def save_now(self):
        """Ep ghi auto-save ngay (vd nguoi dung an Ctrl+S thu cong, hoac app sap thoat)."""
        self.last_save_t = -1e18
        return self.tick()

    def restore(self, path=None):
        """Doc 1 ban (mac dinh ban auto-save moi nhat) ra dict, de EditorPage tu ap dung
        bang dung logic load_project() hien co (Layer.from_dict theo tung lop trong state['layers'])."""
        path = path or self.current_path()
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def has_autosave(self):
        return os.path.isfile(self.current_path())

    def discard(self):
        """Xoa ban auto-save hien tai (goi sau khi nguoi dung da Luu that su bang Ctrl+S / File > Save,
        vi luc do file .gkproj that da la ban moi nhat, auto-save cu khong con can thiet nua)."""
        try:
            os.remove(self.current_path())
        except OSError:
            pass
        self.last_hash = None


def list_recoverable():
    """Quet toan bo thu muc autosave, tra ve danh sach project co ban auto-save moi hon ban .gkproj that
    (dung khi khoi dong app de hoi 'ban co muon khoi phuc khong', theo tinh than muc 6/48 trong danh sach)."""
    out = []
    if not os.path.isdir(AUTOSAVE_DIR):
        return out
    for sub in sorted(os.listdir(AUTOSAVE_DIR)):
        d = os.path.join(AUTOSAVE_DIR, sub)
        cur = os.path.join(d, "current.gkproj.json")
        if os.path.isfile(cur):
            try:
                mt = os.path.getmtime(cur)
            except OSError:
                continue
            out.append((d, cur, mt))
    return sorted(out, key=lambda x: -x[2])
