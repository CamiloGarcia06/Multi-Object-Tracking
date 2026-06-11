#!/usr/bin/env python3
"""bus_head_v5 = bus_head_v3 + 225 frames corregidos (round5).
Base = v3 (dataset del campeón R3); v4/R4 regresionó en golden, no se usa.
Split temporal 85/15 POR CÁMARA en los frames nuevos (val honesto por cámara nueva).
Corre en host (solo stdlib). Dimensiones por imagen leídas del XML."""
import os, shutil
import xml.etree.ElementTree as ET
from collections import defaultdict

REPO = "/home/camilo-pc/Multi-Object-Tracking"
H_ = f"{REPO}/data/_harvest"
EXP = f"{H_}/round5_export_check"
SRC_V3 = f"{REPO}/data/bus_head_v3"
DST = f"{REPO}/data/bus_head_v5"

# 1) v5 = copia de v3
if os.path.exists(DST):
    shutil.rmtree(DST)
for sp in ("train", "val"):
    os.makedirs(f"{DST}/images/{sp}")
    os.makedirs(f"{DST}/labels/{sp}")
n3 = 0
for sp in ("train", "val"):
    for fn in os.listdir(f"{SRC_V3}/images/{sp}"):
        shutil.copy2(f"{SRC_V3}/images/{sp}/{fn}", f"{DST}/images/{sp}/{fn}")
        n3 += 1
    for fn in os.listdir(f"{SRC_V3}/labels/{sp}"):
        shutil.copy2(f"{SRC_V3}/labels/{sp}/{fn}", f"{DST}/labels/{sp}/{fn}")
print(f"v3 copiado: {n3} imágenes")

# 2) parsear xml -> por cámara (dims por imagen)
root = ET.parse(f"{EXP}/annotations.xml").getroot()
bycam = defaultdict(list)  # cam -> [(name, [boxes])]
for im in root.findall("image"):
    name = im.get("name")
    cam = name.rsplit("_f", 1)[0]
    W = float(im.get("width"))
    Hh = float(im.get("height"))
    boxes = []
    for b in im.findall("box"):
        if b.get("label") != "head":
            continue
        x1 = float(b.get("xtl")); y1 = float(b.get("ytl"))
        x2 = float(b.get("xbr")); y2 = float(b.get("ybr"))
        cx = min(max(((x1 + x2) / 2) / W, 0), 1)
        cy = min(max(((y1 + y2) / 2) / Hh, 0), 1)
        bw = min(abs(x2 - x1) / W, 1)
        bh = min(abs(y2 - y1) / Hh, 1)
        boxes.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    bycam[cam].append((name, boxes))

# 3) split temporal 85/15 por cámara + copiar imagen + label
def find_img(name):
    for sub in ("images", "images/default", "."):
        p = f"{EXP}/{sub}/{name}"
        if os.path.exists(p):
            return p
    for r, _, fs in os.walk(EXP):
        if name in fs:
            return f"{r}/{name}"
    return None

added = defaultdict(lambda: [0, 0])
nboxes = 0
for cam, items in bycam.items():
    items.sort(key=lambda x: x[0])
    cut = int(len(items) * 0.85)
    for i, (name, boxes) in enumerate(items):
        sp = "train" if i < cut else "val"
        src = find_img(name)
        if not src:
            print(f"  !! falta imagen {name}")
            continue
        shutil.copy2(src, f"{DST}/images/{sp}/{name}")
        stem = name.rsplit(".", 1)[0]
        with open(f"{DST}/labels/{sp}/{stem}.txt", "w") as fh:
            fh.write("\n".join(boxes) + ("\n" if boxes else ""))
        added[cam][0 if sp == "train" else 1] += 1
        nboxes += len(boxes)
print("nuevos por cámara (train,val):", {k: tuple(v) for k, v in added.items()})
print(f"cabezas nuevas añadidas: {nboxes}")

# 4) resumen + verificación de paridad img/label
for sp in ("train", "val"):
    ni = len(os.listdir(f"{DST}/images/{sp}"))
    nl = len(os.listdir(f"{DST}/labels/{sp}"))
    flag = "OK" if ni == nl else "!! MISMATCH"
    print(f"  {sp}: {ni} imgs / {nl} labels  {flag}")
