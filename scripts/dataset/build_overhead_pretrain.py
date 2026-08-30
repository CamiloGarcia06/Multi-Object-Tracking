#!/usr/bin/env python3
"""Filtra el dataset OverHead Head Detection (Roboflow) para que sea usable.

El dataset crudo NO sirve: 89% de las imagenes no tiene ninguna caja pese a
contener multitudes vistas desde arriba (positivos sin etiquetar -- la misma
enfermedad de s03 que produjo el sub-conteo cronico). Ademas viene inflado por
aumentaciones (13841 archivos <- 4726 fuentes) y con fuga entre sus splits.

Este script deja solo lo aprovechable:
  1. agrupa por imagen FUENTE (prefijo antes de _jpg.rf.<hash>)  -> sin duplicados
  2. descarta cajas basura: area > MAX_AREA de la imagen (grupos enteros mal
     etiquetados), relacion de aspecto extrema, o lado < MIN_SIDE px
  3. se queda solo con imagenes de >= MIN_BOXES cajas validas
  4. re-particiona train/val POR FUENTE (no por archivo) -> sin fuga

Uso:
  python3 scripts/dataset/build_overhead_pretrain.py /ruta/oh_extraido --out data/overhead_head
"""
import argparse, collections, os, random, re, shutil, sys
from pathlib import Path

RF = re.compile(r"(.+?)_(jpg|jpeg|png)\.rf\.[0-9a-f]+$")


def source_key(stem):
    m = RF.match(stem)
    return m.group(1) if m else stem


def read_boxes(p):
    out = []
    for ln in open(p):
        v = ln.split()
        if len(v) != 5:
            continue
        try:
            out.append(tuple(float(x) for x in v[1:]))
        except ValueError:
            continue
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path, help="carpeta con train/ valid/ test/ del export de Roboflow")
    ap.add_argument("--out", type=Path, default=Path("data/overhead_head"))
    ap.add_argument("--min-boxes", type=int, default=3)
    ap.add_argument("--max-area", type=float, default=0.15, help="fraccion max del area de la imagen")
    ap.add_argument("--min-side", type=float, default=10.0, help="lado minimo en px (imagenes 640x640)")
    ap.add_argument("--max-ar", type=float, default=3.0, help="relacion de aspecto max caja")
    ap.add_argument("--val-frac", type=float, default=0.10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    # --- recolectar una sola copia por fuente ---
    best = {}   # source -> (n_cajas_validas, img_path, lbl_path, cajas)
    stats = collections.Counter()
    for split in ("train", "valid", "test"):
        ld = a.src / split / "labels"
        idir = a.src / split / "images"
        if not ld.is_dir():
            continue
        for lp in sorted(ld.glob("*.txt")):
            stem = lp.stem
            ip = idir / f"{stem}.jpg"
            if not ip.is_file():
                stats["sin_imagen"] += 1
                continue
            raw = read_boxes(lp)
            stats["cajas_crudas"] += len(raw)
            keep = []
            for cx, cy, w, h in raw:
                if w * h > a.max_area:
                    stats["descartada_enorme"] += 1; continue
                W = w * 640.0; H = h * 640.0
                if min(W, H) < a.min_side:
                    stats["descartada_diminuta"] += 1; continue
                ar = max(W / max(H, 1e-6), H / max(W, 1e-6))
                if ar > a.max_ar:
                    stats["descartada_aspecto"] += 1; continue
                keep.append((cx, cy, w, h))
            stats["archivos_vistos"] += 1
            if len(keep) < a.min_boxes:
                stats["imagen_pocas_cajas"] += 1
                continue
            k = source_key(stem)
            if k not in best or len(keep) > best[k][0]:
                best[k] = (len(keep), ip, keep)

    srcs = sorted(best)
    print(f"archivos vistos        : {stats['archivos_vistos']}")
    print(f"cajas crudas           : {stats['cajas_crudas']}")
    print(f"  descartadas enormes  : {stats['descartada_enorme']}")
    print(f"  descartadas diminutas: {stats['descartada_diminuta']}")
    print(f"  descartadas aspecto  : {stats['descartada_aspecto']}")
    print(f"imagenes con <{a.min_boxes} cajas : {stats['imagen_pocas_cajas']} (descartadas)")
    print(f"\nFUENTES UNICAS APROVECHABLES: {len(srcs)}")
    print(f"cajas finales               : {sum(v[0] for v in best.values())}")
    if srcs:
        import statistics as st
        print(f"cajas/imagen               : mediana {st.median(v[0] for v in best.values()):.0f}"
              f" max {max(v[0] for v in best.values())}")

    if a.dry_run or not srcs:
        print("\n--dry-run: no se escribio nada" if a.dry_run else "\nnada que escribir")
        return

    random.Random(a.seed).shuffle(srcs)
    ncut = int(len(srcs) * (1 - a.val_frac))
    parts = {"train": srcs[:ncut], "val": srcs[ncut:]}
    for sp in ("train", "val"):
        (a.out / "images" / sp).mkdir(parents=True, exist_ok=True)
        (a.out / "labels" / sp).mkdir(parents=True, exist_ok=True)
    for sp, keys in parts.items():
        for k in keys:
            n, ip, boxes = best[k]
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", k)
            shutil.copy2(ip, a.out / "images" / sp / f"oh_{safe}.jpg")
            (a.out / "labels" / sp / f"oh_{safe}.txt").write_text(
                "".join(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n" for cx, cy, w, h in boxes))
        print(f"{sp}: {len(keys)} imagenes")

    yml = a.out.parent / f"{a.out.name}.yaml"
    yml.write_text(f"path: /workspace/{a.out}\ntrain: images/train\nval: images/val\n\nnames:\n  0: head\n")
    print(f"\nescrito {a.out}  |  yaml: {yml}")


if __name__ == "__main__":
    sys.exit(main())
