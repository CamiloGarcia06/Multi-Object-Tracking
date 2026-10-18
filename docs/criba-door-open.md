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

## Revisión de door.py en los videos de prueba (Tesis 14a/14b, 2026-10-18)

Cada intervalo de door.py revisado a ojo en la zona de la puerta (un frame cada 15 f, ±90 f), y
búsqueda de aperturas perdidas: tramos con similitud suavizada < 0,5 durante ≥ 1 s fuera de toda
apertura, más el tramo lleno del v18 (frames 1–9.000, un frame cada 60 f).

| Video | Intervalos door.py | Reales | Falsos | Candidatas a perdida revisadas | Perdidas | Precisión | Recall |
|---|---|---|---|---|---|---|---|
| DDR s6_v18 | 11 | 11 | 0 | 3 + minutos 0–5 | 0 | 1,00 | 1,00 |
| SDR s1_v08 | 12 | 11 | 1 (13.690) | 9 | 0 | 0,92 | 1,00 |

- **Falso del v08 (13.690–13.738):** pasajero de pie contra la puerta cerrada + bus rojo por el vidrio.
- **Candidatas descartadas:** todas son oclusiones con la puerta CERRADA (la junta de las hojas sigue
  visible): pasajero apoyado en la puerta (DDR 9.481–10.990 y 13.384; SDR 11.977–12.790 y 21.937) o un bus
  rojo del SITP detenido al lado (SDR 6.673–7.246). door.py hizo bien en no contarlas.
- DDR v18 minutos 0–5 (bus lleno): puerta cerrada todo el tramo; el bus no para.
- Límites: el recall cuenta solo lo que la búsqueda pudo ver (no es una revisión frame a frame del video
  entero). En la 11.308 del v08, door.py empieza ~4 s antes por un pasajero contra la puerta (real desde
  ~11.420; el golden de eventos usa los límites revisados a ojo).
