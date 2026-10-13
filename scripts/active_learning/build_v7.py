#!/usr/bin/env python3
"""Construye bus_head_v7 = bus_head_v5_min5 (tal cual) + ronda 7 de puerta corregida en CVAT.

Ronda 7 (data/_harvest/round7_door/export/, de exportar.sh): cajas `head` de la tarea de
CVAT -> etiquetas YOLO (cx cy w h normalizados, imágenes 640x480). Mismo criterio que
min5: solo entran imágenes con >= MIN_HEADS cabezas etiquetadas. Validación: 1 de cada
VAL_EVERY imágenes de cada cámara (por orden de frame), el resto a train.

v5_min5 entra con enlaces duros (mismo disco, no duplica espacio) y SIN cambios: la única
diferencia entre v7 y el campeón es la ronda 7.

  python3 scripts/active_learning/build_v7.py        (desde la raíz del repo, en la torre)
"""
import collections, json, os, re, shutil
from pathlib import Path

ROOT = Path("data")
SRC, R7, DST = ROOT / "bus_head_v5_min5", ROOT / "_harvest/round7_door", ROOT / "bus_head_v7"
W, H, MIN_HEADS, VAL_EVERY = 640, 480, 5, 10


def main():
    if DST.exists():
        shutil.rmtree(DST)
    for split in ("train", "val"):
        (DST / "images" / split).mkdir(parents=True)
        (DST / "labels" / split).mkdir(parents=True)

    n_src = collections.Counter()
    for split in ("train", "val"):
        for img in (SRC / "images" / split).iterdir():
            os.link(img, DST / "images" / split / img.name)
            lab = SRC / "labels" / split / (img.stem + ".txt")
            if lab.exists():
                os.link(lab, DST / "labels" / split / lab.name)
            n_src[split] += 1

    ann = json.load(open(R7 / "export/annotations.json"))
    meta = json.load(open(R7 / "export/meta.json"))
    names = [os.path.basename(f["name"]) for f in meta["frames"]]
    boxes = collections.defaultdict(list)
    for s in ann["shapes"]:
        x1, y1, x2, y2 = s["points"]
        x1, x2 = sorted((max(0, min(W, x1)), max(0, min(W, x2))))
        y1, y2 = sorted((max(0, min(H, y1)), max(0, min(H, y2))))
        if x2 - x1 > 1 and y2 - y1 > 1:
            boxes[names[s["frame"]]].append(((x1 + x2) / 2 / W, (y1 + y2) / 2 / H, (x2 - x1) / W, (y2 - y1) / H))

    by_cam = collections.defaultdict(list)
    for n in names:
        by_cam[re.match(r"(.+)_f\d+\.jpg$", n).group(1)].append(n)
    kept, dropped, per_split = collections.Counter(), collections.Counter(), collections.Counter()
    for cam, imgs in by_cam.items():
        imgs = [n for n in sorted(imgs) if len(boxes[n]) >= MIN_HEADS]
        dropped[cam] = len(by_cam[cam]) - len(imgs)
        for i, n in enumerate(imgs):
            split = "val" if i % VAL_EVERY == VAL_EVERY // 2 else "train"
            shutil.copy2(R7 / "out/img" / n, DST / "images" / split / n)
            (DST / "labels" / split / (n[:-4] + ".txt")).write_text(
                "".join(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n" for cx, cy, w, h in boxes[n]))
            kept[cam] += 1
            per_split[split] += 1

    (ROOT / "bus_head_v7.yaml").write_text(
        "path: /workspace/data/bus_head_v7\ntrain: images/train\nval: images/val\n\nnames:\n  0: head\n")
    print(json.dumps({"v5_min5": dict(n_src), "ronda7_entran": dict(per_split),
                      "ronda7_fuera_por_min5": sum(dropped.values()),
                      "ronda7_por_camara": dict(kept),
                      "cajas_ronda7": sum(len(boxes[n]) for c in by_cam for n in by_cam[c] if len(boxes[n]) >= MIN_HEADS),
                      "total": {s: len(list((DST / "images" / s).iterdir())) for s in ("train", "val")}},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
