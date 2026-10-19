#!/usr/bin/env bash
# Crea en CVAT la tarea de un clip del golden de TRACKING (como tm07_a): un job, etiqueta
# de caja `head`, frames frame_NNNNNN.png, y le importa la pre-anotación MOT 1.1 (tracks). Lee la contraseña de ~/srv/cvat/.credenciales
# (o de CVAT_PASS) sin sacarla de esta máquina.
#   TAREA=N bash crear_tarea.sh  solo reimporta la pre-anotación en la tarea N (BORRA lo anotado).
set -euo pipefail
cd "$(dirname "$0")"
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
echo "autenticado como $USER_"

wait_req() {  # $1 = acción del request de CVAT
  for _ in $(seq 120); do
    sleep 5
    ST=$(curl -sf "${H[@]}" "${A[@]}" "$API/api/requests?task_id=$TASK&action=$1" | python3 -c '
import json, sys
r = json.load(sys.stdin)["results"]
print((r[0]["status"] + " " + (r[0].get("message") or "")) if r else "queued")')
    case $ST in finished*) return 0 ;; failed*) echo "CVAT: $ST"; exit 1 ;; esac
  done
  echo "CVAT no terminó ($1)"; exit 1
}
NAME=$(sed -n 's/^name=//p' seqinfo.ini)
ZIP=${NAME}_preanotacion.zip
if [ -n "${TAREA:-}" ]; then
  TASK=$TAREA
else
TASK=$(curl -sf "${H[@]}" "${A[@]}" -X POST $API/api/tasks -H 'Content-Type: application/json' \
       -d "{\"name\": \"golden tracking $NAME\", \"labels\": [{\"name\": \"head\", \"type\": \"rectangle\"}]}" \
       | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "tarea $TASK creada; subiendo frames..."
trap 'echo "FALLÓ: borra la tarea $TASK en la UI si quedó a medias"' ERR
curl -sf "${H[@]}" "${A[@]}" -X POST $API/api/tasks/$TASK/data -H 'Upload-Start: true' -o /dev/null
mapfile -t FILES < <(ls frames | sort)
for ((s = 0; s < ${#FILES[@]}; s += 100)); do
  args=(); i=0
  for f in "${FILES[@]:s:100}"; do args+=(-F "client_files[$i]=@frames/$f"); i=$((i + 1)); done
  curl -sf "${H[@]}" "${A[@]}" -X POST $API/api/tasks/$TASK/data -H 'Upload-Multiple: true' "${args[@]}" -o /dev/null
  echo "  $((s + i)) / ${#FILES[@]}"
done
curl -sf "${H[@]}" "${A[@]}" -X POST $API/api/tasks/$TASK/data -H 'Upload-Finish: true' \
     -H 'Content-Type: application/json' -d '{"image_quality": 95, "sorting_method": "natural"}' -o /dev/null
echo "procesando en CVAT..."
wait_req create
fi
echo "importando la pre-anotación ($ZIP)..."
curl -sf "${H[@]}" "${A[@]}" -X POST "$API/api/tasks/$TASK/annotations?format=MOT%201.1" \
     -F "annotation_file=@$ZIP" -o /dev/null
wait_req import
N=$(curl -sf "${H[@]}" "${A[@]}" "$API/api/tasks/$TASK/annotations" | python3 -c '
import json, sys; d = json.load(sys.stdin); print(len(d["tracks"]), "tracks,", sum(len(t["shapes"]) for t in d["tracks"]), "cajas")')
echo "  $N"
J=$(curl -sf "${H[@]}" "${A[@]}" "$API/api/jobs?task_id=$TASK" | python3 -c 'import json,sys; print(json.load(sys.stdin)["results"][0]["id"])')
echo "listo: http://cvat.torre/tasks/$TASK (job $J)"
