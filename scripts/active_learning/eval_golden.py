#!/usr/bin/env python3
"""Benchmark de modelos contra el GOLDEN TEST SET.
Reporta, por modelo: Precision / Recall / mAP50 / mAP50-95 (vía yolo val)
y MAE de conteo + sesgo (sobre/sub-conteo) por cámara y global.

Uso (dentro del contenedor mot-dev):
  python3 data/golden/eval_golden.py
Requiere data/golden/images/val + data/golden/labels/val + data/golden/golden.yaml ya construidos.
"""
import os, glob, cv2, subprocess, re
import numpy as np
from ultralytics import YOLO

GOLD="/workspace/data/golden"
MODELS={
    "BASE": "/workspace/models/yolov5mu-head-base.pt",
    "R2":   "/workspace/outputs/head_detector/yolo-bus-head-r2/weights/best.pt",
    "R3":   "/workspace/outputs/head_detector/yolo-bus-head-r3/weights/best.pt",
    "R4":   "/workspace/outputs/head_detector/yolo-bus-head-r4/weights/best.pt",
    "R5":   "/workspace/outputs/head_detector/yolo-bus-head-r5/weights/best.pt",
}
CONF, NMS = 0.25, 0.5

def gt_counts():
    d={}
    for lf in glob.glob(f"{GOLD}/labels/val/*.txt"):
        d[os.path.basename(lf)[:-4]]=sum(1 for ln in open(lf) if len(ln.split())==5)
    return d

def cam_of(stem):  # golden_<cam>_fXXXXXX
    return stem.split("_f")[0].replace("golden_","")

gt=gt_counts()
imgs=sorted(glob.glob(f"{GOLD}/images/val/*.jpg"))
print(f"Golden: {len(imgs)} imágenes, {sum(gt.values())} cabezas reales\n")

for name,mp in MODELS.items():
    m=YOLO(mp)
    # --- métricas detección (yolo val) ---
    out=subprocess.run(["yolo","val",f"model={mp}",f"data={GOLD}/golden.yaml",
                        "imgsz=640","workers=2",f"conf={CONF}",f"iou={NMS}"],
                       capture_output=True,text=True)
    mline=[l for l in out.stdout.splitlines() if re.match(r"\s+all\s",l)]
    # formato: all <imgs> <instances> <P> <R> <mAP50> <mAP50-95>
    det=mline[-1].split() if mline else ["-"]*7
    # --- error de conteo ---
    abs_err=[]; bias=[]; per_cam={}
    for p in imgs:
        stem=os.path.basename(p)[:-4]
        pred=len(m.predict(cv2.imread(p),conf=CONF,iou=NMS,verbose=False)[0].boxes)
        g=gt.get(stem,0); e=pred-g
        abs_err.append(abs(e)); bias.append(e)
        per_cam.setdefault(cam_of(stem),[]).append(abs(e))
    print(f"===== {name} =====")
    if len(det)>=7:
        print(f"  P={det[3]} R={det[4]} mAP50={det[5]} mAP50-95={det[6]}")
    print(f"  MAE conteo = {np.mean(abs_err):.2f} cabezas/frame | sesgo = {np.mean(bias):+.2f} "
          f"({'sobre-cuenta' if np.mean(bias)>0 else 'sub-cuenta'})")
    print("  MAE por cámara: "+" | ".join(f"{c}={np.mean(v):.2f}" for c,v in sorted(per_cam.items())))
    print()
