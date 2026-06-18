#!/usr/bin/env bash
#
# annotate.sh — Lanzador de la demo: pide un video SIN etiquetar y devuelve uno
# ETIQUETADO (cajas + conteo) con el modelo campeón MIN5.
#
# Maneja Docker por ti: corre dentro de la imagen mot-dev (GPU si está disponible),
# monta el repo en /workspace y la carpeta del video en /input.
#
# Uso:
#   ./scripts/demo/annotate.sh [ruta_video] [-- opciones-extra-del-script]
# Ejemplos:
#   ./scripts/demo/annotate.sh
#   ./scripts/demo/annotate.sh ~/Downloads/videoTM_03.mkv
#   ./scripts/demo/annotate.sh ~/Downloads/videoTM_17.mkv -- --start 120 --dur 45
#
set -uo pipefail

REPO="/home/camilo-pc/Multi-Object-Tracking"
IMAGE="mot-dev:latest"
DOCKER="docker -c default"   # el stack real vive en el engine del host

# 1) Resolver el video ------------------------------------------------------
VIDEO="${1:-}"
EXTRA=()
# separar opciones extra tras "--"
if [[ "${1:-}" == "--" ]]; then VIDEO=""; shift; EXTRA=("$@"); fi
if [[ $# -ge 2 ]]; then shift; [[ "${1:-}" == "--" ]] && shift; EXTRA=("$@"); fi

if [[ -z "$VIDEO" ]]; then
  read -r -p "📹 Ruta del video SIN etiquetar: " VIDEO
  VIDEO="${VIDEO//\"/}"
fi
# expandir ~ y a ruta absoluta
VIDEO="${VIDEO/#\~/$HOME}"
VIDEO="$(readlink -f "$VIDEO" 2>/dev/null || echo "$VIDEO")"
if [[ ! -f "$VIDEO" ]]; then
  echo "❌ No existe el archivo: $VIDEO"; exit 1
fi

VID_DIR="$(dirname "$VIDEO")"
VID_FILE="$(basename "$VIDEO")"

# 2) ¿GPU disponible? -------------------------------------------------------
GPU_FLAG=""
if $DOCKER run --rm --gpus all "$IMAGE" nvidia-smi >/dev/null 2>&1; then
  GPU_FLAG="--gpus all"
  echo "🟢 GPU detectada — usando aceleración."
else
  echo "🟡 Sin GPU (o no accesible) — corriendo en CPU (más lento, sirve igual)."
fi

# 3) Correr la app ----------------------------------------------------------
echo "🚀 Procesando '$VID_FILE'..."
$DOCKER run --rm $GPU_FLAG --shm-size=2g \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp -e YOLO_CONFIG_DIR=/tmp/Ultralytics \
  -v "$REPO:/workspace" \
  -v "$VID_DIR:/input:ro" \
  -w /workspace \
  "$IMAGE" \
  python3 scripts/demo/annotate_video.py "/input/$VID_FILE" "${EXTRA[@]}"

RC=$?
if [[ $RC -eq 0 ]]; then
  OUT="$REPO/outputs/demos/${VID_FILE%.*}_anotado.mp4"
  echo
  echo "🎬 Video anotado en: $OUT"
  echo "   (ábrelo con tu reproductor; está en outputs/demos/)"
fi
exit $RC
