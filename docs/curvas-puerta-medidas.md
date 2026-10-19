# Curvas de puerta medidas con detecciones — las 4 cámaras del bus (2026-10-18)

Método del 07 (`scripts/flow/medir_curvas.py margen`): con la puerta CERRADA (±150 f lejos de
toda apertura de door.py) todas las cabezas son de pasajeros que van dentro. Bien puestas, ninguna
pasa la curva **exterior** y la **interior** va pegada a las que más se acercan a la puerta.
Detecciones del campeón (yolo26x-min5 + NMS post-hoc 0,6), conf ≥ 0,3. Distancia a la interior en
px, positiva hacia el pasillo; percentil 1 = la cabeza de dentro más cercana a la puerta.

| Cámara | Video | Cabezas (cerrada) | Pasan la exterior | Pasan la interior | p1 dist. interior | Curvas |
|---|---|---|---|---|---|---|
| DDL | 07 (desarrollo) | 94.121 | 2 | 1.023 (+2.875 detección fija en el vidrio) | −3,6 | Camilo, 11-10 |
| DDL | 03 (validación) | 71.283 | 1 | 939 | −2,4 | copia del 07 |
| DDL | 02 (prueba) | 99.094 | 1 | 594 | +3,7 | copia del 07 |
| SDM | 03(1) (prueba) | 13.584 | 13 | 225 | −12,9 | Camilo, 12-10 |
| DDR | s6_v18 (prueba) | 118.822 | 1 | 8 | +20,4 | medidas, 18-10 |
| SDR | s1_v08 (prueba) | 40.633 | 7 | 10 | +11,1 | medidas, 18-10 |

- **DDL y SDM: sin cambios.** Exterior limpia e interior pegada a las cabezas de dentro (p1 entre
  −13 y +4 px). Los cruces de la exterior del 03(1) sin filtrar (1.035) son una detección falsa fija en
  la pegatina "DE PESO" (x≈20, y≈40; 1.083 frames), como la del vidrio del 07 (x≈528, y≈250): no se
  mueven, no generan eventos. Aquí están ya descontadas.
- **DDR y SDR: ajustadas.** La primera propuesta (parábola al borde del vidrio +8/+32 px, copiando la
  posición del 03(1)) dejaba 35–50 px de holgura sobre el andén (p1 ≈ +50/+41); se movieron +30 px
  hacia el pasillo y la exterior a 40 px de la interior, como el 07.
- Con el bus lleno, quien va apoyado en la puerta tiene la cabeza sobre el vidrio: por eso las curvas
  van por encima del vidrio y no sobre el umbral del piso.
- Mapas de densidad (azul = cerrada, rojo = abierta): `medir_curvas.py mapa`; los de DDR/SDR en
  `data/roi_fondos/curvas_medidas_ddr_sdr.png` (no versionado).
