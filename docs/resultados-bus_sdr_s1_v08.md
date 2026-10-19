# Resultados de prueba: bus_sdr_s1_v08 (2026-10-18)

Evaluado UNA vez. Eventos sellados antes del golden (configs/prueba_sellada.sha256).
Golden: `data/flow_golden/bus_sdr_s1_v08.csv`. Puerta del sistema: door.py (`data/flow_videos/puerta_abierta_bus_sdr_s1_v08.json`).

## Sin corregir

| sistema | apertura | dir | real | contado | error | error % | recall | precisión |
|---|---|---|---|---|---|---|---|---|
| #27 ByteTrack | 4600–4765 | sube | 4 | 2 | -2 | -50% | 0.50 | 1.00 |
| #27 ByteTrack | 4600–4765 | baja | 10 | 9 | -1 | -10% | 0.90 | 1.00 |
| #27 ByteTrack | 6240–6310 | sube | 1 | 1 | +0 | +0% | 1.00 | 1.00 |
| #27 ByteTrack | 6240–6310 | baja | 2 | 0 | -2 | -100% | 0.00 | — |
| #27 ByteTrack | 11415–11590 | sube | 7 | 3 | -4 | -57% | 0.43 | 1.00 |
| #27 ByteTrack | 11415–11590 | baja | 2 | 2 | +0 | +0% | 0.50 | 0.50 |
| #27 ByteTrack | 19685–19805 | sube | 3 | 2 | -1 | -33% | 0.67 | 1.00 |
| #27 ByteTrack | 19685–19805 | baja | 2 | 1 | -1 | -50% | 0.50 | 1.00 |
| #27 ByteTrack | 22190–22270 | sube | 1 | 0 | -1 | -100% | 0.00 | — |
| #27 ByteTrack | 22190–22270 | baja | 2 | 1 | -1 | -50% | 0.50 | 1.00 |
| #27 ByteTrack | TOTAL | sube | 16 | 8 | -8 | -50% | 0.50 | 1.00 |
| #27 ByteTrack | TOTAL | baja | 18 | 13 | -5 | -28% | 0.67 | 0.92 |
| sin tracking | 4600–4765 | sube | 4 | 1 | -3 | -75% | 0.25 | 1.00 |
| sin tracking | 4600–4765 | baja | 10 | 8 | -2 | -20% | 0.80 | 1.00 |
| sin tracking | 6240–6310 | sube | 1 | 1 | +0 | +0% | 0.00 | 0.00 |
| sin tracking | 6240–6310 | baja | 2 | 1 | -1 | -50% | 0.50 | 1.00 |
| sin tracking | 11415–11590 | sube | 7 | 3 | -4 | -57% | 0.43 | 1.00 |
| sin tracking | 11415–11590 | baja | 2 | 2 | +0 | +0% | 1.00 | 1.00 |
| sin tracking | 19685–19805 | sube | 3 | 0 | -3 | -100% | 0.00 | — |
| sin tracking | 19685–19805 | baja | 2 | 1 | -1 | -50% | 0.50 | 1.00 |
| sin tracking | 22190–22270 | sube | 1 | 1 | +0 | +0% | 1.00 | 1.00 |
| sin tracking | 22190–22270 | baja | 2 | 1 | -1 | -50% | 0.50 | 1.00 |
| sin tracking | TOTAL | sube | 16 | 6 | -10 | -62% | 0.31 | 0.83 |
| sin tracking | TOTAL | baja | 18 | 13 | -5 | -28% | 0.72 | 1.00 |

## Corregido: sistema (factor 03+07)

| sistema | dir | real | contado | error % | corregido | IC95 | error % corr. |
|---|---|---|---|---|---|---|---|
| #27 ByteTrack | sube | 16 | 8 | -50% | 11.8 | 8.5–17.1 | -26% |
| #27 ByteTrack | baja | 18 | 13 | -28% | 21.1 | 17.8–25.1 | +17% |

## Corregido: línea base (factor 03+07)

| sistema | dir | real | contado | error % | corregido | IC95 | error % corr. |
|---|---|---|---|---|---|---|---|
| sin tracking | sube | 16 | 6 | -62% | 10.7 | 5.6–17.6 | -33% |
| sin tracking | baja | 18 | 13 | -28% | 24.9 | 17.8–32.2 | +38% |

## Lectura (18-10-2026)

**En SDR el factor de DDL sí vale.** Sin corregir: subidas −50 % (recall 0,50), bajadas −28 % (recall 0,67),
precisión 1,00/0,92: un sesgo del mismo signo y tamaño que en DDL. Corregido: subidas −26 % y bajadas +17 %, y los
dos IC95 contienen el valor real (8,5–17,1 frente a 16; 17,8–25,1 frente a 18). door.py acierta las 5 paradas del
golden (en 11.415–11.590 abre en 11.308, con el pasajero contra la puerta: ver `docs/criba-door-open.md`).

**Cautelas.** Golden REDUCIDO de 34 eventos (16 suben / 18 bajan) en 5 paradas, congestión baja (ningún SDR diurno
nunca visto va lleno con la puerta visible). Los sentados no se anotan en el golden de tracking; en eventos, en principio, no
cuentan porque no nacen en la zona de puerta (sin comprobar caso a caso). No se reajusta nada con este video.
