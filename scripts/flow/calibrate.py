#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "numpy"]
# ///
"""C7 — corrección de sesgo del conteo: factor estimado en VALIDACIÓN y aplicado en el resto.

Tras la tarea 3 (diagnóstico de la puerta) el sistema pierde personas de forma
sistemática y no cuenta de más. En validación (videoTM_03) y en videoTM_07 el recall
es 0,59–0,62 en las dos direcciones y la precisión 0,95–1,00. Si se cuenta
siempre más o menos la misma fracción, el total se estima dividiendo por ella:

  factor_k   = Σ contado_k / Σ real_k   sobre las aperturas de validación (dirección k)
  corregido  = contado / factor_k

Regla fijada ANTES de mirar la prueba: un factor por dirección si la validación tiene
>= `--min-events` eventos reales de esa dirección. Si no, se usa el factor
conjunto de las direcciones que sí llegan. En el 03 las subidas, con 2 eventos, toman
el factor de las bajadas, con 28.

Incertidumbre: bootstrap por APERTURAS (las personas de una misma parada no son
independientes): se remuestrean las aperturas de validación y se recalcula el
factor. IC95 percentil. Al aplicarlo, el conteo corregido lleva el intervalo
contado / [factor_alto, factor_bajo].

Límites:
- corrige el TOTAL, no cada parada;
- supone que la fracción perdida es la misma que en validación, y puede depender
  de la congestión (03 y 07 son de congestión baja; 02 alta).

Uso:
  uv run scripts/flow/calibrate.py fit --golden data/flow_golden/videoTM_03.csv --system ev03.csv \\
      [--golden data/flow_golden/videoTM_07.csv --system ev07.csv] --out configs/calibracion.yaml
  uv run scripts/flow/calibrate.py report --calib configs/calibracion.yaml \\
      --golden data/flow_golden/videoTM_07.csv --system "#27=ev07.csv" [--markdown]
  uv run scripts/flow/calibrate.py selftest
"""
import argparse, datetime, pathlib, sys

import numpy as np
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from eval_flow import KINDS, evaluate, load_events, load_golden  # noqa: E402


def per_stop(golden, events, tol, margin):
    """array (aperturas, dirección, [real, contado])"""
    rows = evaluate(golden, {"s": events}, tol, margin)["s"]
    return np.array([[[rows[k][d][0], rows[k][d][1]] for d in KINDS] for k in golden], float)


def factors(arr, min_events):
    """{dirección: factor} con la regla de respaldo (ver docstring)."""
    real, got = arr[:, :, 0].sum(0), arr[:, :, 1].sum(0)
    ok = real >= min_events
    if not ok.any():
        sys.exit(f"ninguna dirección llega a {min_events} eventos reales: no se puede estimar el factor")
    pooled = got[ok].sum() / real[ok].sum()
    return {d: float(got[i] / real[i]) if ok[i] else float(pooled) for i, d in enumerate(KINDS)}, ok


def fit(arr, min_events, n_boot=10000, seed=0):
    point, ok = factors(arr, min_events)
    rng = np.random.default_rng(seed)
    boot = {d: [] for d in KINDS}
    for _ in range(n_boot):
        s = arr[rng.integers(0, len(arr), len(arr))]
        if (s[:, :, 0].sum(0)[ok] == 0).any():
            continue
        real, got = s[:, :, 0].sum(0), s[:, :, 1].sum(0)
        pooled = got[ok].sum() / real[ok].sum()
        for i, d in enumerate(KINDS):
            boot[d].append(got[i] / real[i] if ok[i] else pooled)
    return {d: {"factor": round(point[d], 4),
                "ic95": [round(float(np.percentile(boot[d], q)), 4) for q in (2.5, 97.5)],
                "fuente": "propia" if ok[i] else "conjunta (pocos eventos)",
                "real_validacion": int(arr[:, i, 0].sum()), "contado_validacion": int(arr[:, i, 1].sum())}
            for i, d in enumerate(KINDS)}


def cmd_fit(a):
    if len(a.golden) != len(a.system):
        sys.exit("fit: un --system por cada --golden, en el mismo orden")
    arr = np.concatenate([per_stop(load_golden(g), load_events(s), a.tol, a.margin)
                          for g, s in zip(a.golden, a.system)])
    res = fit(arr, a.min_events)
    doc = {"descripcion": "corrección de sesgo del conteo (scripts/flow/calibrate.py)",
           "estimado_en": {"golden": a.golden, "sistema": a.system, "aperturas": len(arr),
                           "fecha": datetime.date.today().isoformat()},
           "min_events": a.min_events, "direcciones": res}
    pathlib.Path(a.out).write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
    print(yaml.safe_dump(res, allow_unicode=True, sort_keys=False))


def cmd_report(a):
    cal = yaml.safe_load(open(a.calib))["direcciones"]
    golden = load_golden(a.golden)
    head = ["sistema", "dir", "real", "contado", "error %", "corregido", "IC95", "error % corr."]
    lines = []
    for s in a.system:
        name, path = s.split("=", 1)
        arr = per_stop(golden, load_events(path), a.tol, a.margin)
        for i, d in enumerate(KINDS):
            real, got = arr[:, i, 0].sum(), arr[:, i, 1].sum()
            f, (lo, hi) = cal[d]["factor"], cal[d]["ic95"]
            corr = got / f
            pct = lambda v: f"{(v - real) / real:+.0%}" if real else "—"
            lines.append([name, d, f"{real:.0f}", f"{got:.0f}", pct(got), f"{corr:.1f}",
                          f"{got / hi:.1f}–{got / lo:.1f}", pct(corr)])
    if a.markdown:
        print("| " + " | ".join(head) + " |\n|" + "---|" * len(head))
        print("\n".join("| " + " | ".join(r) + " |" for r in lines))
    else:
        w = [max(len(r[i]) for r in [head] + lines) for i in range(len(head))]
        print("\n".join("  ".join(c.ljust(x) for c, x in zip(r, w)) for r in [head] + lines))


def cmd_selftest(_):
    # 3 aperturas; bajadas: 10 reales / 6 contadas cada una (factor 0,6); subidas: 1 real / 1 contada
    arr = np.array([[[1, 1], [10, 6]]] * 3, float)
    res = fit(arr, 10, n_boot=200)
    ok = (abs(res["baja"]["factor"] - 0.6) < 1e-9 and res["sube"]["factor"] == res["baja"]["factor"]
          and res["sube"]["fuente"].startswith("conjunta") and res["baja"]["ic95"] == [0.6, 0.6])
    arr2 = np.array([[[20, 16], [10, 6]]] * 3, float)  # con datos de sobra, cada dirección el suyo
    res2 = fit(arr2, 10, n_boot=200)
    ok &= abs(res2["sube"]["factor"] - 0.8) < 1e-9 and abs(res2["baja"]["factor"] - 0.6) < 1e-9
    print("selftest OK" if ok else f"selftest FALLO {res} {res2}")
    sys.exit(0 if ok else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("fit", "report"):
        s = sub.add_parser(name)
        s.add_argument("--golden", required=True, action="append" if name == "fit" else "store",
                       help="en fit, repetible: cada uno con su --system (las aperturas se juntan)")
        s.add_argument("--tol", type=int, default=10)
        s.add_argument("--margin", type=int, default=60)
        if name == "fit":
            s.add_argument("--system", required=True, action="append", help="eventos.csv, uno por --golden")
            s.add_argument("--min-events", type=int, default=10)
            s.add_argument("--out", required=True)
        else:
            s.add_argument("--calib", required=True)
            s.add_argument("--system", action="append", required=True, help="nombre=eventos.csv")
            s.add_argument("--markdown", action="store_true")
    sub.add_parser("selftest")
    a = p.parse_args()
    {"fit": cmd_fit, "report": cmd_report, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    main()
