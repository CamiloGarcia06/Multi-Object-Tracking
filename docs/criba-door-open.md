# Criba de door_open por video (DDR s6 y SDR s1, diurnos) — 2026-10-18

Pregunta: ¿en qué videos funciona `door.py` con la referencia de puerta cerrada **del montaje**
(`closed_ref`: DDR desde bus_ddr_s6_v18, SDR desde bus_sdr_s1_v02)? Motivo: el v15 de DDR y el v10 de SDR,
elegidos desde el inventario, van llenos o con gente apoyada en la puerta y door_open no aplica.

- **legible**: % de minutos cuyo p75 de similitud con la puerta cerrada es ≥ 0,6 (la puerta se reconoce).
- **apto**: legible ≥ 80 %, ningún intervalo de puerta abierta > 30 s (oclusión) y ≥ 4 aperturas.
- La referencia se transfiere entre videos del mismo montaje: con la del v11, el v18 da las mismas 11 aperturas que con la propia.
- `lleno` y `p90` vienen del inventario; en SDR el detector cuenta de menos (el v10 da p50 = 3 y va lleno a ratos).

| video | apto | legible % | sim p50 | aperturas | más larga (s) | > 30 s | lleno % | cab. p90 | estado |
|---|---|---|---|---|---|---|---|---|---|
| bus_ddr_s6_v09 | — | 100 | 0.82 | 3 | 5.5 | 0 | 0.0 | 1.0 | nunca visto |
| bus_ddr_s6_v10 | — | 53 | 0.59 | 10 | 211.2 | 2 | 39.9 | 11.0 | nunca visto |
| bus_ddr_s6_v11 | — | 53 | 0.52 | 14 | 8.6 | 0 | 24.7 | 9.0 | nunca visto |
| bus_ddr_s6_v12 | **sí** | 93 | 0.8 | 7 | 15.1 | 0 | 0.0 | 2.0 | nunca visto |
| bus_ddr_s6_v13 | — | 73 | 0.77 | 12 | 11.4 | 0 | 10.8 | 8.0 | nunca visto |
| bus_ddr_s6_v14 | — | 100 | 0.88 | 7 | 72.4 | 1 | 0.0 | 2.0 | nunca visto |
| bus_ddr_s6_v15 | — | 20 | 0.28 | 12 | 188.4 | 4 | 57.1 | 10.0 | nunca visto |
| bus_ddr_s6_v16 | — | 93 | 0.83 | 6 | 77.7 | 1 | 2.7 | 7.0 | nunca visto |
| bus_ddr_s6_v17 | **sí** | 87 | 0.72 | 8 | 7.2 | 0 | 12.7 | 8.0 | nunca visto |
| bus_ddr_s6_v18 | **sí** | 87 | 0.72 | 11 | 6.8 | 0 | 39.1 | 10.0 | nunca visto |
| bus_ddr_s6_v19 | **sí** | 100 | 0.9 | 6 | 4.7 | 0 | 0.0 | 4.0 | nunca visto |
| bus_ddr_s6_v20 | **sí** | 100 | 0.89 | 5 | 6.6 | 0 | 0.1 | 5.0 | nunca visto |
| bus_ddr_s6_v21 | — | 100 | 0.91 | 1 | 7.2 | 0 | 0.0 | 3.0 | nunca visto |
| bus_ddr_s6_v22 | **sí** | 100 | 0.9 | 5 | 5.7 | 0 | 0.0 | 2.0 | nunca visto |
| bus_ddr_s6_v23 | — | 100 | 0.89 | 9 | 38.5 | 1 | 2.6 | 6.0 | nunca visto |
| bus_ddr_s6_v24 | — | 93 | 0.77 | 10 | 37.3 | 1 | 0.0 | 5.0 | nunca visto |
| bus_ddr_s6_v25 | — | 93 | 0.78 | 7 | 81.9 | 1 | 0.1 | 5.0 | nunca visto |
| bus_ddr_s6_v26 | **sí** | 100 | 0.84 | 7 | 12.4 | 0 | 0.0 | 4.0 | nunca visto |
| bus_ddr_s6_v27 | **sí** | 93 | 0.78 | 6 | 6.0 | 0 | 1.2 | 5.0 | nunca visto |
| bus_sdr_s1_v01 | — | 20 | 0.36 | 55 | 32.5 | 2 | 1.2 | 6.0 | nunca visto |
| bus_sdr_s1_v02 | **sí** | 93 | 0.77 | 7 | 10.8 | 0 | 0.0 | 3.0 | nunca visto |
| bus_sdr_s1_v03 | **sí** | 80 | 0.72 | 7 | 9.3 | 0 | 0.2 | 4.0 | nunca visto |
| bus_sdr_s1_v04 | **sí** | 87 | 0.66 | 9 | 11.4 | 0 | 10.8 | 8.0 | entrenado |
| bus_sdr_s1_v05 | **sí** | 100 | 0.74 | 10 | 5.0 | 0 | 0.0 | 3.0 | nunca visto |
| bus_sdr_s1_v06 | **sí** | 100 | 0.76 | 6 | 5.4 | 0 | 0.0 | 4.0 | nunca visto |
| bus_sdr_s1_v07 | — | 60 | 0.56 | 26 | 54.1 | 1 | 0.0 | 4.0 | nunca visto |
| bus_sdr_s1_v08 | **sí** | 93 | 0.64 | 12 | 8.9 | 0 | 0.0 | 3.0 | nunca visto |
| bus_sdr_s1_v09 | — | 60 | 0.52 | 18 | 18.4 | 0 | 0.1 | 4.0 | nunca visto |
| bus_sdr_s1_v10 | — | 7 | 0.41 | 36 | 51.4 | 1 | 0.7 | 6.0 | nunca visto |
| bus_sdr_s1_v11 | — | 0 | 0.45 | 16 | 171.7 | 1 | 3.1 | 7.0 | entrenado |

**Decisión (Tesis 21):** DDR → **v18** (único apto con carga: 39 % lleno, la puerta se ve aunque vaya lleno; reserva v17).
SDR → propuesto **v08** (12 aperturas, gente subiendo a lo largo del video; reserva v05). Ningún SDR diurno nunca visto
va lleno con la puerta visible: SDR queda en congestión baja–media (limitación).

Hojas y mosaicos (no versionados): `data/flow_eval/puerta_revision/`. Regenerar: extraer con `door.py ffmpeg` en la torre
y calcular similitud + intervalos con `door.similarity` / `door.intervals` sobre cada raw.
