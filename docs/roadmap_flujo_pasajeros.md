# Roadmap: del detector de cabezas al modelo de flujo de pasajeros

> Estado al 2026-06-10. Campeón actual: **R3** (golden count-MAE 2.06, NMS iou=0.5,
> desplegado en CVAT/Nuclio, release `bus-head-v3`).

## Objetivo final

Un sistema de **flujo de pasajeros** para buses con cámara cenital/fisheye:
conteo de subidas y bajadas por puerta, ocupación estimada en el tiempo, y
series agregadas por bus/ruta.

Arquitectura del pipeline (cada fase construye sobre la anterior):

```
Video → [1] Detección de cabezas → [2] Tracking (IDs) → [3] Eventos de flujo
        (cruce de línea de puerta, dirección) → [4] Agregación / series de ocupación
```

---

## Fase 0 — Higiene del repo (1 sesión)

- [ ] `gh auth login -h github.com` y abrir el PR pendiente de
      `feature/bus-head-detector` → `main`.
- [ ] Merge a `main`; la rama queda como base estable del pipeline de
      active learning.
- [ ] Resolver el `mlruns/mlflow.db` modificado (commit o gitignore).

**Criterio de salida:** `main` contiene todo el pipeline R1–R4 + golden.

---

## Fase 1 — Detector de cabezas robusto (Rondas 5+)

El golden dice que el problema es **sub-conteo** (recall), peor en cámara no
vista (video02: MAE 2.51 vs S08: 0.76). La palanca es diversidad de datos, no
limpieza (lección de R4) ni arquitectura (todavía).

### Ronda 5 — recall y generalización diurna
1. **Minar frames concurridos de cámaras nuevas/diversas** con
   `scripts/active_learning/extract_bright.py` / `mine_frames.py`.
   Restricción conocida: el footage diurno no usado se agotó (videoTM_02 ya es
   golden — NUNCA entrenar con esos frames). Opciones en orden:
   a. Conseguir footage nuevo (otras cámaras/buses/horas) — la de mayor impacto.
   b. Re-minar segmentos sub-muestreados de cámaras ya usadas (frames >200 de
      distancia de cualquier frame de train/golden).
2. Pre-anotar en CVAT con R3 (conf 0.25) → corregir buscando activamente
   cabezas perdidas (el modo de fallo dominante).
3. `build_v5` estilo `build_v3.py` → entrenar desde
   `models/yolov5mu-head-base.pt` (80ep, batch=8, workers=4, `--shm-size=8g`,
   host engine `docker -c default ... --runtime=nvidia`).
4. `python3 data/golden/eval_golden.py` → desplegar + release `bus-head-v5`
   **solo si count-MAE < 2.06**.

### Ronda 6+ — iterar hasta criterio de salida
- Repetir el loop; si los datos diurnos se agotan de verdad, probar
  `yolo11m` (modelo mayor) como experimento controlado contra el mismo golden.
- **Nocturno**: videoTM_18.mkv / videoTM_29 son de noche (luminancia mediana
  2–11). El flujo de pasajeros también ocurre de noche, así que tarde o
  temprano toca: ronda dedicada con realce de brillo (CLAHE/gamma) en
  pre-proceso, y extender el golden con un subconjunto nocturno SEPARADO
  (no mezclar con el golden diurno congelado).

**Criterios de salida de Fase 1:**
- Golden count-MAE ≤ **1.5** global y ≤ **2.0** en cámara no vista.
- Recall en golden ≥ 0.85 manteniendo el cero-duplicados (NMS 0.5).
- El golden diurno permanece congelado e intocado durante toda la fase.

---

## Fase 2 — Tracking (IDs persistentes)

Sin tracking no hay dirección de movimiento, y sin dirección no hay
entrada/salida. Empieza cuando Fase 1 alcance ~MAE 1.5 (no hace falta
perfección: el tracker tolera detecciones ruidosas).

1. **Integración**: `model.track()` de ultralytics con pesos del campeón +
   ByteTrack y BoT-SORT como candidatos. Nota de dominio: vista cenital
   fisheye + cabezas pequeñas → ReID por apariencia aporta poco; trackers por
   movimiento (ByteTrack/OC-SORT) son la apuesta inicial.
2. **Golden de tracking**: anotar 2–3 clips cortos (300–500 frames c/u, que
   incluyan cruces de puerta con aglomeración) en CVAT en modo *track*
   (IDs persistentes). Congelarlo igual que el golden de detección.
3. **Métricas**: HOTA / IDF1 / MOTA con TrackEval. La métrica que importa
   para flujo es **ID switches en la zona de puertas**.
4. **Tuning**: track buffer (oclusiones al agacharse/cruzarse), umbrales de
   asociación, mín. longitud de track.

**Criterio de salida:** IDF1 alto y <1 ID switch promedio por cruce de puerta
en el golden de tracking.

---

## Fase 3 — Eventos de flujo (subidas/bajadas)

1. **Geometría por cámara**: config YAML por cámara con línea/polígono de
   puerta(s) y sentido de "entrada". (Las cámaras son fijas por bus → se
   define una vez.)
2. **Lógica de eventos**: cruce de línea con dirección sobre la trayectoria
   del track + histéresis (un track solo puede generar un evento por cruce)
   para no duplicar conteos con tracks fragmentados.
3. **Golden de eventos**: anotar a mano subidas/bajadas (timestamps) en N
   segmentos con paradas reales. Métricas: error de conteo por
   parada/segmento, precision/recall de eventos.
4. Salida estructurada: eventos `{timestamp, camara, direccion}` + conteo
   in/out por ventana de tiempo + **ocupación acumulada estimada**.

**Criterio de salida:** error de conteo por parada ≤ ~10% en el golden de
eventos.

---

## Fase 4 — Agregación y modelo de flujo

- Pipeline batch sobre videos completos → series temporales de
  ocupación/flujo (CSV/Parquet) por bus/ruta/franja horaria.
- Validación contra fuente externa si existe (registros de validación de
  pasajes, conteos manuales).
- Aquí recién tiene sentido "modelo de flujo" como producto: predicción de
  demanda, detección de aglomeración, etc., alimentado por estas series.

## Fase 5 — Productización (cuando Fase 3 esté validada)

- Export ONNX/TensorRT del detector, medir FPS en el hardware objetivo.
- Inferencia en tiempo real vs batch nocturno (decisión de producto).
- Monitoreo de drift + el loop de active learning ya montado se convierte en
  el ciclo de mantenimiento/re-entrenamiento.

---

## Tooling del agente (skills y subagentes)

El loop de una ronda está automatizado como skills de Claude Code
(`.claude/skills/`) y subagentes (`.claude/agents/`):

```
[frame-miner] mina frames → tarea CVAT + auto-anotar + corregir (humano)
→ /cvat-export → build_vN → /train-round N → /eval-golden
→ ¿MAE mejora? → /deploy-head N    (si no: [error-analyst] → siguiente ronda)
```

- `/train-round <N>` — entrenamiento GPU con los gotchas de docker horneados.
- `/eval-golden` — benchmark golden + veredicto desplegar/no-desplegar.
- `/deploy-head <N>` — swap de pesos + redeploy Nuclio + release.
- `/cvat-export` — recuperar exports desde el cache de cvat_server.
- `error-analyst` (subagente) — diagnóstico FN/FP por cámara → receta de minado.
- `frame-miner` (subagente) — minado con verificación anti-fuga (golden/train).

## Transversal (todas las fases)

- **Un golden congelado por fase**: detección (existe), tracking (Fase 2),
  eventos (Fase 3). Nada que se evalúa se entrena.
- **Versionado**: cada campeón nuevo = GitHub Release + sha256 + entrada en
  `docs/golden_baseline.md`.
- **Regla de despliegue**: solo se despliega lo que mejora el golden de su
  fase. Empate o regresión = no se despliega (lección de R4).
- **Memoria**: al cierre de cada ronda/fase se actualizan las notas de
  memoria del agente (resume-point + historial) con resultados y lecciones.
