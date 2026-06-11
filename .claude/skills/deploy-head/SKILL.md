---
name: deploy-head
description: Despliega los pesos de la ronda N como función Nuclio en CVAT (swap de best.pt + redeploy con nuctl) y publica el GitHub Release. Solo se usa si /eval-golden dio veredicto de mejora. Uso /deploy-head <N>.
---

# Desplegar ronda N en CVAT (Nuclio) + release

PRE-CONDICIÓN: `/eval-golden` mostró count-MAE estrictamente mejor que el campeón.
Si no hay evidencia de eso en la conversación, pide confirmación explícita al usuario
antes de seguir (regla del proyecto: solo se despliega lo que mejora el golden).

## 1. Swap de pesos en la función principal

Función canónica (la que usa el usuario en CVAT): 
`cvat/serverless/pytorch/ultralytics/yolov5mu-head/nuclio/`

```bash
cd /home/camilo-pc/Multi-Object-Tracking/cvat/serverless/pytorch/ultralytics/yolov5mu-head/nuclio
cp best.pt best_r<ANTERIOR>.pt.bak   # backup del campeón saliente (patrón: best_r2.pt.bak, etc.)
cp /home/camilo-pc/Multi-Object-Tracking/outputs/head_detector/yolo-bus-head-rN/weights/best.pt best.pt
```

Opcional: crear también la función selectable `Head Detector RN` copiando la receta de
`serverless/yolov5mu-head-r3/` → `serverless/yolov5mu-head-rN/` (ajustar nombre/metadata
en `function.yaml`) y replicándola bajo `cvat/serverless/pytorch/ultralytics/` con su best.pt.

## 2. Redeploy con nuctl (GOTCHAS críticos)

- CVAT/Nuclio viven en **Docker Desktop** (contexto desktop-linux), NO en el host engine.
- **NUNCA `docker start`** sobre contenedores de funciones tras un reinicio: el puerto
  registrado en Nuclio se desincroniza y CVAT falla con "host.docker.internal:<port>
  Network is unreachable". Siempre REDEPLOY.
- nuctl necesita `gcr.io/iguazio/alpine:3.17`; si solo está la 3.20:
  `docker -c desktop-linux tag gcr.io/iguazio/alpine:3.20 gcr.io/iguazio/alpine:3.17`.

```bash
export DOCKER_HOST="unix:///home/camilo-pc/.docker/desktop/docker.sock"
cd /home/camilo-pc/Multi-Object-Tracking/cvat/serverless
nuctl deploy --project-name cvat --path pytorch/ultralytics/yolov5mu-head/nuclio \
  --file pytorch/ultralytics/yolov5mu-head/nuclio/function.yaml --platform local \
  --env CVAT_FUNCTIONS_REDIS_HOST=cvat_redis_ondisk \
  --env CVAT_FUNCTIONS_REDIS_PORT=6666 \
  --platform-config '{"attributes": {"network": "cvat_cvat"}}'
unset DOCKER_HOST
```

(Alternativa todo-en-uno tras un reinicio del PC: `./start_all.sh` desde la raíz del repo.)

## 3. Verificación

1. `DOCKER_HOST=unix:///home/camilo-pc/.docker/desktop/docker.sock nuctl get function --platform local` → estado `ready`.
2. Pide al usuario probar Automatic annotation en CVAT (conf 0.25) sobre un frame
   concurrido, o invoca la función directamente con un frame de `data/golden/images/val/`.
3. El NMS es configurable vía `data.get("iou", 0.5)` en `main.py` — el default 0.5 es el
   validado (elimina dobles conteos); no subirlo.

## 4. Release y registro

1. `sha256sum` del best.pt desplegado.
2. GitHub Release: `gh release create bus-head-vN outputs/head_detector/yolo-bus-head-rN/weights/best.pt --title "Bus head detector RN" --notes "<MAE y tabla golden>"`
   (los pesos NO van en git; el release es el canal de distribución).
3. Actualizar `docs/active_learning_pipeline.md` (sección "Modelo desplegado") y
   `docs/golden_baseline.md` (marcador `<-- DESPLEGADO`).
4. Actualizar la memoria del agente: nuevo campeón, sha256, estado del deploy.
