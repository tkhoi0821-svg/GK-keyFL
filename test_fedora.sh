#!/usr/bin/env bash
# GK KeyFL - chay thu tren Fedora (Qt 6 / PySide6)
# Dung: chmod +x test_fedora.sh && ./test_fedora.sh
set -e
cd "$(dirname "$(readlink -f "$0")")"

NEED="gk_keyfl_ui.py gk_theme.py gk_settings.py gk_model.py gk_auth.py gk_pages.py gk_timeline.py gk_panels.py
gk_assets.py gk_project.py gk_prefs.py gk_prefs_ui.py gk_vector.py gk_vector_ui.py gk_matting.py gk_matte_ui.py
gk_ffmpeg.py gk_media.py gk_editor.py gk_keyfl_logo.png"
for f in $NEED; do
  [ -f "$f" ] || { echo "Thieu file: $f (de chung thu muc voi script nay)"; exit 1; }
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "[*] Cai python3..."
  sudo dnf install -y python3
fi

if ! python3 -c "import PySide6.QtWidgets" >/dev/null 2>&1; then
  echo "[*] Cai PySide6 (Qt 6, qua pip - Fedora chua dong goi san ban day du)..."
  python3 -m pip install --user "PySide6>=6.6" || sudo dnf install -y python3-pyside6 || \
    echo "    (chua cai duoc PySide6; can mang internet lan dau chay thu)"
fi

# QtMultimedia: co tieng khi phat video / am thanh. Thieu thi van xem duoc hinh, chi khong co tieng.
python3 -c "import PySide6.QtMultimedia" >/dev/null 2>&1 || \
  echo "[*] Luu y: thieu PySide6.QtMultimedia, se chay khong co tieng (pip install PySide6 da bao gom san; neu dung goi dnf rieng, can them python3-pyside6-multimedia)."

if ! python3 -c "import numpy" >/dev/null 2>&1; then
  echo "[*] Cai numpy (dung cho Tach nen)..."
  sudo dnf install -y python3-numpy || python3 -m pip install --user numpy
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "[*] Cai ffmpeg (dung de doc video/am thanh)..."
  sudo dnf install -y ffmpeg || sudo dnf install -y ffmpeg-free || \
    echo "    (chua cai duoc ffmpeg; video/am thanh se khong hoat dong cho den khi cai thu cong)"
fi

if ! python3 -c "import onnxruntime" >/dev/null 2>&1; then
  echo "[*] (Tuy chon) Cai onnxruntime de dung Tach nen bang AI..."
  python3 -m pip install --user onnxruntime 2>/dev/null || \
    echo "    (bo qua; van dung duoc Tach nen theo mau - Chroma key)"
fi

echo "[*] Mo GK KeyFL..."
exec python3 gk_keyfl_ui.py "$@"
