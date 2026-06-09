# Golden Test Set — Baseline (2026-06-09)
151 frames held-out (video02 no visto + held-out v05/v16/S08), 1241 cabezas reales.
Config: conf=0.25, NMS iou=0.5.

| Modelo | P | R | mAP50 | mAP50-95 | MAE conteo | sesgo |
|--------|---|---|-------|----------|-----------|-------|
| BASE | 0.85 | 0.31 | 0.59 | 0.32 | 5.13 | -5.13 |
| R2   | 0.86 | 0.51 | 0.69 | 0.42 | 4.17 | -4.11 |
| R3   | 0.89 | 0.76 | 0.85 | 0.65 | 2.06 | -1.89 |  <-- DESPLEGADO
| R4   | 0.93 | 0.76 | 0.86 | 0.71 | 2.48 | -2.40 |

MAE por cámara (R3): S08=0.76 v05=1.41 v16=1.35 video02=2.51
Debilidad: sub-conteo (cabezas perdidas), peor en cámara nueva (video02).
Re-correr: python3 data/golden/eval_golden.py  (dentro de mot-dev)
