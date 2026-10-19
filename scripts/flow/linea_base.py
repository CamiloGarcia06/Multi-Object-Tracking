#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "numpy"]
# ///
"""C10 — Tesis 18: ¿aporta el tracking frente a contar sin tracking? Las cuatro pruebas.

Sistema congelado (#27 ByteTrack + door.py + od) frente a la línea base sin tracking
(`baseline.py`: pares de detecciones en frames consecutivos que cruzan la curva interior),
con las mismas detecciones, ROI y puerta, en los videos de prueba de las cuatro cámaras
(DDL 02, SDM 03(1), DDR v18, SDR v08). Los dos se generaron y sellaron antes del golden.

Por video y dirección: real, contado, recall, precisión y error, sin corregir y corregido
con el factor de cada uno fijado en 03+07 (`configs/calibracion.yaml` y
`configs/calibracion_sin_tracking.yaml`). Al final, el agregado de las cuatro pruebas:
error neto del total, media del |error corregido| por video, y recall / precisión / F1 por
EVENTO (aciertos emparejados con el golden) con la diferencia de F1 sistema − línea base e
IC95 por bootstrap de aperturas. El error del total deja que los falsos positivos tapen
las pérdidas; el F1 no.

  uv run scripts/flow/linea_base.py [--md docs/linea-base-prueba.md]
"""
import argparse, pathlib, sys

import numpy as np
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from eval_flow import KINDS, evaluate, load_events, load_golden  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
TESTS = [("DDL", "videoTM_02", "data/flow_eval/test02"), ("SDM", "videoTM_03_1", "data/flow_eval/test03_1"),
         ("DDR", "bus_ddr_s6_v18", "data/flow_eval/test_bus_ddr_s6_v18"),
         ("SDR", "bus_sdr_s1_v08", "data/flow_eval/test_bus_sdr_s1_v08")]
METHODS = [("#27 ByteTrack", "ev.csv", "configs/calibracion.yaml"),
           ("sin tracking", "ev_sin_tracking.csv", "configs/calibracion_sin_tracking.yaml")]


def table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] +
                     ["| " + " | ".join(r) + " |" for r in rows])


def pct(v, real):
    return f"{(v - real) / real:+.0%}" if real else "—"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--n-boot", type=int, default=10000)
    p.add_argument("--md")
    a = p.parse_args()

    cal = {m: yaml.safe_load(open(ROOT / c))["direcciones"] for m, _, c in METHODS}
    # stops[(método, dirección)] = lista de (real, contado) por apertura de todas las pruebas, en el mismo orden
    stops = {(m, d): [] for m, _, _ in METHODS for d in KINDS}
    rows, agg = [], {(m, d): [0, 0, 0.0] for m, _, _ in METHODS for d in KINDS}
    absum = {(m, d): [] for m, _, _ in METHODS for d in KINDS}
    for cam, video, folder in TESTS:
        golden = load_golden(ROOT / f"data/flow_golden/{video}.csv")
        for m, fname, _ in METHODS:
            res = evaluate(golden, {m: load_events(ROOT / folder / fname)}, 10, 60)[m]
            for d in KINDS:
                real, got, hit = res["total"][d]
                corr = got / cal[m][d]["factor"]
                rows.append([f"{cam} {video}", m, d, str(real), str(got),
                             f"{hit / real:.2f}" if real else "—", f"{hit / got:.2f}" if got else "—",
                             pct(got, real), pct(corr, real)])
                agg[(m, d)][0] += real
                agg[(m, d)][1] += got
                agg[(m, d)][2] += corr
                stops[(m, d)] += [res[k][d] for k in golden]
                absum[(m, d)].append(abs(corr - real) / real if real else None)

    parts = ["# Línea base sin tracking en la prueba (Tesis 18)\n",
             "Mismas detecciones (campeón), ROI y puerta (door.py) para los dos; eventos sellados antes del golden "
             "(`configs/prueba_sellada.sha256`). Corregido = contado / factor propio de cada método fijado en 03+07 "
             "(sistema 0,68/0,62; sin tracking 0,56/0,52). Generado por `scripts/flow/linea_base.py`.\n",
             "\n## Por video\n",
             table(["video", "método", "dir", "real", "contado", "recall", "precisión", "error", "corregido"], rows)]

    rows = []
    for (m, d), (real, got, corr) in agg.items():
        rows.append([m, d, str(real), str(got), pct(got, real), pct(corr, real)])
    parts += ["\n## Agregado de las cuatro pruebas (error neto)\n",
              table(["método", "dir", "real", "contado", "error", "corregido"], rows)]

    rows = []
    for (m, d), (real, got, corr) in agg.items():
        v = [x for x in absum[(m, d)] if x is not None]
        rows.append([m, d, f"{np.mean(v):.0%}", ", ".join(f"{x:.0%}" for x in v)])
    parts += ["\n## Media del |error corregido| por video\n",
              "Sin compensación entre videos (cada video cuenta igual).\n",
              table(["método", "dir", "media", "02, 03(1), DDR, SDR"], rows)]

    def prf(arr):
        real, got, hit = arr[:, 0].sum(), arr[:, 1].sum(), arr[:, 2].sum()
        r, p_ = hit / real, (hit / got if got else 0.0)
        return r, p_, (2 * r * p_ / (r + p_) if r + p_ else 0.0)

    rng = np.random.default_rng(0)
    rows = []
    for d in KINDS:
        s_ = np.array(stops[(METHODS[0][0], d)], float)
        b_ = np.array(stops[(METHODS[1][0], d)], float)
        (rs, ps, fs), (rb, pb, fb) = prf(s_), prf(b_)
        boot, n = [], len(s_)
        for _ in range(a.n_boot):
            idx = rng.integers(0, n, n)
            if s_[idx, 0].sum() == 0:
                continue
            boot.append(prf(s_[idx])[2] - prf(b_[idx])[2])
        lo, hi = np.percentile(boot, [2.5, 97.5])
        rows.append([d, f"{rs:.2f}", f"{ps:.2f}", f"{fs:.2f}", f"{rb:.2f}", f"{pb:.2f}", f"{fb:.2f}",
                     f"{fs - fb:+.2f}", f"{lo:+.2f} a {hi:+.2f}", str(n)])
    parts += ["\n## Por evento: recall, precisión y F1 de las cuatro pruebas\n",
              "Aciertos emparejados con el golden (tolerancia 10 frames). Diferencia positiva = el tracking acierta "
              "más. IC95 por bootstrap de aperturas.\n",
              table(["dir", "recall sist.", "precisión sist.", "F1 sist.", "recall s/t", "precisión s/t", "F1 s/t",
                     "ΔF1", "IC95", "aperturas"], rows)]
    text = "\n".join(parts) + "\n"
    print(text)
    if a.md:
        (ROOT / a.md).write_text(text)


if __name__ == "__main__":
    main()
