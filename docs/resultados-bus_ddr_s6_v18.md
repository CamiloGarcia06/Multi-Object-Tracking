# Resultados de prueba: bus_ddr_s6_v18 (2026-10-18)

Evaluado UNA vez. Eventos sellados antes del golden (configs/prueba_sellada.sha256).
Golden: `data/flow_golden/bus_ddr_s6_v18.csv`. Puerta del sistema: door.py (`data/flow_videos/puerta_abierta_bus_ddr_s6_v18.json`).

## Sin corregir

| sistema | apertura | dir | real | contado | error | error % | recall | precisión |
|---|---|---|---|---|---|---|---|---|
| #27 ByteTrack | 9205–9295 | sube | 1 | 1 | +0 | +0% | 1.00 | 1.00 |
| #27 ByteTrack | 9205–9295 | baja | 2 | 2 | +0 | +0% | 1.00 | 1.00 |
| #27 ByteTrack | 12295–12520 | sube | 3 | 2 | -1 | -33% | 0.67 | 1.00 |
| #27 ByteTrack | 12295–12520 | baja | 3 | 2 | -1 | -33% | 0.67 | 1.00 |
| #27 ByteTrack | 13090–13240 | sube | 0 | 0 | +0 | — | — | — |
| #27 ByteTrack | 13090–13240 | baja | 1 | 1 | +0 | +0% | 1.00 | 1.00 |
| #27 ByteTrack | 19640–19860 | sube | 0 | 0 | +0 | — | — | — |
| #27 ByteTrack | 19640–19860 | baja | 9 | 8 | -1 | -11% | 0.89 | 1.00 |
| #27 ByteTrack | 26235–26315 | sube | 0 | 0 | +0 | — | — | — |
| #27 ByteTrack | 26235–26315 | baja | 2 | 1 | -1 | -50% | 0.50 | 1.00 |
| #27 ByteTrack | TOTAL | sube | 4 | 3 | -1 | -25% | 0.75 | 1.00 |
| #27 ByteTrack | TOTAL | baja | 17 | 14 | -3 | -18% | 0.82 | 1.00 |
| sin tracking | 9205–9295 | sube | 1 | 1 | +0 | +0% | 1.00 | 1.00 |
| sin tracking | 9205–9295 | baja | 2 | 1 | -1 | -50% | 0.50 | 1.00 |
| sin tracking | 12295–12520 | sube | 3 | 2 | -1 | -33% | 0.33 | 0.50 |
| sin tracking | 12295–12520 | baja | 3 | 4 | +1 | +33% | 1.00 | 0.75 |
| sin tracking | 13090–13240 | sube | 0 | 1 | +1 | — | — | 0.00 |
| sin tracking | 13090–13240 | baja | 1 | 2 | +1 | +100% | 1.00 | 0.50 |
| sin tracking | 19640–19860 | sube | 0 | 0 | +0 | — | — | — |
| sin tracking | 19640–19860 | baja | 9 | 5 | -4 | -44% | 0.56 | 1.00 |
| sin tracking | 26235–26315 | sube | 0 | 0 | +0 | — | — | — |
| sin tracking | 26235–26315 | baja | 2 | 1 | -1 | -50% | 0.50 | 1.00 |
| sin tracking | TOTAL | sube | 4 | 4 | +0 | +0% | 0.50 | 0.50 |
| sin tracking | TOTAL | baja | 17 | 13 | -4 | -24% | 0.65 | 0.85 |

## Corregido: sistema (factor 03+07)

| sistema | dir | real | contado | error % | corregido | IC95 | error % corr. |
|---|---|---|---|---|---|---|---|
| #27 ByteTrack | sube | 4 | 3 | -25% | 4.4 | 3.2–6.4 | +11% |
| #27 ByteTrack | baja | 17 | 14 | -18% | 22.7 | 19.1–27.0 | +34% |

## Corregido: línea base (factor 03+07)

| sistema | dir | real | contado | error % | corregido | IC95 | error % corr. |
|---|---|---|---|---|---|---|---|
| sin tracking | sube | 4 | 4 | +0% | 7.2 | 3.7–11.7 | +79% |
| sin tracking | baja | 17 | 13 | -24% | 24.9 | 17.8–32.2 | +46% |

## Lectura (18-10-2026)

**En DDR el sistema pierde MENOS que en DDL, y el factor de DDL sobrecorrige.** Sin corregir: subidas −25 %
(3 de 4), bajadas −18 % (14 de 17), con precisión 1,00 y recall 0,75/0,82, frente a 0,59–0,62 en DDL. Con el
factor 03+07 las bajadas pasan a +34 % y el IC95 (19,1–27,0) no contiene las 17 reales: **el factor de DDL no
vale en DDR para las bajadas**. Las subidas (+11 %, IC 3,2–6,4) caen dentro, pero con 4 eventos no dicen nada.
door.py acierta las 5 paradas del golden (más falsos fuera de ellas, que un golden reducido no penaliza).

**Cautelas.** Golden REDUCIDO de 21 eventos (4 suben / 17 bajan) en 5 paradas; las subidas son muy pocas para
estimar nada por cámara. No se reajusta nada con este video.
