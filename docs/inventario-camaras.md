# Inventario por cámara de los 480 videos de Bus (Tesis 20) — 17-10

Generado con `scripts/flow/inventario_camaras.py ~/videos/bus OUT` en la torre (1 frame/s, yolo26x-min5, conf 0,25,
NMS 0,6, frame entero). Datos por video en `data/drive/inventario_camaras.jsonl`; miniaturas en la torre
`~/videos/bus/_inventario/<video>.jpg`.

Criterios:
- **Luz** (luminancia mediana): noche < 20 ≤ penumbra < 60 ≤ día. La distribución es bimodal (157 videos < 10, el grueso en 70–110).
- **Congestión** (% de segundos con ≥ 8 cabezas), anclada en los videos ya evaluados: 07 = 5,6 % y 03 = 6,6 % (baja),
  03(1) = 13,1 % (media), 02 = 34,9 % (alta) → baja < 10 ≤ media < 25 ≤ alta.
- Las cabezas las cuenta el campeón: en SDR/SDM (otro encuadre, más desenfoque) probablemente cuenta de menos,
  así que el nivel no es del todo comparable entre cámaras.

## Por cámara

| cámara | videos | día | penumbra | noche | día nunca vistos: baja / media / alta |
|---|---|---|---|---|---|
| DDL | 151 | 85 | 8 | 58 | 54 / 11 / 12 |
| DDR | 195 | 111 | 10 | 74 | 70 / 18 / 20 |
| SDM | 108 | 59 | 7 | 42 | 43 / 5 / 9 |
| SDR | 26 | 11 | 1 | 14 | 9 / 0 / 0 |

## Por secuencia

| cámara | sec. | videos | día | ya usados (nombre antiguo) |
|---|---|---|---|---|
| DDL | 1 | 4 | 2 | — |
| DDL | 2 | 2 | 0 | — |
| DDL | 3 | 19 | 9 | 03, 04(1), 05(1), 07, 10, 13 |
| DDL | 4 | 25 | 14 | 18 |
| DDL | 5 | 21 | 13 | — |
| DDL | 6 | 20 | 15 | 02, 17 |
| DDL | 7 | 32 | 16 | 14 |
| DDL | 8 | 28 | 16 | 16, 18(1) |
| DDR | 1 | 5 | 3 | — |
| DDR | 2 | 22 | 10 | — |
| DDR | 3 | 36 | 19 | 29 |
| DDR | 4 | 31 | 20 | — |
| DDR | 5 | 23 | 18 | 05, 08, 16(1) |
| DDR | 6 | 38 | 19 | — |
| DDR | 7 | 6 | 2 | — |
| DDR | 8 | 34 | 20 | 04 |
| SDM | 1 | 4 | 1 | — |
| SDM | 2 | 25 | 18 | 10(1) |
| SDM | 3 | 41 | 20 | — |
| SDM | 4 | 38 | 20 | 03(1) |
| SDR | 1 | 26 | 11 | 04(2), 11, 12 |

## Candidatos DDR (día, nunca vistos, por congestión)

| video | luz | cabezas p50 / p90 / máx | % lleno | nivel | secuencia |
|---|---|---|---|---|---|
| bus_ddr_s1_v04.mkv | 64.0 | 10 / 12 / 15 | 78.7 | alta | limpia |
| bus_ddr_s8_v20.mkv | 88.0 | 8 / 11 / 14 | 60.1 | alta | con videos de entrenamiento |
| bus_ddr_s6_v15.mkv | 108.0 | 8 / 10 / 15 | 57.1 | alta | limpia |
| bus_ddr_s4_v16.mkv | 87.0 | 8 / 10 / 13 | 50.6 | alta | limpia |
| bus_ddr_s3_v07.mkv | 70.0 | 7 / 10 / 14 | 43.3 | alta | limpia |
| bus_ddr_s2_v09.mkv | 106.0 | 7 / 10 / 12 | 41.6 | alta | limpia |
| bus_ddr_s6_v10.mkv | 103.5 | 3 / 11 / 14 | 39.9 | alta | limpia |
| bus_ddr_s8_v03.mkv | 79.0 | 1 / 12 / 15 | 39.2 | alta | con videos de entrenamiento |
| bus_ddr_s6_v18.mkv | 93.5 | 6 / 10 / 14 | 39.1 | alta | limpia |
| bus_ddr_s2_v01.mkv | 99.0 | 7 / 9 / 13 | 38.6 | alta | limpia |

## Candidatos SDR (día, nunca vistos, por congestión)

| video | luz | cabezas p50 / p90 / máx | % lleno | nivel | secuencia |
|---|---|---|---|---|---|
| bus_sdr_s1_v01.mkv | 109.0 | 5 / 6 / 10 | 1.2 | baja | con videos de entrenamiento |
| bus_sdr_s1_v10.mkv | 102.0 | 3 / 6 / 8 | 0.7 | baja | con videos de entrenamiento |
| bus_sdr_s1_v03.mkv | 92.0 | 2 / 4 / 9 | 0.2 | baja | con videos de entrenamiento |
| bus_sdr_s1_v09.mkv | 89.0 | 2 / 4 / 10 | 0.1 | baja | con videos de entrenamiento |
| bus_sdr_s1_v02.mkv | 99.0 | 1 / 3 / 6 | 0.0 | baja | con videos de entrenamiento |
| bus_sdr_s1_v05.mkv | 82.0 | 2 / 3 / 6 | 0.0 | baja | con videos de entrenamiento |
| bus_sdr_s1_v06.mkv | 98.0 | 2 / 4 / 6 | 0.0 | baja | con videos de entrenamiento |
| bus_sdr_s1_v07.mkv | 106.0 | 3 / 4 / 6 | 0.0 | baja | con videos de entrenamiento |
| bus_sdr_s1_v08.mkv | 86.0 | 2 / 3 / 6 | 0.0 | baja | con videos de entrenamiento |
