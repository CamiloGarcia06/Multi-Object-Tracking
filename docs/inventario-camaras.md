# Inventario de videos por congestión (tarea 4, 12-10)

Los 24 videos del `sda2`, ya en `~/videos/` de la torre (640×480, 30 fps, 15 min).
`scripts/flow/inventario_camaras.py` toma 1 frame por segundo y mide:
- luminancia mediana;
- cabezas por frame con yolo26x-min5 (conf 0,25, NMS 0,6, frame entero, sin ROI).

**"Lleno"** = % de segundos con 8 o más cabezas. Las miniaturas (minuto 7,5 y el
segundo con más cabezas) están en `data/flow_eval/inventario/hoja_inventario.jpg`.

| Video | Estado | p50 | p90 | máx | lleno | Nivel |
|---|---|---|---|---|---|---|
| 04 | entrenado | 14 | 16 | 18 | 100 % | alta |
| 10 | entrenado (s03) | 10 | 15 | 17 | 82 % | alta |
| 16 | entrenado | 9 | 12 | 15 | 74 % | alta |
| 14 | entrenado | 8 | 9 | 12 | 54 % | alta |
| 05 | entrenado | 7 | 11 | 15 | 49 % | alta |
| **02** | **reservado: golden de detección** | 6 | 10 | 14 | 35 % | **alta** |
| 18(1) | entrenado (v18S08, inferido) | 6 | 9 | 12 | 29 % | media |
| 16(1) | entrenado | 7 | 8 | 11 | 26 % | media |
| 12 | entrenado | 7 | 8 | 11 | 23 % | media |
| **03(1)** | **nunca visto** | 0 | 8 | 14 | 13 % | **media** (picos) |
| 04(2) | entrenado | 3 | 8 | 9 | 11 % | media |
| **03** | **nunca visto** | 3 | 7 | 10 | 7 % | **baja** |
| 07 | reservado: evaluación de eventos | 5 | 7 | 10 | 6 % | baja |
| 05(1), 04(1), 11, 10(1) | entrenado | 3–5 | 5–7 | 8–10 | 0–5 % | baja |
| **08** | **nunca visto** | 1 | 2 | 4 | 0 % | **muy baja** |
| 13, 17, 18, 29 | nunca visto, **nocturno** | 1–2 | 3–5 | 6–8 | 0 % | fuera de alcance |
| intelC1, intelC36 | nunca visto, **otra escena** | 0–1 | 0–3 | 1–6 | 0 % | fuera de alcance |

## Lo que cambia respecto a lo que creíamos

- **videoTM_17 es nocturno** (luminancia 0), no un candidato diurno como decía
  `plan_tracking_flujo.md`. Los nocturnos son 13, 17, 18 y 29.
- **intelC1 e intelC36 no son el interior de un bus**: son una cámara cenital sobre
  el andén de una estación (suelo con flechas amarillas). Es otra escena: no sirve
  para la regla de la puerta del bus.
- **La luminancia baja de 04, 10 y 12 no es noche**: el frame está lleno de ropa
  oscura. Se ven diurnos en las miniaturas.
- **videoTM_07 es de congestión baja.** La Tabla I actual sale de un caso fácil.

## El problema: solo hay 4 videos diurnos de bus que el detector no ha visto

02 (alta), 03(1) (media), 03 (baja) y 08 (muy baja). Todo lo de congestión alta
restante ya se usó para entrenar: medir ahí favorece al detector, que memorizó esas
caras. Así que hay un solo video nunca visto por nivel de congestión.

**Reparto DECIDIDO por Camilo el 12-10** (tareas 5 y 6):

| Uso | Videos | Por qué |
|---|---|---|
| **Prueba final** (no se toca hasta la Fase 5) | **02** (alta) + **03(1)** (media) | Los dos niveles que importan, nunca vistos. El 02 ya está fuera de entrenamiento por `DO_NOT_TRAIN.txt`; usarlo para eventos no entrena nada, pero hay que dejarlo escrito |
| **Validación** (golden de eventos de la tarea 6: valida los ajustes sin fuga) | **03** (baja) | Nunca visto; misma cámara de bus; la otra mitad del par 03 |
| **Desarrollo** (lo que ya usamos) | **07** (baja) | Se sigue usando para el diagnóstico |
| **Reentrenamiento** (tarea 9) | 04, 10, 16, 14, 05 (alta) + medios | Ya son de entrenamiento: sacar más frames de puerta de ahí no contamina la prueba |
| Descartados | 08 (casi vacío), nocturnos, intel* | Limitaciones declaradas |

**Riesgo:** la validación (03) es de congestión baja, como el 07. Un ajuste que solo
funcione en alta no se vería hasta la prueba. Alternativa: validar en unas
aperturas del 03(1) y probar con otras. Es más débil (mismo video), pero cubre la
congestión media.

## Golden de validación: videoTM_03 (12-10)

**El 03 es el mismo bus y el mismo montaje que el 07.** Con la puerta abierta (frame
17.401) coinciden el piso amarillo, el letrero CERRADAS y el andén. Por eso
`configs/cameras/videoTM_03.yaml` copia la geometría del 07 sin reajustarla y solo
cambian los `closed_frames`. Es un video nunca visto, pero de la misma cámara: la
validación no cubre el cambio de cámara. Eso lo mide la prueba con el 03(1), que es
otro bus y tiene la puerta a la izquierda.

**Aperturas revisadas a ojo: 7.** Son 6.673–7.000, 9.361–9.487, 11.020–11.098,
11.485–11.557, 12.568–12.817, 13.684–13.762 y 17.311–17.647. `door.py`, con la
config del 07, detecta 4 y pierde 3: las dos de 11.0xx–11.5xx y la de 13.684. Las
tres duran menos de 3 s (`min_frames`). Sus caídas de 2.790 a 5.900 son falsas
(gente apoyada en la puerta cerrada, un bus rojo fuera, un túnel), igual que la del
18.170 (un bus verde fuera).

El golden se anota sobre estas 7 aperturas, no sobre las de `door.py`, para que no
dependa del detector que se evalúa. Tarea de CVAT generada con
`scripts/flow/golden_eventos.py`: 7 jobs con ±60 frames de margen, 2.113 imágenes,
en `data/cvat_import/eventos_videoTM_03/` de la torre.

### Golden y línea base de validación (12-10 noche)

Camilo anotó el golden en CVAT (tarea 7, jobs 22–28): `data/flow_golden/videoTM_03.csv`
tiene **30 eventos, 28 bajadas y 2 subidas**. El sistema es el #27 sin tocar: campeón,
ROI del 07 (mismo montaje) y `bytetrack_buffer90_match09`. La detección está en
`dets_03.npy` en la torre y los tracks en `data/flow_eval/val03/base.txt`.

| Puerta | Subidas (2) | Bajadas (28) | Precisión de bajadas |
|---|---|---|---|
| `door.py` (el sistema real) | 3 (+1) | 11 (**−61 %**) | 1,00 |
| aperturas revisadas a mano | 3 (+1) | 17 (**−39 %**) | 1,00 |

- **Con la puerta bien detectada, las bajadas del 03 (−39 %) cuadran con las del 07
  (−41 %).** El error del detector de cabezas más el tracker se repite en un video
  nuevo: el número es estable.
- **El detector de puerta tiene un fallo que no se vio en el 07:** pierde las aperturas
  de menos de 3 s (`min_frames` 90) y con ellas 6 bajadas (de −39 % a −61 %). Se
  puede corregir, y ajustarlo en el 03 es legítimo porque para eso está la
  validación.
- Subidas: solo hay 2 reales, así que no permiten sacar conclusiones en este video.
  Hay 1 subida falsa en la apertura 6.673.
- En la apertura 12.568–12.817 no se cuenta ninguna de las 3 bajadas aunque la
  puerta se detecta bien: es una pérdida del detector de cabezas o del tracker,
  para mirar.

### `door.py` corregido (12-10 noche)

`min_frames` pasa de 90 a 45 (1,5 s) y se añade `min_brightness: 40`: un recorte casi
negro, como en un túnel, cuenta como puerta cerrada. Hay un selftest nuevo para el
túnel. Lo que dice la revisión a ojo en los dos videos:
- toda caída de la señal de 57 frames o más es una apertura real;
- los falsos duran 33 frames o menos: el túnel del 03 (5.359, brillo 8) y el 2.539
  del 07 (oscuro, con un bus fuera).

- **03:** 7 aperturas, a ±3 frames de las revisadas. Bajadas **−61 % → −39 %**,
  igual que con la puerta revisada a mano.
- **07:** las 7 de antes, sin cambios, más **6 aperturas cortas que el golden del 07
  NO cubre**: 544, 4.051, 14.821, 15.544, 17.257 y 17.824. La Tabla I del 07 (−35 % /
  −41 %) se calculó sobre un golden al que le faltan esas paradas. Están preparadas
  como tarea complementaria de CVAT (`data/cvat_import/eventos_videoTM_07_cortas/`, 6
  jobs, 1.140 imágenes). Hay que recalcular la Tabla I del 07 cuando estén anotadas.

### Golden del 07 completado y nueva Tabla I (12-10 noche)

Camilo anotó las 6 aperturas cortas (CVAT tarea 8, jobs 29–34): 17 eventos más (9
subidas y 8 bajadas); la de 17.257 no tiene ninguno. `data/flow_golden/videoTM_07.csv`
pasa de 52 a **69 eventos (32 subidas, 37 bajadas)**. Una apertura sin eventos va como
fila `ninguno`, para que un evento falso ahí cuente.

Sistema #27 (campeón + ByteTrack + regla od) sobre los dos goldens:

| Video | Puerta | Subidas | Bajadas | Precisión |
|---|---|---|---|---|
| 07 (69 eventos) | `door.py` viejo | −53 % | −54 % | 1,00 / 1,00 |
| 07 (69 eventos) | **`door.py` corregido** | **−38 %** | **−38 %** | 0,95 / 1,00 |
| 03 (30 eventos) | **`door.py` corregido** | +1 de 2 | **−39 %** | 0,67 / 1,00 |

- **El −35 %/−41 % anterior estaba medido sobre un golden incompleto.** Con el
  `door.py` viejo, el error real del 07 era −53 %/−54 %: el sistema perdía todas
  las paradas cortas.
- **Con la puerta corregida, el error queda en torno a −38 % en los dos videos y en
  las dos direcciones.** Es la nueva línea base. Lo que queda son pérdidas del
  detector de cabezas y del tracker, no de la puerta.

## Golden de PRUEBA: videoTM_02 (12-10 noche)

**Mismo montaje que el 07 y el 03** (curvas superpuestas sobre un frame vacío). Se
usan `configs/cameras/videoTM_02.yaml` y la geometría del 07, sin reajustar. Solo
cambian los `closed_frames`, tomados de la segunda mitad, que va vacía.

**`door.py` (congelado) falla con el bus lleno.** En los primeros ~3.400 frames la
gente tapa la puerta, la similitud se queda en ≈0,3 y marca 15 "aperturas", la
mayoría falsas. Fuera de ese tramo marca un falso más en 17.518 (un bus rojo
fuera). No se reajusta: el 02 es prueba, y ese fallo cuenta contra el sistema.

**Aperturas reales, revisadas a ojo** (las caídas profundas de la similitud, < 0,2,
más los frames completos): 64–178, 901–979, 3.268–3.397, 9.511–9.664,
11.194–11.434, 12.361–12.457, 14.503–14.584 y 16.264–16.390. Entre 179 y 900 la
puerta no se ve (gente apretujada, mucho movimiento) y puede seguir abierta, así que
ese tramo va en el primer job con la cabecera "puerta: no se ve". La tarea de CVAT
tiene 7 jobs y 2.587 imágenes, en `data/cvat_import/eventos_videoTM_02/` de la torre.

**Para que los falsos de `door.py` cuenten**, al construir el CSV se añaden como
paradas sin eventos (`ninguno`) los tramos con la puerta verificada como cerrada:
1.100–3.145 (escena quieta, gente apoyada en la puerta) y 17.518–17.578. Si no,
`eval_flow` no vería los eventos falsos que el sistema cuente ahí.

**Limitación:** entre 3.400 y 9.500 el bus sigue lleno y no hay ninguna caída de la
señal. Si hubo una apertura totalmente tapada, falta en el golden y en el sistema.

### Resultado de PRUEBA en el 02 (12-10 noche, evaluado una sola vez)

Camilo anotó la tarea 9 de CVAT (jobs 35–41). El job 35 incluye una segunda
apertura (902–976); de 1.040 a 1.160 la puerta está cerrada, verificado en un job
de complemento. `data/flow_golden/videoTM_02.csv` tiene **59 eventos (18 subidas,
41 bajadas)** en 8 aperturas, más 3 paradas cerradas sin eventos (300–780,
1.160–3.145 y 17.518–17.578), donde `door.py` da falsos.

Sistema congelado: #27 + `door.py` + `configs/calibracion.yaml`. Tracks en
`data/flow_eval/test02/base.txt`.

| 02 (congestión alta) | Real | Contado | Error | Recall | Precisión | Corregido (IC95) | Error corregido |
|---|---|---|---|---|---|---|---|
| Subidas | 18 | 13 | −28 % | 0,61 | 0,85 | 19,2 (13,9–27,7) | **+7 %** |
| Bajadas | 41 | 25 | −39 % | 0,56 | 0,92 | 40,6 (34,2–48,3) | **−1 %** |

- **El factor aguanta con congestión alta.** El recall (0,56–0,61) es el mismo que
  en el 03 y el 07, y el conteo real cae dentro del IC95 en las dos direcciones.
- **Primeros falsos positivos (3), y todos vienen de `door.py`.** Son 1 subida en
  300–780 y 1 subida y 1 bajada en 1.160–3.145: tramos en que el bus va lleno, la
  gente tapa la puerta cerrada y `door.py` la da por abierta. Bajan la precisión a
  0,85/0,92. Es la limitación a declarar: el detector de puerta por bordes no
  funciona con oclusión total.
- Queda la segunda prueba, el **03(1)**: otro bus, con la puerta a la izquierda.
