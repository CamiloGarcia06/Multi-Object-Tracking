# Línea base sin tracking en la prueba (Tesis 18)

Mismas detecciones (campeón), ROI y puerta (door.py) para los dos; eventos sellados antes del golden (`configs/prueba_sellada.sha256`). Corregido = contado / factor propio de cada método fijado en 03+07 (sistema 0,68/0,62; sin tracking 0,56/0,52). Generado por `scripts/flow/linea_base.py`.


## Por video

| video | método | dir | real | contado | recall | precisión | error | corregido |
|---|---|---|---|---|---|---|---|---|
| DDL videoTM_02 | #27 ByteTrack | sube | 18 | 13 | 0.61 | 0.85 | -28% | +7% |
| DDL videoTM_02 | #27 ByteTrack | baja | 41 | 25 | 0.56 | 0.92 | -39% | -1% |
| DDL videoTM_02 | sin tracking | sube | 18 | 20 | 0.56 | 0.50 | +11% | +99% |
| DDL videoTM_02 | sin tracking | baja | 41 | 27 | 0.49 | 0.74 | -34% | +26% |
| SDM videoTM_03_1 | #27 ByteTrack | sube | 54 | 13 | 0.22 | 0.92 | -76% | -64% |
| SDM videoTM_03_1 | #27 ByteTrack | baja | 11 | 8 | 0.73 | 1.00 | -27% | +18% |
| SDM videoTM_03_1 | sin tracking | sube | 54 | 14 | 0.22 | 0.86 | -74% | -54% |
| SDM videoTM_03_1 | sin tracking | baja | 11 | 8 | 0.45 | 0.62 | -27% | +39% |
| DDR bus_ddr_s6_v18 | #27 ByteTrack | sube | 4 | 3 | 0.75 | 1.00 | -25% | +11% |
| DDR bus_ddr_s6_v18 | #27 ByteTrack | baja | 17 | 14 | 0.82 | 1.00 | -18% | +34% |
| DDR bus_ddr_s6_v18 | sin tracking | sube | 4 | 4 | 0.50 | 0.50 | +0% | +79% |
| DDR bus_ddr_s6_v18 | sin tracking | baja | 17 | 13 | 0.65 | 0.85 | -24% | +46% |
| SDR bus_sdr_s1_v08 | #27 ByteTrack | sube | 16 | 8 | 0.50 | 1.00 | -50% | -26% |
| SDR bus_sdr_s1_v08 | #27 ByteTrack | baja | 18 | 13 | 0.67 | 0.92 | -28% | +17% |
| SDR bus_sdr_s1_v08 | sin tracking | sube | 16 | 6 | 0.31 | 0.83 | -62% | -33% |
| SDR bus_sdr_s1_v08 | sin tracking | baja | 18 | 13 | 0.72 | 1.00 | -28% | +38% |

## Agregado de las cuatro pruebas (error neto)

| método | dir | real | contado | error | corregido |
|---|---|---|---|---|---|
| #27 ByteTrack | sube | 92 | 37 | -60% | -41% |
| #27 ByteTrack | baja | 87 | 60 | -31% | +12% |
| sin tracking | sube | 92 | 44 | -52% | -14% |
| sin tracking | baja | 87 | 61 | -30% | +34% |

## Media del |error corregido| por video

Sin compensación entre videos (cada video cuenta igual).

| método | dir | media | 02, 03(1), DDR, SDR |
|---|---|---|---|
| #27 ByteTrack | sube | 27% | 7%, 64%, 11%, 26% |
| #27 ByteTrack | baja | 18% | 1%, 18%, 34%, 17% |
| sin tracking | sube | 66% | 99%, 54%, 79%, 33% |
| sin tracking | baja | 37% | 26%, 39%, 46%, 38% |

## Por evento: recall, precisión y F1 de las cuatro pruebas

Aciertos emparejados con el golden (tolerancia 10 frames). Diferencia positiva = el tracking acierta más. IC95 por bootstrap de aperturas.

| dir | recall sist. | precisión sist. | F1 sist. | recall s/t | precisión s/t | F1 s/t | ΔF1 | IC95 | aperturas |
|---|---|---|---|---|---|---|---|---|---|
| sube | 0.37 | 0.92 | 0.53 | 0.32 | 0.66 | 0.43 | +0.10 | -0.00 a +0.37 | 25 |
| baja | 0.66 | 0.95 | 0.78 | 0.56 | 0.80 | 0.66 | +0.11 | -0.03 a +0.25 | 25 |

## Lectura (18-10-2026)

1. **Por evento, el tracking acierta más en las dos direcciones**: F1 0,53 frente a 0,43 en subidas y 0,78 frente a
   0,66 en bajadas (ΔF1 +0,10 y +0,11). La ventaja es sobre todo de **precisión** (0,92 frente a 0,66; 0,95 frente a
   0,80): sin tracking se cuentan cruces falsos o la misma persona dos veces. El recall también sube (0,37 frente a
   0,32; 0,66 frente a 0,56). Con 25 aperturas los IC95 de ΔF1 rozan el cero (−0,00 a +0,37; −0,03 a +0,25): la mejora
   es consistente pero no significativa al 95 %.
2. **Corregido, el tracking se equivoca menos en 7 de 8 casos** (video × dirección). Media del |error| por video:
   27 % frente a 66 % en subidas y 18 % frente a 37 % en bajadas. La excepción es SDM subidas (−64 % frente a −54 %),
   donde los dos dependen de la misma puerta de door.py, que se corta en la parada llena.
3. **El error neto del total engaña.** Sin tracking, las subidas agregadas corregidas quedan en −14 % (frente a −41 %
   del sistema), pero porque sus falsos positivos tapan las pérdidas: en el 02 y en DDR cuenta tantas subidas como
   las reales con precisión 0,50 (la mitad de lo que cuenta no existe). Por eso la comparación se hace por evento.
4. Es coherente con DDL en validación (07: sin tracking −70/−62 % frente a −35/−41 % del #27 con el golden viejo).

**Cautelas.** Goldens reducidos (25 aperturas en total; 53 de las 92 subidas en una parada de SDM). La puerta es la
misma para los dos métodos, así que su fallo no se refleja en la diferencia entre ellos.
