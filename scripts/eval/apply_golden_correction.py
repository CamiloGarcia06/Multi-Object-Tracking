#!/usr/bin/env python3
"""Aplica al golden las etiquetas corregidas exportadas desde CVAT.

Toma el zip exportado de la tarea de auditoria (formato **Ultralytics YOLO
Detection 1.0**), reescribe data/golden/labels/val y reporta el diff contra la
version congelada v1: cajas agregadas, borradas y movidas, por camara.

NO toca data/golden/labels_val_v1_frozen (el benchmark original).

Uso:
  python3 scripts/eval/apply_golden_correction.py data/_harvest/<export>.zip
  python3 scripts/eval/apply_golden_correction.py <zip> --dry-run
"""
import argparse, collections, os, shutil, sys, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GOLD = REPO / "data" / "golden"
V1 = GOLD / "labels_val_v1_frozen"
DST = GOLD / "labels" / "val"


def read_boxes(text):
    out = []
    for ln in text.splitlines():
        v = ln.split()
        if len(v) == 5:
            out.append(tuple(round(float(x), 6) for x in v[1:]))
    return out


def centre_dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def diff(old, new, tol=0.004):
    """Clasifica en identicas / movidas / agregadas / borradas."""
    rem_new = list(new); moved = same = 0
    for o in old:
        exact = next((n for n in rem_new if n == o), None)
        if exact is not None:
            rem_new.remove(exact); same += 1; continue
        near = min(rem_new, key=lambda n: centre_dist(o, n), default=None)
        if near is not None and centre_dist(o, near) < tol:
            rem_new.remove(near); moved += 1; continue
    deleted = len(old) - same - moved
    return same, moved, len(rem_new), deleted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip_path", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not a.zip_path.is_file():
        sys.exit(f"no existe {a.zip_path}")
    if not V1.is_dir():
        sys.exit(f"falta el congelado {V1} -- no hay contra que comparar")

    new = {}
    with zipfile.ZipFile(a.zip_path) as zf:
        for n in zf.namelist():
            if n.endswith(".txt") and "/labels/" in f"/{n}" and not n.endswith("obj.names"):
                new[Path(n).stem] = read_boxes(zf.read(n).decode("utf-8", "replace"))
    if not new:
        sys.exit("el zip no trae labels/*.txt -- exportaste en el formato correcto? "
                 "(Ultralytics YOLO Detection 1.0)")

    old = {p.stem: read_boxes(p.read_text()) for p in V1.glob("*.txt")}
    faltan = set(old) - set(new)
    if faltan:
        print(f"AVISO: {len(faltan)} frames del golden no vienen en el export "
              f"(p.ej. {sorted(faltan)[:3]}) -- se dejan como estaban")

    cam = collections.defaultdict(lambda: collections.Counter())
    for stem in sorted(old):
        if stem not in new:
            continue
        c = stem.split("_f")[0].replace("golden_", "")
        s, m, added, deleted = diff(old[stem], new[stem])
        k = cam[c]
        k["frames"] += 1; k["igual"] += s; k["movida"] += m
        k["agregada"] += added; k["borrada"] += deleted
        k["gt_v1"] += len(old[stem]); k["gt_v2"] += len(new[stem])

    print(f"\n{'cam':10s}{'frames':>7}{'GT v1':>8}{'GT v2':>8}{'delta':>7}"
          f"{'igual':>8}{'movida':>8}{'agreg':>7}{'borr':>7}")
    tot = collections.Counter()
    for c, k in sorted(cam.items()):
        tot.update(k)
        print(f"{c:10s}{k['frames']:7d}{k['gt_v1']:8d}{k['gt_v2']:8d}"
              f"{k['gt_v2']-k['gt_v1']:+7d}{k['igual']:8d}{k['movida']:8d}"
              f"{k['agregada']:7d}{k['borrada']:7d}")
    print(f"{'TOTAL':10s}{tot['frames']:7d}{tot['gt_v1']:8d}{tot['gt_v2']:8d}"
          f"{tot['gt_v2']-tot['gt_v1']:+7d}{tot['igual']:8d}{tot['movida']:8d}"
          f"{tot['agregada']:7d}{tot['borrada']:7d}")

    if a.dry_run:
        print("\n--dry-run: no se escribio nada")
        return

    n = 0
    for stem, boxes in new.items():
        if stem not in old:
            continue
        (DST / f"{stem}.txt").write_text(
            "".join(f"0 {b[0]:.6f} {b[1]:.6f} {b[2]:.6f} {b[3]:.6f}\n" for b in boxes))
        n += 1
    for c in GOLD.glob("labels/val.cache"):
        c.unlink()   # ultralytics cachea las etiquetas: invalidar
    print(f"\nescritos {n} archivos en {DST}")
    print("cache de ultralytics invalidada")
    print("\nsiguiente paso:\n  python3 scripts/eval/compare_golden_versions.py")


if __name__ == "__main__":
    main()
