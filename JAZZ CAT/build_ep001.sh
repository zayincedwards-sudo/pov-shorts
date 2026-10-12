#!/usr/bin/env bash
# Rebuild episode 001 at full quality on your own PC (free: no API calls).
# Run from Git Bash inside the JAZZ CAT folder:   bash build_ep001.sh
# Needs: Python 3 with numpy + scipy, and ffmpeg on PATH.
set -e
cd "$(dirname "$0")"
PY=$(command -v python || command -v python3)
"$PY" -c "import numpy, scipy" 2>/dev/null || "$PY" -m pip install --quiet numpy scipy
command -v ffmpeg >/dev/null || { echo "ffmpeg not found on PATH. Install it (winget install Gyan.FFmpeg), reopen Git Bash, run again."; exit 1; }
mkdir -p build
[ -f build/rain_354.wav ] || "$PY" tools/rain.py build/rain_354.wav
MIN=${MINUTES:-265}
"$PY" tools/assemble.py episodes/001_rainy_window --minutes "$MIN" --deliver-crf 22 --abr 192k
OUT="."
mkdir -p "$OUT"
mv -f episodes/001_rainy_window/render/final.mp4 "$OUT/Rainy 1950s Jazz & Cozy Window.mp4"
rm -rf episodes/001_rainy_window/render/tmp
echo
echo "DONE: $OUT/Rainy 1950s Jazz & Cozy Window.mp4"
