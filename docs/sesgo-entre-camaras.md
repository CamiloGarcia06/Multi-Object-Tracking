# Sesgo entre cámaras (Tesis 22)

Sistema congelado (#27 ByteTrack + door.py + regla od). Factor = contado / real, IC95 por bootstrap de aperturas. Generado por `scripts/flow/sesgo_camaras.py`.


## Factor propio de cada cámara

DDL junta validación (03, 07) y prueba (02). Si el IC de una cámara no toca el de DDL, el sesgo es distinto.

| cámara | dir | real | contado | factor | IC95 | aperturas | fuente |
|---|---|---|---|---|---|---|---|
| DDL | sube | 52 | 36 | 0.69 | 0.54–0.88 | 31 | propia |
| DDL | baja | 106 | 65 | 0.61 | 0.52–0.73 | 31 | propia |
| SDM | sube | 54 | 13 | 0.24 | 0.23–1.00 | 4 | propia |
| SDM | baja | 11 | 8 | 0.73 | 0.70–1.00 | 4 | propia |
| DDR | sube | 4 | 3 | 0.82 | 0.64–0.93 | 5 | conjunta (pocos eventos) |
| DDR | baja | 17 | 14 | 0.82 | 0.64–0.93 | 5 | propia |
| SDR | sube | 16 | 8 | 0.50 | 0.38–0.67 | 5 | propia |
| SDR | baja | 18 | 13 | 0.72 | 0.30–0.89 | 5 | propia |

## Videos de prueba: factor de DDL frente a leave-one-camera-out

LOCO = factor estimado con las otras tres cámaras (post-hoc). «IC ok» = el valor real cae en el intervalo del conteo corregido.

| video | dir | real | contado | error | factor DDL | error | IC ok | LOCO | error | IC ok |
|---|---|---|---|---|---|---|---|---|---|---|
| DDL videoTM_02 | sube | 18 | 13 | -28% | 19.2 (13.9–27.7) | +7% | sí | 40.1 (18.6–51.6) | +123% | **no** |
| DDL videoTM_02 | baja | 41 | 25 | -39% | 40.6 (34.2–48.3) | -1% | sí | 32.9 (29.0–41.7) | -20% | sí |
| SDM videoTM_03_1 | sube | 54 | 13 | -76% | 19.2 (13.9–27.7) | -64% | **no** | 19.9 (16.4–24.3) | -63% | **no** |
| SDM videoTM_03_1 | baja | 11 | 8 | -27% | 13.0 (10.9–15.4) | +18% | sí | 12.3 (10.7–14.3) | +11% | sí |
| DDR bus_ddr_s6_v18 | sube | 4 | 3 | -25% | 4.4 (3.2–6.4) | +11% | sí | 6.4 (4.0–9.1) | +61% | sí |
| DDR bus_ddr_s6_v18 | baja | 17 | 14 | -18% | 22.7 (19.1–27.0) | +34% | **no** | 22.0 (19.1–25.7) | +29% | **no** |
| SDR bus_sdr_s1_v08 | sube | 16 | 8 | -50% | 11.8 (8.5–17.1) | -26% | sí | 16.9 (9.6–24.7) | +6% | sí |
| SDR bus_sdr_s1_v08 | baja | 18 | 13 | -28% | 21.1 (17.8–25.1) | +17% | sí | 20.0 (17.5–23.2) | +11% | sí |

Factores LOCO (sube / baja) usados para cada cámara:

| cámara fuera | sube | baja |
|---|---|---|
| DDL | 0.32 (0.25–0.70) | 0.76 (0.60–0.86) |
| SDM | 0.65 (0.54–0.79) | 0.65 (0.56–0.75) |
| DDR | 0.47 (0.33–0.76) | 0.64 (0.55–0.73) |
| SDR | 0.47 (0.32–0.83) | 0.65 (0.56–0.74) |

## Agregado de las cuatro pruebas

Suma de los cuatro videos de prueba (umbral APC de la Tesis 10: ≤ 5 % agregado). «error neto» deja que los errores de signo contrario se compensen; «error absoluto» = Σ|estimado − real| / Σ real, sin compensación.

| corrección | dir | real | estimado | error neto | error absoluto |
|---|---|---|---|---|---|
| sin corregir | sube | 92 | 37.0 | -60% | 60% |
| sin corregir | baja | 87 | 60.0 | -31% | 31% |
| factor DDL | sube | 92 | 54.7 | -41% | 44% |
| factor DDL | baja | 87 | 97.5 | +12% | 13% |
| LOCO | sube | 92 | 83.3 | -9% | 65% |
| LOCO | baja | 87 | 87.1 | +0% | 19% |

## Diagnóstico post-hoc del 03(1): la puerta del golden en lugar de door.py

Mismos tracks (`test03_1/base.txt`, que reproduce byte a byte el `ev.csv` sellado) y misma regla od. Solo se cambia
la puerta de la 4.ª parada: 22.336–23.475 (golden) en vez de 22.336–22.519 (door.py). Ficheros en
`data/flow_eval/diag03_1/`. No sustituye al resultado sellado: separa la parte de door.py de la del tracker.

| puerta | suben (real 54) | error | corregido DDL | IC95 | bajan (real 11) | corregido DDL |
|---|---|---|---|---|---|---|
| door.py (sellado) | 13 | −76 % | 19,2 (−64 %) | 13,9–27,7 **no** | 8 | 13,0 (+18 %) |
| golden | 31 | −43 % | 45,8 (−15 %) | 33,1–66,1 sí | 9 | 14,6 (+33 %) |

De las 41 subidas perdidas, **18 son de door.py** (puerta tapada) y **23 del tracking/detector**. Con la puerta bien
vista, el recall de subidas de SDM (0,54) es el de DDL (0,59–0,62) y el factor de DDL vuelve a valer.

## Lectura (18-10-2026)

1. **El factor de DDL vale en la mayoría de casos.** En 6 de los 8 casos (video × dirección), el valor real cae
   dentro del IC95 del conteo corregido. Los dos que fallan tienen causas distintas y conocidas:
   - **SDM subidas (−64 %):** door.py da la puerta por cerrada cuando el bus va lleno y la gente la tapa. Con la
     puerta bien vista queda en −15 %, dentro del IC. No es un sesgo distinto del tracker: es un fallo de door.py.
   - **DDR bajadas (+34 %):** en DDR el sistema pierde MENOS (factor 0,82 frente a 0,61 de DDL; los IC95 apenas se
     tocan, 0,64–0,93 frente a 0,52–0,73), y el factor de DDL sobrecorrige.
2. **Un factor global sin la cámara (LOCO) no mejora: empeora.** Su error neto agregado (−9 % / +0 %) es una
   compensación: sobrecorrige el 02 (+123 % en subidas, por el factor 0,32 que arrastra la parada llena de SDM) e
   infracorrige el 03(1). En error absoluto, LOCO 65 % / 19 % frente a 44 % / 13 % del factor de DDL. Juntar
   cámaras mete en el factor el fallo de door.py de SDM.
3. **Un factor por cámara no se puede estimar bien con estos datos.** Cada cámara nueva tiene 4–5 aperturas, el
   bootstrap por aperturas da IC muy anchos (SDM subidas 0,23–1,00) y estimarlo con el mismo video de prueba sería
   evaluar con los datos de ajuste.
4. **Ninguna corrección llega al umbral APC agregado (≤ 5 %, Tesis 10).** Con el factor de DDL el error absoluto
   agregado es 44 % en subidas y 13 % en bajadas. Sin SDM (con door.py, como está sellado), las subidas del 02, DDR y
   SDR quedan en +7 %, +11 % (4 eventos) y −26 %.

**Propuesta para el artículo:** mantener el factor de DDL fijado antes de la prueba (sin reajustar), declarar que el
sesgo depende de la cámara (DDR) y que door.py falla con el bus lleno (SDM, igual que en el 02), con el diagnóstico de
la puerta del golden como cuantificación: 18 de las 41 subidas perdidas en SDM son de door.py. Trabajo futuro: un
detector de puerta robusto a la oclusión, y calibrar por cámara con aperturas que no sean de prueba.

**Cautelas.** Goldens reducidos (4–5 aperturas por cámara nueva; 53 de las 54 subidas de SDM en una parada; 4
subidas en DDR). Los IC por bootstrap con tan pocas aperturas son orientativos. LOCO y el diagnóstico de la puerta
son post-hoc: usan videos de prueba ya evaluados.
