#!/usr/bin/env python3
"""Arma el paquete CVAT para re-etiquetar s03 con pre-anotacion del modelo.

Contexto: los 1097 frames de s03 descartados por el filtro >=5 tienen 1 sola caja
cada uno (patron sistematico, no descuido) pese a ser escenas llenas -- el modelo
propone ~13 cabezas por frame. PERO estan separados 3 frames (0.1 s) y cubren solo
1.8 min de video: son casi duplicados. Por eso se muestrea con espaciado temporal.

La pre-anotacion usa conf BAJA a proposito: que el modelo sobre-proponga y el
anotador BORRE es mucho mas rapido que cazar cabezas faltantes, y el modo de falla
conocido del detector es sub-contar. Aceptable para datos de ENTRENAMIENTO;
no se haria asi para un test set.

Uso (dentro de mot-dev):
  python3 /workspace/scripts/dataset/build_s03_task.py --stride 10 --conf 0.10
"""
import argparse, glob, json, os, re, shutil, zipfile
from pathlib import Path

REPO = Path("/workspace")
SRC = REPO / "data" / "bus_head_v5"
MIN5 = REPO / "data" / "bus_head_v5_min5"
MODEL = REPO / "outputs" / "head_detector" / "yolo26x-min5" / "weights" / "best.pt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stride", type=int, default=10, help="1 de cada N frames (10 = ~1 s a 30fps)")
    ap.add_argument("--conf", type=float, default=0.10)
    ap.add_argument("--out", type=Path, default=REPO / "outputs" / "cvat_packages")
    ap.add_argument("--name", default="s03_relabel_b1")
    a = ap.parse_args()

    keep = {p.name for p in MIN5.glob("labels/*/*.txt")}
    lbls = sorted(p for p in SRC.glob("labels/*/*.txt")
                  if p.name not in keep and p.name.startswith("s03"))
    lbls.sort(key=lambda p: int(re.search(r"_f(\d+)", p.name).group(1)))
    pick = lbls[::a.stride]
    print(f"s03 descartados: {len(lbls)} | muestreados 1/{a.stride}: {len(pick)}")

    from ultralytics import YOLO
    m = YOLO(str(MODEL))

    stage = a.out / a.name
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "images" / "train").mkdir(parents=True)
    (stage / "labels" / "train").mkdir(parents=True)

    total = 0
    for lp in pick:
        ip = Path(str(lp).replace("/labels/", "/images/").replace(".txt", ".jpg"))
        if not ip.is_file():
            print(f"  falta imagen {ip.name}"); continue
        r = m.predict(str(ip), conf=a.conf, iou=0.5, verbose=False)[0]
        H, W = r.orig_shape
        lines = []
        for b in r.boxes:
            x1, y1, x2, y2 = b.xyxy[0].tolist()
            cx, cy = (x1 + x2) / 2 / W, (y1 + y2) / 2 / H
            w, h = (x2 - x1) / W, (y2 - y1) / H
            lines.append(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
        total += len(lines)
        shutil.copy2(ip, stage / "images" / "train" / ip.name)
        (stage / "labels" / "train" / lp.name).write_text("".join(lines))

    print(f"pre-anotadas {total} cajas (conf={a.conf}) -> {total/max(len(pick),1):.1f}/frame")

    zp = a.out / f"{a.name}.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("data.yaml", "path: .\ntrain: images/train\n\nnames:\n  0: head\n")
        zf.writestr(zipfile.ZipInfo("images/train/"), b"")
        for p in sorted((stage / "images" / "train").iterdir()):
            zf.write(p, f"images/train/{p.name}")
        for p in sorted((stage / "labels" / "train").iterdir()):
            zf.write(p, f"labels/train/{p.name}")
    print(f"zip -> {zp} ({zp.stat().st_size/1e6:.1f} MB)")
    json.dump([p.name for p in pick], open(a.out / f"{a.name}_frames.json", "w"))


if __name__ == "__main__":
    main()
