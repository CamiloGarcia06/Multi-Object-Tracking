---
name: train-round
description: Entrena la ronda N del detector de cabezas (bus_head_vN) con la receta GPU completa y todos los gotchas de docker horneados. Uso /train-round <N>. Al terminar localiza best.pt, calcula sha256 y encadena la evaluación golden.
---

# Entrenar ronda N del detector de cabezas

Argumento: `N` = número de ronda (ej. `/train-round 5` entrena sobre `data/bus_head_v5`).

## Pre-checks (NO entrenar si alguno falla)

1. **Dataset listo**: deben existir `data/bus_head_vN.yaml` y `data/bus_head_vN/` con
   `images/{train,val}` + `labels/{train,val}`. Si no existen, detente y dile al usuario
   que primero hay que construir el dataset (estilo `scripts/active_learning/build_v3.py`
   a partir del export de CVAT).
2. **Cero fugas del golden**: ningún stem de `data/golden/images/val/` puede aparecer en
   train/val del nuevo dataset. Verifica comparando nombres de frame (los golden son
   `golden_<cam>_fXXXXXX`; compara cámara+nº de frame contra los stems del dataset).
   Si hay solape, ABORTA y repórtalo.
3. **GPU en el engine del host**: `docker -c default run --rm --runtime=nvidia -e NVIDIA_VISIBLE_DEVICES=all mot-dev:latest nvidia-smi` debe funcionar.
   GOTCHA: Docker Desktop (desktop-linux) NO pasa CUDA — entrenar SIEMPRE con `docker -c default`.

## Entrenamiento

Lanza en background (tarda ~1-2h) y monitorea con `docker logs`:

```bash
docker -c default run -d --name train-rN --runtime=nvidia -e NVIDIA_VISIBLE_DEVICES=all \
  --memory 16g --memory-swap 16g --shm-size=8g \
  -v /home/camilo-pc/Multi-Object-Tracking:/workspace -w /workspace mot-dev:latest \
  yolo detect train model=models/yolov5mu-head-base.pt data=data/bus_head_vN.yaml \
    epochs=80 imgsz=640 batch=8 workers=4 cache=False device=0 \
    project=outputs/head_detector name=yolo-bus-head-rN
```

GOTCHAS obligatorios (NO los quites):
- `--shm-size=8g` o los DataLoader workers crashean con "Unexpected bus error / insufficient shared memory".
- `batch=8 workers=4 cache=False --memory 16g`: el auto-batch + workers por defecto congelaron el PC una vez.
- Siempre entrenar desde el BASE `models/yolov5mu-head-base.pt`, nunca desde el best.pt de la ronda anterior (receta validada R2–R4).

## Post-entrenamiento

1. GOTCHA: el `project=` relativo puede anidarse bajo `runs/detect/`. Localiza los pesos con:
   `find /home/camilo-pc/Multi-Object-Tracking -name best.pt -path "*rN*" -newer <algo>` y
   si quedaron anidados, muévelos a `outputs/head_detector/yolo-bus-head-rN/weights/best.pt`.
2. Calcula y reporta `sha256sum` del best.pt.
3. Limpia el contenedor: `docker -c default rm train-rN`.
4. Encadena `/eval-golden` (añadiendo el modelo RN al dict MODELS si falta).

## Registro en memoria

Al cerrar la ronda, actualiza la memoria del agente (`bus-head-active-learning` con el
resultado de la ronda y `bus-head-resume-point` con el nuevo estado/próximo paso).
