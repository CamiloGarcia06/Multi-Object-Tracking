#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "numpy"]
# ///
"""C9 — Tesis 22: ¿el factor de sesgo calibrado en DDL vale en las otras cámaras?

Junta las aperturas de validación (DDL: 03 + 07) y de prueba (DDL 02, SDM 03(1), DDR v18,
SDR v08), cada una con los eventos del sistema congelado (#27 + door.py + od), y compara
tres formas de corregir el conteo de cada video de prueba:

- sin corregir;
- factor de DDL: `configs/calibracion.yaml` (03 + 07), el que se fijó ANTES de la prueba;
- leave-one-camera-out (LOCO): factor estimado con TODAS las aperturas de las otras
  cámaras (validación y prueba), aplicado a la que se deja fuera. Responde a "si tuviera
  un factor global sin ver esta cámara, ¿cuánto me equivocaría?". Es POST-HOC: usa los
  videos de prueba de las otras cámaras, que ya están evaluados.

También da el factor propio de cada cámara (contado/real, IC95 por bootstrap de
aperturas) para ver si las cámaras difieren entre sí. Mismas reglas que calibrate.py
(un factor por dirección si hay >= 10 eventos reales; si no, el conjunto).

  uv run scripts/flow/sesgo_camaras.py [--md docs/sesgo-entre-camaras.md]
"""
import argparse, pathlib, sys

import numpy as np
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from calibrate import fit, per_stop  # noqa: E402
from eval_flow import KINDS, load_events, load_golden  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
# (cámara, video, papel, golden, eventos del sistema)
SETS = [
    ("DDL", "videoTM_03", "validación", "data/flow_golden/videoTM_03.csv", "data/flow_eval/val03/ev_door2.csv"),
    ("DDL", "videoTM_07", "validación", "data/flow_golden/videoTM_07.csv", "data/flow_eval/v7/ev27_puerta_nueva.csv"),
    ("DDL", "videoTM_02", "prueba", "data/flow_golden/videoTM_02.csv", "data/flow_eval/test02/ev.csv"),
    ("SDM", "videoTM_03_1", "prueba", "data/flow_golden/videoTM_03_1.csv", "data/flow_eval/test03_1/ev.csv"),
    ("DDR", "bus_ddr_s6_v18", "prueba", "data/flow_golden/bus_ddr_s6_v18.csv",
     "data/flow_eval/test_bus_ddr_s6_v18/ev.csv"),
    ("SDR", "bus_sdr_s1_v08", "prueba", "data/flow_golden/bus_sdr_s1_v08.csv",
     "data/flow_eval/test_bus_sdr_s1_v08/ev.csv"),
]
CAMS = ["DDL", "SDM", "DDR", "SDR"]


def apply(arr, cal):
    """[(dirección, real, contado, corregido, lo, hi)] corrigiendo el total con el factor `cal`."""
    out = []
    for i, d in enumerate(KINDS):
        real, got = arr[:, i, 0].sum(), arr[:, i, 1].sum()
        f, (lo, hi) = cal[d]["factor"], cal[d]["ic95"]
        out.append((d, real, got, got / f, got / hi, got / lo))
    return out


def pct(v, real):
    return f"{(v - real) / real:+.0%}" if real else "—"


def table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] +
                     ["| " + " | ".join(r) + " |" for r in rows])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--calib", default="configs/calibracion.yaml")
    p.add_argument("--n-boot", type=int, default=10000)
    p.add_argument("--md")
    a = p.parse_args()

    data = {(cam, video): (role, per_stop(load_golden(ROOT / g), load_events(ROOT / e), 10, 60))
            for cam, video, role, g, e in SETS}
    ddl = yaml.safe_load(open(ROOT / a.calib))["direcciones"]
    parts = ["# Sesgo entre cámaras (Tesis 22)\n",
             "Sistema congelado (#27 ByteTrack + door.py + regla od). Factor = contado / real, IC95 por bootstrap "
             "de aperturas. Generado por `scripts/flow/sesgo_camaras.py`.\n"]

    # 1. factor propio de cada cámara (todas sus aperturas)
    rows = []
    for cam in CAMS:
        arr = np.concatenate([v[1] for k, v in data.items() if k[0] == cam])
        res = fit(arr, 10, n_boot=a.n_boot)
        for i, d in enumerate(KINDS):
            r = res[d]
            rows.append([cam, d, str(r["real_validacion"]), str(r["contado_validacion"]), f"{r['factor']:.2f}",
                         f"{r['ic95'][0]:.2f}–{r['ic95'][1]:.2f}", str(len(arr)), r["fuente"]])
    parts += ["\n## Factor propio de cada cámara\n",
              "DDL junta validación (03, 07) y prueba (02). Si el IC de una cámara no toca el de DDL, el sesgo "
              "es distinto.\n",
              table(["cámara", "dir", "real", "contado", "factor", "IC95", "aperturas", "fuente"], rows)]

    # 2. cada video de prueba: sin corregir, factor DDL, LOCO
    rows, agg = [], {m: {d: [0.0, 0.0, 0.0] for d in KINDS} for m in ("sin corregir", "factor DDL", "LOCO")}
    loco_factors = []
    for (cam, video), (role, arr) in data.items():
        if role != "prueba":
            continue
        others = np.concatenate([v[1] for k, v in data.items() if k[0] != cam])
        loco = fit(others, 10, n_boot=a.n_boot)
        loco_factors.append([cam] + [f"{loco[d]['factor']:.2f} ({loco[d]['ic95'][0]:.2f}–{loco[d]['ic95'][1]:.2f})"
                                     for d in KINDS])
        for (d, real, got, c1, lo1, hi1), (_, _, _, c2, lo2, hi2) in zip(apply(arr, ddl), apply(arr, loco)):
            inside = lambda lo, hi: "sí" if lo <= real <= hi else "**no**"
            rows.append([f"{cam} {video}", d, f"{real:.0f}", f"{got:.0f}", pct(got, real),
                         f"{c1:.1f} ({lo1:.1f}–{hi1:.1f})", pct(c1, real), inside(lo1, hi1),
                         f"{c2:.1f} ({lo2:.1f}–{hi2:.1f})", pct(c2, real), inside(lo2, hi2)])
            for m, v in (("sin corregir", got), ("factor DDL", c1), ("LOCO", c2)):
                agg[m][d][0] += real
                agg[m][d][1] += v
                agg[m][d][2] += abs(v - real)
    parts += ["\n## Videos de prueba: factor de DDL frente a leave-one-camera-out\n",
              "LOCO = factor estimado con las otras tres cámaras (post-hoc). «IC ok» = el valor real cae en el "
              "intervalo del conteo corregido.\n",
              table(["video", "dir", "real", "contado", "error", "factor DDL", "error", "IC ok",
                     "LOCO", "error", "IC ok"], rows),
              "\nFactores LOCO (sube / baja) usados para cada cámara:\n",
              table(["cámara fuera", "sube", "baja"], loco_factors)]

    rows = [[m, d, f"{v[0]:.0f}", f"{v[1]:.1f}", pct(v[1], v[0]), f"{v[2] / v[0]:.0%}"]
            for m in agg for d, v in agg[m].items()]
    parts += ["\n## Agregado de las cuatro pruebas\n",
              "Suma de los cuatro videos de prueba (umbral APC de la Tesis 10: ≤ 5 % agregado). «error neto» deja que "
              "los errores de signo contrario se compensen; «error absoluto» = Σ|estimado − real| / Σ real, sin "
              "compensación.\n",
              table(["corrección", "dir", "real", "estimado", "error neto", "error absoluto"], rows)]
    text = "\n".join(parts) + "\n"
    print(text)
    if a.md:
        (ROOT / a.md).write_text(text)


if __name__ == "__main__":
    main()
