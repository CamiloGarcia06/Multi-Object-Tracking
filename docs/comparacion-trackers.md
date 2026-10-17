# Trackers por nivel de congestión (golden de tracking)

Mismas detecciones (campeón, NMS post-hoc 0,6) y misma ROI para todos: solo cambia la asociación. Ordenado por HOTA. IoU 0,5 para MOTA/IDF1.


## tm07_a — congestión baja

| tracker | HOTA | DetA | AssA | IDF1 | MOTA | IDSW | Frag | GT_IDs | IDs |
|---|---|---|---|---|---|---|---|---|---|
| bytetrack_27 | 61.1 | 58.8 | 63.9 | 69.5 | 61.8 | 5 | 8 | 10 | 13 |
| botsort_osnet | 51.8 | 49.6 | 54.4 | 74.6 | 63.8 | 2 | 13 | 10 | 12 |
| deepocsort_osnet_iou020 | 43.1 | 39.5 | 47.3 | 65.5 | 51.6 | 2 | 7 | 10 | 11 |
| ocsort | 35.2 | 37.2 | 33.4 | 51.6 | 45.7 | 7 | 9 | 10 | 15 |
| deepocsort_osnet | 34.2 | 35.6 | 33.0 | 50.0 | 43.7 | 7 | 7 | 10 | 16 |

## tm03_1_a — congestión media

| tracker | HOTA | DetA | AssA | IDF1 | MOTA | IDSW | Frag | GT_IDs | IDs |
|---|---|---|---|---|---|---|---|---|---|
| bytetrack_27 | 55.2 | 61.8 | 49.5 | 59.9 | 59.8 | 33 | 54 | 36 | 52 |
| botsort_osnet | 48.4 | 54.5 | 43.5 | 57.8 | 57.1 | 37 | 55 | 36 | 50 |
| deepocsort_osnet_iou020 | 39.6 | 41.3 | 38.3 | 53.7 | 48.0 | 27 | 38 | 36 | 43 |
| ocsort | 35.6 | 42.6 | 30.0 | 47.1 | 47.6 | 38 | 44 | 36 | 51 |
| deepocsort_osnet | 34.0 | 39.3 | 29.7 | 46.8 | 44.1 | 38 | 43 | 36 | 51 |

## tm02_a — congestión alta

| tracker | HOTA | DetA | AssA | IDF1 | MOTA | IDSW | Frag | GT_IDs | IDs |
|---|---|---|---|---|---|---|---|---|---|
| botsort_osnet | 68.8 | 67.4 | 70.4 | 72.5 | 66.0 | 11 | 36 | 18 | 25 |
| bytetrack_27 | 66.0 | 72.6 | 60.0 | 65.7 | 66.6 | 11 | 34 | 18 | 26 |
| deepocsort_osnet_iou020 | 52.6 | 57.7 | 48.0 | 57.5 | 57.8 | 11 | 35 | 18 | 20 |
| ocsort | 50.3 | 59.4 | 42.6 | 51.5 | 58.7 | 17 | 37 | 18 | 24 |
| deepocsort_osnet | 46.4 | 57.3 | 37.7 | 45.9 | 56.8 | 17 | 38 | 18 | 22 |

## Todos los clips

| tracker | HOTA | DetA | AssA | IDF1 | MOTA | IDSW | Frag | GT_IDs | IDs |
|---|---|---|---|---|---|---|---|---|---|
| bytetrack_27 | 60.8 | 66.2 | 55.9 | 63.5 | 62.9 | 49 | 96 | 64 | 91 |
| botsort_osnet | 58.6 | 59.3 | 58.3 | 66.2 | 61.7 | 50 | 104 | 64 | 87 |
| deepocsort_osnet_iou020 | 46.3 | 48.2 | 44.6 | 56.7 | 52.6 | 40 | 80 | 64 | 74 |
| ocsort | 42.8 | 49.3 | 37.3 | 49.7 | 52.2 | 62 | 90 | 64 | 90 |
| deepocsort_osnet | 40.1 | 46.7 | 34.6 | 46.7 | 49.6 | 62 | 88 | 64 | 89 |
## Lectura (17-10-2026)

**Control.** En tm07_a, `bytetrack_27` reproduce el job #23/#27 publicado (HOTA 61,1 · IDF1 69,5 · IDSW 5) y
`deepocsort_osnet_iou020` el #24/#28 (43,1 · 65,5 · 2). BoT-SORT, OC-SORT y Deep OC-SORT no coinciden con los
jobs #17/#19/#20 porque aquellos corrían **sin ROI**; aquí todos llevan la misma ROI.

**Resultados.**
- En conjunto, **ByteTrack** tiene el mejor HOTA (60,8) y el mejor DetA (66,2); **BoT-SORT + ReID OSNet**, el mejor
  IDF1 (66,2) y AssA (58,3). Deep OC-SORT y OC-SORT quedan 14–20 puntos de HOTA por debajo en los tres niveles.
- Por nivel: ByteTrack gana en baja y media; en **alta** gana BoT-SORT + ReID (HOTA 68,8 frente a 66,0; AssA 70,4
  frente a 60,0). Es el primer caso en que la apariencia aporta: con el bus lleno, la asociación solo por
  movimiento se equivoca más y el ReID la corrige.
- El iou 0,2 de Deep OC-SORT (candidata del 01-10) mejora a su versión por defecto en los tres niveles (+6 a +9 de HOTA).

**Cautelas que hay que declarar.**
- **Sesgo de pre-anotación:** los tres goldens se pre-anotaron con ByteTrack y Camilo los corrigió. Eso favorece a
  ByteTrack; que BoT-SORT le gane en alta pese a ello hace ese resultado más sólido, no menos.
- **Nivel y montaje se confunden:** media = 03(1), otro bus y puerta a la izquierda; baja y alta = el mismo montaje
  (07/02). Que media salga más difícil que alta (AssA de ByteTrack 49,5 frente a 60,0) puede deberse al montaje y
  no a la congestión.
- **Clips cortos:** 200 frames (100 en tm07_a) y 10/36/18 identidades. Diferencias de pocos puntos entre dos
  trackers no son concluyentes sin un intervalo (p. ej. bootstrap por identidades).
- DetA cambia entre trackers con las mismas detecciones porque cada uno publica cajas distintas (suavizado del
  Kalman, tracks sin confirmar que no salen).
