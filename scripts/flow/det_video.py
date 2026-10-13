#!/usr/bin/env python3
"""Detecciones cacheadas de un video con unos pesos cualesquiera (para comparar detectores en la Tabla I).

Idéntico a `tools/sweep_trackers.py detect` de track-studio (conf 0,10, imgsz 640, NMS
post-hoc 0,6 entre detector y tracker), pero con los pesos como argumento. Formato de
salida: filas (frame contado desde 1, x1, y1, x2, y2, conf, cls), como `dets.npy`.
Control: con los pesos del campeón tiene que reproducir el `dets.npy` del sweep del 01-10.

Necesita ultralytics: en la torre con el venv de track-studio.
  ~/Projects/track-studio/.venv/bin/python det_video.py PESOS.pt ~/videos/videoTM_07.mkv dets_v7.npy
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.home() / "Projects/track-studio/src"))
from track_studio.jobs.infrastructure.tracking.ultralytics_tracker import nms_posthoc  # noqa: E402

CONF, IMGSZ, NMS_IOU = 0.10, 640, 0.6


def main():
    import cv2
    from ultralytics import YOLO

    weights, video, out = sys.argv[1:4]
    model, cap = YOLO(weights), cv2.VideoCapture(video)
    rows, n = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        n += 1
        boxes = model.predict(source=frame, conf=CONF, imgsz=IMGSZ, quantize=16, verbose=False)[0].boxes
        if boxes is None or len(boxes) == 0:
            continue
        data = boxes.data.cpu().numpy()
        data = data[nms_posthoc(data, NMS_IOU)]
        rows.append(np.column_stack([np.full(len(data), n), data]))
    np.save(out, np.vstack(rows).astype(np.float32))
    print(f"{n} frames, {sum(len(r) for r in rows)} cajas -> {out}")


if __name__ == "__main__":
    main()
