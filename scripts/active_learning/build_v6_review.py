#!/usr/bin/env python3
"""Arma el lote de revisión COMPLETA para bus_head_v6.
Toma TODOS los frames de bus_head_v5 (train+val), pre-carga cada uno con
union(GT actual, propuestas R5 conf0.25) dedup IoU>0.5 a favor del GT,
y exporta CVAT-for-images (images/ + annotations.xml) para revisar a mano TODO.
GT -> source=manual ; cabeza extra propuesta por R5 -> source=auto."""
import glob, os, shutil
from xml.sax.saxutils import escape
from ultralytics import YOLO

R5 = "/workspace/outputs/head_detector/yolo-bus-head-r5/weights/best.pt"
SRC = "/workspace/data/bus_head_v5"
OUT = "/workspace/data/_harvest/v6_full"
W, H = 640, 480
CONF, IOU = 0.25, 0.5

def iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0, ix2-ix1), max(0, iy2-iy1)
    inter = iw*ih
    ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter/ua if ua > 0 else 0

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

if os.path.exists(OUT): shutil.rmtree(OUT)
os.makedirs(f"{OUT}/images")
m = YOLO(R5)

imgs = sorted(glob.glob(f"{SRC}/images/train/*.jpg")) + sorted(glob.glob(f"{SRC}/images/val/*.jpg"))
lines = ['<?xml version="1.0" encoding="utf-8"?>', '<annotations>', '  <version>1.1</version>',
         '  <meta><task><labels><label><name>head</name><type>rectangle</type><attributes></attributes></label></labels></task></meta>']
n_gt = n_auto = 0
for idx, im in enumerate(imgs):
    name = os.path.basename(im)
    lf = im.replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt"
    gts = gt_boxes(lf)
    r = m.predict(im, conf=CONF, iou=IOU, verbose=False)[0]
    preds = r.boxes.xyxy.cpu().numpy().tolist() if r.boxes is not None else []
    # union: todas las GT (manual) + R5 que no solape GT (auto)
    boxes = [(b, "manual") for b in gts]
    for pb in preds:
        if all(iou(pb, gb) <= IOU for gb in gts):
            boxes.append((pb, "auto"))
    shutil.copy2(im, f"{OUT}/images/{name}")
    lines.append(f'  <image id="{idx}" name="{escape(name)}" width="{W}" height="{H}">')
    for (x1, y1, x2, y2), src in boxes:
        x1 = max(0, min(W, x1)); x2 = max(0, min(W, x2))
        y1 = max(0, min(H, y1)); y2 = max(0, min(H, y2))
        lines.append(f'    <box label="head" source="{src}" occluded="0" '
                     f'xtl="{x1:.2f}" ytl="{y1:.2f}" xbr="{x2:.2f}" ybr="{y2:.2f}" z_order="0"></box>')
        if src == "manual": n_gt += 1
        else: n_auto += 1
    lines.append('  </image>')
lines.append('</annotations>')

with open(f"{OUT}/annotations.xml", "w") as fh:
    fh.write("\n".join(lines))
print(f"Frames: {len(imgs)}")
print(f"Cajas GT (manual): {n_gt}")
print(f"Cabezas extra propuestas por R5 (auto): {n_auto}")
print(f"Total cajas pre-cargadas: {n_gt + n_auto}")
print(f"Salida: {OUT}/images ({len(imgs)} jpg) + {OUT}/annotations.xml")
