#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "numpy"]
# ///
"""C11 — Tesis 25: candidatos de puerta para anotar la verdad de terreno en videos de DESARROLLO.

La verdad de la puerta (cuándo está abierta y cuándo no se ve) se anota revisando candidatos,
no el video entero. Candidatos de un video, unidos si se solapan o están a < 2 s:

- `door`: intervalos de door.py tal cual (mismos parámetros que el sistema sellado);
- `baja`: similitud suavizada < 0,5 durante >= 1 s fuera de esos intervalos (posible apertura perdida
  u oclusión con la puerta cerrada);
- `oscura`: recorte con brillo < `min_brightness` durante >= 1 s (la guarda de túnel de door.py
  la da por cerrada: es el fallo del 03(1) con el bus lleno).

`candidatos` escribe `<out>/<video>.candidatos.csv` (la plantilla que Camilo corrige) y
`<out>/<video>.frames.txt` (frames de la hoja de revisión, un frame cada 0,5 s con ±60 f de margen,
como mucho 48 por candidato). Las hojas se arman en la torre con `hojas.sh` (ffmpeg + drawtext).

Nunca se usa con los videos de prueba (02, 03(1), DDR v18, SDR v08).

  uv run scripts/flow/puerta_dev.py candidatos --camera configs/cameras/X.yaml --ref R.npy \\
      --raw data/door_dev/V.door.raw --video V --out data/door_dev
  uv run scripts/flow/puerta_dev.py ref --camera C --raw R.raw --out R.npy   # closed_frames del yaml
"""
import argparse, csv, pathlib, sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import door  # noqa: E402

TESTS = {"videoTM_02", "videoTM_03_1", "bus_sdm_s4_v03", "bus_ddl_s6_v02", "bus_ddr_s6_v18", "bus_sdr_s1_v08"}


def runs(mask, min_len):
    """[(i, j)] tramos de True de al menos `min_len` muestras (j inclusive)."""
    out, i = [], 0
    while i < len(mask):
        if not mask[i]:
            i += 1
            continue
        j = i
        while j < len(mask) and mask[j]:
            j += 1
        if j - i >= min_len:
            out.append((i, j - 1))
        i = j
    return out


def candidates(cfg, samples, sim):
    step, k = cfg["step"], cfg["smooth"]
    sm = np.array([np.median(sim[max(0, i - k // 2):i + k // 2 + 1]) for i in range(len(sim))])
    frame = lambda i: step * i + 1
    iv = [(a, b, "door") for a, b in door.intervals(cfg, sim)]
    in_door = np.zeros(len(sim), bool)
    for a, b, _ in iv:
        in_door[(a - 1) // step:(b - 1) // step + 1] = True
    sec = int(round(cfg.get("fps", 30) / step))
    iv += [(frame(i), frame(j), "baja") for i, j in runs((sm < 0.5) & ~in_door, sec)]
    dark = samples.mean((1, 2)) < cfg.get("min_brightness", 0)
    iv += [(frame(i), frame(j), "oscura") for i, j in runs(dark, sec)]
    iv.sort()
    merged = []
    for a, b, src in iv:
        if merged and a - merged[-1][1] < 2 * cfg.get("fps", 30):
            m = merged[-1]
            m[1] = max(m[1], b)
            m[2] |= {src}
        else:
            merged.append([a, b, {src}])
    return [(a, b, "+".join(sorted(s))) for a, b, s in merged], sm


def cmd_candidatos(a):
    if a.video in TESTS:
        sys.exit(f"{a.video} es un video de prueba: no se usa para desarrollar la puerta")
    cfg = door.load_config(a.camera)
    cfg["closed_ref"], cfg["exclude"] = a.ref, []
    samples = door.read_samples(cfg, pathlib.Path(a.raw).read_bytes())
    sim = door.similarity(cfg, samples)
    cand, sm = candidates(cfg, samples, sim)
    out = pathlib.Path(a.out)
    n_frames = len(sim) * cfg["step"]
    with open(out / f"{a.video}.candidatos.csv", "w", newline="") as f:
        w = csv.writer(f)
        # Camilo rellena: abierta_inicio/abierta_fin (vacío si no abre), no_visible (tramos a-b;c-d), nota
        w.writerow(["id", "inicio", "fin", "fuente", "sim_min", "abierta_inicio", "abierta_fin", "no_visible", "nota"])
        for n, (s, e, src) in enumerate(cand, 1):
            lo, hi = (s - 1) // cfg["step"], (e - 1) // cfg["step"] + 1
            w.writerow([n, s, e, src, f"{sm[lo:hi].min():.2f}", "", "", "", ""])
    with open(out / f"{a.video}.frames.txt", "w") as f:
        for n, (s, e, _) in enumerate(cand, 1):
            # frames 15k+1: los que saca la pasada única de `hojas` (uno cada 0,5 s)
            lo, hi = (max(1, s - 60) - 1) // 15 * 15 + 1, min(n_frames, e + 60)
            stride = max(15, -(-(hi - lo) // 47 // 15) * 15)
            f.write(f"{n} " + " ".join(str(x) for x in range(lo, hi + 1, stride)) + "\n")
    src_count = {k: sum(k in c[2] for c in cand) for k in ("door", "baja", "oscura")}
    print(f"{a.video}: {len(cand)} candidatos {src_count}; similitud cerrada≈{np.median(sim):.2f}", file=sys.stderr)


def cmd_hojas(a):
    """Imprime el bash que arma en la torre las hojas de un video: una pasada de ffmpeg saca un frame
    cada 0,5 s con su número dibujado y luego una hoja (8×6) por candidato."""
    lines = [l.split() for l in pathlib.Path(a.frames).read_text().splitlines() if l.strip()]
    d = f"{a.video}_hojas"
    draw = "drawtext=text='%{eif\\:n+1\\:d}':x=6:y=6:fontsize=36:fontcolor=yellow:box=1:boxcolor=black@0.6"
    print(f"set -e; cd ~/Multi-Object-Tracking/data/door_dev; rm -rf {d}; mkdir -p {d}/f; cd {d}")
    print(f"ffmpeg -nostdin -v error -i \"{a.src}\" -vf \"{draw},select='not(mod(n,15))',scale=320:240\" "
          f"-fps_mode passthrough -q:v 4 f/%06d.jpg")
    idx = lambda f: (f - 1) // 15 + 1
    for l in lines:
        n, fr = l[0], [int(x) for x in l[1:]]
        print("printf '" + "".join(f"file 'f/{idx(f):06d}.jpg'\\n" for f in fr) + f"' > c{n}.txt")
        print(f"ffmpeg -nostdin -v error -f concat -safe 0 -i c{n}.txt -vf tile=8x6:padding=4 -frames:v 1 -q:v 3 "
              f"-y {a.video}_c{int(n):03d}.jpg")
    print("rm -rf f c*.txt filtro.txt; echo hojas listas")


def cmd_ref(a):
    cfg = door.load_config(a.camera)
    g = door.edges(door.read_samples(cfg, pathlib.Path(a.raw).read_bytes()))
    np.save(a.out, door.closed_reference(cfg, g, cfg["closed_frames"]).astype(np.float32))
    print(f"{a.out}: referencia de {len(cfg['closed_frames'])} frames", file=sys.stderr)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("candidatos")
    for k in ("camera", "ref", "raw", "video", "out"):
        s.add_argument(f"--{k}", required=True)
    s.set_defaults(fn=cmd_candidatos)
    s = sub.add_parser("hojas")
    for k in ("frames", "video", "src"):
        s.add_argument(f"--{k}", required=True)
    s.set_defaults(fn=cmd_hojas)
    s = sub.add_parser("ref")
    for k in ("camera", "raw", "out"):
        s.add_argument(f"--{k}", required=True)
    s.set_defaults(fn=cmd_ref)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
