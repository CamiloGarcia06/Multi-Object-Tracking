# Prueba multicámara: evaluación UNA vez (Tesis 19a/19b/19c → 22, 18) — preparada el 2026-10-18

Videos de prueba, uno por cámara nueva: **SDM** videoTM_03(1), **DDR** bus_ddr_s6_v18, **SDR** bus_sdr_s1_v08
(DDL ya evaluada en el 02). Pregunta de la Tesis 22: ¿el factor de sesgo calibrado en DDL (03+07) vale en
las otras cámaras?

## Sellado ANTES del golden

Los eventos del sistema congelado y de la línea base se generaron sin mirar ningún golden, y sus
SHA-256 están en `configs/prueba_sellada.sha256` (los CSV de eventos y las puertas de door.py, versionados
con `git add -f`; los MOT de ByteTrack solo por hash, viven en `data/flow_eval/test_*` y en la torre).

| Video | Sistema (#27 + door.py + od) | Línea base sin tracking | MOT |
|---|---|---|---|
| 03(1) | `data/flow_eval/test03_1/ev.csv` | `…/ev_sin_tracking.csv` | `test03_1/base.txt` (13-10) |
| DDR v18 | `data/flow_eval/test_bus_ddr_s6_v18/ev.csv` | `…/ev_sin_tracking.csv` | `bytetrack.txt` (18-10) |
| SDR v08 | `data/flow_eval/test_bus_sdr_s1_v08/ev.csv` | `…/ev_sin_tracking.csv` | `bytetrack.txt` (18-10) |

- Sistema: ByteTrack `bytetrack_buffer90_match09` (`diag_bytetrack.py run`) sobre las detecciones del
  campeón con la ROI de la cámara, `events.py events` (regla od) con la puerta de door.py.
- Línea base: `baseline.py events --roi` (mismas detecciones, ROI y puerta).
- Factores, fijados en 03+07 antes de la prueba: sistema `configs/calibracion.yaml` (0,68/0,62); línea base
  `configs/calibracion_sin_tracking.yaml` (0,56/0,52, IC95 por bootstrap de aperturas; formaliza el ajuste
  a mano del 17-10).
- Control: `evaluar_prueba.sh videoTM_02 data/flow_eval/test02` reproduce la Tabla I del 02
  (−28/−39 %, corregido +7/−1 %).

## Cuando Camilo termine cada golden de eventos

1. Exportar sus jobs en la torre: `bash exportar_job.sh <jobs…>` en `data/cvat_import/eventos_<video>/`
   y traer `export/` al portátil.
2. CSV del golden, con las MISMAS aperturas de golden_eventos.py (golden reducido: sin `--ninguno`):
   - DDR: `uv run scripts/flow/golden_csv.py build --export …/export --aperturas 9205-9295,12295-12520,13090-13240,19640-19860,26235-26315 --out data/flow_golden/bus_ddr_s6_v18.csv`
   - SDR: `… --aperturas 4600-4765,6240-6310,11415-11590,19685-19805,22190-22270 --out data/flow_golden/bus_sdr_s1_v08.csv`
   - 03(1): las aperturas de la tarea 11 de CVAT.
3. `bash scripts/flow/evaluar_prueba.sh <video> [DIR]` → `docs/resultados-<video>.md` (sin corregir,
   corregido sistema, corregido línea base). Comprueba el sello y se para si algo cambió.

## Decisiones

- Golden reducido = solo las aperturas elegidas; los falsos de door.py fuera de ellas no se penalizan aquí
  (su precisión está medida aparte en `docs/criba-door-open.md`).
- No se reajusta nada con estos videos: ni curvas, ni door.py, ni factores.
