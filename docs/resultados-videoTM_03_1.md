# Resultados de prueba: videoTM_03_1 (2026-10-18)

Evaluado UNA vez. Eventos sellados antes del golden (configs/prueba_sellada.sha256).
Golden: `data/flow_golden/videoTM_03_1.csv`. Puerta del sistema: door.py (`data/flow_videos/puerta_abierta_videoTM_03_1.json`).

## Sin corregir

| sistema | apertura | dir | real | contado | error | error % | recall | precisión |
|---|---|---|---|---|---|---|---|---|
| #27 ByteTrack | 2908–3034 | sube | 1 | 1 | +0 | +0% | 1.00 | 1.00 |
| #27 ByteTrack | 2908–3034 | baja | 1 | 1 | +0 | +0% | 1.00 | 1.00 |
| #27 ByteTrack | 5500–5623 | sube | 0 | 0 | +0 | — | — | — |
| #27 ByteTrack | 5500–5623 | baja | 0 | 0 | +0 | — | — | — |
| #27 ByteTrack | 9925–10144 | sube | 0 | 0 | +0 | — | — | — |
| #27 ByteTrack | 9925–10144 | baja | 10 | 7 | -3 | -30% | 0.70 | 1.00 |
| #27 ByteTrack | 22336–23475 | sube | 53 | 12 | -41 | -77% | 0.21 | 0.92 |
| #27 ByteTrack | 22336–23475 | baja | 0 | 0 | +0 | — | — | — |
| #27 ByteTrack | TOTAL | sube | 54 | 13 | -41 | -76% | 0.22 | 0.92 |
| #27 ByteTrack | TOTAL | baja | 11 | 8 | -3 | -27% | 0.73 | 1.00 |
| sin tracking | 2908–3034 | sube | 1 | 1 | +0 | +0% | 1.00 | 1.00 |
| sin tracking | 2908–3034 | baja | 1 | 1 | +0 | +0% | 1.00 | 1.00 |
| sin tracking | 5500–5623 | sube | 0 | 0 | +0 | — | — | — |
| sin tracking | 5500–5623 | baja | 0 | 0 | +0 | — | — | — |
| sin tracking | 9925–10144 | sube | 0 | 0 | +0 | — | — | — |
| sin tracking | 9925–10144 | baja | 10 | 4 | -6 | -60% | 0.40 | 1.00 |
| sin tracking | 22336–23475 | sube | 53 | 13 | -40 | -75% | 0.21 | 0.85 |
| sin tracking | 22336–23475 | baja | 0 | 3 | +3 | — | — | 0.00 |
| sin tracking | TOTAL | sube | 54 | 14 | -40 | -74% | 0.22 | 0.86 |
| sin tracking | TOTAL | baja | 11 | 8 | -3 | -27% | 0.45 | 0.62 |

## Corregido: sistema (factor 03+07)

| sistema | dir | real | contado | error % | corregido | IC95 | error % corr. |
|---|---|---|---|---|---|---|---|
| #27 ByteTrack | sube | 54 | 13 | -76% | 19.2 | 13.9–27.7 | -64% |
| #27 ByteTrack | baja | 11 | 8 | -27% | 13.0 | 10.9–15.4 | +18% |

## Corregido: línea base (factor 03+07)

| sistema | dir | real | contado | error % | corregido | IC95 | error % corr. |
|---|---|---|---|---|---|---|---|
| sin tracking | sube | 54 | 14 | -74% | 25.1 | 13.0–41.0 | -54% |
| sin tracking | baja | 11 | 8 | -27% | 15.3 | 10.9–19.8 | +39% |

## Lectura (18-10-2026)

**El −76 % de subidas sale casi entero de door.py, no del tracking.** La 4.ª parada (bus lleno) va de 22.336 a
23.475 en el golden (el job 48 de CVAT ya empieza con la puerta cerrada), pero door.py la corta en **22.519**: con la
gente tapando la puerta la da por cerrada y el sistema deja de contar. Subidas del golden / del sistema por tramo:

| tramo | door.py | golden | sistema |
|---|---|---|---|
| 22.336–22.519 | abierta | 15 | 8 |
| 22.520–22.720 | cerrada | 34 | 4 |
| 22.721–23.475 | cerrada | 4 | 0 |

Donde door.py ve la puerta, el recall es 8/15 = 0,53, del orden del de DDL (0,59–0,62). Es el mismo fallo que en el 02
(door.py no ve la puerta con el bus lleno), aquí en la parada con más subidas. Por eso el factor de DDL no basta
(corregido −64 %, fuera del IC95). Las bajadas (+18 % corregido) caen dentro del IC95 (10,9–15,4 frente a 11 reales).

**Cautelas.** Golden REDUCIDO: 53 de las 54 subidas están en una sola parada, así que el resultado de subidas de SDM
es, en la práctica, el de esa parada llena. Fin de la 4.ª parada fijado en 23.475 (fin del job 47) porque en las
imágenes no se distingue el cierre. No se reajusta nada con este video (ni door.py ni factores).
