# Recall del detector por cámara (goldens de tracking)

Generado por `scripts/eval/recall_por_camara.py`. Recall = cota superior (goldens pre-anotados con el detector).

| clip | cámara | nivel | conf | IoU | GT | recall | recall ROI | precisión ROI |
|---|---|---|---|---|---|---|---|---|
| tm07_a | DDL | baja | 0.1 | 0.5 | 323 | 0.697 | 0.772 | 0.824 |
| tm07_a | DDL | baja | 0.1 | 0.3 | 323 | 0.731 | 0.807 | 0.854 |
| tm07_a | DDL | baja | 0.25 | 0.5 | 323 | 0.65 | 0.74 | 0.9 |
| tm07_a | DDL | baja | 0.25 | 0.3 | 323 | 0.666 | 0.756 | 0.919 |
| tm02_a | DDL | alta | 0.1 | 0.5 | 1138 | 0.825 | 0.834 | 0.824 |
| tm02_a | DDL | alta | 0.1 | 0.3 | 1138 | 0.873 | 0.881 | 0.87 |
| tm02_a | DDL | alta | 0.25 | 0.5 | 1138 | 0.793 | 0.803 | 0.861 |
| tm02_a | DDL | alta | 0.25 | 0.3 | 1138 | 0.834 | 0.843 | 0.903 |
| tm03_1_a | SDM | media | 0.1 | 0.5 | 1080 | 0.745 | 0.746 | 0.781 |
| tm03_1_a | SDM | media | 0.1 | 0.3 | 1080 | 0.772 | 0.773 | 0.81 |
| tm03_1_a | SDM | media | 0.25 | 0.5 | 1080 | 0.702 | 0.704 | 0.856 |
| tm03_1_a | SDM | media | 0.25 | 0.3 | 1080 | 0.722 | 0.724 | 0.88 |
