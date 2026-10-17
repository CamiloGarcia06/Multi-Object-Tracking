# Inventario del Drive por cámara (tarea 13, 17-10-2026)

Listado de `videos tesis/` en el Drive de Camilo (conector de Google Drive), cruzado con los 24 videos de
`~/videos/` de la torre **por tamaño exacto en bytes**: los nombres (`videoTM_01.mkv`…) se repiten en cada
carpeta, así que el nombre no identifica el video. Los 24 de la torre tienen pareja en el Drive. Listado completo
(ruta, nombre, bytes, id de Drive) en `data/drive/inventario_drive.json`.

**Tamaño:** 1.070 videos, 106 GB. **Bus: 480 videos (45 GB)**, de los que la torre tiene 22. Station: 590 (61 GB),
de los que la torre tiene 2 (intelC1, intelC36), la mitad son vídeos de profundidad (RGBD).

Mediana de 92 MB por video de Bus; 63 pesan menos de 30 MB, como los nocturnos de la torre (22–43 MB): el
video oscuro comprime más. Es una pista, no una clasificación: hay que mirarlos.

## Bus: estado por cámara

| Cámara | Videos | En la torre | Geometría + ROI | Golden de tracking | Golden de eventos |
|---|---|---|---|---|---|
| DoubleDoorCameraLeft | 151 | 12: videoTM_02.mkv, videoTM_03.mkv, videoTM_04(1).mkv, videoTM_05(1).mkv, videoTM_07.mkv, videoTM_10.mkv, videoTM_13.mkv, videoTM_14.mkv, videoTM_16.mkv, videoTM_17.mkv, videoTM_18(1).mkv, videoTM_18.mkv | ✅ 07/03/02 | ✅ tm07_a (baja), tm02_a (alta) | ✅ 07, 03, 02 |
| SingleDoorMiddle | 108 | 2: videoTM_03(1).mkv, videoTM_10(1).mkv | ✅ 03(1) | ✅ tm03_1_a (media) | ⏳ 03(1) (tarea 5) |
| DoubleDoorCameraRight | 195 | 5: videoTM_04.mkv, videoTM_05.mkv, videoTM_08.mkv, videoTM_16(1).mkv, videoTM_29.mkv | ❌ | ❌ | ❌ |
| SingleDoorRear | 26 | 3: videoTM_04(2).mkv, videoTM_11.mkv, videoTM_12.mkv | ❌ | ❌ | ❌ |

## Bus: por secuencia

| Carpeta | Videos | GB | En la torre |
|---|---|---|---|
| DoubleDoorCameraLeft/Sequence1 | 4 | 0.4 | — |
| DoubleDoorCameraLeft/Sequence2 | 2 | 0.0 | — |
| DoubleDoorCameraLeft/Sequence3 | 19 | 2.0 | videoTM_03.mkv, videoTM_04(1).mkv, videoTM_05(1).mkv, videoTM_07.mkv, videoTM_10.mkv, videoTM_13.mkv |
| DoubleDoorCameraLeft/Sequence4 | 25 | 2.4 | videoTM_18.mkv |
| DoubleDoorCameraLeft/Sequence5 | 21 | 2.3 | — |
| DoubleDoorCameraLeft/Sequence6 | 20 | 2.4 | videoTM_02.mkv, videoTM_17.mkv |
| DoubleDoorCameraLeft/Sequence7 | 32 | 2.8 | videoTM_14.mkv |
| DoubleDoorCameraLeft/Sequence8 | 28 | 2.9 | videoTM_16.mkv, videoTM_18(1).mkv |
| DoubleDoorCameraRight/Sequence1 | 5 | 0.5 | — |
| DoubleDoorCameraRight/Sequence2 | 22 | 2.2 | — |
| DoubleDoorCameraRight/Sequence3 | 36 | 3.1 | videoTM_29.mkv |
| DoubleDoorCameraRight/Sequence4 | 31 | 3.1 | — |
| DoubleDoorCameraRight/Sequence5 | 23 | 2.6 | videoTM_05.mkv, videoTM_08.mkv, videoTM_16(1).mkv |
| DoubleDoorCameraRight/Sequence6 | 38 | 3.2 | — |
| DoubleDoorCameraRight/Sequence7 | 6 | 0.4 | — |
| DoubleDoorCameraRight/Sequence8 | 34 | 3.3 | videoTM_04.mkv |
| SingleDoorMiddle/Sequence1 | 4 | 0.3 | — |
| SingleDoorMiddle/Sequence2 | 25 | 2.8 | videoTM_10(1).mkv |
| SingleDoorMiddle/Sequence3 | 41 | 3.3 | — |
| SingleDoorMiddle/Sequence4 | 38 | 3.4 | videoTM_03(1).mkv |
| SingleDoorRear/Sequence1 | 26 | 1.6 | videoTM_04(2).mkv, videoTM_11.mkv, videoTM_12.mkv |

## Lo que cambia

- **Ya no faltan videos nunca vistos.** El inventario del 12-10 decía que solo había 4 videos diurnos de bus que
  el detector no había visto; eran los 4 de la torre. En el Drive hay **458 videos de Bus sin bajar**, ninguno
  usado para entrenar.
- **Dos cámaras sin nada:** DoubleDoorCameraRight (195 videos, la más grande) y SingleDoorRear (26). Los videos
  que la torre tiene de ellas (04, 05, 16(1), 08, 29 y 11, 12, 04(2)) son de entrenamiento o descartados.
- **El 07 y el 03 son de la misma secuencia que tres videos de entrenamiento** (05(1), 04(1), 10):
  DoubleDoorCameraLeft/Sequence3. La validación comparte sesión de grabación con el entrenamiento del detector.
  El 02 (prueba) está en otra secuencia (Sequence6), sin videos de entrenamiento diurnos.
- **El 03(1) no es "otro bus" sin más: es otra cámara** (SingleDoorMiddle), la del centro de un bus de una puerta.
- Una secuencia parece una sesión de grabación; dentro de ella cambia la hora (hay nocturnos, como el 13 en la
  Sequence3 y el 17 en la Sequence6).

## Siguiente

1. Bajar una muestra por cámara y secuencia sin cubrir, empezando por DoubleDoorCameraRight y SingleDoorRear.
   Bajar 45 GB por el conector no es viable (devuelve base64); hace falta rclone en la torre o la web de Drive.
2. Pasar `scripts/flow/inventario_camaras.py` a lo bajado (luminancia y cabezas por frame) para elegir
   diurnos por nivel de congestión.
3. Por cámara nueva: geometría + ROI (unos 15 min de Camilo), golden de tracking y golden de eventos.

