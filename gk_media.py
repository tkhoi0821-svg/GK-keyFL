"""Video / am thanh trong editor: nguon media (proxy khung hinh tao nen bang ffmpeg) + bo phat am thanh."""
import os
from collections import OrderedDict
from PySide6.QtCore import QObject, QProcess, QTimer, QUrl, Signal
from PySide6.QtGui import QPixmap
import gk_ffmpeg as F

try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    HAVE_AUDIO = True
except Exception:                       # chua cai QtMultimedia: van xem video, khong co tieng
    HAVE_AUDIO = False


class MediaSource(QObject):
    """1 tep video / am thanh. Khung hinh duoc ffmpeg tach san thanh anh nho (proxy) nen tua va phat muot;
    ban xuat se dung tep goc. Khung xuat hien dan trong luc tach (xem duoc ngay)."""
    updated = Signal()

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.info = F.probe(path)
        i = self.info or {}
        self.duration, self.fps = float(i.get("duration", 0.0)), float(i.get("fps", 0.0))
        self.w, self.h = int(i.get("w", 0)), int(i.get("h", 0))
        self.has_video, self.has_audio = bool(i.get("has_video")), bool(i.get("has_audio"))
        self.dir = None
        self.cache = OrderedDict()
        self.procs = []
        self.timer = QTimer(self)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self._tick)
        if self.info:
            self.dir = F.proxy_dir(path)
            os.makedirs(self.dir, exist_ok=True)

    # ---------------------------------------------------------------- tach proxy
    def _marker(self, name):
        return os.path.join(self.dir, name)

    def start(self):
        if not self.info or self.procs:
            return
        jobs = []
        if self.has_video and not os.path.exists(self._marker("done_v")):
            jobs.append((F.proxy_cmd(self.path, self.dir), "done_v"))
        if self.has_audio and not os.path.exists(self._marker("done_a")):
            jobs.append((F.audio_cmd(self.path, self._marker("audio.wav")), "done_a"))
        for cmd, mark in jobs:
            pr = QProcess(self)
            pr.finished.connect(lambda code, _st, m=mark: self._done(code, m))
            pr.start(cmd[0], cmd[1:])
            self.procs.append(pr)
        if jobs:
            self.timer.start()
        else:
            self.updated.emit()

    def _done(self, code, mark):
        if code == 0:
            open(self._marker(mark), "w").close()
        self.procs = [p for p in self.procs if p.state() != QProcess.NotRunning]
        if not self.procs:
            self.timer.stop()
        self.updated.emit()

    def _tick(self):
        self.updated.emit()

    def busy(self):
        return bool(self.procs)

    # ---------------------------------------------------------------- khung hinh / am thanh
    def frame(self, t):
        """Khung proxy tai thoi diem t (giay, tinh tu dau tep) hoac None neu chua tach xong khung do."""
        if not self.has_video or not self.dir:
            return None
        i = F.frame_index(max(0.0, min(t, self.duration)))
        for j in range(i, max(-1, i - 13), -1):          # khung gan nhat da co (luc dang tach hoac het tep)
            pm = self.cache.get(j)
            if pm is None:
                p = F.frame_path(self.dir, j)
                if not os.path.exists(p):
                    continue
                pm = QPixmap(p)
                if pm.isNull():
                    continue
                self.cache[j] = pm
                while len(self.cache) > 160:
                    self.cache.popitem(last=False)
            else:
                self.cache.move_to_end(j)
            return pm
        return None

    def wav_path(self):
        p = self._marker("audio.wav")
        return p if (self.dir and os.path.exists(self._marker("done_a")) and os.path.exists(p)) else None

    def grab_full(self, t, out_png):
        """Khung do phan giai goc tai t -> file PNG (dung cho cat anh / tach nen tu video)."""
        return F.grab_frame(self.path, t, out_png)


class AudioEngine(QObject):
    """Phat am thanh cua cac lop video / am thanh dong bo voi dau phat."""

    def __init__(self):
        super().__init__()
        self.players = {}                # id(layer) -> (QMediaPlayer, duong dan wav)

    def _player(self, L, wav):
        ent = self.players.get(id(L))
        if ent is None or ent[1] != wav:
            pl = QMediaPlayer()
            out = QAudioOutput()                 # Qt6: am thanh phat qua QAudioOutput rieng
            pl.setAudioOutput(out)
            pl.setSource(QUrl.fromLocalFile(wav))
            ent = self.players[id(L)] = (pl, wav, out)
        return ent[0]

    def sync(self, layers, t, playing, force=False):
        """force=True khi nguoi dung tua luc dang phat; con lai chi bat/tat va sua lech lon."""
        if not HAVE_AUDIO:
            return
        for L in layers:
            src = getattr(L, "vid", None)
            wav = src.wav_path() if src else None
            if not wav:
                continue
            clip = L.clip_at(t) if L.visible else None
            pl = self._player(L, wav)
            if not (playing and clip is not None):
                if pl.playbackState() == QMediaPlayer.PlayingState:
                    pl.pause()
                continue
            want = int(max(0.0, t - clip.start + getattr(clip, "src_off", 0.0)) * 1000)
            if pl.playbackState() != QMediaPlayer.PlayingState:
                pl.setPosition(want)
                pl.play()
            elif force or abs(pl.position() - want) > 500:
                pl.setPosition(want)

    def stop_all(self):
        if not HAVE_AUDIO:
            return
        for pl, _wav, _out in self.players.values():
            pl.pause()
