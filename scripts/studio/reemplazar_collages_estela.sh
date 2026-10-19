#!/usr/bin/env bash
# Tesis 27: cambia en track-studio los 15 collages de eventos (#63-#77) por los re-renderizados con
# la estela de cada cabeza. Como el importador no repite un MOT ya subido, borra antes los jobs
# viejos, comprobando que cada uno es un collage de eventos con render, y al reimportar publica
# otra vez sus métricas contra el golden de tracking que cae dentro.
# Lee el token del .env del servicio sin enseñarlo. No despliega ni reinicia nada.
#   ssh torre 'bash ~/Multi-Object-Tracking-studio/scripts/studio/reemplazar_collages_estela.sh'
set -euo pipefail
TS=~/Projects/track-studio
API=http://127.0.0.1:8099
TRACK_STUDIO_TOKEN=$(sed -n 's/^TRACK_STUDIO_TOKEN=//p' "$TS/.env" | tr -d '"'"'"' \r')
[ -n "$TRACK_STUDIO_TOKEN" ] || { echo "no encontré TRACK_STUDIO_TOKEN en $TS/.env"; exit 1; }
export TRACK_STUDIO_TOKEN
for id in $(seq 63 77); do
  src=$(curl -sf "$API/api/jobs/$id" | python3 -c 'import json,sys; j=json.load(sys.stdin); print(j["source_name"] if j.get("has_output") and "collage de las" in (j.get("imported_from") or "") else "")')
  case "$src" in eventos_*.mp4) ;; *) echo "el job #$id no es un collage de eventos ($src): paro aquí"; exit 1;; esac
  code=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE -H "Authorization: Bearer $TRACK_STUDIO_TOKEN" "$API/api/jobs/$id")
  [ "$code" = 204 ] || { echo "no se pudo borrar el job #$id: HTTP $code"; exit 1; }
  echo "  borrado #$id ($src)"
done
cd ~/Multi-Object-Tracking-studio
uv run -q scripts/tracking/importar_studio.py --videos data/collage_eventos --gt data/tracking_golden --api "$API" \
  | grep -E "job #|HOTA" | sed 's|http://127.0.0.1:8099|http://track.torre|'
