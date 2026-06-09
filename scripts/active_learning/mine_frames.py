#!/usr/bin/env python3
"""
Active-learning frame miner para ronda 3 (objetivo: detectar TODAS las cabezas).
Corre R2 sobre cámaras nuevas y selecciona los frames de mayor valor para anotar:
  - multitudes (muchas detecciones)
  - incertidumbre (detecciones de confianza media 0.15-0.40)
  - oscuridad (luminancia baja = debilidad conocida)
con diversidad temporal (top-K por segmento del video).
Salida: data/_harvest/round3_candidates/<cam>/*.jpg  (para subir a CVAT y auto-anotar).
"""
import os, cv2, csv
import numpy as np
from ultralytics import YOLO

MODEL = "/workspace/outputs/head_detector/yolo-bus-head-r2/weights/best.pt"
VID = "/videos"
OUT = "/workspace/data/_harvest/round3_candidates"
STEP = 25            # muestrear 1 de cada 25 frames como candidato
PER_VIDEO = 60       # frames finales por video
BINS = 30            # segmentos temporales para diversidad
CONF_LOW, CONF_HI = 0.15, 0.40

VIDEOS = [("video02", "videoTM_02.mkv"),
          ("video16", "videoTM_16.mkv"),
          ("S08",     "videoTM_18(1).mkv")]

model = YOLO(MODEL)
os.makedirs(OUT, exist_ok=True)

for cam, fname in VIDEOS:
    path = f"{VID}/{fname}"
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"\n=== {cam} ({fname}) — {total} frames, candidatos cada {STEP} ===")
    cand = []  # (idx, score, img)
    idx = 0
    while True:
        ret, img = cap.read()
        if not ret:
            break
        if idx % STEP == 0:
            r = model.predict(img, conf=CONF_LOW, verbose=False)[0]
            confs = r.boxes.conf.cpu().numpy() if r.boxes is not None else np.array([])
            n_det = int((confs >= 0.25).sum())
            n_unc = int(((confs >= CONF_LOW) & (confs < CONF_HI)).sum())
            lum = float(img.mean())
            dark = 3.0 if lum < 50 else (1.0 if lum < 80 else 0.0)
            score = n_det + 2.0 * n_unc + dark
            cand.append((idx, score, n_det, n_unc, lum, img.copy()))
        idx += 1
    cap.release()
    if not cand:
        print(f"  sin candidatos para {cam}"); continue

    # diversidad temporal: top-K por bin
    maxidx = max(c[0] for c in cand)
    binsz = max(1, (maxidx + 1) // BINS)
    by_bin = {}
    for c in cand:
        b = c[0] // binsz
        by_bin.setdefault(b, []).append(c)
    per_bin = max(1, PER_VIDEO // max(1, len(by_bin)))
    sel = []
    for b in sorted(by_bin):
        top = sorted(by_bin[b], key=lambda x: x[1], reverse=True)[:per_bin]
        sel.extend(top)
    # completar hasta PER_VIDEO con los de mayor score globales no incluidos
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
    avg_det = np.mean([c[2] for c in sel]); n_dark = sum(1 for c in sel if c[4] < 50)
    print(f"  {cam}: {len(sel)} frames seleccionados | media det={avg_det:.1f} | oscuros={n_dark}")

print("\nListo. Candidatos en data/_harvest/round3_candidates/<cam>/")
