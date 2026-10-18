#!/usr/bin/env bash
# Exporta de CVAT un job del golden de TRACKING en MOT 1.1 (la exportación oficial, que
# interpola las cajas entre keyframes) y lo deja como golden:
#   data/cvat_export/<clip>_<fecha>/   export.zip + gt/ (copia de seguridad)
#   data/tracking_golden/<clip>/       gt/gt.txt + seqinfo.ini (de data/cvat_import/<clip>/)
# Lee la contraseña de ~/srv/cvat/.credenciales (o de CVAT_PASS) sin sacarla de esta máquina.
#   bash exportar_mot.sh 55 tm03_1_a
#   bash exportar_mot.sh t16          por tarea: saca el job y el clip del nombre "golden tracking <clip>"
set -euo pipefail
JOB=$1 CLIP=${2:-}
DATA=$(cd "$(dirname "$0")/../../data" && pwd)
API=http://localhost:8080
H=(-H "Host: cvat.torre")
USER_=${CVAT_USER:-camilo}
CRED=~/srv/cvat/.credenciales
ok() { [ "$(curl -s -o /dev/null -w '%{http_code}' "${H[@]}" -u "$USER_:$1" $API/api/users/self)" = 200 ]; }
PASS=""
for cand in "${CVAT_PASS:-}" \
    "$(grep -iE 'pass|contrase|clave' "$CRED" 2>/dev/null | head -1 | sed -E 's/^[^:=]*[:=][[:space:]]*//')" \
    "$(head -1 "$CRED" | sed -E 's/^[^:]*:[[:space:]]*//')" \
    "$(head -1 "$CRED")"; do
  if [ -n "$cand" ] && ok "$cand"; then PASS=$cand; break; fi
done
[ -n "$PASS" ] || { echo "No pude autenticar como $USER_: exporta CVAT_PASS=... y repite"; exit 1; }
A=(-u "$USER_:$PASS")

if [[ $JOB == t* ]]; then
  TASK=${JOB#t}
  NAME=$(curl -sf "${H[@]}" "${A[@]}" "$API/api/tasks/$TASK" | python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])')
  JOB=$(curl -sf "${H[@]}" "${A[@]}" "$API/api/jobs?task_id=$TASK" | python3 -c 'import json,sys; print(json.load(sys.stdin)["results"][0]["id"])')
  [ -n "$CLIP" ] || CLIP=${NAME#golden tracking }
  echo "tarea $TASK = \"$NAME\" -> job $JOB, clip $CLIP"
fi
[ -f "$DATA/cvat_import/$CLIP/seqinfo.ini" ] || { echo "no existe $DATA/cvat_import/$CLIP/seqinfo.ini"; exit 1; }

RQ=$(curl -sf "${H[@]}" "${A[@]}" -X POST "$API/api/jobs/$JOB/dataset/export?format=MOT%201.1&save_images=false" \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["rq_id"])')
echo "exportando job $JOB ($RQ)..."
URL=""
for _ in $(seq 60); do
  sleep 2
  read -r ST URL < <(curl -sf "${H[@]}" "${A[@]}" "$API/api/requests/$RQ" | python3 -c '
import json, sys
r = json.load(sys.stdin)
print(r["status"], r.get("result_url") or "-")')
  case $ST in
    finished) break ;;
    failed) echo "CVAT falló la exportación"; exit 1 ;;
  esac
done
[ "$ST" = finished ] || { echo "la exportación no terminó a tiempo"; exit 1; }

OUT=$DATA/cvat_export/${CLIP}_$(date +%Y%m%d_%H%M)
mkdir -p "$OUT"
curl -sf "${H[@]}" "${A[@]}" "${URL/http:\/\/cvat.torre/$API}" -o "$OUT/export.zip"
python3 -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$OUT/export.zip" "$OUT"
[ -s "$OUT/gt/gt.txt" ] || { echo "el zip no trae gt/gt.txt: mira $OUT"; exit 1; }

G=$DATA/tracking_golden/$CLIP
mkdir -p "$G/gt"
cp "$OUT/gt/gt.txt" "$G/gt/gt.txt"
cp "$DATA/cvat_import/$CLIP/seqinfo.ini" "$G/seqinfo.ini"
python3 - "$G/gt/gt.txt" <<'PY'
import sys
rows = [l.split(",") for l in open(sys.argv[1]) if l.strip()]
frames = {int(r[0]) for r in rows}
print(f"golden: {len(rows)} cajas, {len({r[1] for r in rows})} tracks, frames {min(frames)}-{max(frames)} -> {sys.argv[1]}")
PY
