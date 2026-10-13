#!/usr/bin/env python3
"""3d — apariencia del inicio y del final de cada track, para unir trozos (stitch.py --feats).

Por track se toman sus K primeras y K últimas cajas y, de cada una, un recorte AMPLIADO
(`--scale` veces la caja, centrado en la cabeza): desde arriba la cabeza sola dice poco, y
hombros, pelo y ropa distinguen a una persona de la siguiente en la cola de la puerta.
Dos descriptores por recorte, promediados y normalizados por extremo del track:

  osnet  OSNet x0.25 (MSMT17) de boxmot, el ReID que usó DeepOC en el #28
  hsv    histograma HSV 8x4x4 (referencia barata, sin red)

Salida .npz: ids, y para cada descriptor `<d>_ini` y `<d>_fin` (una fila por id).

Necesita boxmot y opencv: en la torre con el venv de track-studio.
  ~/Projects/track-studio/.venv/bin/python reid_feats.py tracks.txt ~/videos/videoTM_03.mkv feats.npz
"""
import argparse, collections
from pathlib import Path

import cv2
import numpy as np

WEIGHTS = Path.home() / "Projects/track-studio/models/osnet_x0_25_msmt17.pt"


def hsv_hist(img):
    h = cv2.calcHist([cv2.cvtColor(img, cv2.COLOR_BGR2HSV)], [0, 1, 2], None, [8, 4, 4], [0, 180, 0, 256, 0, 256])
    return h.ravel()


def unit(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9)


def main():
    from boxmot.reid.core.runtime import ReID

    ap = argparse.ArgumentParser()
    ap.add_argument("mot")
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--scale", type=float, default=2.0)
    a = ap.parse_args()

    tracks = collections.defaultdict(list)
    for line in open(a.mot):
        q = line.split(",")
        if len(q) >= 6:
            tracks[int(q[1])].append((int(q[0]), *map(float, q[2:6])))
    ids = sorted(tracks)
    # (frame) -> [(id, extremo, x1, y1, x2, y2)]
    want = collections.defaultdict(list)
    for t in ids:
        pts = sorted(tracks[t])
        for end, sel in (("ini", pts[:a.k]), ("fin", pts[-a.k:])):
            for f, x, y, w, h in sel:
                cx, cy, s = x + w / 2, y + h / 2, a.scale * max(w, h) / 2
                want[f].append((t, end, cx - s, cy - s, cx + s, cy + s))

    reid = ReID(weights=WEIGHTS, device="0", half=False)
    acc = {(t, e, d): [] for t in ids for e in ("ini", "fin") for d in ("osnet", "hsv")}
    cap, n = cv2.VideoCapture(a.video), 0
    last = max(want)
    while n < last:
        ok, img = cap.read()
        if not ok:
            break
        n += 1  # frames del MOT contados desde 1
        if n not in want:
            continue
        H, W = img.shape[:2]
        boxes = np.array([[max(0, x1), max(0, y1), min(W, x2), min(H, y2)] for _, _, x1, y1, x2, y2 in want[n]])
        feats = reid(img, boxes)
        for (t, e, *_), b, f in zip(want[n], boxes.astype(int), feats):
            acc[(t, e, "osnet")].append(f)
            acc[(t, e, "hsv")].append(unit(hsv_hist(img[b[1]:b[3], b[0]:b[2]])))
    cap.release()

    out = {"ids": np.array(ids)}
    for d in ("osnet", "hsv"):
        for e in ("ini", "fin"):
            out[f"{d}_{e}"] = unit(np.stack([np.mean(acc[(t, e, d)], 0) for t in ids]))
    np.savez(a.out, **out)
    print(f"{len(ids)} tracks, {sum(map(len, want.values()))} recortes -> {a.out}")


if __name__ == "__main__":
    main()
