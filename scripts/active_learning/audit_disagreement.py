#!/usr/bin/env python3
"""Audita desacuerdo R5 vs GT sobre bus_head_v5 para estimar carga de re-anotación.
Reporta cuántos frames tocaría revisar a mano (cabezas faltantes, cajas sin respaldo, duplicados)."""
import glob
from ultralytics import YOLO

R5 = "/workspace/outputs/head_detector/yolo-bus-head-r5/weights/best.pt"
root = "/workspace/data/bus_head_v5"
W, H = 640, 480
CONF_PROPOSE = 0.25

def iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / ua if ua > 0 else 0

def gt_boxes(lf):
    out = []
    try:
        for ln in open(lf):
            p = ln.split()
            if len(p) != 5: continue
            cx, cy, w, h = map(float, p[1:])
            out.append(((cx-w/2)*W, (cy-h/2)*H, (cx+w/2)*W, (cy+h/2)*H))
    except FileNotFoundError:
        pass
    return out

m = YOLO(R5)
flagged = set()
flag_missed = flag_wrong = flag_dup = 0
tot_missed = tot_wrong = nframes = 0
for sp in ("train", "val"):
    for im in sorted(glob.glob(f"{root}/images/{sp}/*.jpg")):
        nframes += 1
        lf = im.replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt"
        gts = gt_boxes(lf)
        r = m.predict(im, conf=CONF_PROPOSE, iou=0.5, verbose=False)[0]
        preds = r.boxes.xyxy.cpu().numpy().tolist() if r.boxes is not None else []
        used = set()
        for pb in preds:
            best, bj = -1, -1
            for j, gb in enumerate(gts):
                if j in used: continue
                v = iou(pb, gb)
                if v > best: best, bj = v, j
            if best > 0.4: used.add(bj)
        unmatched_pred = len(preds) - len(used)
        unmatched_gt = len(gts) - len(used)
        dup = any(iou(gts[i], gts[j]) > 0.5
                  for i in range(len(gts)) for j in range(i+1, len(gts)))
        if unmatched_pred >= 1:
            flag_missed += 1; flagged.add(im); tot_missed += unmatched_pred
        if unmatched_gt >= 2:
            flag_wrong += 1; flagged.add(im); tot_wrong += unmatched_gt
        if dup:
            flag_dup += 1; flagged.add(im)

print(f"Frames totales en v5: {nframes}")
print(f"--- frames a revisar (cualquier criterio): {len(flagged)}  ({100*len(flagged)/nframes:.0f}%)")
print(f"  - con cabezas que R5 ve y NO estan en GT (>=1): {flag_missed}  (total {tot_missed} cabezas candidatas a anadir)")
print(f"  - con 2+ cajas GT sin respaldo de R5: {flag_wrong}")
print(f"  - con duplicados GT (IoU>0.5): {flag_dup}")
print(f"--- frames LIMPIOS (sin tocar): {nframes-len(flagged)}  ({100*(nframes-len(flagged))/nframes:.0f}%)")
