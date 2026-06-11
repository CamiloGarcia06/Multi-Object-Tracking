---
name: eval-golden
description: Evalúa los modelos del detector de cabezas contra el golden test set congelado (151 frames, count-MAE) y emite veredicto desplegar/no-desplegar contra el campeón. Actualiza docs/golden_baseline.md.
---

# Evaluar contra el golden test set

El golden (`data/golden/`, 151 frames, 1241 cabezas, `DO_NOT_TRAIN`) es el benchmark
congelado. Métrica que manda: **count-MAE**. Campeón actual y su MAE: ver tabla en
`docs/golden_baseline.md` (al crearse este skill: R3 = 2.06).

## Pasos

1. Si hay un modelo nuevo (ej. R5), añádelo al dict `MODELS` de
   `scripts/active_learning/eval_golden.py` (y su copia `data/golden/eval_golden.py` si
   existe — verifica cuál es el canónico con `ls`). Rutas con prefijo `/workspace/`.
2. Ejecuta dentro de mot-dev en el engine del host:
   ```bash
   docker -c default run --rm --runtime=nvidia -e NVIDIA_VISIBLE_DEVICES=all \
     --shm-size=8g -v /home/camilo-pc/Multi-Object-Tracking:/workspace -w /workspace \
     mot-dev:latest python3 data/golden/eval_golden.py
   ```
   Config fija: conf=0.25, NMS iou=0.5 — NO cambiarla, o los números dejan de ser comparables.
3. Presenta la tabla completa (P / R / mAP50 / mAP50-95 / MAE / sesgo) + MAE por cámara,
   comparando contra TODAS las rondas anteriores.

## Veredicto (regla de despliegue)

- **MAE nuevo < MAE campeón** → recomendar `/deploy-head <N>`.
- **Empate o peor** → NO desplegar (lección R4: 2.48 > 2.06 ⇒ R4 nunca se desplegó).
  Diagnostica: ¿el sesgo sigue negativo (sub-conteo)? ¿qué cámara empeoró? Eso define
  qué minar en la siguiente ronda (delegar al agente `error-analyst` si se quiere detalle).

## Registro

1. Actualiza la tabla de `docs/golden_baseline.md` y la de `docs/active_learning_pipeline.md`
   con la fila nueva (marca el desplegado con `<-- DESPLEGADO` solo después del deploy real).
2. Actualiza `data/golden/BASELINE_RESULTS.md` si existe.
3. Actualiza la memoria del agente (resultado de la ronda + nuevo objetivo).
4. RECUERDA: el golden jamás se modifica ni se entrena con él. Si alguien propone
   "refrescar" el golden, eso es una decisión explícita del usuario y crea un golden v2
   aparte, nunca edita el v1.
