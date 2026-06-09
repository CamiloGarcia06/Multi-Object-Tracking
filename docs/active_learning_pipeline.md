# Bus Head Detector — Active Learning Pipeline

Detector de cabezas para video CCTV top-down/fisheye de buses (interior, multitudes),
servido en CVAT vía Nuclio para auto-anotación, mejorado por rondas de active learning.

## Modelo desplegado
**R3** (`outputs/head_detector/yolo-bus-head-r3/weights/best.pt`) con **NMS iou=0.5**.
Base de entrenamiento: `models/yolov5mu-head-base.pt` (CrowdHuman head, eye-level).
> Pesos y datasets NO están en git (ver `.gitignore`); el modelo se publica como
> GitHub Release. Las recetas Nuclio en `serverless/` no incluyen el `.pt`.

## El loop
1. **Seleccionar frames** de cámaras nuevas/diversas (no al azar):
   - `scripts/active_learning/mine_frames.py` — multitudes + incertidumbre + oscuros.
   - `scripts/active_learning/extract_bright.py` — solo iluminados + con gente + diversos.
2. **Pre-anotar en CVAT** con el modelo actual (Automatic annotation, conf 0.25).
3. **Corregir** a mano (completar lo que el modelo se salta, quitar FPs).
4. **Construir dataset**: `build_v3.py` (merge), `clean_v4.py` (dedup IoU>0.5).
5. **Entrenar** desde el base (GPU, host engine):
   ```
   docker -c default run --rm --runtime=nvidia -e NVIDIA_VISIBLE_DEVICES=all \
     --memory 16g --memory-swap 16g --shm-size=8g \
     -v $PWD:/workspace -w /workspace mot-dev:latest \
     yolo detect train model=models/yolov5mu-head-base.pt data=data/bus_head_vN.yaml \
       epochs=80 imgsz=640 batch=8 workers=4 cache=False device=0
   ```
   (`--shm-size=8g` es obligatorio o los workers crashean por memoria compartida.)
6. **Evaluar contra el golden** (ver abajo) y **redeployar** si baja el MAE de conteo.

## Golden test set (benchmark fijo)
151 frames held-out (video02 no visto + held-out de v05/v16/S08), etiquetados a mano,
**prohibido entrenar con ellos**. Métrica clave = **MAE de conteo** (cabezas pred vs reales).
- Selección: `golden_select.py` · construcción: `build_golden.py` · evaluación: `eval_golden.py`
- Resultados base: `docs/golden_baseline.md`

| Modelo | mAP50 | Recall | **MAE conteo** |
|--------|:---:|:---:|:---:|
| BASE (CrowdHuman) | 0.59 | 0.31 | 5.13 |
| R2 | 0.69 | 0.51 | 4.17 |
| **R3 (desplegado)** | 0.85 | 0.76 | **2.06** |
| R4 (datos deduplicados) | 0.86 | 0.76 | 2.48 |

Objetivo de la próxima ronda: bajar de **2.06**. Debilidad medida: sub-conteo en
cámaras nuevas (video02 MAE 2.51) → priorizar recall y generalización.

## Despliegue en CVAT
Tres funciones Nuclio (selectables en Automatic annotation): `Head Detector R3`,
`Head Detector R4`, y la genérica `YOLOv5mu Head Detector` (= R3). NMS configurable
vía `data.get("iou", 0.5)` en `main.py`. Re-arranque tras reinicio: `start_all.sh`.
