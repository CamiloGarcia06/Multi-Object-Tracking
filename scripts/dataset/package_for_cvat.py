#!/usr/bin/env python3
"""Empaqueta un dataset YOLO local en zips autocontenidos listos para:

  1. respaldar en la nube (Drive / Dropbox / NAS), y
  2. re-importarse a CVAT sin tocar nada:
       - crear la tarea subiendo el mismo zip (CVAT toma solo los .jpg), y
       - importar las cajas con el formato "Ultralytics YOLO Detection 1.0".

Estructura generada dentro de cada zip (la que espera datumaro 0.3, el
importador que usa CVAT):

    data.yaml            path: .  /  <split>: images/<split>  /  names: {0: head}
    images/<split>/*.jpg
    labels/<split>/*.txt

Uso:
    python scripts/dataset/package_for_cvat.py data/bus_head_v5
    python scripts/dataset/package_for_cvat.py data/bus_head_v5 --splits val
    python scripts/dataset/package_for_cvat.py data/bus_head_v5 --labels-only
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def data_yaml(split: str, names: list[str]) -> str:
    lines = ["path: .", f"{split}: images/{split}", "", "names:"]
    lines += [f"  {i}: {n}" for i, n in enumerate(names)]
    return "\n".join(lines) + "\n"


def read_names(dataset: Path) -> list[str]:
    """Lee las clases del <dataset>.yaml hermano (o de un .yaml interno)."""
    sidecar = dataset.with_suffix(".yaml")
    if not sidecar.is_file():
        internos = sorted(dataset.glob("*.yaml"))
        if not internos:
            return ["head"]
        sidecar = internos[0]
    names: dict[int, str] = {}
    in_names = False
    for raw in sidecar.read_text().splitlines():
        if raw.startswith("names:"):
            in_names = True
            continue
        if in_names:
            if raw.strip() and not raw.startswith((" ", "\t", "-")):
                break
            if ":" in raw:
                idx, _, name = raw.strip().partition(":")
                try:
                    names[int(idx)] = name.strip()
                except ValueError:
                    continue
    return [names[i] for i in sorted(names)] if names else ["head"]


def package(dataset: Path, split: str, out_dir: Path, names: list[str], labels_only: bool) -> Path:
    img_dir = dataset / "images" / split
    lbl_dir = dataset / "labels" / split
    if not lbl_dir.is_dir():
        raise SystemExit(f"no existe {lbl_dir}")

    images = sorted(p for p in img_dir.iterdir() if p.suffix.lower() in IMG_EXTS) if img_dir.is_dir() else []
    labels = sorted(lbl_dir.glob("*.txt"))

    huerfanos = {p.stem for p in labels} - {p.stem for p in images}
    if images and huerfanos:
        print(f"  aviso: {len(huerfanos)} labels sin imagen (p.ej. {sorted(huerfanos)[:3]})")

    suffix = "labels" if labels_only else "full"
    zip_path = out_dir / f"{dataset.name}_{split}_{suffix}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("data.yaml", data_yaml(split, names))
        # El directorio images/<split> DEBE existir aunque vaya vacío: datumaro
        # exige isdir() y, si no encuentra imágenes, reconstruye los ítems a
        # partir de los frames que CVAT ya tiene en la tarea (image_info).
        zf.writestr(zipfile.ZipInfo(f"images/{split}/"), b"")
        if not labels_only:
            for p in images:
                zf.write(p, f"images/{split}/{p.name}")
        for p in labels:
            zf.write(p, f"labels/{split}/{p.name}")

    mb = zip_path.stat().st_size / 1e6
    print(f"  {zip_path.name}: {len(labels)} labels, "
          f"{0 if labels_only else len(images)} imgs, {mb:.1f} MB")
    return zip_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dataset", type=Path, help="ruta al dataset, p.ej. data/bus_head_v5")
    ap.add_argument("--splits", nargs="+", default=None, help="por defecto: los que existan")
    ap.add_argument("--out", type=Path, default=Path("outputs/cvat_packages"))
    ap.add_argument("--labels-only", action="store_true",
                    help="zip liviano solo con las cajas (las imágenes ya están en CVAT)")
    args = ap.parse_args()

    dataset = args.dataset.resolve()
    if not dataset.is_dir():
        raise SystemExit(f"no existe {dataset}")

    splits = args.splits or [d.name for d in sorted((dataset / "labels").iterdir()) if d.is_dir()]
    names = read_names(dataset)
    args.out.mkdir(parents=True, exist_ok=True)

    print(f"dataset: {dataset}\nclases:  {names}\nsplits:  {splits}\n")
    zips = [package(dataset, s, args.out, names, args.labels_only) for s in splits]

    sums = args.out / f"{dataset.name}_SHA256SUMS.txt"
    sums.write_text("".join(f"{sha256(z)}  {z.name}\n" for z in zips))
    print(f"\nchecksums: {sums}")
    print(f"listo -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
