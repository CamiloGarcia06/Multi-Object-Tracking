#!/usr/bin/env python3
"""Recall y precisión del detector campeón sobre los goldens de TRACKING, por cámara.

Cada golden (data/tracking_golden/<clip>/gt/gt.txt, MOT 1.1) tiene TODAS las cabezas de sus
frames con caja corregida a mano, así que sirve también de golden de detección. Por cada frame:
detecciones (yolo26x-min5, NMS post-hoc 0,6) emparejadas 1-a-1 con el GT por IoU (húngaro).

  recall      = GT emparejado / GT                       (frame entero)
  recall_roi  = igual, solo GT con centro dentro de la ROI del pipeline
  precisión   = detecciones emparejadas / detecciones con centro en la ROI
                (fuera de la ROI el golden no está anotado)

Ojo: los goldens se pre-anotaron con este mismo detector + ByteTrack; una cabeza que el detector
no vio y que Camilo tampoco añadió no cuenta como fallo → el recall sale como cota SUPERIOR.

  ~/Projects/track-studio/.venv/bin/python scripts/eval/recall_por_camara.py [--md docs/recall-por-camara.md]
"""
import argparse, json, sys
from collections import defaultdict
from pathlib import Path

import numpy as np

TS = Path.home() / "Projects/track-studio"
sys.path.insert(0, str(TS / "src"))
from track_studio.jobs.infrastructure.tracking.ultralytics_tracker import nms_posthoc  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
WEIGHTS = TS / "models/yolo26x-min5-best.pt"
IMGSZ, NMS_IOU = 640, 0.6
CONFS = (0.10, 0.25)
IOUS = (0.5, 0.3)
CLIPS = {  # clip: (cámara, nivel, ROI del pipeline)
    "tm07_a": ("DDL", "baja", "roi_videoTM_07.json"),
    "tm02_a": ("DDL", "alta", "roi_videoTM_07.json"),  # el 02 corrió con la ROI del job 27 (= 07)
    "tm03_1_a": ("SDM", "media", "roi_videoTM_03_1.json"),
}


def inside(poly, x, y):
    c, j = False, len(poly) - 1
    for i in range(len(poly)):
        (xi, yi), (xj, yj) = poly[i], poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def iou(a, b):
    """a: (n,4) b: (m,4) en xyxy → (n,m)."""
    x1 = np.maximum(a[:, None, 0], b[None, :, 0]); y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2]); y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area = lambda r: (r[:, 2] - r[:, 0]) * (r[:, 3] - r[:, 1])
    return inter / (area(a)[:, None] + area(b)[None, :] - inter + 1e-9)


def match(gt, det, thr):
    from scipy.optimize import linear_sum_assignment

    if len(gt) == 0 or len(det) == 0:
        return np.zeros(len(gt), bool), np.zeros(len(det), bool)
    m = iou(gt, det)
    r, c = linear_sum_assignment(-m)
    ok = m[r, c] >= thr
    g, d = np.zeros(len(gt), bool), np.zeros(len(det), bool)
    g[r[ok]], d[c[ok]] = True, True
    return g, d


def main():
    import cv2
    from ultralytics import YOLO

    ap = argparse.ArgumentParser()
    ap.add_argument("--md", type=Path)
    a = ap.parse_args()
    model = YOLO(str(WEIGHTS))
    rows = []
    for clip, (cam, nivel, roi_file) in CLIPS.items():
        poly = json.load(open(REPO / "configs/cameras" / roi_file))["polygon"]
        gt = defaultdict(list)
        for l in (REPO / "data/tracking_golden" / clip / "gt/gt.txt").read_text().split():
            f, _, x, y, w, h, *_ = map(float, l.split(","))
            gt[int(f)].append((x, y, x + w, y + h))
        acc = {(c, t): defaultdict(int) for c in CONFS for t in IOUS}
        for f in sorted(gt):
            img = cv2.imread(str(REPO / "data/cvat_import" / clip / "frames" / f"frame_{f:06d}.png"))
            boxes = model.predict(source=img, conf=min(CONFS), imgsz=IMGSZ, verbose=False)[0].boxes
            data = np.zeros((0, 6)) if boxes is None or len(boxes) == 0 else boxes.data.cpu().numpy()
            d_all = data[nms_posthoc(data, NMS_IOU)] if len(data) else data
            g = np.array(gt[f])
            g_roi = np.array([inside(poly, (b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in g])
            for c in CONFS:
                d = d_all[d_all[:, 4] >= c][:, :4]
                d_roi = np.array([inside(poly, (b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in d], bool)
                for t in IOUS:
                    gm, dm = match(g, d, t)
                    s = acc[(c, t)]
                    s["gt"] += len(g); s["tp"] += gm.sum()
                    s["gt_roi"] += g_roi.sum(); s["tp_roi"] += (gm & g_roi).sum()
                    s["det_roi"] += d_roi.sum(); s["dtp_roi"] += (dm & d_roi).sum()
        for (c, t), s in acc.items():
            rows.append({"clip": clip, "camara": cam, "nivel": nivel, "conf": c, "iou": t, "frames": len(gt),
                         "gt": s["gt"], "recall": round(s["tp"] / s["gt"], 3),
                         "recall_roi": round(s["tp_roi"] / max(s["gt_roi"], 1), 3),
                         "precision_roi": round(s["dtp_roi"] / max(s["det_roi"], 1), 3)})
            print(json.dumps(rows[-1]), flush=True)
    if a.md:
        lines = ["# Recall del detector por cámara (goldens de tracking)", "",
                 "Generado por `scripts/eval/recall_por_camara.py`. Recall = cota superior (goldens pre-anotados con el detector).", "",
                 "| clip | cámara | nivel | conf | IoU | GT | recall | recall ROI | precisión ROI |", "|---|---|---|---|---|---|---|---|---|"]
        lines += [f"| {r['clip']} | {r['camara']} | {r['nivel']} | {r['conf']} | {r['iou']} | {r['gt']} | {r['recall']} | {r['recall_roi']} | {r['precision_roi']} |" for r in rows]
        a.md.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
