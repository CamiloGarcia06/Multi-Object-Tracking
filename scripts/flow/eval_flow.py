#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "numpy"]
# ///
"""C5 — evaluación del conteo de subidas y bajadas contra el golden de eventos.

Verdad: `data/flow_golden/<cámara>.csv` (una fila por persona que sube o baja,
anotada a mano en CVAT; `raro` no cuenta). Sistemas: CSV de eventos con columnas
`frame,track_id,direccion`, como los que escriben events.py y baseline.py.

Por apertura de puerta y en total, por separado para subidas (ingresos) y bajadas
(egresos), como la Tabla I del anteproyecto:
  - conteo real y contado, error absoluto y porcentual (con signo);
  - aciertos emparejando por dirección a ±`--tol` frames: recall (personas
    contadas) y precisión (eventos que son una persona real). El error de conteo
    puede ser 0 con eventos mal puestos; por eso van los dos.

Un evento del sistema cuenta en una apertura si cae en [inicio - margen, fin + margen].

Uso:
  uv run scripts/flow/eval_flow.py --golden data/flow_golden/videoTM_07.csv \\
      --system "#27 ByteTrack=ev27.csv" --system "sin tracking=base.csv" [--markdown]
"""
import argparse, collections, csv, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from events import match  # noqa: E402

KINDS = ("sube", "baja")


def load_golden(path):
    """{(inicio, fin): [(frame, 0, dirección)]}"""
    stops = collections.defaultdict(list)
    for r in csv.DictReader(open(path)):
        key = (int(r["parada_inicio"]), int(r["parada_fin"]))
        stops[key]  # la apertura existe aunque no tenga eventos
        if r["direccion"] in KINDS:
            stops[key].append((int(r["frame"]), 0, r["direccion"]))
    return dict(sorted(stops.items()))


def load_events(path):
    return [(int(r["frame"]), r["track_id"], r["direccion"]) for r in csv.DictReader(open(path))]


def score(truth, pred, tol):
    """{dirección: (real, contado, aciertos)}"""
    return {k: (sum(1 for e in truth if e[2] == k), sum(1 for e in pred if e[2] == k),
                match([e for e in truth if e[2] == k], [e for e in pred if e[2] == k], tol)) for k in KINDS}


def evaluate(golden, systems, tol, margin):
    """{sistema: {apertura | 'total': {dirección: (real, contado, aciertos)}}}"""
    out = {}
    for name, events in systems.items():
        rows, tot = {}, {k: [0, 0, 0] for k in KINDS}
        for (lo, hi), truth in golden.items():
            pred = [e for e in events if lo - margin <= e[0] <= hi + margin]
            rows[(lo, hi)] = score(truth, pred, tol)
            for k in KINDS:
                tot[k] = [a + b for a, b in zip(tot[k], rows[(lo, hi)][k])]
        rows["total"] = {k: tuple(v) for k, v in tot.items()}
        out[name] = rows
    return out


def pct(n, d):
    return f"{n / d:+.0%}" if d else "—"


def ratio(n, d):
    return f"{n / d:.2f}" if d else "—"


def render(result, markdown):
    sep = " | " if markdown else "  "
    head = ["sistema", "apertura", "dir", "real", "contado", "error", "error %", "recall", "precisión"]
    lines = [head]
    for name, rows in result.items():
        for key, by_kind in rows.items():
            label = "TOTAL" if key == "total" else f"{key[0]}–{key[1]}"
            for k in KINDS:
                real, got, hits = by_kind[k]
                lines.append([name, label, k, str(real), str(got), f"{got - real:+d}", pct(got - real, real),
                              ratio(hits, real), ratio(hits, got)])
    if markdown:
        out = ["| " + " | ".join(lines[0]) + " |", "|" + "---|" * len(head)]
        out += ["| " + " | ".join(r) + " |" for r in lines[1:]]
        return "\n".join(out)
    widths = [max(len(r[i]) for r in lines) for i in range(len(head))]
    return "\n".join(sep.join(c.rjust(w) if i >= 3 else c.ljust(w) for i, (c, w) in enumerate(zip(r, widths)))
                     for r in lines)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--golden", required=True)
    p.add_argument("--system", action="append", required=True, help="nombre=eventos.csv (repetible)")
    p.add_argument("--tol", type=int, default=10, help="frames de tolerancia al emparejar")
    p.add_argument("--margin", type=int, default=60, help="frames alrededor de cada apertura")
    p.add_argument("--only-total", action="store_true")
    p.add_argument("--markdown", action="store_true")
    a = p.parse_args()
    systems = {s.split("=", 1)[0]: load_events(s.split("=", 1)[1]) for s in a.system}
    result = evaluate(load_golden(a.golden), systems, a.tol, a.margin)
    if a.only_total:
        result = {n: {"total": r["total"]} for n, r in result.items()}
    print(render(result, a.markdown))


if __name__ == "__main__":
    main()
