# Golden Test Set — Baseline (2026-06-09)
151 frames held-out (video02 no visto + held-out v05/v16/S08), 1241 cabezas reales.
Config: conf=0.25, NMS iou=0.5.

| Modelo | P | R | mAP50 | mAP50-95 | MAE conteo | sesgo |
|--------|---|---|-------|----------|-----------|-------|
| BASE | 0.85 | 0.31 | 0.59 | 0.32 | 5.13 | -5.13 |
| R2   | 0.86 | 0.51 | 0.69 | 0.42 | 4.17 | -4.11 |
| R3   | 0.89 | 0.76 | 0.85 | 0.65 | 2.06 | -1.89 |
| R4   | 0.93 | 0.76 | 0.86 | 0.71 | 2.48 | -2.40 |
| R5   | 0.90 | 0.79 | 0.87 | 0.63 | 2.04 | -1.87 |  <-- DESPLEGADO

MAE por cámara (R3): S08=0.76 v05=1.41 v16=1.35 video02=2.51
MAE por cámara (R5): S08=1.12 v05=1.35 v16=1.18 video02=2.46
R5 (sha256 41a9f2ce0906...) = v3 + 225 frames de 5 cámaras diurnas nuevas (v04_1/v04_2/v05_1/v11/v12).
Gana a R3 por margen mínimo en MAE (2.04<2.06) pero sube recall 0.76→0.79 y mAP50 0.85→0.87
(objetivo: generalización/recall). Regresión: S08 0.76→1.12. Sigue sub-contando; aún sin
cumplir salida Fase 1 (MAE≤1.5, ≤2.0 unseen, recall≥0.85).
Debilidad persistente: sub-conteo (cabezas perdidas), peor en cámara nueva (video02).
Re-correr: python3 data/golden/eval_golden.py  (dentro de mot-dev)
