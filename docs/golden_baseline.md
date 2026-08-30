# Golden Test Set — Baseline

## Golden v2 (2026-08-23) — VIGENTE
151 frames held-out (video02 no visto + held-out v05/v16/S08), **1271 cabezas reales**.
Config: conf=0.25, NMS iou=0.5. P/R/mAP vía `yolo val`; MAE por conteo directo.

| Modelo | P | R | mAP50 | mAP50-95 | MAE conteo | sesgo |
|--------|---|---|-------|----------|-----------|-------|
| BASE | 0.852 | 0.308 | 0.590 | 0.320 | 5.32 | -5.32 |
| R2   | 0.866 | 0.502 | 0.684 | 0.415 | 4.36 | -4.31 |
| R3   | 0.902 | 0.747 | 0.849 | 0.642 | 2.21 | -2.09 |
| R4   | 0.931 | 0.745 | 0.855 | 0.694 | 2.69 | -2.60 |
| R5   | 0.908 | 0.780 | 0.868 | 0.620 | 2.17 | -2.07 |
| MIN5 | 0.889 | **0.801** | **0.872** | 0.625 | **1.83** | -1.57 | <-- DESPLEGADO (campeón)
| yolo26m-min5 | 0.898 | 0.732 | 0.837 | 0.559 | 1.91 | -1.81 | <-- COCO, 21.9M
| v5mu-coco-min5 | 0.906 | 0.745 | 0.845 | — | 1.76 | -1.52 | <-- COCO, 25.1M
| **yolo26x-min5** | 0.908 | 0.762 | 0.854 | — | **1.64** | -1.36 | <-- COCO, 59.0M — MEJOR MAE

MAE por cámara (R3):   S08=0.94 v05=1.82 v16=1.65 video02=2.58
MAE por cámara (R5):   S08=1.41 v05=1.65 v16=1.24 video02=2.55
MAE por cámara (MIN5): S08=1.35 v05=1.47 v16=1.47 video02=2.04

El ranking se mantiene idéntico al de v1: MIN5 campeón, R5 y R3 empatados detrás.
La corrección de etiquetas no reordenó las comparaciones históricas.

### yolo26m desde COCO (2026-08-23) — la arquitectura nueva es competitiva
Receta idéntica a MIN5 (mismo dataset `bus_head_v5_min5`, 80 ep, imgsz 640, batch 8) pero
partiendo de **`yolo26m.pt` (COCO), SIN la base de CrowdHuman**. 39,3 min, mejor época 21.
MAE por cámara: S08=1.53 v05=2.00 v16=1.35 video02=2.06

Resultado: **MAE 1.91 vs 1.83 de MIN5** — a 4% del campeón, y por encima de R5 (2.17), R3 (2.21)
y R4 (2.69), que sí tienen la base de CrowdHuman. Precisión incluso mayor (0.898 vs 0.889);
pierde en recall (0.732 vs 0.801) y mAP50 (0.837 vs 0.872).

Lectura: yolo26m (21.9M params) alcanza casi al campeón yolov5mu (25.1M) **sin las 30k imágenes
de cabezas de CrowdHuman**. Es la evidencia más fuerte de que la arquitectura nueva tiene margen.
SIGUIENTE EXPERIMENTO OBVIO: pre-entrenar yolo26m en CrowdHuman (~6h; el OOM histórico era por
batch 16-32, con batch 8 entra en 4.7GB) y luego fine-tune en min5 -> deberia superar a MIN5.
Nota de despliegue: yolo26 tiene inferencia end-to-end; revisar la semántica de NMS iou=0.5 en la
función Nuclio antes de desplegarlo.
CAVEAT: mejor época 21 de 80 -> converge rápido y luego se estanca; con más datos hay headroom.

### Ablaciones de arquitectura y pre-entrenamiento (2026-08-23)
Todas con receta idéntica a MIN5: `bus_head_v5_min5`, 80 ep, imgsz 640, batch 8.

| corrida | base | params | MAE | mejor época | tiempo |
|---------|------|--------|-----|-------------|--------|
| yolo26m-min5 | COCO | 21.9M | 1.91 | 21 | 39 min |
| v5mu-coco-min5 | COCO | 25.1M | 1.76 | 19 | 27 min |
| yolo26x-min5 | COCO | 59.0M | **1.64** | 22 | 79 min |
| MIN5 (campeón) | CrowdHuman | 25.1M | 1.83 | — | 31 min |

**1. CrowdHuman no aporta nada medible.** `v5mu-coco-min5` (sin CrowdHuman) vs MIN5 (con), misma
arquitectura y receta, medidos ambos a conf=0.25 con matcher greedy propio:
recall +0.006 IC95 [-0.017,+0.027] | precisión +0.013 IC95 [-0.010,+0.035] |
MAE +0.07 IC95 [-0.285,+0.132], Wilcoxon p=0.47. **Los tres cruzan el cero.**
CrowdHuman sí enseña qué es una cabeza (BASE solo: recall 0.308 partiendo de un COCO sin la
clase), pero el fine-tune con 1044 frames de bus lo sobrescribe por completo.
NOTA: `yolo val` reporta P/R en el máximo F1 DE CADA MODELO (umbrales distintos) -> no comparar
modelos con esas cifras; usar un conf fijo.

**2. Más capacidad SÍ ayuda** (contra la predicción inicial). Tendencia monótona en MAE:
21.9M -> 1.91 | 25.1M -> 1.76 | 59.0M -> **1.64**. La convergencia temprana (mejor época ~20 de
80) NO implicaba saturación de capacidad.
yolo26x vs MIN5: dif -0.192, IC95 [-0.404,+0.026], Wilcoxon **p=0.043**, gana 67 / empata 42 /
pierde 42. Significancia LIMÍTROFE y con un solo seed; además hay comparaciones múltiples.
yolo26x vs v5mu-coco: dif -0.119, IC95 [-0.325,+0.086], p=0.24 -> INDISTINGUIBLE.
yolo26x da además el mejor resultado histórico en la cámara no vista: **video02 = 1.85**.
ANTES DE DESPLEGAR: repetir con 3 seeds (~4h) para separar la mejora de la varianza entre corridas.

### Qué cambió respecto de v1
Auditoría manual completa en CVAT (task 6 / job 12 `golden_val_full_audit`), a ciegas
respecto del modelo: el anotador vio solo las cajas del golden, nunca las predicciones.
Diff: **+93 agregadas, -63 borradas, 3 movidas, 1178 idénticas** (1241 -> 1271 cajas).

| cámara | frames | GT v1 | GT v2 | agregadas | borradas |
|--------|--------|-------|-------|-----------|----------|
| S08 | 17 | 97 | 106 | 34 | 25 |
| v05 | 17 | 143 | 150 | 13 | 6 |
| v16 | 17 | 130 | 135 | 6 | 1 |
| video02 | 100 | 871 | 880 | 40 | 31 |

Original congelado e intacto en `data/golden/labels_val_v1_frozen/` (1241 cajas).
Export de la auditoría: `data/_harvest/golden_v2_export.zip`.

### Conclusiones de la auditoría
1. **Las etiquetas NO eran el problema.** Se estimaba que 25-50% de los falsos positivos
   de MIN5 eran cabezas sin etiquetar; la auditoría rescató 8 de 60. El resto son FP
   genuinos. La precisión real de MIN5 no tenía margen oculto.
2. **El recall empeora al medir mejor** (0.751 -> 0.740 con matching greedy propio; 0.809
   -> 0.801 por `yolo val`): las 93 cabezas agregadas son las difíciles y el modelo no ve
   34 de ellas. El número de v1 era generoso, no el modelo peor.
3. **Modo de falla nombrado: APOYACABEZAS.** De las 63 cajas borradas, 36 (57%) eran
   detectadas por MIN5 con conf>=0.25 y tamaño mediano 58px. Inspección visual confirmó
   que son apoyacabezas de los asientos, no cabezas. Es un FP sistemático y de alta
   confianza -> atacar con negativos duros en la próxima ronda.
   Lámina de evidencia: `outputs/borradas_sospechosas.jpg`.

### Diagnóstico de MIN5 (medido sobre v1, sigue siendo válido en dirección)
Descomposición de los 309 FN: 130 (42%) miss total, **119 (38%) detectada con IoU>=0.5
pero conf<0.25**, 44 (14%) caja GT mal dibujada, 16 (5%) débil y mal localizada.
Recall por tamaño de cabeza: **<32px = 0.25 | 32-48px = 0.60 | >48px = 0.835**.
El cuello de botella es la cabeza chica.
OJO: video02 aporta 100/151 frames y 880/1271 cabezas -> la métrica global ES,
en la práctica, la de la cámara no vista.

Barrido de umbral (MIN5, golden v1): conf 0.15 -> P .837/R .840 | 0.25 -> .877/.809
| 0.35 -> .898/.774. Mejor F1 = 0.843 @ conf 0.228. **Subir imgsz en INFERENCIA empeora**
(960: mAP50 .880 | 1280: .836) por desajuste train/test -> para ganar con resolución hay
que RE-ENTRENAR a 960.

### Camino a P>=0.90 y R>=0.90
El umbral solo no alcanza: haría falta F1>=0.90 y MIN5 está en 0.843. Plan:
1. ~~Auditar el golden~~ HECHO — descartó la hipótesis de etiquetas.
2. Re-entrenar a **imgsz=960** (ataca los 130 miss totales, casi todos cabezas <48px).
3. **Recuperar s03** con etiquetas completas (ataca los 119 de baja confianza).
4. Negativos duros de apoyacabezas (ataca la precisión).
5. Datos de video02 en entrenamiento o inferencia con tiles (SAHI) para el tramo final.

## Historial

### Golden v1 (2026-06-09) — SUPERADO por v2, se conserva congelado
151 frames, 1241 cabezas. Las cifras de abajo NO son comparables con la tabla de v2.

| Modelo | P | R | mAP50 | mAP50-95 | MAE conteo | sesgo |
|--------|---|---|-------|----------|-----------|-------|
| BASE | 0.85 | 0.31 | 0.59 | 0.32 | 5.13 | -5.13 |
| R2   | 0.86 | 0.51 | 0.69 | 0.42 | 4.17 | -4.11 |
| R3   | 0.89 | 0.76 | 0.85 | 0.65 | 2.06 | -1.89 |
| R4   | 0.93 | 0.76 | 0.86 | 0.71 | 2.48 | -2.40 |
| R5   | 0.90 | 0.79 | 0.87 | 0.63 | 2.04 | -1.87 |
| MIN5 | —    | 0.809 | 0.873 | —  | 1.66 | -1.37 |

MAE por cámara (MIN5, v1): S08=0.94 v05=1.06 v16=1.18 video02=1.97

MIN5 (sha256 d158852aad42...) = bus_head_v5 filtrado a frames con >=5 cabezas etiquetadas
(2440 -> 1107 frames: 1044 train / 63 val), fine-tune desde la base de 80ep.
Motivo: la fuente dominante s03/video10 (~70% del dataset) estaba gravemente sub-etiquetada
(mediana 1 cabeza/frame en escenas llenas), enseñando "cabeza visible = fondo" -> sub-conteo
crónico. Con la MITAD de los datos supera a todo lo anterior: calidad de etiquetas > cantidad.
Desplegado como campeón canónico en CVAT ("YOLOv5mu Head Detector") el 2026-07-27;
backup del anterior en cvat/serverless/.../yolov5mu-head/nuclio/best_r5.pt.bak.

R5 (sha256 41a9f2ce0906...) = v3 + 225 frames de 5 cámaras diurnas nuevas (v04_1/v04_2/v05_1/v11/v12).

## Cómo re-correr

```bash
# los 6 modelos contra el golden vigente (dentro de mot-dev)
python3 data/golden/eval_golden.py

# comparar un modelo entre v1 y v2
python3 scripts/eval/compare_golden_versions.py

# aplicar una nueva corrección exportada de CVAT
python3 scripts/eval/apply_golden_correction.py data/_harvest/<export>.zip --dry-run
```

GOTCHA: borrar siempre `data/golden/labels/val.cache` después de cambiar etiquetas, o
ultralytics evalúa con las viejas sin avisar (`apply_golden_correction.py` ya lo hace).
