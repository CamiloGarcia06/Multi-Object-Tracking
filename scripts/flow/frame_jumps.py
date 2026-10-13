#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""Tarea 8 — saltos de frames del video: dónde están y si rompen los tracks.

Las marcas de tiempo del mkv son regulares (30 fps, sin huecos): el salto está en
el CONTENIDO. La cámara repite un frame y se salta el siguiente, de modo que el
movimiento se ve 0 y luego doble. Firma, sobre la diferencia media entre frames
consecutivos (gris a 80x60), dividida por su mediana local (±15 frames):

  congela  ratio < 0,5 con la escena en movimiento (mediana > 2)
  salta    el frame siguiente, ratio > 1,8   -> se marca el frame que salta

Calibrado con el salto anotado a mano 5.396 -> 5.397 (congela 0,4, salta 2,6).
Aparte, los tramos congelados (diferencia < 0,3: frame idéntico al anterior).

  ssh torre 'ffmpeg -v error -i ~/videos/videoTM_07.mkv -vf scale=80:60,format=gray -f rawvideo -' > gray.raw
  uv run scripts/flow/frame_jumps.py gray.raw --mot job27.txt \\
      --door data/flow_videos/puerta_abierta_videoTM_07.json > saltos.csv
"""
import argparse, json, sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def diffs(path, w=80, h=60):
    g = np.fromfile(path, np.uint8).reshape(-1, h, w).astype(np.float32)
    return np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))  # d[i]: cambio al llegar el frame i+2 (1-indexado)


def jumps(d, half=15):
    med = np.median(sliding_window_view(np.pad(d, half, mode="edge"), 2 * half + 1), axis=1)
    r = d / np.maximum(med, 0.5)
    return [i + 3 for i in range(len(d) - 1) if med[i] > 2 and r[i] < 0.5 and r[i + 1] > 1.8]


def frozen_runs(d, thr=0.3):
    runs, i = [], 0
    while i < len(d):
        if d[i] < thr:
            j = i
            while j < len(d) and d[j] < thr:
                j += 1
            runs.append((i + 2, j - i))
            i = j
        else:
            i += 1
    return runs


def enrichment(mot, door, js):
    """Cuánto más nacen, mueren o se pierden los tracks junto a un salto que en un frame cualquiera."""
    m = np.loadtxt(mot, delimiter=",", usecols=(0, 1), ndmin=2).astype(int)
    in_door = lambda f: any(a <= f <= b for a, b in door)
    near = lambda f: f in js or f - 1 in js
    base = np.mean([near(f) for f in range(1, int(m[:, 0].max()) + 1) if in_door(f)])
    out, by = {}, {}
    for f, t in m:
        by.setdefault(t, []).append(f)
    born = [min(v) for v in by.values()]
    died = [max(v) + 1 for v in by.values()]
    lost = [f + 1 for v in by.values() for f, g in zip(sorted(v), sorted(v)[1:]) if g - f > 1]
    for name, ev in (("nacimientos", born), ("muertes", died), ("perdidas", lost)):
        ev = [f for f in ev if in_door(f)]
        k = sum(near(f) for f in ev)
        out[name] = {"n": len(ev), "junto_a_salto": k, "veces_el_azar": round(k / len(ev) / base, 1) if ev else None}
    out["azar"] = round(float(base), 3)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("gray")
    p.add_argument("--mot", help="MOT de un job: mide el efecto en los tracks")
    p.add_argument("--door", help="JSON de intervalos de puerta abierta")
    a = p.parse_args()
    d = diffs(a.gray)
    js = set(jumps(d))
    runs = frozen_runs(d)
    print("frame,tipo,longitud")
    for f in sorted(js):
        print(f"{f},salto,1")
    for f, n in runs:
        print(f"{f},congelado,{n}")
    door = json.load(open(a.door)) if a.door else []
    summary = {"frames": len(d) + 1, "saltos": len(js), "tramos_congelados": len(runs),
               "frames_congelados": int(sum(n for _, n in runs)),
               "saltos_en_aperturas": sum(any(x <= f <= y for x, y in door) for f in js)}
    if a.mot and door:
        summary["efecto"] = enrichment(a.mot, door, js)
    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
