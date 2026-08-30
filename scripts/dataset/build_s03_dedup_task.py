#!/usr/bin/env python3
"""Arma la tarea CVAT de re-etiquetado de s03 SOLO con los frames visualmente distintos.

Motivacion medida: los frames de s03 estan separados 0.1 s y cubren 1.8 min de UNA camara.
De los 1097 frames mal etiquetados (1 caja cada uno pese a ser escenas llenas), solo ~338
son visualmente distintos con umbral de similitud 0.90 -- el resto son repeticiones.
Revisar los 1097 es triplicar el trabajo por la misma informacion, y reincorporar s03 en
bloque restaura el desbalance que MIN5 arreglo al descartarlo (s03 ya es el 54% de min5).

Las cajas NO se re-predicen: se toman del export vigente de la tarea de review, para
conservar las correcciones humanas ya hechas.

Uso (dentro de mot-dev):
  python3 /workspace/scripts/dataset/build_s03_dedup_task.py \
      --export data/_harvest/task5_v6review.zip --thr 0.90
"""
import argparse, os, glob, re, shutil, zipfile
from pathlib import Path

import cv2
import numpy as np

REPO = Path("/workspace")
SRC = REPO / "data" / "bus_head_v5"
MIN5 = REPO / "data" / "bus_head_v5_min5"


def descriptor(p):
    im = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
    if im is None:
        return None
    v = cv2.resize(im, (32, 24)).astype(np.float32).ravel()
    v -= v.mean()
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", type=Path, required=True, help="zip export de la tarea de review")
    ap.add_argument("--thr", type=float, default=0.90, help="similitud maxima permitida entre frames elegidos")
    ap.add_argument("--out", type=Path, default=REPO / "outputs" / "cvat_packages")
    ap.add_argument("--name", default="s03_dedup")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    # cajas vigentes desde el export (incluye correcciones humanas)
    boxes = {}
    with zipfile.ZipFile(a.export) as zf:
        for n in zf.namelist():
            if n.endswith(".txt") and "/labels/" in f"/{n}":
                boxes[Path(n).stem] = [l for l in zf.read(n).decode().splitlines()
                                       if len(l.split()) == 5]
    print(f"export: {len(boxes)} frames con cajas")

    keep = {p.name for p in MIN5.glob("images/*/*.jpg")}
    bad = sorted((p for p in SRC.glob("images/*/s03_*.jpg") if p.name not in keep),
                 key=lambda p: int(re.search(r"_f(\d+)", p.name).group(1)))
    print(f"s03 mal etiquetados: {len(bad)}")

    D, K = [], []
    for p in bad:
        d = descriptor(p)
        if d is not None:
            D.append(d); K.append(p)
    D = np.array(D)
    sel = [0]
    for i in range(1, len(D)):
        if (D[sel] @ D[i]).max() < a.thr:
            sel.append(i)
    pick = [K[i] for i in sel]
    ncaj = sum(len(boxes.get(p.stem, [])) for p in pick)
    print(f"seleccionados (umbral {a.thr}): {len(pick)} frames  |  {ncaj} cajas ya puestas "
          f"({ncaj/max(len(pick),1):.1f}/frame)")
    sinc = [p.stem for p in pick if p.stem not in boxes]
    if sinc:
        print(f"  aviso: {len(sinc)} frames sin cajas en el export (p.ej. {sinc[:2]})")
    if a.dry_run:
        print("--dry-run: no se escribio nada"); return

    stage = a.out / a.name
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "images" / "train").mkdir(parents=True)
    (stage / "labels" / "train").mkdir(parents=True)
    for p in pick:
        shutil.copy2(p, stage / "images" / "train" / p.name)
        (stage / "labels" / "train" / f"{p.stem}.txt").write_text(
            "\n".join(boxes.get(p.stem, [])) + ("\n" if boxes.get(p.stem) else ""))

    zp = a.out / f"{a.name}.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("data.yaml", "path: .\ntrain: images/train\n\nnames:\n  0: head\n")
        zf.writestr(zipfile.ZipInfo("images/train/"), b"")
        for p in sorted((stage / "images" / "train").iterdir()):
            zf.write(p, f"images/train/{p.name}")
        for p in sorted((stage / "labels" / "train").iterdir()):
            zf.write(p, f"labels/train/{p.name}")
    print(f"zip -> {zp} ({zp.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
