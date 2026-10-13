#!/usr/bin/env python3
"""Ronda 7: el detector reentrenado con frames de puerta contra el campeón, en el golden de detección.

Criterio idéntico al número "honesto" del campeón (dup_analysis.py, A1): conf 0,25, NMS
post-hoc a 0,6 sobre la salida end-to-end de yolo26, matcher voraz a IoU 0,5. Reporta por
modelo P / R / MAE de conteo / sesgo, global y por cámara, y la comparación PAREADA imagen
a imagen (diferencia de error absoluto, IC95 por bootstrap y Wilcoxon).

Control: el campeón tiene que dar MAE 1,68 / sesgo -1,58 (golden_baseline.md). Si no, la
comparación no vale.

  python3 /workspace/scripts/eval/eval_v7.py            (dentro de mot-dev)
"""
import glob, json, os, sys

import cv2
import numpy as np
from ultralytics import YOLO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dup_analysis import cam_of, greedy_match, load_gt, nms_posthoc  # noqa: E402

G = "/workspace/data/golden"
O = "/workspace/outputs/head_detector"
MODELS = {"campeón yolo26x-min5": f"{O}/yolo26x-min5/weights/best.pt",
          "ronda 7 yolo26x-v7": f"{O}/yolo26x-v7/weights/best.pt"}
CONF, DUP, MATCH = 0.25, 0.6, 0.5


def run(path, images):
    model, out = YOLO(path), {}
    for p in images:
        img = cv2.imread(p)
        h, w = img.shape[:2]
        r = model.predict(source=img, conf=CONF, verbose=False)[0]
        pred, conf = r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy()
        pred, conf, _ = nms_posthoc(pred, conf, DUP)
        gt = load_gt(p.replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt", w, h)
        tp = len(greedy_match(pred, conf, gt, MATCH))
        out[os.path.basename(p)] = (len(pred), len(gt), tp)
    return out


def summary(res):
    n_pred, n_gt, tp = (np.array([v[i] for v in res.values()]) for i in range(3))
    err = n_pred - n_gt
    cams = {}
    for k, (p, g, _) in res.items():
        cams.setdefault(cam_of(k), []).append(abs(p - g))
    return {"P": round(tp.sum() / max(1, n_pred.sum()), 3), "R": round(tp.sum() / max(1, n_gt.sum()), 3),
            "MAE": round(float(np.abs(err).mean()), 2), "sesgo": round(float(err.mean()), 2),
            "MAE_por_camara": {c: round(float(np.mean(v)), 2) for c, v in sorted(cams.items())}}


def main():
    images = sorted(glob.glob(f"{G}/images/val/*.jpg"))
    res = {name: run(path, images) for name, path in MODELS.items() if os.path.exists(path)}
    out = {name: summary(r) for name, r in res.items()}
    if len(res) < 2:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    a, b = (np.array([abs(r[k][0] - r[k][1]) for k in sorted(r)]) for r in res.values())
    d = b - a  # < 0: la ronda 7 se equivoca menos
    rng = np.random.default_rng(0)
    boot = [rng.choice(d, len(d)).mean() for _ in range(10000)]
    try:
        from scipy.stats import wilcoxon
        p = float(wilcoxon(b, a).pvalue) if np.any(d) else 1.0
    except ImportError:
        p = None
    out["pareado (v7 - campeón, error absoluto por imagen)"] = {
        "dif_media": round(float(d.mean()), 3), "IC95": [round(float(np.percentile(boot, q)), 3) for q in (2.5, 97.5)],
        "wilcoxon_p": p, "gana/empata/pierde": [int((d < 0).sum()), int((d == 0).sum()), int((d > 0).sum())]}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
