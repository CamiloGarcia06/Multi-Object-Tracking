# Diagnóstico de ByteTrack en la puerta (tarea 1 del roadmap 12-10)

Pregunta: ¿por qué el job #27 (ByteTrack `buffer90_match09` + ROI de la puerta) no da
ID a detecciones de 0,7–0,9 en la puerta? Casos: las 16 perdidas marcadas S o I en
`data/flow_golden/errores_job27_revisados.csv`.

## Método

`scripts/flow/diag_bytetrack.py` repite el mismo ByteTrack de ultralytics (8.4.157,
el del venv de track-studio) sobre `dets.npy` filtrado por la ROI del job, y anota
el destino de cada detección en cada frame. **Reproduce el job #27**: las mismas 37.204
cajas, con el mismo ID en todas menos una (diferencias de 0,14 px de mediana, del
Kalman). Corrida y salidas en la torre:
`~/Projects/track-studio/data/experiments/2026-10-12-diag-bytetrack/`.

## Lo que NO es

- **No es el dedup**: el NMS post-hoc ya está aplicado en `dets.npy`, que es justo
  lo que recibe el tracker.
- **No es la ROI**: en las paradas 5347, 22018 y 23806 no hay ninguna detección
  (conf >= 0,25, x > 400) fuera del polígono junto a la puerta.
- **Parte de las "S" son un efecto de las hojas de revisión.** Las hojas enseñan un
  frame de cada 6. Una caja blanca sin ID es casi siempre el **primer frame de un
  track nuevo**: ByteTrack no lo saca hasta el segundo frame, por diseño. Ejemplo:
  en el frame 5361 la detección de 0,83 "sin ID" es el nacimiento del #122.

## Las tres causas

**A. Activación (tracker, 4 casos).** Un track nuevo nace sin confirmar y solo se
confirma si en el frame **siguiente** hay una detección de score alto (>= 0,25,
`track_high_thresh`) con IoU·score > 0,3. Ese umbral de 0,7 está fijo en el código
de ultralytics. Si falla una sola vez, el track se borra: no hay `track_buffer` para
los tracks sin confirmar. En la puerta falla porque el score oscila (0,87 → 0,11) y
porque una cabeza de unos 50 px que se mueve 20–40 px por frame da poca IoU.
Ejemplo: en 22077–22081 nacen y mueren tres tracks seguidos (r638, r640 y r641).

**B. Huecos del detector (detector, 7 casos).** Aquí no hay ninguna detección de
conf >= 0,10 a menos de 120 px de la persona:
- durante 8–25 frames con la persona en la puerta: #131 en 5397–5420, #649 en
  22106–22116, #125 en 5385–5401;
- o la persona no se ve en el pasillo antes de llegar a la puerta. En las bajadas,
  el track nace ya en el umbral (d entre −42 y +65 frente a los 80 exigidos) sin
  ningún track previo cerca.

**C. Reenganche de tracks perdidos (tracker, 5 casos).** Tras un hueco, ByteTrack
recupera solo por IoU contra la predicción del Kalman. Eso falla de dos maneras:
- crea un ID nuevo aunque la persona sea la misma: #635 → #636, y #278 → #279 → #278;
- se lleva a otra persona: el #120 salta a otra cabeza en el frame 5357, el #131 se
  recupera en 5421 sobre la persona de 5416, y el #685 y el #625 hacen lo mismo.

## Caso a caso

| Frame | Rev. | Causa | Detalle |
|---|---|---|---|
| 23846 | S | A | r668 y r672 nacen (0,56–0,59) y no se confirman |
| 23886 | I | C | #689 dura 2 frames; el #685, recuperado, se queda la cabeza |
| 22031 | I | B (+C) | #629 nace en d+41, sin pasillo previo; el #625 se recupera encima |
| 22049 | S | A | r631 de 0,87; al frame siguiente solo hay 0,11 → borrado |
| 22066 | I | C | #635 muere en d+5 y 8 frames después nace el #636: no se reengancha |
| 22077 | S | A | r638, r640 y r641 nacen y mueren (score 0,10–0,20 o IoU 0,35) |
| 22085 | S | B | #644 nace en d+65, sin track previo: no se vio en el pasillo |
| 22098 | S | B | #647 nace en d−1, sin track previo |
| 22104 | S | B | #649 nace en d−42 y luego tiene un hueco de 12 frames |
| 22135 | I | B | #653 nace en d+35, sin track previo |
| 5367 | S | C | #120 salta a otra cabeza en 5357; el #122 nace tarde y se corta |
| 5384 | S | B | #125 sí cuenta, pero un hueco de 18 frames le saca de ±tol |
| 5396 | I | B+C | hueco de 24 frames; el #131 se recupera sobre otra persona |
| 5401 | S | B (¿C?) | hueco de 6 frames y el #128 muere en d−19. Dudoso: el #125 reaparece a 68 px en un frame (¿salto de video?) |
| 12678 | I | C | #278 perdido, nace el #279 (4 cajas) y luego el #278 se reengancha |
| 12703 | S | A | r286 de 0,87 aislado; 8 frames vacíos; el #287 nace en d−54 |

**Recuento de las 23 perdidas:**
- tracker (A+C): 9 de 16 S/I, es decir, unos 9–10 de 23, alrededor del **40 %**;
- detector (B + las 5 V): unos 12 de 23, alrededor del **50 %**;
- regla: 2.

**Esto corrige la revisión a ojo** (~70 % tracker): con el detalle frame a frame, el
detector vuelve a pesar más que el tracker. Ojo con la confianza: B en las bajadas se
infiere de que no hay detecciones ni tracks a < 90 px del nacimiento en los 30 frames
anteriores, no se ha visto a ojo.

## Qué implica para la tarea 3 (candidato de tracker)

- **A** se ataca con la activación. Bajar `track_high_thresh` a 0,10–0,15 hace que
  las detecciones débiles también sirvan para confirmar. El 0,7 de la asociación de
  los tracks sin confirmar no se puede tocar por yaml: haría falta una subclase.
- **C** no se arregla con `match_thresh` (ya está en 0,9, muy flojo). El hueco es
  demasiado largo para la IoU. Candidato: **unir trozos de track después del
  tracker**: uno que muere y otro que nace dentro de N frames y R px, con la
  dirección coherente. Es independiente del tracker y se mide con la Tabla I.
- **B** solo lo arregla el detector (tarea 9, reentrenar con cabezas de puerta).
  Pesa casi la mitad: el reentrenamiento vuelve a ser prioridad alta.
- Los saltos de video (tarea 8) pueden estar detrás del 5401 y de algún
  reenganche: medirlos antes de interpretar los reenganches lejanos.

## Tarea 8: saltos de frames del video (12-10)

`scripts/flow/frame_jumps.py` (lista en `data/flow_eval/saltos_videoTM_07.csv`).

- **Las marcas de tiempo del mkv son regulares** (26.999 frames a 30 fps, sin
  huecos): el salto está en el contenido, no en el contenedor.
- **Firma, calibrada con el 5.396→5.397 anotado a mano:** la cámara repite un frame
  (cambio casi nulo) y en el siguiente el movimiento sale doble. En 5392→5393 pasa
  lo mismo.
- **556 saltos en el video; 32 en las 7 aperturas**, uno cada ~48 frames.
- **Efecto en el #27 dentro de las aperturas:** junto a un salto, los tracks nacen
  ×2,6, mueren ×3,0 y se pierden ×4,0 más que por azar. Aun así, eso es solo el
  11–16 % de los nacimientos, muertes y pérdidas. **Contribuye, pero no es la causa
  principal.** De los reenganches lejanos, el 5421 (#131) cae justo en un salto; el
  5402 (#125) no, así que el 5401 sigue siendo dudoso.
- **Aparte, 4.560 frames (17 %) están congelados** en 1.004 tramos (mediana 2, máximo
  185). En las aperturas no hay ninguno. No afectan a la Tabla I, pero sí a métricas
  de tracking sobre el video entero: un tramo congelado alarga los tracks gratis.

**Para la 3b (unir trozos):**
- Los huecos que hay que cubrir vienen del detector (8–25 frames), no de los saltos:
  hueco máximo de ~30 frames.
- Tras un salto el paso es doble: el radio debe admitir ~2× la velocidad del track.

**Candidato barato (3c):** en cada salto, sustituir las detecciones del frame
congelado por el punto medio entre el anterior y el siguiente. Así se recupera un
movimiento uniforme antes del tracker.

## Tarea 3a: candidato de activación — resultado NEGATIVO (12-10)

`diag_bytetrack.py run --set track_high_thresh=… --set new_track_thresh=…` sobre
`dets.npy` + ROI del #27 (la variante base reproduce las 37.204 cajas del job).
Tabla I total (golden de 52 eventos):

| track_high | new_track | sube (error) | baja (error) |
|---|---|---|---|
| 0,25 | 0,25 (= #27) | −35 % | −41 % |
| 0,20 / 0,15 | 0,25 | −35 % | −41 % |
| 0,10 | 0,25 | −35 % | −45 % |
| cualquiera | 0,40 | −39 % | −41/−45 % |

Precisión 1,00 en todas. **No se adopta nada.** En los casos A, confirmar el track
antes no basta: dura 2–3 frames y no llega del umbral al pasillo, así que la regla
origen–destino tampoco lo cuenta. La palanca es la **continuidad** (B y C), no la
activación. Como no se ajustó nada a partir de este resultado, no hay fuga de
evaluación.

## Tareas 3c y 3b — resultados (12-10)

**3c, interpolar el frame congelado de cada salto** (`diag_bytetrack.py run --interp`):
**neutro**, −35 % / −41 %, igual que el #27. Cuadra con la tarea 8: los saltos
pesan poco.

**3b, unir trozos tras el tracker** (`scripts/flow/stitch.py`, parámetros fijados
de antemano: hueco <= 30 f, radio 20 + 15·hueco px, dirección coherente): **peor**.
Hace 49 uniones (228 → 179 tracks), pero las subidas pasan a −39 % y las bajadas a
−52 % (precisión 0,93).

**Por qué falla:** unir por cercanía confunde la **cola**. Cuando varias personas bajan
en fila, cada una aparece donde y cuando desapareció la anterior. El #403 (alguien de
pie junto a la puerta durante 7.000 frames) acaba encadenado con el #635, el #644 y el
#649, tres personas distintas: cuatro bajadas cuentan como una. Pasa lo mismo con
#278+#287+#298+#305 y con #639+#652+#654+#656. No se arregla tocando radios ni
huecos: hace falta **apariencia** para separar a una persona de la siguiente. **No
se reajusta con este golden**: sería fuga de evaluación.

## Balance del ajuste del tracker (3a, 3b y 3c)

Ninguno de los tres candidatos mejora el #27. Con la regla origen–destino, ByteTrack
tal cual es el mejor de lo probado. Lo que queda:
- **Detector (tarea 9)**: es la palanca principal (≈50 % de las perdidas son B o V).
- **3d, solo si hace falta**: unir trozos con apariencia (embeddings OSNet por trozo).
  Que el ReID no aportara dentro del tracker no lo descarta para esto, que es otro
  uso. Se mediría en el golden de otra cámara (tarea 6), no aquí.
