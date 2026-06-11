---
name: cvat-export
description: Recupera un export de anotaciones de CVAT directamente del cache del contenedor cvat_server (los exports muchas veces NO llegan a Downloads) y lo deja listo para construir dataset. Uso /cvat-export <task-o-job>.
---

# Recuperar export de anotaciones desde CVAT

GOTCHA central del proyecto: al exportar un dataset desde la UI de CVAT, el zip queda
generado en el **cache del contenedor** y la descarga del navegador a veces no ocurre.
Buscar SIEMPRE primero en el cache. CVAT corre en Docker Desktop (`-c desktop-linux`).

## Pasos

1. Si el usuario aún no exportó: que lo haga en la UI (Task/Job → Export dataset →
   formato **CVAT for images 1.1**, que es el que parsean los builders del repo).
2. Buscar el zip en el cache (el patrón incluye el job/task id):
   ```bash
   docker -c desktop-linux exec cvat_server ls -lat /home/django/data/cache/export/ | head
   ```
   Ejemplos reales: `job-10-dataset-instance*-cvat-for-images-11.zip` (ronda 3),
   `job-11-*` (golden). Elegir el más reciente que coincida con el job pedido.
3. Copiar al repo:
   ```bash
   docker -c desktop-linux cp cvat_server:/home/django/data/cache/export/<archivo>.zip \
     /home/camilo-pc/Multi-Object-Tracking/data/_harvest/
   ```
4. Verificar contenido: el zip debe traer `annotations.xml` (formato CVAT-for-images).
   Reportar nº de imágenes y de boxes (un `grep -c '<box' annotations.xml` rápido sirve).

## Gotcha de API (si se intenta por API en vez de UI)

El token DRF devuelve **401 a través de traefik** (host :8080) pero funciona desde
DENTRO de cvat_server: `docker -c desktop-linux exec cvat_server curl localhost:8080/...`.
Import de anotaciones: `POST /api/tasks/{id}/annotations?format=CVAT%201.1 -F annotation_file=@zip`.

## Siguiente paso típico

Con el zip en `data/_harvest/`, construir el dataset de la ronda con un builder estilo
`scripts/active_learning/build_v3.py` (parsea annotations.xml → YOLO labels → merge con
el dataset anterior, split temporal 85/15 por cámara) y seguir con `/train-round <N>`.
