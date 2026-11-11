#!/usr/bin/env bash
# GK KeyFL - chay thu tren Fedora
# Dung: chmod +x test_fedora.sh && ./test_fedora.sh
set -e
cd "$(dirname "$(readlink -f "$0")")"

for f in gk_keyfl_ui.py gk_theme.py gk_settings.py gk_model.py gk_auth.py gk_pages.py gk_timeline.py gk_panels.py gk_editor.py gk_keyfl_logo.png; do
  [ -f "$f" ] || { echo "Thieu file: $f (de chung thu muc voi script nay)"; exit 1; }
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "[*] Cai python3..."
  sudo dnf install -y python3
fi

if ! python3 -c "import PyQt5.QtWidgets" >/dev/null 2>&1; then
  echo "[*] Cai PyQt5 (dnf)..."
  sudo dnf install -y python3-qt5 qt5-qtwayland
fi

echo "[*] Mo GK KeyFL..."
exec python3 gk_keyfl_ui.py "$@"
