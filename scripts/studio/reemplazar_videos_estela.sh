#!/usr/bin/env bash
# Tesis 27: cambia en track-studio los 24 videos por clip (9 _b + 15 _a) por los re-renderizados
# con la estela de cada cabeza. Como el importador no repite un MOT ya subido, borra antes los
# jobs viejos (#54-#62 y #78-#92), comprobando que cada uno es un video por clip con render.
# Los _a se vuelven a evaluar contra su golden; los _b no tienen golden.
# Lee el token del .env del servicio sin enseñarlo. No despliega ni reinicia nada.
#   ssh torre 'bash ~/Multi-Object-Tracking-studio/scripts/studio/reemplazar_videos_estela.sh'
set -euo pipefail
TS=~/Projects/track-studio
API=http://127.0.0.1:8099
TRACK_STUDIO_TOKEN=$(sed -n 's/^TRACK_STUDIO_TOKEN=//p' "$TS/.env" | tr -d '"'"'"' \r')
[ -n "$TRACK_STUDIO_TOKEN" ] || { echo "no encontré TRACK_STUDIO_TOKEN en $TS/.env"; exit 1; }
export TRACK_STUDIO_TOKEN
CLIPS="tm02_a.mp4 tm03_1_a.mp4 tm07_a.mp4 ddr_s6_v18_a.mp4 sdr_s1_v08_a.mp4 tm03_1_b.mp4 tm07_b.mp4 ddr_s6_v18_b.mp4"
for id in $(seq 54 62) $(seq 78 92); do
  src=$(curl -sf "$API/api/jobs/$id" | python3 -c 'import json,sys; j=json.load(sys.stdin); print(j["source_name"] if j.get("has_output") and "recortado a la apertura" in (j.get("imported_from") or "") else "")')
  case " $CLIPS " in *" $src "*) ;; *) echo "el job #$id no es un video por clip ($src): paro aquí"; exit 1;; esac
  code=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE -H "Authorization: Bearer $TRACK_STUDIO_TOKEN" "$API/api/jobs/$id")
  [ "$code" = 204 ] || { echo "no se pudo borrar el job #$id: HTTP $code"; exit 1; }
  echo "  borrado #$id ($src)"
done
cd ~/Multi-Object-Tracking-studio
echo "== 15 clips _a (con golden)"
uv run -q scripts/tracking/importar_studio.py --videos data/videos_apertura --gt data/tracking_golden --api "$API" \
  | grep -E "job #|HOTA" | sed 's|http://127.0.0.1:8099|http://track.torre|'
echo "== 9 clips _b"
uv run -q scripts/tracking/importar_studio.py --videos ~/Multi-Object-Tracking/data/videos_apertura --api "$API" \
  | sed 's|http://127.0.0.1:8099|http://track.torre|'
