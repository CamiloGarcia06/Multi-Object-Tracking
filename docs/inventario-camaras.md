# Inventario de videos por congestión (tarea 4, 12-10)

Los 24 videos del `sda2`, ya en `~/videos/` de la torre (640×480, 30 fps, 15 min).
`scripts/flow/inventario_camaras.py` toma 1 frame por segundo y mide:
- luminancia mediana;
- cabezas por frame con yolo26x-min5 (conf 0,25, NMS 0,6, frame entero, sin ROI).

**"Lleno"** = % de segundos con 8 o más cabezas. Las miniaturas (minuto 7,5 y el
segundo con más cabezas) están en `data/flow_eval/inventario/hoja_inventario.jpg`.

| Video | Estado | p50 | p90 | máx | lleno | Nivel |
|---|---|---|---|---|---|---|
| 04 | entrenado | 14 | 16 | 18 | 100 % | alta |
| 10 | entrenado (s03) | 10 | 15 | 17 | 82 % | alta |
| 16 | entrenado | 9 | 12 | 15 | 74 % | alta |
| 14 | entrenado | 8 | 9 | 12 | 54 % | alta |
| 05 | entrenado | 7 | 11 | 15 | 49 % | alta |
| **02** | **reservado: golden de detección** | 6 | 10 | 14 | 35 % | **alta** |
| 18(1) | entrenado (v18S08, inferido) | 6 | 9 | 12 | 29 % | media |
| 16(1) | entrenado | 7 | 8 | 11 | 26 % | media |
| 12 | entrenado | 7 | 8 | 11 | 23 % | media |
| **03(1)** | **nunca visto** | 0 | 8 | 14 | 13 % | **media** (picos) |
| 04(2) | entrenado | 3 | 8 | 9 | 11 % | media |
| **03** | **nunca visto** | 3 | 7 | 10 | 7 % | **baja** |
| 07 | reservado: evaluación de eventos | 5 | 7 | 10 | 6 % | baja |
| 05(1), 04(1), 11, 10(1) | entrenado | 3–5 | 5–7 | 8–10 | 0–5 % | baja |
| **08** | **nunca visto** | 1 | 2 | 4 | 0 % | **muy baja** |
| 13, 17, 18, 29 | nunca visto, **nocturno** | 1–2 | 3–5 | 6–8 | 0 % | fuera de alcance |
| intelC1, intelC36 | nunca visto, **otra escena** | 0–1 | 0–3 | 1–6 | 0 % | fuera de alcance |

## Lo que cambia respecto a lo que creíamos

- **videoTM_17 es nocturno** (luminancia 0), no un candidato diurno como decía
  `plan_tracking_flujo.md`. Los nocturnos son 13, 17, 18 y 29.
- **intelC1 e intelC36 no son el interior de un bus**: son una cámara cenital sobre
  el andén de una estación (suelo con flechas amarillas). Es otra escena: no sirve
  para la regla de la puerta del bus.
- **La luminancia baja de 04, 10 y 12 no es noche**: el frame está lleno de ropa
  oscura. Se ven diurnos en las miniaturas.
- **videoTM_07 es de congestión baja.** La Tabla I actual sale de un caso fácil.

## El problema: solo hay 4 videos diurnos de bus que el detector no ha visto

02 (alta), 03(1) (media), 03 (baja) y 08 (muy baja). Todo lo de congestión alta
restante ya se usó para entrenar: medir ahí favorece al detector, que memorizó esas
caras. Así que hay un solo video nunca visto por nivel de congestión.

**Propuesta de reparto** (decisión tuya, tareas 5 y 6):

| Uso | Videos | Por qué |
|---|---|---|
| **Prueba final** (no se toca hasta la Fase 5) | **02** (alta) + **03(1)** (media) | Los dos niveles que importan, nunca vistos. El 02 ya está fuera de entrenamiento por `DO_NOT_TRAIN.txt`; usarlo para eventos no entrena nada, pero hay que dejarlo escrito |
| **Validación** (golden de eventos de la tarea 6: valida los ajustes sin fuga) | **03** (baja) | Nunca visto; misma cámara de bus; la otra mitad del par 03 |
| **Desarrollo** (lo que ya usamos) | **07** (baja) | Se sigue usando para el diagnóstico |
| **Reentrenamiento** (tarea 9) | 04, 10, 16, 14, 05 (alta) + medios | Ya son de entrenamiento: sacar más frames de puerta de ahí no contamina la prueba |
| Descartados | 08 (casi vacío), nocturnos, intel* | Limitaciones declaradas |

**Riesgo:** la validación (03) es de congestión baja, como el 07. Un ajuste que solo
funcione en alta no se vería hasta la prueba. Alternativa: validar en unas
aperturas del 03(1) y probar con otras. Es más débil (mismo video), pero cubre la
congestión media.
