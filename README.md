# Multi-Object-Tracking

Entorno reproducible para una tesis de Maestría en IA sobre Multi-Object Tracking (MOT) en vista cenital, usando PyTorch en contenedores. Diseñado para que dos estudiantes trabajen en 3 máquinas distintas (Windows/macOS/Linux) con NVIDIA GPUs, minimizando “funciona en mi PC”.

**Qué incluye**
- PyTorch (imagen base oficial, CPU o CUDA).
- TrackEval para métricas MOT (HOTA/MOTA/IDF1, etc.).
- Tracking de experimentos con W&B (offline por defecto) y MLflow.
- JupyterLab dentro del contenedor.
- Utilidades típicas de visión (ffmpeg, OpenCV, numpy, etc.).

**Estructura**
- `docker/` Dockerfile + requirements
- `compose.yaml` servicios `dev` y `mlflow`
- `compose.gpu.yaml` override opcional para GPU
- `Taskfile.yml` comandos reproducibles
- `.env.example` configuración
- `src/` scripts de smoke/check
- `data/`, `outputs/`, `mlruns/`, `wandb/` persistencia local

## Prerrequisitos

**Todos los sistemas**
- Docker Engine / Docker Desktop actualizado.
- `task` (go-task). Si no lo tienes, instala desde el repositorio oficial.

**GPU (NVIDIA)**
- NVIDIA Container Toolkit instalado y funcionando.
- Drivers compatibles con la versión CUDA de la imagen base.

## Quickstart

1. Copia variables de entorno

```bash
cp .env.example .env
```

2. Construye imágenes y levanta servicios

```bash
task build
task up
```

Si quieres GPU:

```bash
task up-gpu
```

3. Verifica el entorno

```bash
task check
```

4. Pruebas rápidas

```bash
task trackeval-smoke
task mlflow-smoke
task wandb-smoke
```

## URLs locales

- JupyterLab: `http://localhost:8888` (token desde `.env`)
- MLflow UI: `http://localhost:5000`

## CPU vs GPU

Por defecto el `.env.example` usa imagen GPU pero el `compose.yaml` no requiere GPU.

- Para **CPU**: deja `NVIDIA_VISIBLE_DEVICES_COUNT=0` y usa una imagen CPU, por ejemplo:
  - `BASE_IMAGE=pytorch/pytorch:2.2.2-cpu`

- Para **GPU**:
  - Usa una imagen CUDA (ejemplo por defecto).
  - Cambia `NVIDIA_VISIBLE_DEVICES_COUNT=1` (o `all` para todas las GPUs).
  - Levanta con `task up-gpu` para activar la configuración NVIDIA.

Si el contenedor falla por CUDA, cambia a imagen CPU y/o verifica drivers y toolkit.

## Recomendaciones de reproducibilidad

- Mantener la **misma imagen base** y el mismo `.env` entre los equipos.
- Evitar actualizar versiones sin coordinar al equipo.

## Workflow del repositorio

1. Configurar entorno una sola vez:
```bash
cp .env.example .env
task build
task up
```

2. Desarrollo diario:
```bash
task check
task jupyter
```

3. Entrenamiento / inferencia / evaluación:
```bash
task shell
# Ejecutar scripts desde /workspace (el repo montado)
```

4. Registro de experimentos:
- W&B en modo offline por defecto.
- MLflow disponible en `http://localhost:5000`.

## Cómo organizar notebooks, scripts, modelos y data

- Notebooks:
  - Coloca notebooks en `notebooks/` (crear carpeta si no existe).
  - Nombra con prefijo ordenado: `00_`, `01_`, `02_` para mantener flujo.

- Scripts Python:
  - Coloca scripts en `src/` (ej: `src/train.py`, `src/infer.py`, `src/eval.py`).
  - Importa utilidades comunes desde `src/` para reutilizar código.

- Modelos:
  - Guardar checkpoints y pesos en `outputs/models/` (crear carpeta si no existe).
  - Evita subir modelos pesados al repo (usa storage externo si es necesario).

- Data:
  - Coloca datasets en `data/`.
  - Organiza por nombre de dataset: `data/MOT17/`, `data/Custom/`, etc.
  - No subir datos sensibles o grandes al repo.

## Convenciones recomendadas

- Experimentos reproducibles: fija seeds y guarda configs en `outputs/`.
- Mantén un registro de cambios clave en `outputs/notes/` o en el README.

## Comandos útiles (Taskfile)

- `task build` construye imágenes
- `task up` levanta servicios
- `task down` baja servicios
- `task logs` ver logs
- `task shell` entrar al contenedor `dev`
- `task check` valida PyTorch/CUDA/TrackEval
- `task jupyter` lanza JupyterLab
- `task wandb-smoke` smoke test W&B (offline)
- `task mlflow-smoke` smoke test MLflow
- `task trackeval-smoke` smoke test TrackEval

## Notas

- Los runs de MLflow persisten en `mlruns/`.
- Los runs de W&B (offline) persisten en `wandb/`.
- Los datos deben ir en `data/` y los outputs en `outputs/`.
