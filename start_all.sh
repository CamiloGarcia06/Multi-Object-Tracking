#!/usr/bin/env bash
#
# start_all.sh — Arranca CVAT (en Docker Desktop) + el detector de cabezas en Nuclio,
# evitando los dos problemas típicos tras un reinicio:
#   1) Un segundo stack de CVAT en el engine del host que roba el puerto 8080.
#   2) Las funciones Nuclio que quedan "Exited" con el puerto desincronizado.
#
# CVAT y Nuclio viven en DOCKER DESKTOP (contexto desktop-linux).
# El entrenamiento con GPU va aparte, en el engine del host (docker -c default).
#
set -uo pipefail

REPO="/home/camilo-pc/Multi-Object-Tracking"
CVAT_DIR="$REPO/cvat"
DESKTOP_SOCK="unix:///home/camilo-pc/.docker/desktop/docker.sock"
COMPOSE_FILES="-f docker-compose.yml -f components/serverless/docker-compose.serverless.yml"
FUNCS=("nuclio-nuclio-pth-ultralytics-yolov5mu-head" "nuclio-nuclio-pth-ultralytics-yolo11x")

say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }

# 1) Asegurar Docker Desktop arriba ------------------------------------------
say "Arrancando Docker Desktop (si hace falta)..."
if ! timeout 10 docker -c desktop-linux info >/dev/null 2>&1; then
  systemctl --user start docker-desktop 2>/dev/null || true
  for i in $(seq 1 30); do
    timeout 8 docker -c desktop-linux info >/dev/null 2>&1 && break
    echo "  esperando a Docker Desktop... ($i)"; sleep 6
  done
fi
docker -c desktop-linux info >/dev/null 2>&1 || { echo "ERROR: Docker Desktop no respondió"; exit 1; }
echo "  Docker Desktop OK"

# 2) Parar el CVAT duplicado del host (libera :8080) -------------------------
say "Parando cualquier CVAT duplicado en el engine del host..."
( cd "$CVAT_DIR" && docker -c default compose stop >/dev/null 2>&1 ) || true

# 3) Levantar CVAT en Desktop (con serverless) ------------------------------
say "Levantando CVAT (Desktop) con componente serverless..."
cd "$CVAT_DIR"
docker -c desktop-linux compose $COMPOSE_FILES up -d

# 4) Asegurar que traefik publique el :8080 al host -------------------------
say "Verificando publicación del puerto 8080..."
if ! docker -c desktop-linux ps --format '{{.Names}} {{.Ports}}' | grep -q "traefik.*0.0.0.0:8080->"; then
  echo "  traefik sin mapeo de host -> recreando..."
  docker -c desktop-linux compose $COMPOSE_FILES up -d --force-recreate traefik
fi
for i in $(seq 1 15); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/api/server/about 2>/dev/null)" = "200" ] \
    && { echo "  CVAT responde en http://localhost:8080"; break; }
  echo "  esperando a CVAT... ($i)"; sleep 4
done

# 5) Redeploy de las funciones Nuclio (resincroniza puertos) -----------------
# Tras un reinicio, 'docker start' deja el puerto desincronizado y la
# auto-anotación falla. Redeploy con nuctl lo arregla (imágenes ya cacheadas).
say "Redeployando funciones Nuclio del detector..."
export DOCKER_HOST="$DESKTOP_SOCK"
# nuclio usa gcr.io/iguazio/alpine:3.17; si solo está la 3.20, la retagueamos
if docker -c desktop-linux image inspect gcr.io/iguazio/alpine:3.20 >/dev/null 2>&1 \
   && ! docker -c desktop-linux image inspect gcr.io/iguazio/alpine:3.17 >/dev/null 2>&1; then
  docker -c desktop-linux tag gcr.io/iguazio/alpine:3.20 gcr.io/iguazio/alpine:3.17
fi
cd "$CVAT_DIR/serverless"
for FUNC in pytorch/ultralytics/yolov5mu-head/nuclio; do
  echo "  deploy: $FUNC"
  nuctl deploy --project-name cvat --path "$FUNC" \
    --file "$FUNC/function.yaml" --platform local \
    --env CVAT_FUNCTIONS_REDIS_HOST=cvat_redis_ondisk \
    --env CVAT_FUNCTIONS_REDIS_PORT=6666 \
    --platform-config '{"attributes": {"network": "cvat_cvat"}}' >/dev/null 2>&1 \
    && echo "    OK" || echo "    (falló — revisa 'nuctl get function --platform local')"
done
unset DOCKER_HOST

say "Listo. CVAT: http://localhost:8080  |  Modelo: 'YOLOv5mu Head Detector' en Automatic annotation"
echo "Estado de funciones:"
DOCKER_HOST="$DESKTOP_SOCK" nuctl get function --platform local 2>/dev/null | grep -iE "NAME|yolo" || true
