# Plan: de yolo26x a conteo de subidas/bajadas

> Fecha: 2026-08-30. Rama `feature/bus-head-detector`, commit base `f7526a4`.
> Sustituye la parte operativa de las Fases 2–3 de `roadmap_flujo_pasajeros.md`,
> que queda como documento de visión.

## Decisión tomada

**yolo26x-min5 pasa a ser el modelo principal** (golden count-MAE 1.64, sesgo
−1.36, mejor resultado histórico en la cámara no vista video02 = 1.85). La
evidencia estadística es limítrofe (p=0.043, IC95 cruza el cero, un solo seed) y
**se acepta así**: el argumento que sostiene la decisión no es el p-valor sino el
mejor resultado histórico en la cámara no vista, que es lo más parecido a
producción que hay disponible. Confirmarlo con 3 seeds no cambiaría nada de lo que
se va a hacer, así que queda postergado (ver Bloque A).

## Principio que ordena todo el plan

Un filtro de Kalman **no baja el MAE del golden**: el golden son 151 frames
independientes y Kalman es un estimador temporal. Lo que Kalman sí hace es
reducir el error del sistema sobre video, y ya viene dentro de ByteTrack /
BoT-SORT — no se escribe, se configura.

Por eso la métrica que manda cambia de fase: en Fase 1 era count-MAE por frame;
desde Fase 2 es **IDF1 e ID switches en la zona de puerta**, y en Fase 3 el
**error de conteo de eventos por parada**. Un ±1.6 por frame se promedia y
desaparece; un ID switch en la puerta mete un pasajero fantasma permanente.

## Modo de operación: batch, no tiempo real

**Decisión del usuario (2026-08-30).** El sistema procesa **videos subidos**, no
cámaras en vivo. El tiempo real queda como posibilidad futura según avance el
proyecto, explícitamente **fuera del alcance** de este plan.

No es una limitación: es una ventaja, y conviene aprovecharla en vez de tolerarla.

### Lo que se gana

**Se puede mirar el futuro.** Un tracker en vivo solo puede usar los frames que ya
pasaron: cuando un ID se rompe, se rompió y no hay vuelta atrás. En batch tenés el
video entero, así que podés hacer una **segunda pasada que cosa tracklets**: si el
track 7 muere en el frame 100 cerca de la puerta y el track 23 nace en el frame 112
a 30px de ahí, con movimiento compatible, casi seguro son la misma persona y se
pueden unir mirando *hacia adelante*.

Esto importa mucho porque ataca de frente el **riesgo número uno del proyecto** —
la fragmentación de IDs en la puerta, que es la que produce pasajeros fantasma. Un
sistema en tiempo real simplemente no puede hacerlo. Ser batch no es el plan B, es
una capacidad extra.

**Y desaparece el presupuesto de latencia**: no hay que sacrificar precisión por
velocidad, ni descartar yolo26x por sus 59M params (ver A2).

### La decisión de arquitectura que mantiene la puerta abierta

Como el tiempo real puede aparecer más adelante, conviene no cerrarse ahora — y
sale gratis si se estructura en dos pasadas separadas:

- **Pasada 1 — causal.** Frame entra, tracks salen. **Sin mirar el futuro.** Es la
  pasada que un sistema en vivo podría ejecutar tal cual, sin cambios.
- **Pasada 2 — offline.** Cosido de tracklets, suavizado de trayectorias, resolución
  de eventos ambiguos. Usa el video completo.

Con esa separación, agregar tiempo real más adelante es **apagar la pasada 2**, no
reescribir el sistema. Si en cambio se mezclan las dos —por ejemplo, dejando que la
lógica de eventos consulte frames futuros a mitad de la pasada 1— el día que haga
falta streaming hay que rehacer todo. Es una restricción barata de respetar hoy y
cara de recuperar después.

Corolario para B3: **medir las dos pasadas por separado.** Cuánto aporta el cosido
offline es un número que interesa por sí mismo, porque es exactamente lo que se
perdería al pasar a vivo.

### Separar cómputo de visualización

Ser batch permite lo obvio: procesar una vez, escribir artefactos a disco
(MOTChallenge `.txt`, eventos `.csv`, MP4 anotado), y que la interfaz solo
**reproduzca**. Nada de recalcular para volver a mirar.

Cachear por hash de `(video, modelo, configuración del tracker)` hace que revisar un
resultado sea instantáneo y que comparar dos configuraciones sea barato — que es
justamente lo que uno termina haciendo todo el día durante B4.

---

# Bloque A — Cerrar yolo26x

yolo26x **ya está en uso** y no se va a reemplazar. Este bloque no decide eso: son
las cosas que quedaron sueltas alrededor de esa decisión. Corre en paralelo al
Bloque B y ninguna de sus tareas lo bloquea.

## A1. Duplicados con NMS-free ← la única que importa para el tracking

Parcialmente resuelto ya. `serverless/yolo26x-head/main.py` documenta —y verificó
empíricamente— que yolo26 es **end-to-end / NMS-free**: el parámetro `iou` se
acepta por compatibilidad con el resto de las funciones del proyecto pero **no
tiene ningún efecto** (iou 0.3 / 0.5 / 0.7 / 0.9 devuelven exactamente las mismas
cajas). El modelo resuelve los duplicados en su propia cabeza de detección.

Lo que queda abierto no es la semántica del parámetro sino la consecuencia: el
"cero duplicados" del pipeline se conseguía **configurando** NMS a 0.5. Ahora es una
propiedad **aprendida** del modelo, no un ajuste. Hay que comprobarla, no asumirla.

- Contar duplicados en las predicciones de yolo26x sobre el golden: pares de cajas
  con IoU > 0.6 asignadas a la misma cabeza real.
- Comparar contra el mismo conteo para MIN5 con NMS 0.5.
- Revisar en particular los frames de mayor aglomeración, donde el doble conteo
  apareció históricamente.

**Por qué importa acá y no solo en detección:** una caja duplicada que entra al
tracker se convierte en un **track duplicado**, y un track duplicado que cruza la
línea de puerta es un **pasajero fantasma** en el conteo final. Es el único punto
del Bloque A con efecto real sobre el producto.

**Criterio:** duplicados ≤ los de MIN5. Si el modelo NMS-free duplica más, ya no hay
una perilla que ajustar: hay que filtrar en post-proceso, antes de que las cajas
lleguen al tracker.

Costo: ~1h, sin GPU de entrenamiento.

## A2. Throughput (30 min)

El sistema es **batch por decisión de producto** (ver "Modo de operación"), así que
el FPS no define la arquitectura: define el costo. No hay criterio de aprobado o
rechazado, hay un número que producir.

- Medir FPS de inferencia a imgsz 640 sobre un clip real, en la GPU del host.
- Traducirlo a lo operativo: cuántos minutos de cómputo cuesta un video de 15 min,
  y por lo tanto una jornada completa.

Con ese número se decide **más adelante** si vale la pena FP16 o TensorRT. Hoy no.

Efecto secundario ya incorporado: al no haber presupuesto de latencia, desaparece la
principal objeción a los 59M params de yolo26x.

## A3. Despliegue y release

Cuando quieras que CVAT pre-anote con yolo26x. Solo requiere que A1 pase.

- `/deploy-head` con los pesos de yolo26x (swap de `best.pt` + redeploy con
  `nuctl`), release `bus-head-yolo26x`.
- Actualizar `CHAMPION` en `scripts/demo/annotate_video.py`, que hoy apunta a
  `yolo-bus-head-min5/weights/best.pt`.

## Lo que se sacó de este bloque, y por qué

**Los 3 seeds (~4h GPU) ya no están acá.** Estaban para decidir entre yolo26x y
`v5mu-coco-min5`, y esa decisión ya está tomada — con un argumento que no depende del
p-valor: yolo26x da el mejor resultado histórico en la cámara no vista
(`video02` = 1.85), que es la evidencia más parecida a lo que pasará en producción.

Reentrenar con otra seed **no produce un modelo mejor**; produce información sobre
cuánto varía el proceso de entrenamiento. Y esa información solo servía para elegir
entre dos modelos. Además, el argumento de costo que la sostenía —"si empatan,
quedate con el de 25.1M"— se cayó cuando el sistema pasó a ser batch: sin
presupuesto de latencia, que sea 2,4× más grande no cuesta nada.

Ninguno de los dos resultados posibles del experimento cambiaría lo que se va a
hacer. Eso lo descalifica.

La honestidad se mantiene por escrito, no por GPU: `docs/golden_baseline.md` ya dice
que la comparación es de un solo seed y que la significancia es limítrofe
(`p=0.043`, IC95 que cruza el cero, con comparaciones múltiples de por medio). Eso
queda como está.

**Cuándo sí conviene pagarlas: al entrenar v6.** Ahí vuelve a haber una decisión real
("¿esta mejora es de verdad?"), y las seeds sirven para algo distinto y más
duradero — medir el **piso de ruido del golden**. Si dos corridas idénticas difieren
±0.10 en MAE, entonces una mejora de 0.05 no significa nada y una de 0.30 sí. Ese
número se mide **una vez** y calibra todas las comparaciones futuras.

Dicho de otro modo: las seeds no son un peaje para usar yolo26x, son una calibración
del banco de pruebas. Se pagan cuando haya una decisión que dependa de ellas.

Anotado también en la conclusión "más capacidad ayuda" (21.9M → 1.91, 25.1M → 1.76,
59.0M → 1.64): se apoya en corridas de un solo seed, pero **no hay ninguna decisión
colgando de ella** —no queda un modelo más grande por probar en esa familia—, así
que tampoco justifica el gasto.

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

## B1b. Interfaz de inspección — "Track Studio" (2–3 días)

Una UI local para elegir un video, correr el tracking y **ver** el resultado sin
tocar la terminal. Es la herramienta del paso "ver", no un entregable de producto.

**FastAPI + frontend vanilla**, servido desde el contenedor `dev`. Sin build, sin
framework, sin npm.

### La decisión de diseño que ordena todo: no quemar las cajas en el video

La forma ingenua es procesar el video, dibujarle las cajas encima y devolver un MP4
nuevo. Eso obliga a re-codificar el archivo entero cada vez que se mueve una perilla,
y entrega algo que solo se puede reproducir.

En su lugar: se sirve el **video original** (normalizado a H.264 una sola vez) y,
por separado, un **JSON con los tracks**. El navegador superpone un `<canvas>`
transparente sobre el `<video>` y dibuja sincronizado con `video.currentTime`.

Lo que habilita:

- **Transcodificar una vez por video, no una vez por configuración.** El problema
  del códec se reduce a un paso de normalización al ingresar el video.
- **Los toggles son instantáneos.** Cajas, IDs, estelas, línea de puerta, filtrar a
  un solo track: todo es dibujo en el cliente, cero reprocesamiento.
- **Se puede ir y volver en el tiempo.** Ver algo raro en el segundo 12, retroceder,
  avanzar cuadro a cuadro. Esta es *la* tarea de inspección, y con un MP4 con las
  cajas quemadas es imposible.
- **Se puede hacer clic en un ID** y seguirlo, resaltarlo, ver dónde nace y muere.

Este es el motivo por el que no alcanza con Gradio o similar: dan un reproductor, y
un reproductor solo reproduce.

### Arquitectura

El procesamiento es batch y largo, así que no vive dentro de un request. La forma es
**disparar y consultar**:

```
GET  /api/videos                  videos disponibles + flag "fuente usada en train"
POST /api/runs                    {video, modelo, params} -> run_id, arranca en background
GET  /api/runs/{id}               estado y progreso (%)
GET  /api/runs/{id}/tracks.json   tracks por frame, para el canvas
GET  /media/{video}.mp4           video normalizado H.264
POST /api/cameras/{cam}/door      guarda la línea de puerta (ver C1)
```

Un **run es una carpeta**: `outputs/runs/<hash>/` con `tracks.json`, el `.txt` en
formato MOTChallenge para TrackEval, `config.yaml` y `status.json`. El hash sale de
`(video, modelo, parámetros del tracker)`, así que **pedir dos veces la misma
configuración devuelve el resultado guardado al instante**. Eso es lo que vuelve
tolerable el Bloque B4, donde se comparan configuraciones todo el día.

Pantallas (tres, sin más):

1. **Videos** — lista, con el cartel de "usado en entrenamiento".
2. **Configurar y lanzar** — los controles, y barra de progreso.
3. **Visor** — `<video>` + `<canvas>` + línea de tiempo de tracks.

### Dónde NO gastar

FastAPI invita a construir de más. El corte:

- **Sin base de datos.** Los runs son carpetas y el estado es un `status.json`.
  SQLite recién si algún día hay muchos.
- **Sin cola de trabajos.** `BackgroundTasks` y un lock para no pisar la GPU con dos
  corridas simultáneas. Es un solo usuario.
- **Sin autenticación, sin usuarios, sin servicio aparte.** Corre en el contenedor
  `dev`, con el puerto publicado en `compose.yaml`.
- **Sin build de frontend.** HTML, CSS y JS estáticos.

### La línea de tiempo (la parte que decide si sirve)

Debajo del video, **una franja horizontal por track**, dibujada desde que nace hasta
que muere.

Esto convierte la fragmentación en algo *visible sin contar nada*: si un clip con 12
personas reales muestra 40 franjas cortas en vez de 12 largas, el problema salta a la
vista. Hacer clic en una franja que se corta lleva el video a ese instante con el
track resaltado, y ahí se ve **por qué** se rompió — se agachó, lo taparon, se cruzó
con otro.

Es el mismo indicador que antes iba a ser un número suelto ("IDs únicos totales"),
pero ubicado en el tiempo, que es donde se puede actuar sobre él.

### Comparar dos runs (lo que justifica la infraestructura)

Con los runs guardados en disco, comparar es cambiar qué JSON dibuja el canvas sobre
el mismo video, en el mismo instante. Subís `track_buffer`, relanzás, y alternás
A/B en el segundo exacto donde el ID se rompía.

Este es el flujo real del Bloque B4, y es la razón de todo lo anterior.

### Controles a exponer

La UI vale la pena en la medida en que exponga las perillas del tracker.

- Modelo: yolo26x / MIN5.
- `conf` de detección — clave, porque el rango interesante es 0.10–0.25.
- Tracker: ByteTrack / BoT-SORT.
- `track_buffer`, `match_thresh`, `track_high_thresh`, `new_track_thresh`.
- Longitud mínima de track.
- Segmento: segundo de inicio y duración.
- Pasada 2 (cosido de tracklets) encendida/apagada — ver "Modo de operación".
- Toggles de dibujo (cliente): cajas, IDs, estelas, línea de puerta, track aislado.

El toggle de la pasada 2 merece estar desde el principio: poder ver el antes y el
después del cosido, sobre el mismo run, es la forma directa de entender cuánto está
aportando y cuánto está tapando.

### No es la herramienta de medición

Conviene decirlo fuerte, porque la línea de tiempo la hace parecer más rigurosa de lo
que es. Mirar un video y que "se vea bien" es la forma clásica de auto-engañarse: un
tracker con ID switches frecuentes en la puerta se ve perfectamente bien en
movimiento, porque el ojo no lleva la cuenta de los IDs.

Las decisiones se toman con TrackEval sobre el golden congelado (B3). La UI sirve
para **encontrar qué está mal y formular la hipótesis**; el golden dice si la
hipótesis era cierta.

### Gotchas concretos

1. **El códec.** `scripts/demo/annotate_video.py` escribe con `mp4v`
   (`VideoWriter_fourcc(*"mp4v")`, línea 83). Eso es MPEG-4 Part 2 y **los navegadores
   no lo reproducen** — el reproductor queda en negro y parece un bug del tracking
   cuando es del contenedor de video. Normalizar a **H.264** con `ffmpeg` (ya está en
   la imagen, `docker/Dockerfile` línea 10) al ingresar el video.
   `opencv-python-headless` no trae codificador H.264 propio.
2. **Sincronía canvas/video.** `video.currentTime` es segundos, los tracks están
   indexados por frame. Convertir con el FPS real del archivo normalizado (que puede
   no ser el del original si ffmpeg lo cambia) y no con un 30 hardcodeado, o el
   overlay se va corriendo a lo largo del clip.
3. **El puerto.** `compose.yaml` solo publica `${JUPYTER_PORT}`. Agregar el puerto de
   la API a `ports:` y a `.env`.
4. **Las dependencias.** `fastapi` y `uvicorn` a `docker/requirements.txt`, con
   versión fija como el resto del archivo, y reconstruir la imagen.
5. **El tiempo de proceso.** yolo26x son 59M params; un video de 15 min no es
   interactivo. Tope por defecto de 20–30 s de clip, progreso real, y dejar claro en
   la UI que procesa un segmento.
6. **Videos grandes.** Subir un `.mkv` de varios GB por navegador es incómodo. El
   camino principal es el desplegable de videos ya montados en el contenedor
   (depende de B0); la subida es el caso secundario.

### Qué videos usar (y por qué importa)

El uso previsto son **videos que el modelo nunca vio**. Eso convierte a la UI, sin
proponérselo, en una prueba de generalización continua — pero solo si se respeta la
disciplina de fuentes, porque un video ya usado en entrenamiento se ve espectacular
y no significa nada.

Inventario de `~/Downloads` cruzado contra las fuentes de `bus_head_v5_min5`
(`s03`, `videoTM_14`, `v04`, `v04_1`, `v04_2`, `v05`, `v05_1`, `v10b`, `v11`, `v12`,
`v16`, `v16b`, `v18S08`):

| Video | Estado | Nota |
|-------|--------|------|
| `videoTM_03`, `videoTM_03(1)` | **nunca visto** | candidato directo |
| `videoTM_08` | **nunca visto** | candidato directo |
| `videoTM_17` | **nunca visto** | candidato directo |
| `videoTM_intelC1`, `videoTM_intelC36` | **nunca visto** | otra cámara/hardware — el más interesante |
| `videoTM_18`, `videoTM_29` | nunca visto, **nocturno** | luminancia mediana 2–11; esperar que falle |
| `videoTM_02` | held-out | es el **golden de detección** — mirarlo está bien, pero no es "nuevo" |
| el resto | usados en train | se ven bien por memorización, no por generalización |

Todos son **640×480 @30fps, 15 min** (verificado con ffprobe, incluidos los `intelC*`).
No hay sorpresa de resolución escondida ahí: el techo físico de 640×480 sigue vigente.

Los `intelC*` merecen atención especial por el nombre: parecen otra cámara u otro
hardware de captura. Si el encuadre difiere de las `videoTM_*`, es la mejor prueba de
generalización disponible hoy sin conseguir metraje nuevo.

**Regla:** que la UI muestre de qué fuente viene el video y si esa fuente está en el
set de entrenamiento. Un cartel de "esta cámara se usó para entrenar" evita la
conclusión alegre, que es el error fácil cuando se está mirando un video bonito.

### Por qué se paga tres veces

1. **C1 (línea de puerta).** Dibujar la línea sobre un frame es un `<canvas>` y dos
   clics — el mismo canvas del visor. Hacerlo a mano con coordenadas en un YAML es
   una fuente de errores silenciosos. Con esta arquitectura sale casi gratis; con un
   componente de UI cerrado es una pelea.
2. **B4 (tuning).** La comparación A/B sobre runs cacheados es el flujo de trabajo de
   todo ese bloque.
3. **Tiempo real, si algún día llega.** La pasada causal empujando tracks por
   WebSocket en vez de por JSON estático, con el mismo canvas del lado del cliente.
   El frontend no cambia.

### Estructura

- `scripts/tracking/api.py` — FastAPI.
- `scripts/tracking/static/` — HTML/CSS/JS.
- El procesamiento **reutiliza** `track_video.py` de B1, no lo reimplementa: lo que
  se ve en pantalla tiene que ser exactamente lo que corre en batch. La API orquesta;
  no contiene lógica de tracking.

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
4. **Duplicados de la cabeza NMS-free** (A1). Una caja duplicada se vuelve un track
   duplicado, y un track duplicado que cruza la puerta es un pasajero fantasma. Es
   el riesgo del Bloque A que llega hasta el conteo final, y ya existió antes como
   bug de detección.
5. **El costo de cómputo por jornada resulta incómodo** (A2). Riesgo menor: al ser
   batch no rompe nada, solo obliga a FP16/TensorRT antes de lo previsto.
6. **La pasada offline puede volverse una muleta.** El cosido de tracklets (pasada 2)
   arregla fragmentaciones, y por eso mismo puede tapar un tracker mal ajustado. Si
   B4 se optimiza mirando solo el resultado final, se termina con una pasada 1 mala
   compensada por una pasada 2 agresiva — y el día que se quiera tiempo real, el
   sistema se cae entero. Por eso B3 mide las dos por separado.
7. **Nocturno sigue sin cubrir.** `videoTM_18` y `videoTM_29` son de noche
   (luminancia mediana 2–11). El flujo de pasajeros también ocurre de noche.
   Queda fuera de este plan de forma consciente, pero es deuda conocida.

# Dependencias

```
A1 (duplicados) ──> A3 (despliegue)   [paralelo, no bloquea B]
A2 (throughput) ─────┘

3 seeds: postergado a v6 (ver "Lo que se sacó de este bloque")

B0 ──> B1 ──> B2 ──> B3 ──> B4 ──> B5 ──> C1 ──> C2 ──> C3 ──> C4
        │     ↑                                  ↑
        │  cuello de botella:                    │
        │  anotación humana                      │
        └──> B1b (Track Studio, FastAPI) ────────┘
             visor + comparación A/B de runs;
             el mismo canvas dibuja la línea de puerta
```

# Higiene (Fase 0 del roadmap)

- ~~Abrir el PR de `feature/bus-head-detector` → `main`.~~ **HECHO** (2026-08-30,
  PR #3, merge `87576df`). `main` ya contiene todo el pipeline R1–R5 + MIN5 +
  golden v2 + las ablaciones de arquitectura.
- Resolver `mlruns/mlflow.db` (commitear o ignorar).
