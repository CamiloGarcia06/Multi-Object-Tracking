#!/usr/bin/env bash
# C8 — evaluación UNA VEZ de un video de prueba (Tesis 19/22/18): Tabla I del sistema congelado
# (ByteTrack #27 + door.py + regla od) y de la línea base sin tracking, sin corregir y corregidas.
#
# Los eventos se generaron y SELLARON antes de existir el golden (configs/prueba_sellada.sha256):
# si cambian, la evaluación no vale y el script se para. El golden sale de golden_csv.py.
#
#   bash scripts/flow/evaluar_prueba.sh bus_ddr_s6_v18 [DIR]    # DIR = data/flow_eval/test_<video>
#
# Escribe docs/resultados-<video>.md. Factores: configs/calibracion.yaml (sistema, 03+07) y
# configs/calibracion_sin_tracking.yaml (línea base, 03+07).
set -euo pipefail
cd "$(dirname "$0")/../.."
V=$1
D=${2:-data/flow_eval/test_$V}
G=data/flow_golden/$V.csv
OUT=docs/resultados-$V.md

grep -F "$D/" configs/prueba_sellada.sha256 | sha256sum -c --quiet - \
  || { echo "Los eventos de $D no coinciden con el sello: la evaluación no vale"; exit 1; }
[ -s "$G" ] || { echo "Falta el golden $G (golden_csv.py build ...)"; exit 1; }

SYS="#27 ByteTrack=$D/ev.csv"
BASE="sin tracking=$D/ev_sin_tracking.csv"
{
  echo "# Resultados de prueba: $V ($(date +%F))"
  echo
  echo "Evaluado UNA vez. Eventos sellados antes del golden (configs/prueba_sellada.sha256)."
  echo "Golden: \`$G\`. Puerta del sistema: door.py (\`data/flow_videos/puerta_abierta_$V.json\`)."
  echo
  echo "## Sin corregir"
  echo
  uv run -q scripts/flow/eval_flow.py --golden "$G" --system "$SYS" --system "$BASE" --markdown
  echo
  echo "## Corregido: sistema (factor 03+07)"
  echo
  uv run -q scripts/flow/calibrate.py report --calib configs/calibracion.yaml --golden "$G" --system "$SYS" --markdown
  echo
  echo "## Corregido: línea base (factor 03+07)"
  echo
  uv run -q scripts/flow/calibrate.py report --calib configs/calibracion_sin_tracking.yaml --golden "$G" --system "$BASE" --markdown
} > "$OUT"
echo "$OUT"
