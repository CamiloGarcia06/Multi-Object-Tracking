#!/usr/bin/env bash
# Tesis 27: sube a track-studio los 15 videos de TRACKING de los clips golden _a
# (tm02_a, tm03_1_a, tm07_a, ddr_s6_v18_a, sdr_s1_v08_a x 3 trackers), evaluados contra su golden.
# Lee el token del .env del servicio sin enseñarlo. No despliega, no reinicia ni borra jobs.
#   ssh torre 'bash ~/Multi-Object-Tracking-studio/scripts/studio/subir_videos_tracking.sh'
set -euo pipefail
TS=~/Projects/track-studio
TRACK_STUDIO_TOKEN=$(sed -n 's/^TRACK_STUDIO_TOKEN=//p' "$TS/.env" | tr -d '"'"'"' \r')
[ -n "$TRACK_STUDIO_TOKEN" ] || { echo "no encontré TRACK_STUDIO_TOKEN en $TS/.env"; exit 1; }
export TRACK_STUDIO_TOKEN
cd ~/Multi-Object-Tracking-studio
uv run -q scripts/tracking/importar_studio.py --videos data/videos_apertura --gt data/tracking_golden \
  --api http://127.0.0.1:8099 | sed 's|http://127.0.0.1:8099|http://track.torre|'
