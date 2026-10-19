# Auditoría del dataset del detector (`bus_head_v5_min5`) — 17-10

Generado con `scripts/dataset/auditar_etiquetas.py data/bus_head_v5_min5 data/auditoria_v5_min5` (torre).
Etiquetas vs detecciones del campeón (conf 0,10, NMS 0,6, IoU ≥ 0,3). El campeón se entrenó con estas
imágenes: las discrepancias son una cota inferior; sirven para comparar videos entre sí.

| video (cámara) | imgs | etiquetas | % etiquetas que el detector NO cubre | dets ≥0,5 sin etiqueta /100 etiq. | % imgs con cabeza sin anotar |
|---|---|---|---|---|---|
| s03 = videoTM_10 (DDL s3) | 602 | 9.102 | 0,1 | 0,5 | 7,0 |
| videoTM_14 (DDL s7) | 84 | 626 | 0,5 | 1,4 | 10,7 |
| v04 = videoTM_04 (DDR s8) | 45 | 664 | **6,5** | 3,2 | **40,0** |
| v12 (SDR s1) | 45 | 325 | 1,2 | 4,0 | 26,7 |
| v16 (DDL s8) | 45 | 425 | 1,4 | 3,5 | 26,7 |
| v16b = 16(1) (DDR s5) | 42 | 293 | 2,4 | 4,1 | 26,2 |
| v04_2 = 04(2) (SDR s1) | 40 | 280 | 1,4 | 2,9 | 20,0 |
| v04_1 = 04(1) (DDL s3) | 38 | 241 | 2,1 | 2,5 | 15,8 |
| v05_1 = 05(1) (DDL s3) | 36 | 241 | 0,4 | 1,2 | 8,3 |
| v05 = videoTM_05 (DDR s5) | 36 | 327 | 1,2 | 3,1 | 25,0 |
| v11 (SDR s1) | 36 | 237 | 3,0 | 0,8 | 5,6 |
| v18S08 = 18(1) (DDL s8) | 36 | 260 | 0,4 | 3,1 | 16,7 |
| v10b = 10(1) (SDM s2) | 22 | 125 | 1,6 | 0,0 | 0,0 |

Lectura:
- El s03 (58 % de las imágenes, 72 % de las cajas, frames cada 3 → casi duplicados) está **memorizado**:
  el detector reproduce sus etiquetas casi al 100 %, así que esta auditoría no puede juzgar su calidad.
- En los videos minoritarios el detector falla incluso **sobre sus propias imágenes de entrenamiento**
  (v04: 6,5 % de etiquetas sin cubrir, cabezas claras): síntoma de desbalance, el modelo se ajustó al s03.
- Las detecciones sin etiqueta (rojo en las hojas `peores_<video>.jpg`) son sobre todo cabezas parciales
  en el borde del fisheye: criterio de anotación no uniforme entre videos.
