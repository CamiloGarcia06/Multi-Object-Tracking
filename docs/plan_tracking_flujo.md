# Plan: de yolo26x a conteo de subidas/bajadas

> Fecha: 2026-08-30. Rama `feature/bus-head-detector`, commit base `f7526a4`.
> Sustituye la parte operativa de las Fases 2–3 de `roadmap_flujo_pasajeros.md`,
> que queda como documento de visión.

## Decisión tomada

**yolo26x-min5 pasa a ser el modelo principal** (golden count-MAE 1.64, sesgo
−1.36, mejor resultado histórico en la cámara no vista video02 = 1.85). La
evidencia estadística es limítrofe (p=0.043, IC95 cruza el cero, un solo seed),
pero el Bloque A cierra esa duda **en paralelo** en vez de bloquear el trabajo
de tracking, que es la ruta crítica del producto.

## Principio que ordena todo el plan

Un filtro de Kalman **no baja el MAE del golden**: el golden son 151 frames
independientes y Kalman es un estimador temporal. Lo que Kalman sí hace es
reducir el error del sistema sobre video, y ya viene dentro de ByteTrack /
BoT-SORT — no se escribe, se configura.

Por eso la métrica que manda cambia de fase: en Fase 1 era count-MAE por frame;
desde Fase 2 es **IDF1 e ID switches en la zona de puerta**, y en Fase 3 el
**error de conteo de eventos por parada**. Un ±1.6 por frame se promedia y
desaparece; un ID switch en la puerta mete un pasajero fantasma permanente.

---

# Bloque A — Cerrar yolo26x

Corre en paralelo al Bloque B. Solo A3 es bloqueante para desplegar.

## A1. Tres seeds (~4h GPU, desatendido)

El baseline compara corridas de un solo seed. Con `yolo26x vs MIN5` en
p=0.043 e IC95 [−0.404, +0.026], no se puede separar la mejora de la varianza
entre corridas.

- Repetir `yolo26x-min5` con seeds distintos (receta idéntica: `bus_head_v5_min5`,
  80 ep, imgsz 640, batch 8, desde `yolo26x.pt` COCO).
- Evaluar los 3 contra el golden con el matcher greedy propio a **conf fijo 0.25**
  (no usar el P/R de `yolo val`: reporta en el máximo F1 de cada modelo, umbrales
  distintos, no comparables entre modelos).
- Reportar media ± desviación de MAE, no el mejor.

**Criterio:** si la media de los 3 seeds queda ≤ 1.75, yolo26x se confirma. Si
queda ≥ 1.80, es indistinguible de `v5mu-coco-min5` (1.76) y conviene quedarse
con el modelo de 25.1M por costo de inferencia.

Salida: fila nueva en `docs/golden_baseline.md`.

## A2. Throughput (30 min)

59.0M params vs 25.1M del campeón anterior. Para tracking sobre videos completos
el FPS deja de ser un detalle y pasa a ser restricción de diseño.

- Medir FPS de inferencia pura a imgsz 640 sobre un clip real, en la GPU del host.
- Medir también con `half=True` (FP16) y, si el margen es estrecho, exportar a
  TensorRT y volver a medir.
- Estimar el costo de procesar un video completo de una jornada.

**Criterio:** si yolo26x no alcanza tiempo real (~25–30 FPS) en el hardware de
destino, el tracking pasa a ser proceso batch offline, no en vivo. Eso es una
decisión de arquitectura del producto, no un detalle de implementación —
conviene saberlo antes de construir la Fase 3.

## A3. Duplicados con NMS-free (bloqueante para desplegar)

Parcialmente resuelto ya. `serverless/yolo26x-head/main.py` documenta —y verificó
empíricamente— que yolo26 es **end-to-end / NMS-free**: el parámetro `iou` se
acepta por compatibilidad con el resto de las funciones del proyecto pero **no
tiene ningún efecto** (iou 0.3 / 0.5 / 0.7 / 0.9 devuelven exactamente las mismas
cajas). El modelo resuelve los duplicados en su propia cabeza de detección.

Lo que queda abierto no es la semántica del parámetro sino la consecuencia: el
"cero duplicados" del pipeline actual se conseguía **configurando** NMS a 0.5.
Ahora es una propiedad aprendida del modelo, no un ajuste. Hay que comprobarla,
no asumirla.

- Contar duplicados en las predicciones de yolo26x sobre el golden: pares de
  cajas con IoU > 0.6 asignadas a la misma cabeza real.
- Comparar contra el mismo conteo para MIN5 con NMS 0.5.
- Revisar en particular los frames de mayor aglomeración, donde el doble conteo
  apareció históricamente.

**Criterio:** duplicados ≤ los de MIN5. Si el modelo NMS-free duplica más, ya no
hay una perilla que ajustar —hay que filtrar en post-proceso— y eso cambia el
balance frente a `v5mu-coco-min5`.

## A4. Despliegue y release

Solo si A1 confirma y A3 pasa.

- `/deploy-head` con los pesos de yolo26x (swap de `best.pt` + redeploy con
  `nuctl`), release `bus-head-yolo26x`.
- Actualizar `CHAMPION` en `scripts/demo/annotate_video.py`, que hoy apunta a
  `yolo-bus-head-min5/weights/best.pt`.

---

# Bloque B — Fase 2: tracking con IDs persistentes

Ruta crítica. Sin IDs no hay dirección de movimiento, y sin dirección no hay
entrada/salida.

## B0. Infraestructura (1–2h)

- **Montar los videos en el contenedor.** `mine_frames.py` asume `VID = "/videos"`,
  pero `compose.yaml` solo monta `./:/workspace`. Los `.mkv` viven en
  `~/Downloads/`. Agregar el montaje al compose para no seguir dependiendo de
  `docker run` ad-hoc.
- **Verificar TrackEval de verdad.** `src/trackeval_smoke.py` solo hace `import
  trackeval` y no valida nada. Antes de depender de él, correr una evaluación
  real sobre un ejemplo mínimo con GT conocido.
- Crear `scripts/tracking/` y `data/tracking_golden/`.

## B1. Prototipo de tracking (medio día)

`scripts/tracking/track_video.py`, modelado sobre `scripts/demo/annotate_video.py`
(que ya resuelve lectura de video, overlay y escritura de MP4).

- `model.track()` de ultralytics con `persist=True`, pesos de yolo26x.
- ByteTrack y BoT-SORT como candidatos. **Nota de dominio:** vista cenital fisheye
  con cabezas pequeñas y visualmente casi idénticas ⇒ el ReID por apariencia
  aporta poco o es contraproducente. ByteTrack (solo movimiento) es la apuesta
  inicial; BoT-SORT sin ReID como control.
- Overlay: caja + ID + traza de los últimos N centroides, para poder ver
  fragmentaciones y switches a ojo antes de tener métricas.
- Salida paralela en formato MOTChallenge (`frame,id,x,y,w,h,conf,-1,-1,-1`),
  que es lo que consume TrackEval.

Entregable: video anotado con IDs sobre un clip de puerta. Sirve para calibrar
expectativas y detectar problemas groseros antes de invertir en anotación.

## B2. Golden de tracking (el cuello de botella real)

Esto es trabajo de anotación humana y es lo que gobierna el calendario. Sin
esto, todo tuning del tracker es a ciegas.

- **Selección: 3 clips de 300–500 frames.** Criterios: (a) contener al menos un
  cruce de puerta completo, (b) incluir un momento de aglomeración con oclusión
  mutua, (c) **una cámara nunca vista** para medir generalización.
- **Restricción de fuga (crítica).** `videoTM_02` es el golden de detección y
  está en `DO_NOT_TRAIN.txt`. Se puede usar para el golden de *tracking* sin
  problema — no se entrena nada con él — pero hay que dejar la decisión
  documentada de forma explícita, porque la regla escrita hoy dice "jamás".
- **Anotación en CVAT en modo track** (IDs persistentes, no cajas por frame).
  Reutilizar `scripts/dataset/package_for_cvat.py`.
- Pre-anotar con el prototipo de B1 para reducir trabajo manual, y **corregir
  buscando activamente IDs rotos** — el modo de fallo que importa, igual que en
  Fase 1 se corregía buscando cabezas perdidas.
- **Congelar** igual que el golden de detección: `data/tracking_golden/DO_NOT_TRAIN.txt`
  y `manifest.csv`.

## B3. Evaluación (`scripts/tracking/eval_tracking.py`)

Modelado sobre `data/golden/eval_golden.py`.

- HOTA, IDF1, MOTA vía TrackEval.
- **Métrica propia y decisiva: ID switches dentro de la región de puerta.** Las
  métricas MOT estándar promedian sobre toda la escena; a nosotros nos importa
  desproporcionadamente lo que pasa en la puerta. Un tracker con mejor HOTA
  global pero más switches en la puerta es peor para este producto.
- Además: fragmentación de tracks (cuántos IDs por persona real) y duración
  media de track.

Salida: `docs/tracking_baseline.md`, con el mismo formato de tabla que
`golden_baseline.md`.

## B4. Tuning del tracker

Aquí es donde el Kalman de ByteTrack ataca tu sesgo de sub-conteo. El modo de
fallo dominante son cabezas visibles en *t−1* y *t+1* pero perdidas en *t*;
el filtro mantiene el track vivo y lo re-asocia al reaparecer.

La palanca más específica es la **doble asociación de ByteTrack**: asocia primero
con detecciones de alta confianza y después con las de **baja** confianza que
normalmente se descartarían.

- Correr el detector a `conf=0.10` (en vez de 0.25) dejando `track_high_thresh`
  en ~0.25. Las cabezas en la franja 0.10–0.25 —los falsos negativos de hoy—
  pasan a poder **sostener** un track existente sin poder **crear** tracks nuevos.
  Es el mecanismo diseñado exactamente para este problema.
- `track_buffer`: cuántos frames sobrevive un track perdido. Con oclusión al
  agacharse o cruzarse en vista cenital, probablemente haya que subirlo.
- `match_thresh`: IoU de asociación. Cabezas pequeñas ⇒ el IoU cae muy rápido
  con poco desplazamiento; casi seguro hay que aflojarlo.
- `new_track_thresh` y longitud mínima de track: controlan tracks espurios.

Barrido sobre el golden de tracking, no sobre intuición. Documentar la
configuración ganadora en un YAML versionado, no como flags sueltos.

**Riesgo a vigilar en cada iteración:** Kalman coasteando de más produce **tracks
fantasma**. Se convierte sub-conteo en sobre-conteo y el sesgo cambia de signo
sin que el MAE global lo delate. Reportar siempre el sesgo, no solo el error
absoluto.

## B5. Congelar

Tracker + configuración fijos, documentados, con su fila en el baseline.

**Criterio de salida de Fase 2:** IDF1 alto y **< 1 ID switch promedio por cruce
de puerta** en el golden de tracking.

---

# Bloque C — Fase 3: eventos de subida y bajada

Empieza cuando B5 esté cerrado. Es donde el sistema produce por fin el número
que interesa.

## C1. Geometría por cámara

`configs/cameras/<camara>.yaml`. Las cámaras son fijas por bus, así que se
define una vez.

- Línea o polígono de puerta, y **sentido de "entrada"** (vector normal).
- Zona de exclusión si hay áreas donde el conteo no aplica.
- Herramienta chica para dibujar la línea sobre un frame y volcarla al YAML;
  hacerlo a mano con coordenadas es una fuente de errores silenciosos.

## C2. Lógica de eventos (`scripts/flow/events.py`)

- Cruce de línea con dirección, sobre la trayectoria del centroide del track.
- **Histéresis:** un track solo puede generar un evento por cruce. Sin esto, un
  track que oscila sobre la línea (o que se fragmenta y se re-crea) duplica
  conteos. Esta es la principal fuente de error de la fase.
- Manejo explícito de tracks fragmentados: si un ID muere antes de la línea y
  otro nace después, hoy son dos personas. Decidir si se intenta re-unir por
  proximidad espacio-temporal o si se acepta el error y se mide.
- Salida: eventos `{timestamp, camara, track_id, direccion}`.

## C3. Golden de eventos

- Anotar a mano subidas y bajadas (timestamps) en N segmentos con paradas reales.
- Es más barato de anotar que el golden de tracking: son eventos, no cajas.
- Métricas: error de conteo por parada, y precision/recall de eventos.

## C4. Salida estructurada

- Conteo in/out por ventana de tiempo.
- **Ocupación acumulada estimada.** Atención: la ocupación es una suma
  acumulativa, así que los errores **no se promedian, se acumulan**. Un sesgo
  sistemático de +0.5 pasajeros por parada es catastrófico a lo largo de una
  jornada, aunque el error por parada parezca aceptable. Considerar anclajes
  periódicos (por ejemplo, ocupación cero en el fin de recorrido).
- Export CSV/Parquet por bus/ruta/franja horaria.

**Criterio de salida de Fase 3:** error de conteo por parada ≤ ~10% en el golden
de eventos.

---

# Riesgos, ordenados por probabilidad de mordernos

1. **El golden de tracking es el cuello de botella.** Anotar 900–1500 frames en
   modo track con IDs persistentes es trabajo humano lento y no paralelizable.
   Todo el calendario cuelga de esto. Empezar B2 temprano, incluso mientras B1
   sigue en curso.
2. **Tracks fantasma por coasting excesivo** (B4). Se detecta solo si se reporta
   el sesgo, no solo el MAE.
3. **Fragmentación en la puerta** — el peor caso para el producto, porque es
   exactamente donde importa: aglomeración, oclusión mutua y cambio de dirección
   ocurren todos en el mismo lugar.
4. **yolo26x demasiado lento** (A2) ⇒ el producto es batch, no tiempo real.
5. **NMS end-to-end reintroduce duplicados** (A3) ⇒ doble conteo, un bug que ya
   existió antes.
6. **Nocturno sigue sin cubrir.** `videoTM_18` y `videoTM_29` son de noche
   (luminancia mediana 2–11). El flujo de pasajeros también ocurre de noche.
   Queda fuera de este plan de forma consciente, pero es deuda conocida.

# Dependencias

```
A1 ─┐
A2 ─┼─> A4 (despliegue)          [paralelo, no bloquea B]
A3 ─┘

B0 ──> B1 ──> B2 ──> B3 ──> B4 ──> B5 ──> C1 ──> C2 ──> C3 ──> C4
              ↑
        cuello de botella:
        anotación humana
```

# Higiene pendiente (Fase 0 del roadmap)

- Abrir el PR de `feature/bus-head-detector` → `main`. Son 7 commits acumulados.
- Resolver `mlruns/mlflow.db` (commitear o ignorar).
