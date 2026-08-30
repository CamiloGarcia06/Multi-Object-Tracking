#!/usr/bin/env python3
"""Compara el rendimiento de un modelo contra DOS versiones del golden test set.

Uso tipico: despues de corregir las etiquetas del golden en CVAT, medir cuanto
del error del modelo era realmente error de etiquetado.

  v1 = data/golden/labels_val_v1_frozen   (etiquetas originales, congeladas)
  v2 = data/golden/labels/val             (etiquetas corregidas en CVAT)

Reporta, para cada version: P / R / F1 / MAE de conteo / sesgo, global y por camara,
mas el delta. Todo con matching greedy por confianza a IoU 0.5, igual que yolo val.

Uso (dentro del contenedor mot-dev):
  python3 /workspace/scripts/eval/compare_golden_versions.py
  python3 /workspace/scripts/eval/compare_golden_versions.py --conf 0.15
"""
import argparse, collections, glob, os

import cv2
import numpy as np
from ultralytics import YOLO

GOLD = "/workspace/data/golden"
DEFAULT_MODEL = "/workspace/outputs/head_detector/yolo-bus-head-min5/weights/best.pt"


def iou_mat(a, b):
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    x1 = np.maximum(a[:, None, 0], b[None, :, 0]); y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2]); y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    aa = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    bb = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / (aa[:, None] + bb[None, :] - inter + 1e-9)


def load_gt(lbl_path, W, H):
    g = []
    if not os.path.isfile(lbl_path):
        return np.zeros((0, 4))
    for ln in open(lbl_path):
        v = ln.split()
        if len(v) != 5:
            continue
        cx, cy, w, h = (float(x) for x in v[1:])
        g.append([(cx - w / 2) * W, (cy - h / 2) * H, (cx + w / 2) * W, (cy + h / 2) * H])
    return np.array(g).reshape(-1, 4)


def evaluate(model, lbl_dir, conf, nms, iou_thr):
    per_cam = collections.defaultdict(lambda: collections.Counter())
    err = collections.defaultdict(list)
    for img in sorted(glob.glob(f"{GOLD}/images/val/*.jpg")):
        stem = os.path.basename(img)[:-4]
        cam = stem.split("_f")[0].replace("golden_", "")
        im = cv2.imread(img)
        H, W = im.shape[:2]
        g = load_gt(f"{lbl_dir}/{stem}.txt", W, H)
        r = model.predict(im, conf=conf, iou=nms, verbose=False)[0]
        pr = r.boxes.xyxy.cpu().numpy().reshape(-1, 4)
        cf = r.boxes.conf.cpu().numpy()
        M = iou_mat(pr, g)
        mg, mp = set(), set()
        if M.size:
            for pi in np.argsort(-cf):
                cand = [gi for gi in range(len(g)) if gi not in mg and M[pi, gi] >= iou_thr]
                if cand:
                    gi = max(cand, key=lambda x: M[pi, x])
                    mg.add(gi); mp.add(int(pi))
        per_cam[cam]["TP"] += len(mg)
        per_cam[cam]["FN"] += len(g) - len(mg)
        per_cam[cam]["FP"] += len(pr) - len(mp)
        err[cam].append(len(pr) - len(g))
    return per_cam, err


def summarize(per_cam, err):
    tot = collections.Counter()
    for c in per_cam.values():
        tot.update(c)
    allerr = [e for v in err.values() for e in v]
    tp, fn, fp = tot["TP"], tot["FN"], tot["FP"]
    p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1)
    return {
        "P": p, "R": r, "F1": 2 * p * r / max(p + r, 1e-9),
        "MAE": float(np.mean(np.abs(allerr))), "bias": float(np.mean(allerr)),
        "TP": tp, "FN": fn, "FP": fp, "GT": tp + fn,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--nms", type=float, default=0.5)
    ap.add_argument("--iou", type=float, default=0.5, help="IoU de matching TP")
    ap.add_argument("--v1", default=f"{GOLD}/labels_val_v1_frozen")
    ap.add_argument("--v2", default=f"{GOLD}/labels/val")
    a = ap.parse_args()

    model = YOLO(a.model)
    print(f"modelo : {a.model}")
    print(f"config : conf={a.conf} nms={a.nms} matching IoU={a.iou}\n")

    res = {}
    for tag, d in (("v1 (original)", a.v1), ("v2 (corregido)", a.v2)):
        pc, er = evaluate(model, d, a.conf, a.nms, a.iou)
        res[tag] = (summarize(pc, er), pc, er)

    print(f"{'version':16s}{'GT':>6}{'TP':>6}{'FN':>6}{'FP':>6}{'P':>8}{'R':>8}{'F1':>8}{'MAE':>8}{'sesgo':>8}")
    for tag, (s, _, _) in res.items():
        print(f"{tag:16s}{s['GT']:6d}{s['TP']:6d}{s['FN']:6d}{s['FP']:6d}"
              f"{s['P']:8.3f}{s['R']:8.3f}{s['F1']:8.3f}{s['MAE']:8.2f}{s['bias']:+8.2f}")
    s1 = res["v1 (original)"][0]; s2 = res["v2 (corregido)"][0]
    print(f"{'DELTA':16s}{s2['GT']-s1['GT']:+6d}{s2['TP']-s1['TP']:+6d}{s2['FN']-s1['FN']:+6d}"
          f"{s2['FP']-s1['FP']:+6d}{s2['P']-s1['P']:+8.3f}{s2['R']-s1['R']:+8.3f}"
          f"{s2['F1']-s1['F1']:+8.3f}{s2['MAE']-s1['MAE']:+8.2f}{s2['bias']-s1['bias']:+8.2f}")

    print("\n--- por camara ---")
    print(f"{'cam':10s}{'ver':16s}{'GT':>6}{'TP':>6}{'FN':>6}{'FP':>6}{'P':>8}{'R':>8}{'MAE':>8}")
    cams = sorted(res["v1 (original)"][1])
    for cam in cams:
        for tag, (_, pc, er) in res.items():
            k = pc[cam]; tp, fn, fp = k["TP"], k["FN"], k["FP"]
            mae = float(np.mean(np.abs(er[cam])))
            print(f"{cam:10s}{tag:16s}{tp+fn:6d}{tp:6d}{fn:6d}{fp:6d}"
                  f"{tp/max(tp+fp,1):8.3f}{tp/max(tp+fn,1):8.3f}{mae:8.2f}")
        print()


if __name__ == "__main__":
    main()
