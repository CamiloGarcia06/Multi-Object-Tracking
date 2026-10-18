#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""C5 — del export de CVAT al CSV del golden de eventos (data/flow_golden/<video>.csv).

Entrada: los `export/jobN.json` de `exportar_job.sh` (cada punto ya con el frame del
video) y las MISMAS aperturas revisadas a ojo que se pasaron a golden_eventos.py
(`--aperturas`). Cada punto va a la apertura cuyo job lo contiene: [inicio - margen,
fin + margen], con el margen de golden_eventos.py (60).

Salida, como videoTM_02.csv: parada_inicio,parada_fin,frame,direccion,x,y,nota.
`sube`/`baja` cuentan; `raro` va con su nota y eval_flow.py no lo cuenta. `--ninguno a-b`
añade tramos con la puerta cerrada (penalizan los falsos de door.py); en un golden
REDUCIDO no se ponen: solo se evalúan las aperturas elegidas.

  uv run scripts/flow/golden_csv.py --export DIR/export --aperturas 9205-9295,... \\
      --out data/flow_golden/bus_ddr_s6_v18.csv
  uv run scripts/flow/golden_csv.py selftest
"""
import argparse, csv, glob, io, json, sys

LABELS = ("sube", "baja", "raro")


def spans(txt):
    return [tuple(map(int, r.split("-"))) for r in txt.split(",") if r]


def build(points, aperturas, margen=60, ninguno=()):
    """Filas del golden y puntos que no caen en ninguna apertura (o con etiqueta rara)."""
    rows, fuera = [], []
    for p in points:
        if p["label"] not in LABELS or p.get("type") != "points":
            fuera.append((p, f"etiqueta/tipo {p['label']}/{p.get('type')}"))
            continue
        hit = [(a, b) for a, b in aperturas if a - margen <= p["frame"] <= b + margen]
        if len(hit) != 1:
            fuera.append((p, "fuera de toda apertura" if not hit else "en dos aperturas"))
            continue
        nota = (p.get("attrs") or {}).get("nota", "") if p["label"] == "raro" else ""
        rows.append((*hit[0], p["frame"], p["label"], p["x"], p["y"], nota))
    rows += [(a, b, "", "ninguno", "", "", "puerta cerrada") for a, b in ninguno]
    rows.sort(key=lambda r: (r[0], r[2] if r[2] != "" else -1))
    return rows, fuera


def write(rows, out):
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["parada_inicio", "parada_fin", "frame", "direccion", "x", "y", "nota"])
    w.writerows(rows)


def cmd_build(a):
    points = [p for f in sorted(glob.glob(f"{a.export}/job*.json")) for p in json.load(open(f))["points"]]
    if not points:
        sys.exit(f"{a.export}: no hay export/jobN.json (corre antes exportar_job.sh)")
    aperturas = spans(a.aperturas)
    rows, fuera = build(points, aperturas, a.margen, spans(a.ninguno))
    for p, why in fuera:
        print(f"AVISO frame {p['frame']} {p['label']}: {why}", file=sys.stderr)
    with open(a.out, "w") as h:
        write(rows, h)
    n = {k: sum(r[3] == k for r in rows) for k in LABELS}
    por = {f"{x}-{y}": sum(r[0] == x and r[3] in ("sube", "baja") for r in rows) for x, y in aperturas}
    print(json.dumps({"out": a.out, **n, "por_apertura": por, "avisos": len(fuera)}, ensure_ascii=False))


def cmd_selftest(_):
    ap = [(100, 200), (500, 600)]
    pts = [{"frame": 150, "label": "sube", "x": 1, "y": 2, "type": "points"},
           {"frame": 650, "label": "baja", "x": 3, "y": 4, "type": "points"},          # margen de 60
           {"frame": 520, "label": "raro", "x": 5, "y": 6, "type": "points", "attrs": {"nota": "duda"}},
           {"frame": 350, "label": "sube", "x": 0, "y": 0, "type": "points"},          # fuera
           {"frame": 120, "label": "head", "x": 0, "y": 0, "type": "rectangle"}]       # etiqueta ajena
    rows, fuera = build(pts, ap, 60, [(300, 400)])
    buf = io.StringIO(); write(rows, buf)
    got = list(csv.DictReader(io.StringIO(buf.getvalue())))
    checks = [
        ("una fila por evento válido + el tramo ninguno", len(got) == 4),
        ("la subida va a su apertura", got[0]["parada_inicio"] == "100" and got[0]["direccion"] == "sube"),
        ("el margen del job cuenta (650 → 500-600)", any(r["frame"] == "650" and r["parada_inicio"] == "500" for r in got)),
        ("raro conserva su nota", any(r["direccion"] == "raro" and r["nota"] == "duda" for r in got)),
        ("ninguno sin frame", any(r["direccion"] == "ninguno" and r["frame"] == "" for r in got)),
        ("avisa del punto fuera y de la etiqueta ajena", len(fuera) == 2),
    ]
    ok = True
    for name, cond in checks:
        ok &= bool(cond)
        print(f"{'OK  ' if cond else 'FALLO'}  {name}")
    sys.exit(0 if ok else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("build")
    s.add_argument("--export", required=True, help="carpeta con export/jobN.json")
    s.add_argument("--aperturas", required=True, help="a-b,... las mismas de golden_eventos.py")
    s.add_argument("--ninguno", default="", help="a-b,...: tramos con la puerta cerrada (solo golden completo)")
    s.add_argument("--margen", type=int, default=60)
    s.add_argument("--out", required=True)
    sub.add_parser("selftest")
    a = p.parse_args()
    {"build": cmd_build, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    main()
