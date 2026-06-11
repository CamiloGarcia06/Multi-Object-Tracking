#!/usr/bin/env python3
"""
Ronda 5 — minado de frames de alto valor (recall diurno / generalizacion).
Receta extract_bright: frames bien iluminados (lum>=65) con gente (n_det>=3),
score = n_det + 2*n_uncertain[0.15-0.40], diversidad por bins temporales.
Scorer = modelo CAMPEON R3. Sobre 5 videos nuevos.
Salida: data/_harvest/round5_candidates/<cam>/*.jpg
"""
import os, cv2, csv
import numpy as np
from ultralytics import YOLO

MODEL = "/workspace/outputs/head_detector/yolo-bus-head-r3/weights/best.pt"
VID = "/videos"
OUT = "/workspace/data/_harvest/round5_candidates"
STEP = 20
PER_VIDEO = 45
BINS = 30
MIN_LUM = 65
MIN_DET = 3
CONF_LOW, CONF_HI = 0.15, 0.40

# codigos de camara colision-safe: no chocan con stems de entrenamiento (v04,v05,v16,...)
# ni del golden (video02,v05,v16,S08).
VIDEOS = [("v11",   "videoTM_11.mkv"),
          ("v12",   "videoTM_12.mkv"),
          ("v04_2", "videoTM_04(2).mkv"),
          ("v05_1", "videoTM_05(1).mkv"),
          ("v04_1", "videoTM_04(1).mkv")]

model = YOLO(MODEL)
os.makedirs(OUT, exist_ok=True)
grand = 0

for cam, fname in VIDEOS:
    path = f"{VID}/{fname}"
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"  !! no se pudo abrir {fname} — SALTADO"); continue
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"\n=== {cam} ({fname}) — {total} frames ===")
    cand = []
    idx = 0
    while True:
        ret, img = cap.read()
        if not ret:
            break
        if idx % STEP == 0:
            lum = float(img.mean())
            if lum >= MIN_LUM:
                r = model.predict(img, conf=CONF_LOW, verbose=False)[0]
                confs = r.boxes.conf.cpu().numpy() if r.boxes is not None else np.array([])
                n_det = int((confs >= 0.25).sum())
                if n_det >= MIN_DET:
                    n_unc = int(((confs >= CONF_LOW) & (confs < CONF_HI)).sum())
                    score = n_det + 2.0 * n_unc
                    cand.append((idx, score, n_det, n_unc, lum, img.copy()))
        idx += 1
    cap.release()
    if not cand:
        print(f"  sin candidatos validos para {cam}"); continue

    maxidx = max(c[0] for c in cand)
    binsz = max(1, (maxidx + 1) // BINS)
    by_bin = {}
    for c in cand:
        by_bin.setdefault(c[0] // binsz, []).append(c)
    per_bin = max(1, PER_VIDEO // max(1, len(by_bin)))
    sel = []
    for b in sorted(by_bin):
        sel.extend(sorted(by_bin[b], key=lambda x: x[1], reverse=True)[:per_bin])
    sel_idx = {c[0] for c in sel}
    extra = sorted([c for c in cand if c[0] not in sel_idx], key=lambda x: x[1], reverse=True)
    sel.extend(extra[:max(0, PER_VIDEO - len(sel))])
    sel = sel[:PER_VIDEO]

    cdir = f"{OUT}/{cam}"; os.makedirs(cdir, exist_ok=True)
    with open(f"{cdir}/_scores.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["frame", "score", "n_det", "n_unc", "luminance"])
        for fidx, sc, nd, nu, lum, img in sorted(sel, key=lambda x: x[0]):
            cv2.imwrite(f"{cdir}/{cam}_f{fidx:06d}.jpg", img)
            w.writerow([fidx, f"{sc:.1f}", nd, nu, f"{lum:.1f}"])
    grand += len(sel)
    print(f"  {cam}: {len(sel)} frames | candidatos brillantes={len(cand)} | "
          f"media det={np.mean([c[2] for c in sel]):.1f} | lum media={np.mean([c[4] for c in sel]):.0f}")

print(f"\nTOTAL seleccionados: {grand} frames en {OUT}/<cam>/")
