# Trackers por nivel de congestión (golden de tracking)

Mismas detecciones (campeón, NMS post-hoc 0,6) y misma ROI para todos: solo cambia la asociación. Ordenado por HOTA. IoU 0,5 para MOTA/IDF1.


## tm07_a — DDL, congestión baja

| tracker | HOTA | DetA | AssA | IDF1 | MOTA | IDSW | Frag | GT_IDs | IDs |
|---|---|---|---|---|---|---|---|---|---|
| bytetrack_27 | 61.1 | 58.8 | 63.9 | 69.5 | 61.8 | 5 | 8 | 10 | 13 |
| botsort_osnet | 51.8 | 49.6 | 54.4 | 74.6 | 63.8 | 2 | 13 | 10 | 12 |
| deepocsort_osnet_iou020 | 43.1 | 39.5 | 47.3 | 65.5 | 51.6 | 2 | 7 | 10 | 11 |
| ocsort | 35.2 | 37.2 | 33.4 | 51.6 | 45.7 | 7 | 9 | 10 | 15 |
| deepocsort_osnet | 34.2 | 35.6 | 33.0 | 50.0 | 43.7 | 7 | 7 | 10 | 16 |

## tm02_a — DDL, congestión alta

| tracker | HOTA | DetA | AssA | IDF1 | MOTA | IDSW | Frag | GT_IDs | IDs |
|---|---|---|---|---|---|---|---|---|---|
| botsort_osnet | 68.8 | 67.4 | 70.4 | 72.5 | 66.0 | 11 | 36 | 18 | 25 |
| bytetrack_27 | 66.0 | 72.6 | 60.0 | 65.7 | 66.6 | 11 | 34 | 18 | 26 |
| deepocsort_osnet_iou020 | 52.6 | 57.7 | 48.0 | 57.5 | 57.8 | 11 | 35 | 18 | 20 |
| ocsort | 50.3 | 59.4 | 42.6 | 51.5 | 58.7 | 17 | 37 | 18 | 24 |
| deepocsort_osnet | 46.4 | 57.3 | 37.7 | 45.9 | 56.8 | 17 | 38 | 18 | 22 |

## tm03_1_a — SDM, congestión media

| tracker | HOTA | DetA | AssA | IDF1 | MOTA | IDSW | Frag | GT_IDs | IDs |
|---|---|---|---|---|---|---|---|---|---|
| bytetrack_27 | 55.2 | 61.8 | 49.5 | 59.9 | 59.8 | 33 | 54 | 36 | 52 |
| botsort_osnet | 48.4 | 54.5 | 43.5 | 57.8 | 57.1 | 37 | 55 | 36 | 50 |
| deepocsort_osnet_iou020 | 39.6 | 41.3 | 38.3 | 53.7 | 48.0 | 27 | 38 | 36 | 43 |
| ocsort | 35.6 | 42.6 | 30.0 | 47.1 | 47.6 | 38 | 44 | 36 | 51 |
| deepocsort_osnet | 34.0 | 39.3 | 29.7 | 46.8 | 44.1 | 38 | 43 | 36 | 51 |

## ddr_s6_v18_a — DDR, congestión alta

| tracker | HOTA | DetA | AssA | IDF1 | MOTA | IDSW | Frag | GT_IDs | IDs |
|---|---|---|---|---|---|---|---|---|---|
| bytetrack_27 | 81.8 | 82.1 | 81.8 | 80.0 | 83.6 | 3 | 7 | 9 | 11 |
| botsort_osnet | 76.0 | 76.8 | 75.6 | 78.7 | 81.8 | 3 | 10 | 9 | 11 |
| deepocsort_osnet_iou020 | 74.4 | 70.5 | 78.6 | 87.6 | 77.0 | 2 | 13 | 9 | 11 |
| ocsort | 73.8 | 71.2 | 76.7 | 85.0 | 76.1 | 6 | 13 | 9 | 13 |
| deepocsort_osnet | 73.3 | 70.1 | 76.8 | 85.3 | 76.1 | 4 | 13 | 9 | 13 |

## sdr_s1_v08_a — SDR, congestión baja

| tracker | HOTA | DetA | AssA | IDF1 | MOTA | IDSW | Frag | GT_IDs | IDs |
|---|---|---|---|---|---|---|---|---|---|
| bytetrack_27 | 77.5 | 73.8 | 81.5 | 82.2 | 75.0 | 6 | 20 | 17 | 24 |
| botsort_osnet | 68.4 | 66.4 | 71.0 | 83.6 | 77.4 | 4 | 23 | 17 | 20 |
| deepocsort_osnet_iou020 | 49.7 | 52.9 | 47.1 | 65.7 | 64.3 | 9 | 21 | 17 | 21 |
| ocsort | 49.2 | 54.4 | 44.8 | 62.0 | 65.1 | 14 | 26 | 17 | 24 |
| deepocsort_osnet | 47.0 | 51.4 | 43.4 | 59.9 | 61.9 | 14 | 24 | 17 | 23 |

## Todos los clips

| tracker | HOTA | DetA | AssA | IDF1 | MOTA | IDSW | Frag | GT_IDs | IDs |
|---|---|---|---|---|---|---|---|---|---|
| bytetrack_27 | 68.0 | 70.2 | 66.0 | 70.0 | 68.7 | 58 | 123 | 90 | 126 |
| botsort_osnet | 63.6 | 63.5 | 64.3 | 71.8 | 68.0 | 57 | 137 | 90 | 118 |
| deepocsort_osnet_iou020 | 52.6 | 52.7 | 52.8 | 64.1 | 58.8 | 51 | 114 | 90 | 106 |
| ocsort | 50.4 | 53.8 | 47.6 | 58.5 | 58.6 | 82 | 129 | 90 | 127 |
| deepocsort_osnet | 48.4 | 51.4 | 46.0 | 56.4 | 56.3 | 80 | 125 | 90 | 125 |
## Lectura (18-10-2026, Tesis 17b)

**Control.** Las tablas de tm07_a, tm02_a y tm03_1_a salen idénticas a `docs/comparacion-trackers.md` (Tesis 17):
la ampliación no cambia nada de lo anterior. `bytetrack_27` en DDR/SDR es byte a byte la corrida con la que se
pre-anotaron los clips (`diag_bytetrack.py run`, bytetrack_buffer90_match09, ROI del montaje). Corridas del video
entero con `scripts/tracking/correr_17b.sh` (torre, unidad `tesis-17b`, ~20 min).

**Resultados.**
- En las dos cámaras nuevas gana **ByteTrack** en HOTA (DDR 81,8 · SDR 77,5) y **BoT-SORT + ReID** queda segundo
  (76,0 · 68,4). En conjunto (5 clips, 90 identidades) el orden de la 17 no cambia: ByteTrack 68,0, BoT-SORT 63,6,
  Deep OC-SORT iou 0,2 52,6, OC-SORT 50,4, Deep OC-SORT 48,4.
- **DDR separa poco a los trackers** (HOTA 73–82; los de apariencia tienen el mejor IDF1, 85–88, con 2–6 IDSW).
  **SDR sí separa:** ByteTrack y BoT-SORT 68–78, el resto 47–50 (AssA 43–47).
- La ventaja de BoT-SORT con el bus lleno (tm02_a) no se repite en DDR, pero el clip de DDR no está lleno dentro
  de la ROI (ver abajo), así que no lo contradice.

**Cautelas que hay que declarar.**
- **El nivel es el del VIDEO, no el del clip.** Cabezas por frame dentro de la ROI (media / máx.): tm07_a 2,5 / 6 ·
  tm02_a 5,1 / 8 · tm03_1_a 5,4 / 12 · **ddr_s6_v18_a 2,9 / 4** · sdr_s1_v08_a 3,6 / 8. El v18 va lleno el 39 %
  del tiempo, pero en este tramo la gente está casi quieta y fuera de la ROI: el clip de DDR es de carga baja.
  Para la tabla por congestión conviene agrupar por esta medida y no por la etiqueta del video.
- **Sesgo de pre-anotación, más fuerte en las cámaras nuevas:** caja sin tocar desde ByteTrack (centro a <2 px)
  tm02_a 77 %, tm03_1_a 61 %, **ddr 81 %, sdr 72 %**. Favorece a ByteTrack; su ventaja en DDR/SDR hay que leerla así.
- **SDR, sentados:** no se anotan, pero la ROI los incluye. Los trackers que los siguen pagan falsos positivos y la
  persona sentada de abajo queda a medias en el golden (tracks 9, 12 y 17). Pendiente: filtro de tracks estáticos
  o ROI (decisión de Camilo); repetir SDR con y sin estáticos.
- **Clips cortos:** 200 frames y 9/17 identidades; diferencias de pocos puntos no son concluyentes sin intervalo.
