# Bloque C del artículo — Prueba multicámara (borrador, 2026-10-18)

Borrador de la Tesis 15: método (§C.1–C.6), resultados (§C.7), discusión (§C.8) y limitaciones
(§C.9) de la prueba en las cuatro cámaras. Quedan dos huecos `«PENDIENTE …»`, que dependen de la
Tesis 10 (umbral que se declara) y de la 12 (alcance con el profesor). Las cifras salen de
`docs/inventario-camaras.md`, `docs/criba-door-open.md`, `docs/curvas-puerta-medidas.md`,
`docs/resultados-<video>.md`, `docs/sesgo-entre-camaras.md`, `docs/linea-base-prueba.md` y
`docs/comparacion-trackers-camaras.md`.

---

## C.1 Datos y estratificación

El corpus son 480 videos de bus de cámaras cenitales con lente ojo de pez (640×480, 30 fps),
en cuatro posiciones de cámara (nombres del conjunto de datos): DDL (*DoubleDoorCameraLeft*),
DDR (*DoubleDoorCameraRight*), SDM (*SingleDoorMiddle*) y SDR (*SingleDoorRear*), cada una en
varias secuencias de grabación, que se agrupan por **montaje**. Un montaje es una combinación cámara–secuencia: misma posición física, mismo
encuadre y misma puerta.

Cada video se describió de forma automática a un fotograma por segundo con el detector de
cabezas final (§B) para estratificarlo antes de elegir nada:

- **Iluminación** por la luminancia mediana: noche < 20 ≤ penumbra < 60 ≤ día. La
  distribución es bimodal (157 videos por debajo de 10).
- **Congestión** por el porcentaje de segundos con ocho o más cabezas visibles, con los
  umbrales anclados en videos ya anotados: baja < 10 % ≤ media < 25 % ≤ alta.
- **Estado**: si el video, o su secuencia, aportó imágenes al entrenamiento del detector.

| Cámara | Videos | Día | Diurnos nunca vistos (baja / media / alta) |
|---|---|---|---|
| DDL | 151 | 85 | 54 / 11 / 12 |
| DDR | 195 | 111 | 70 / 18 / 20 |
| SDM | 108 | 59 | 43 / 5 / 9 |
| SDR | 26 | 11 | 9 / 0 / 0 |

Los conteos de cabezas los hace el propio detector, que en SDM y SDR (encuadre distinto y más
desenfoque) cuenta de menos: el nivel de congestión no es del todo comparable entre cámaras.

**Partición.** Desarrollo, validación y la primera prueba son de un mismo montaje DDL:
videoTM_07 (desarrollo, congestión baja), videoTM_03 (validación, baja) y videoTM_02 (prueba,
alta). Para medir si el sistema y su corrección de sesgo se transfieren a otras cámaras se
añade **un video de prueba por cámara nueva**, nunca visto y diurno:

| Cámara | Video de prueba | Nivel (% lleno) | Uso previo |
|---|---|---|---|
| DDL | videoTM_02 | alta (34,9) | prueba (ya evaluada) |
| SDM | videoTM_03(1) = bus_sdm_s4_v03 | media (13,1) | prueba |
| DDR | bus_ddr_s6_v18 | alta (39,1) | prueba |
| SDR | bus_sdr_s1_v08 | baja (0,0) | prueba |

Ningún video de prueba se usó para ajustar nada: ni parámetros de la regla, ni factores de
corrección, ni el detector.

## C.2 Geometría por montaje

Cada montaje lleva tres elementos fijados **antes** de anotar su prueba y que valen para todos
sus videos:

1. **Región de interés (ROI):** polígono trazado a mano sobre un fotograma sin pasajeros de la
   misma secuencia (el más parecido a la mediana temporal). Deja fuera el andén, las ventanas y
   el exterior visible a través del vidrio. Las detecciones fuera de la ROI se descartan antes
   del seguimiento.
2. **Curvas de puerta:** dos polilíneas que siguen la puerta en la imagen deformada por el ojo
   de pez. La **exterior** separa el andén del umbral y la **interior** el umbral del pasillo; la
   regla de conteo (§C.4) se define respecto de la interior.
3. **Detector de puerta abierta** (§C.3), con su referencia de puerta cerrada.

**Medición de las curvas.** En lugar de colocarlas a ojo, las curvas se validan con las propias
detecciones (`medir_curvas.py`). Con la puerta cerrada, lejos (±150 fotogramas) de toda apertura,
todas las cabezas visibles son de pasajeros que van dentro. Unas curvas bien colocadas cumplen dos
condiciones: **ninguna cabeza pasa la exterior** y la **interior va pegada** a las cabezas de dentro
que más se acercan a la puerta (percentil 1 de la distancia firmada ≈ 0). Las detecciones fijas
que no se mueven en todo el video (un reflejo en el vidrio, una pegatina) se descuentan.

| Cámara | Cabezas con la puerta cerrada | Pasan la exterior | p1 a la interior (px) | Curvas |
|---|---|---|---|---|
| DDL (07 / 03 / 02) | 94.121 / 71.283 / 99.094 | 2 / 1 / 1 | −3,6 / −2,4 / +3,7 | a mano, sin cambios |
| SDM 03(1) | 13.584 | 13 | −12,9 | a mano, sin cambios |
| DDR s6 | 118.822 | 1 | +20,4 | medidas: +30 px |
| SDR s1 | 40.633 | 7 | +11,1 | medidas: +30 px |

En DDR y SDR la primera propuesta dejaba 35–50 px de holgura sobre el andén; se desplazó 30 px
hacia el pasillo. Las curvas quedan sobre el vidrio y no sobre el umbral del piso porque, con el
bus lleno, la cabeza de quien va apoyado en la puerta cae sobre el vidrio.

## C.3 Detección de la puerta abierta

Solo cuentan los cruces con la puerta abierta, así que el sistema necesita saber cuándo lo está.
`door.py` lo infiere de la imagen y no de una señal del bus:

1. Recorte fijo de la zona de las hojas, en gris y reducido a 36×52, una muestra cada 3 fotogramas.
2. Mapa de bordes (magnitud del gradiente), robusto a los cambios de luz.
3. **Referencia de puerta cerrada:** mediana de los mapas de bordes de un tramo con la puerta
   cerrada y sin gente. Se guarda **por montaje** y se transfiere entre videos de la misma
   secuencia: en DDR s6, la referencia de un video da en otro las mismas 11 aperturas que la propia.
4. Similitud por correlación cruzada normalizada con la referencia (cerrada 0,6–0,95; abierta
   0,05–0,2), mediana móvil de 10 muestras, umbral 0,35 y tramos de al menos 1,5 s. Un recorte
   casi negro (túnel) cuenta como cerrado.

Los parámetros son los del montaje DDL y no se reajustan por cámara: solo cambian el recorte y la
referencia.

**Elegibilidad del video.** El método falla cuando la puerta no se ve: gente apoyada en ella o un
bus detenido al lado, visible a través del vidrio. Por eso los videos de prueba se eligieron entre
aquellos en que la puerta es **legible**: el percentil 75 de la similitud por minuto es ≥ 0,6 en al
menos el 80 % de los minutos, ningún intervalo de puerta abierta dura más de 30 s y hay al menos
cuatro aperturas. De 30 videos diurnos de DDR s6 y SDR s1, 14 cumplen (8 y 6). Los dos videos que
el inventario proponía primero (DDR v15 y SDR v10, los más llenos) quedaron fuera: en ellos la
puerta se ve el 20 % y el 7 % de los minutos.

**Precisión del detector de puerta en la prueba.** Cada intervalo se revisó a ojo y se buscaron
aperturas perdidas en los tramos de similitud baja fuera de todo intervalo:

| Video | Intervalos | Reales | Falsos | Perdidas | Precisión | Recall |
|---|---|---|---|---|---|---|
| DDR s6_v18 | 11 | 11 | 0 | 0 | 1,00 | 1,00 |
| SDR s1_v08 | 12 | 11 | 1 | 0 | 0,92 | 1,00 |

El único falso (SDR) es un pasajero de pie contra la puerta cerrada con un bus rojo detrás del
vidrio. El recall es el de una búsqueda dirigida, no el de una revisión fotograma a fotograma.

## C.4 Sistema evaluado (congelado)

El sistema se congeló al cerrar la validación (12-10) y es el mismo en las cuatro cámaras:

- detector de cabezas yolo26x-min5 con NMS posterior a 0,6 (§B);
- descarte fuera de la ROI;
- ByteTrack (búfer 90, emparejamiento 0,9);
- **regla origen–destino:** con la puerta abierta, una subida es un track que nace a ≤ 40 px de la
  curva interior y llega a ≥ 80 px hacia el pasillo; una bajada, al revés;
- **corrección de sesgo:** conteo / factor, con el factor por dirección = Σcontado / Σreal en los
  videos 03 y 07 (subidas 0,68, IC95 0,47–0,94; bajadas 0,62, IC95 0,52–0,73) e intervalo por
  bootstrap de aperturas.

**Línea base sin seguimiento.** Mismas detecciones, ROI y puerta; empareja cada detección con la
más cercana del fotograma siguiente (≤ 40 px) y cuenta los pares que cruzan la curva interior. Así,
la única diferencia con el sistema es el seguimiento. Tiene su propio factor de corrección, ajustado
igual en 03+07: subidas 0,56 (IC95 0,34–1,08), bajadas 0,52 (0,40–0,73).

## C.5 Verdad de terreno

**Eventos.** Una persona (el autor) anota en CVAT un punto por persona y cruce, sobre la cabeza,
en el primer fotograma en que alcanza la curva interior: `sube`, `baja` o `raro` cuando hay duda de
si cuenta o en qué dirección (no cuenta y se lista aparte). El criterio, los casos difíciles y el
recorrido de cada tarea están en la guía de anotación (`docs/guia-anotacion.md`, Anexo X). Medido
en el 07, el criterio adelanta el evento 1–4 fotogramas respecto del cruce del centro de la cabeza,
de forma constante y por debajo de la tolerancia de emparejamiento.

En las cámaras nuevas el golden es **reducido**: cinco aperturas por video, elegidas a ojo entre
las que tienen subidas (con 60 fotogramas de margen a cada lado), en lugar del video completo.
Las aperturas se delimitan a ojo y **no salen de door.py**, para que la verdad no dependa del
componente evaluado. Las imágenes no llevan pre-anotación.

| Video | Aperturas | Imágenes | Subidas | Bajadas | Raros |
|---|---|---|---|---|---|
| SDM 03(1) | 4 | ≈ 2.090 | 54 | 11 | 0 |
| DDR s6_v18 | 5 | 1.370 | 4 | 17 | 0 |
| SDR s1_v08 | 5 | 1.215 | 16 | 18 | 0 |

En SDM, 53 de las 54 subidas son de una sola parada con el bus lleno (22.336–23.475), y una de
las cuatro aperturas (5.500–5.623) no tiene cruces. El cierre de esa parada no se distingue en
las imágenes; se fijó al final del último fotograma anotado.

**Seguimiento.** Para comparar trackers (§D) hay un clip de 200 fotogramas por cámara nueva
(DDR s6_v18 desde el 12.261, SDR s1_v08 desde el 4.581), pre-anotado con ByteTrack y corregido a
mano (cajas e identidades). La pre-anotación favorece a ByteTrack; se declara como sesgo.

## C.6 Protocolo de evaluación

```mermaid
flowchart LR
  A[Geometría y puerta<br/>fijadas por montaje] --> B[Eventos del sistema<br/>y de la línea base]
  B --> C[Sello SHA-256]
  C --> D[Golden de eventos<br/>anotado a ciegas]
  D --> E[Evaluación única:<br/>sin corregir y corregida]
```

1. **Orden.** Geometría y puerta se fijan con el video de prueba sin anotar. Después se generan
   los eventos del sistema y de la línea base y se **sellan** con su SHA-256
   (`configs/prueba_sellada.sha256`). Solo entonces se anota el golden. La evaluación comprueba el
   sello y se detiene si algún fichero cambió.
2. **Una sola evaluación por video.** No se reajusta nada con su resultado.
3. **Métricas por apertura y en total**, separadas por dirección, como la Tabla I del
   anteproyecto: conteo real y contado, error absoluto y porcentual con signo, y, emparejando por
   dirección a ±10 fotogramas, recall (personas contadas) y precisión (eventos que son una persona
   real). Se dan las dos porque el error de conteo puede ser nulo con eventos mal colocados.
4. **Corrección:** el factor de 03+07 se aplica sin reestimar. La pregunta de la prueba
   multicámara es si el total real cae dentro del intervalo corregido en las cámaras que no
   aportaron al factor.
5. **Golden reducido:** solo se evalúan las aperturas anotadas. Los falsos de door.py fuera de ellas
   no se penalizan aquí; se reportan aparte (§C.3). Una apertura anotada sin cruces cuenta igual, y
   cualquier evento del sistema en ella es un falso positivo.

## C.7 Resultados

Cada video de prueba se evaluó una sola vez, después de comprobar el sello. Las tablas completas,
por apertura, están en `docs/resultados-<video>.md`, `docs/sesgo-entre-camaras.md`,
`docs/linea-base-prueba.md` y `docs/comparacion-trackers-camaras.md`.

### C.7.1 Tabla I multicámara

Valores sube / baja. «Corregido» = conteo / factor de 03+07, sin reestimar; «IC» indica si el
total real cae dentro del IC95 del conteo corregido.

| Cámara | Video | Nivel | Real | Sin corregir | Corregido | IC | Recall | Precisión | Línea base corregida |
|---|---|---|---|---|---|---|---|---|---|
| DDL | 02 | alta | 18 / 41 | −28 / −39 % | +7 / −1 % | sí / sí | 0,61 / 0,56 | 0,85 / 0,92 | +99 / +26 % |
| SDM | 03(1) | media | 54 / 11 | −76 / −27 % | −64 / +18 % | **no** / sí | 0,22 / 0,73 | 0,92 / 1,00 | −54 / +39 % |
| DDR | s6_v18 | alta | 4 / 17 | −25 / −18 % | +11 / +34 % | sí / **no** | 0,75 / 0,82 | 1,00 / 1,00 | +79 / +46 % |
| SDR | s1_v08 | baja | 16 / 18 | −50 / −28 % | −26 / +17 % | sí / sí | 0,50 / 0,67 | 1,00 / 0,92 | −33 / +38 % |

Tres rasgos se repiten en las cuatro cámaras:

1. **El sistema cuenta de menos y casi no inventa.** El error sin corregir es negativo en los ocho
   casos (−18 % a −76 %) y la precisión va de 0,85 a 1,00: el error es de personas perdidas, no de
   eventos falsos.
2. **El factor de DDL vale en 6 de 8 casos.** Los dos fallos tienen causas distintas, que se
   analizan en §C.7.2.
3. **El seguimiento mejora a la línea base una vez corregidos los dos** en 7 de 8 casos (§C.7.3).

### C.7.2 ¿Un factor de sesgo para todas las cámaras?

**Factor propio de cada cámara** (Σcontado / Σreal con todas sus aperturas, IC95 por bootstrap):

| Cámara | Subidas | Bajadas | Aperturas |
|---|---|---|---|
| DDL (03, 07, 02) | 0,69 (0,54–0,88) | 0,61 (0,52–0,73) | 31 |
| SDM | 0,24 (0,23–1,00) | 0,73 (0,70–1,00) | 4 |
| DDR | 0,82 (0,64–0,93)ᵃ | 0,82 (0,64–0,93) | 5 |
| SDR | 0,50 (0,38–0,67) | 0,72 (0,30–0,89) | 5 |

ᵃ Con 4 subidas reales, DDR usa el factor conjunto de las dos direcciones.

**SDM, subidas (−64 % corregido): fallo de door.py, no del seguimiento.** En la parada llena,
door.py da la puerta por cerrada en el fotograma 22.519, cuando el golden la tiene abierta hasta el
23.475: con la gente tapando las hojas, la similitud con la referencia cerrada no baja. Para separar
las dos causas se repitió la evaluación **a posteriori** con los mismos tracks y la misma regla,
cambiando solo la puerta de esa parada por la del golden:

| Puerta | Subidas contadas (real 54) | Sin corregir | Corregido (IC95) |
|---|---|---|---|
| door.py (resultado sellado) | 13 | −76 % | 19,2 (13,9–27,7), −64 % |
| la del golden | 31 | −43 % | 45,8 (33,1–66,1), −15 % |

De las 41 subidas perdidas, **18 se deben a door.py** y 23 al detector y al seguimiento. Con la
puerta bien vista, el recall de subidas de SDM (0,54) es el de DDL (0,59–0,62) y el factor de DDL
vuelve a contener el valor real. Es el mismo fallo que da los falsos de door.py en el 02 (§C.3).
Este diagnóstico no sustituye al resultado sellado, que es el que se reporta en la Tabla I.

**DDR, bajadas (+34 % corregido): sesgo distinto de la cámara.** En DDR el sistema pierde menos
(recall 0,82 frente a 0,56–0,62 en DDL; factor 0,82 frente a 0,61, con IC95 que apenas se tocan) y
el factor de DDL sobrecorrige. Las subidas de DDR caen dentro del IC, pero con 4 eventos no informan.

**Un factor global no mejora.** Como alternativa se estimó, para cada cámara, un factor con todas
las aperturas de las otras tres (*leave-one-camera-out*, LOCO, también a posteriori). Su error neto
agregado parece bueno (−9 % / +0 %) porque los errores se compensan: sobrecorrige las subidas del
02 (+123 %, por el factor 0,32 que arrastra la parada llena de SDM) e infracorrige las del 03(1). Sin
compensación entre videos es peor que el factor de DDL:

| Corrección | Error neto (sube / baja) | Error absoluto (sube / baja) |
|---|---|---|
| sin corregir | −60 / −31 % | 60 / 31 % |
| factor de DDL (fijado antes de la prueba) | −41 / +12 % | 44 / 13 % |
| LOCO | −9 / +0 % | 65 / 19 % |

Error absoluto = Σ|estimado − real| / Σreal sobre los cuatro videos (92 subidas y 87 bajadas reales).

Un factor **por cámara** tampoco se puede estimar bien con estos datos: cada cámara nueva aporta
4–5 aperturas, los intervalos por bootstrap son muy anchos (SDM subidas 0,23–1,00) y estimarlo con el
propio video de prueba sería evaluar con los datos de ajuste. Por eso se mantiene el factor de DDL,
fijado antes de la prueba.

**Umbral de exactitud.** Con el factor de DDL, el error absoluto agregado es del 44 % en subidas y
del 13 % en bajadas, lejos del ≤ 5 % agregado que pide la NTD para los sistemas APC
(«PENDIENTE 10: umbral que se declara»). Solo el 02 (DDL, +7 / −1 %) se acerca, y con 18 subidas el ±5 % es
menos de un pasajero.

### C.7.3 ¿Aporta el seguimiento? Línea base sin tracking

Mismas detecciones, ROI y puerta para los dos métodos, cada uno corregido con su propio factor de
03+07. Por evento (emparejando con el golden a ±10 fotogramas, las 25 aperturas de las cuatro pruebas):

| Dirección | Recall sist. / s.t. | Precisión sist. / s.t. | F1 sist. / s.t. | ΔF1 (IC95) |
|---|---|---|---|---|
| Subidas | 0,37 / 0,32 | 0,92 / 0,66 | 0,53 / 0,43 | +0,10 (−0,00 a +0,37) |
| Bajadas | 0,66 / 0,56 | 0,95 / 0,80 | 0,78 / 0,66 | +0,11 (−0,03 a +0,25) |

El seguimiento acierta más en las dos direcciones, sobre todo por **precisión**: sin él se cuentan
cruces falsos y la misma persona dos veces. Con 25 aperturas, el IC95 de la diferencia roza el cero:
la mejora es consistente, pero no significativa al 95 %.

En conteo corregido, el seguimiento se equivoca menos en 7 de 8 casos. Media del |error corregido|
por video: 27 % frente a 66 % en subidas y 18 % frente a 37 % en bajadas. La excepción es SDM subidas
(−64 % frente a −54 %), donde los dos métodos dependen de la misma puerta cortada.

El error neto del total engaña: sin seguimiento, las subidas agregadas corregidas quedan en −14 %
(frente a −41 % del sistema), pero porque sus falsos positivos tapan las pérdidas. En el 02 y en DDR,
la línea base cuenta tantas subidas como las reales con precisión 0,50. Por eso la comparación se
hace por evento y no por el total.

### C.7.4 Comparación de trackers en las cámaras nuevas

Mismas detecciones y ROI; solo cambia la asociación. Clips de 200 fotogramas con identidades
anotadas (§C.5). HOTA / IDF1:

| Tracker | DDL baja (07) | DDL alta (02) | SDM media (03(1)) | DDR (v18) | SDR baja (v08) | Conjunto |
|---|---|---|---|---|---|---|
| ByteTrack (#27) | 61,1 / 69,5 | 66,0 / 65,7 | 55,2 / 59,9 | **81,8** / 80,0 | **77,5** / 82,2 | **68,0** / 70,0 |
| BoT-SORT + OSNet | 51,8 / 74,6 | **68,8** / 72,5 | 48,4 / 57,8 | 76,0 / 78,7 | 68,4 / 83,6 | 63,6 / 71,8 |
| Deep OC-SORT (IoU 0,2) | 43,1 / 65,5 | 52,6 / 57,5 | 39,6 / 53,7 | 74,4 / 87,6 | 49,7 / 65,7 | 52,6 / 64,1 |
| OC-SORT | 35,2 / 51,6 | 50,3 / 51,5 | 35,6 / 47,1 | 73,8 / 85,0 | 49,2 / 62,0 | 50,4 / 58,5 |
| Deep OC-SORT | 34,2 / 50,0 | 46,4 / 45,9 | 34,0 / 46,8 | 73,3 / 85,3 | 47,0 / 59,9 | 48,4 / 56,4 |

ByteTrack gana en HOTA en las dos cámaras nuevas y en el conjunto (5 clips, 90 identidades), y
BoT-SORT con reidentificación queda segundo. El único caso en que la apariencia aporta sigue siendo
el bus lleno de DDL (02). DDR separa poco a los trackers (HOTA 73–82). Los de apariencia tienen ahí
el mejor IDF1 (85–88), pero el clip de DDR es de carga baja dentro de la ROI (2,9 cabezas por
fotograma de media, máximo 4), aunque el video va lleno el 39 % del tiempo. Para hablar de congestión
conviene usar la carga del clip y no la etiqueta del video.

## C.8 Discusión

- **El error es sistemático, pero su tamaño depende de la cámara y de la puerta.** En las cuatro
  cámaras el sistema pierde personas (recall 0,22–0,82) y casi no inventa (precisión ≥ 0,85). Eso
  justifica corregir con un factor, y el de DDL contiene el valor real en 6 de 8 casos sin
  reestimarlo. Pero no es universal: en DDR el sistema pierde menos y el factor sobrecorrige.
- **El punto débil es la puerta, no el seguimiento.** El fallo más grande (SDM subidas) viene de
  door.py con el bus lleno, y es la misma causa que los falsos del 02. La mayor mejora del
  desarrollo también fue de la puerta (golden del 07: +15 puntos al corregir door.py). Un detector de
  puerta robusto a la oclusión es el trabajo futuro con más retorno.
- **El seguimiento aporta sobre todo precisión.** Frente a contar pares de detecciones, ByteTrack
  sube el F1 por evento unos 0,10 en las dos direcciones y reduce a la mitad el error corregido medio.
  La apariencia (ReID) no compensa en vista cenital salvo con el bus muy lleno.
- **Lo que no se puede afirmar:** que el sistema cumpla un umbral APC (≤ 5 %) fuera de DDL, que el
  factor transfiera a cámaras sin calibrar, o que un tracker sea mejor que otro por pocos puntos de
  HOTA en clips de 200 fotogramas.

## C.9 Limitaciones de la prueba multicámara

- **Un video por cámara nueva y 4–5 aperturas:** el intervalo del error es ancho; la prueba
  detecta un sesgo grande entre cámaras, no uno de pocos puntos. En SDM, 53 de las 54 subidas son de
  una sola parada; en DDR solo hay 4 subidas.
- **Cámara y congestión confundidas:** cada cámara nueva aporta un solo nivel (SDM media, DDR alta,
  SDR baja). En SDR no hay ningún video diurno nunca visto lleno con la puerta visible.
- **Selección por legibilidad de la puerta:** los videos donde la puerta no se ve quedaron fuera
  por construcción; el error en ellos sería mayor, sobre todo por door.py.
- **Golden reducido:** los falsos de door.py fuera de las aperturas anotadas no se penalizan en la
  Tabla I; su precisión se mide aparte (§C.3).
- **Análisis a posteriori:** LOCO y el diagnóstico con la puerta del golden usan videos de prueba ya
  evaluados; explican el resultado, no lo sustituyen.
- **Goldens de seguimiento pre-anotados con ByteTrack:** entre el 72 % y el 81 % de las cajas de
  DDR y SDR quedaron sin tocar, lo que favorece a ByteTrack. En SDR los sentados no se anotan, pero la
  ROI los incluye, y los trackers que los siguen pagan falsos positivos.
- **Un solo anotador**, sin medida de acuerdo entre anotadores.
- **SDR s1 tiene videos en el entrenamiento** del detector (la secuencia, no el video de prueba).
- El nivel de congestión lo mide el mismo detector que se evalúa, que cuenta de menos en SDM y SDR.

«PENDIENTE 12: confirmar con el profesor que Station queda fuera del alcance.»
