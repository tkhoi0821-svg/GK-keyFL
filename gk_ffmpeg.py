"""Goi ffmpeg / ffprobe (khong phu thuoc Qt): tim cong cu, doc thong tin, lenh tao proxy hinh + am thanh, lay 1 khung."""
import os, json, shutil, subprocess, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "gk_keyfl", "proxy")
PROXY_FPS, PROXY_W = 12, 480


def find_tool(name):
    """Uu tien ban dong goi kem ung dung (vendor/ffmpeg/), sau do toi PATH cua he thong."""
    for d in (os.path.join(HERE, "vendor", "ffmpeg"), os.path.join(HERE, "vendor"), os.path.join(HERE, "ffmpeg")):
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return shutil.which(name)


def available():
    return bool(find_tool("ffmpeg") and find_tool("ffprobe"))


def _fps(s):
    try:
        a, b = s.split("/")
        return float(a) / float(b) if float(b) else 0.0
    except (ValueError, AttributeError):
        try:
            return float(s)
        except (TypeError, ValueError):
            return 0.0


def probe(path, timeout=20):
    """Thong tin tep media hoac None neu khong doc duoc. Khung tra ve da tinh ca xoay (video quay doc)."""
    ff = find_tool("ffprobe")
    if not ff or not os.path.isfile(path):
        return None
    try:
        r = subprocess.run([ff, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
                           capture_output=True, text=True, timeout=timeout)
        j = json.loads(r.stdout or "{}")
    except (subprocess.SubprocessError, ValueError, OSError):
        return None
    vs = [s for s in j.get("streams", []) if s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic", 0) == 0]
    au = [s for s in j.get("streams", []) if s.get("codec_type") == "audio"]
    if not vs and not au:
        return None
    dur = 0.0
    for src in ([j.get("format", {})] + vs + au):
        try:
            dur = max(dur, float(src.get("duration") or 0))
        except (TypeError, ValueError):
            pass
    info = dict(duration=dur, fps=0.0, w=0, h=0, has_video=bool(vs), has_audio=bool(au), rotate=0)
    if vs:
        v = vs[0]
        info["fps"] = _fps(v.get("avg_frame_rate") or v.get("r_frame_rate") or "0")
        info["w"], info["h"] = int(v.get("width") or 0), int(v.get("height") or 0)
        rot = 0
        try:
            rot = int((v.get("tags") or {}).get("rotate") or 0)
        except ValueError:
            pass
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(sd["rotation"])
        info["rotate"] = rot
        if abs(rot) % 180 == 90:
            info["w"], info["h"] = info["h"], info["w"]
    return info


def proxy_dir(path, pf=PROXY_FPS, pw=PROXY_W):
    st = os.stat(path)
    key = hashlib.sha1(("%s|%s|%s|%s|%s" % (os.path.realpath(path), st.st_mtime_ns, st.st_size, pf, pw)).encode()).hexdigest()[:20]
    return os.path.join(CACHE, key)


def proxy_cmd(path, outdir, pf=PROXY_FPS, pw=PROXY_W):
    return [find_tool("ffmpeg"), "-y", "-v", "error", "-i", path, "-vf", "fps=%d,scale=%d:-2" % (pf, pw), "-q:v", "5",
            os.path.join(outdir, "%06d.jpg")]


def audio_cmd(path, out_wav):
    return [find_tool("ffmpeg"), "-y", "-v", "error", "-i", path, "-vn", "-ac", "2", "-ar", "44100", "-acodec", "pcm_s16le", out_wav]


def frame_path(outdir, idx):
    return os.path.join(outdir, "%06d.jpg" % (idx + 1))


def frame_index(t, pf=PROXY_FPS):
    return max(0, int(t * pf + 1e-6))


def grab_frame(path, t, out_png, timeout=30):
    """Lay 1 khung do phan giai goc tai thoi diem t (giay) ra file PNG. Tra ve True neu thanh cong."""
    ff = find_tool("ffmpeg")
    if not ff:
        return False
    try:
        subprocess.run([ff, "-y", "-v", "error", "-ss", "%.3f" % max(0.0, t), "-i", path, "-frames:v", "1", out_png],
                       capture_output=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError):
        return False
    return os.path.isfile(out_png) and os.path.getsize(out_png) > 0
