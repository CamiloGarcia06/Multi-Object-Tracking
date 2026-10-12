#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "numpy"]
# ///
"""C2 — de tracks a eventos de subida y bajada.

Cada track es la trayectoria del centro de su caja. La puerta son DOS curvas
(configs/cameras/<camara>.yaml) que cruzan la imagen de arriba abajo, trazadas
por Camilo siguiendo la curvatura del ojo de pez:

  - `outer`: del lado del andén.
  - `inner`: del lado del pasillo.

Van por donde pasan las CABEZAS, no por el suelo: una línea en el suelo con
puntas deja que las cabezas (1,6 m más arriba, desplazadas por el ojo de pez)
la rodeen. Sin puntas no hay nada que rodear.

Un track está FUERA cuando su centro pasa la exterior hacia el andén y DENTRO
cuando pasa la interior hacia el pasillo; entre las dos conserva el lado que
tenía. Así:

  - fuera → dentro = `sube` (IN); dentro → fuera = `baja` (OUT).
  - **Histéresis = el hueco entre las líneas.** Quien oscila en el umbral no
    suma eventos.
  - **Quien está de pie junto a la puerta no sube.** Si nace entre las dos
    líneas y se va al pasillo, solo cruza una: nunca estuvo FUERA.
  - **Fragmentación: se acepta y se mide** (`nacen_o_mueren_en_la_puerta`).

Falta (no está aquí): ignorar lo que pase con la puerta cerrada.

Uso:
  uv run scripts/flow/events.py selftest
  uv run scripts/flow/events.py events --camera configs/cameras/videoTM_07.yaml --tracks gt.txt
  uv run scripts/flow/events.py events --camera ... --job 23 [--gt data/tracking_golden/tm07_a]
  uv run scripts/flow/events.py compare --camera ... --gt data/tracking_golden/tm07_a --job 23

`--job` baja el MOT del job de track-studio; con `--gt` se corta al tramo de ese
clip (start/seqLength del seqinfo.ini), como hace eval_tracking.py publish.
`compare` usa como verdad los eventos del golden de tracking y empareja por
dirección dentro de ±`--tol` frames.
"""
import argparse, collections, csv, json, pathlib, sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tracking"))
from eval_tracking import _http, cut_lines, seqinfo  # noqa: E402

INSIDE, OUTSIDE = 1, -1


def _curve(pts):
    """Polilínea ordenada de arriba abajo: la curva es una función x(y)."""
    return sorted(((float(x), float(y)) for x, y in pts), key=lambda p: p[1])


def x_at(curve, y):
    """x de la curva a la altura y (fuera de su alto, la de la punta más cercana)."""
    if y <= curve[0][1]:
        return curve[0][0]
    for (x1, y1), (x2, y2) in zip(curve, curve[1:]):
        if y1 <= y <= y2:
            return x1 + (x2 - x1) * (y - y1) / (y2 - y1) if y2 > y1 else x1
    return curve[-1][0]


def load_camera(path):
    data = yaml.safe_load(pathlib.Path(path).read_text())
    cam = {"outer": _curve(data["door"]["outer"]), "inner": _curve(data["door"]["inner"]),
           "size": tuple(data["size"]), "name": pathlib.Path(path).stem}
    ix, iy = data["inside"]
    for k in ("outer", "inner"):
        gap = x_at(cam[k], iy) - ix
        if gap == 0:
            sys.exit(f"{path}: el punto `inside` cae sobre la curva {k}")
        cam[k + "_sign"] = 1 if gap > 0 else -1
    return cam


def signed(cam, which, x, y):
    """Distancia horizontal con signo a una de las curvas: positiva hacia el pasillo (px)."""
    return (x_at(cam[which], y) - x) * cam[which + "_sign"]


def at_door(cam, x, y):
    """Las curvas cruzan la imagen entera: todo punto está a la altura de la puerta."""
    return True


def side_of(cam, x, y):
    if signed(cam, "outer", x, y) < 0:
        return OUTSIDE
    if signed(cam, "inner", x, y) > 0:
        return INSIDE
    return None  # en el umbral, entre las dos líneas


def parse_tracks(lines):
    """{id: [(frame, cx, cy), ...]} ordenado por frame, desde líneas MOT."""
    tracks = collections.defaultdict(list)
    for line in lines:
        p = line.split(",")
        x, y, w, h = (float(v) for v in p[2:6])
        tracks[int(float(p[1]))].append((int(float(p[0])), x + w / 2, y + h / 2))
    return {i: sorted(v) for i, v in tracks.items()}


def track_events(cam, points):
    """Eventos de un track: [(frame, 'sube'|'baja')]."""
    events, side = [], None
    for f, x, y in points:
        if not at_door(cam, x, y):
            continue
        now = side_of(cam, x, y)
        if now is None:
            continue
        if side is not None and now != side:
            events.append((f, "sube" if now == INSIDE else "baja"))
        side = now
    return events


def detect(cam, lines):
    tracks = parse_tracks(lines)
    events = sorted((f, tid, kind) for tid, pts in tracks.items() for f, kind in track_events(cam, pts))
    # tracks que nacen o mueren junto al borde de la puerta: candidatos a persona no contada
    edge = sum(1 for pts in tracks.values() for f, x, y in (pts[0], pts[-1])
               if at_door(cam, x, y) and -30 <= signed(cam, "outer", x, y) and signed(cam, "inner", x, y) <= 30)
    return events, {"tracks": len(tracks), "nacen_o_mueren_en_la_puerta": edge}


def source_lines(a):
    if a.tracks:
        return [l for l in pathlib.Path(a.tracks).read_text().splitlines() if l.strip()]
    status, body = _http("GET", f"{a.api.rstrip('/')}/api/jobs/{a.job}/tracks")
    if status != 200:
        sys.exit(f"job {a.job}: HTTP {status}")
    lines = [l for l in body.splitlines() if l.strip()]
    if a.gt:
        info = seqinfo(pathlib.Path(a.gt) / "gt" / "gt.txt")
        lines = cut_lines(lines, int(info["start"]), int(info["seqlength"]))
    return lines


def summary(events):
    c = collections.Counter(kind for _, _, kind in events)
    return {"sube": c["sube"], "baja": c["baja"]}


def cmd_events(a):
    cam = load_camera(a.camera)
    events, diag = detect(cam, source_lines(a))
    w = csv.writer(sys.stdout)
    w.writerow(["frame", "track_id", "direccion"])
    w.writerows(events)
    print(json.dumps({**summary(events), **diag}, ensure_ascii=False), file=sys.stderr)


def match(truth, pred, tol):
    """Emparejamiento voraz por dirección y cercanía en frames. Devuelve aciertos."""
    used, hits = set(), 0
    for f, _, kind in truth:
        best = min(((abs(g - f), j) for j, (g, _, k) in enumerate(pred)
                    if k == kind and j not in used and abs(g - f) <= tol), default=None)
        if best:
            used.add(best[1])
            hits += 1
    return hits


def cmd_compare(a):
    cam = load_camera(a.camera)
    gt_lines = [l for l in (pathlib.Path(a.gt) / "gt" / "gt.txt").read_text().splitlines() if l.strip()]
    truth, _ = detect(cam, gt_lines)
    pred, diag = detect(cam, source_lines(a))
    hits = match(truth, pred, a.tol)
    t, p = summary(truth), summary(pred)
    print(f"verdad (golden):  sube {t['sube']}  baja {t['baja']}")
    print(f"job {a.job}:          sube {p['sube']}  baja {p['baja']}   "
          f"(tracks que nacen/mueren en la puerta: {diag['nacen_o_mueren_en_la_puerta']})")
    for k in ("sube", "baja"):
        if t[k]:
            print(f"  error de conteo {k}: {p[k] - t[k]:+d} ({(p[k] - t[k]) / t[k]:+.0%})")
    print(f"  eventos: precision {hits / len(pred) if pred else 0:.2f}  "
          f"recall {hits / len(truth) if truth else 0:.2f}  (±{a.tol} frames)")


def cmd_selftest(_):
    """Casos con respuesta conocida, sin video ni modelo.

    Puerta vertical: exterior en x=120 (andén a la derecha), interior en x=100.
    Una tercera curva doblada comprueba que se sigue la forma, no una recta.
    """
    cam = {"outer": _curve([(120, 0), (120, 400)]), "inner": _curve([(100, 0), (100, 400)]),
           "outer_sign": 1, "inner_sign": 1}
    bent = {**cam, "outer": _curve([(120, 0), (160, 200), (120, 400)]), "inner": _curve([(100, 0), (140, 200), (100, 400)])}
    walk = lambda xs, y=100: [(i + 1, x, y) for i, x in enumerate(xs)]  # noqa: E731
    cases = [
        ("del andén al pasillo = sube", walk(range(180, 40, -10)), ["sube"]),
        ("del pasillo al andén = baja", walk(range(40, 190, 10)), ["baja"]),
        ("oscila en el umbral = nada", walk([150, 115, 105, 115, 105, 150]), []),
        ("oscila pero cruza una vez = un evento", walk([150, 110, 125, 110, 60, 50]), ["sube"]),
        ("sube y vuelve a bajar = dos", walk([150, 50, 150]), ["sube", "baja"]),
        ("de pie en el umbral y se va al pasillo = nada", walk([110, 105, 80, 50]), []),
        ("camina por el pasillo = nada", walk(range(10, 90, 10)), []),
        ("cruza por la punta de abajo, sin rodear nada = sube", walk(range(180, 40, -10), y=390), ["sube"]),
        ("curva doblada: en x=130 a media altura ya es pasillo", [(1, 180, 200), (2, 130, 200)], ["sube"]),
    ]
    ok = True
    for name, pts, want in cases:
        got = [k for _, k in track_events(bent if name.startswith("curva") else cam, pts)]
        ok &= got == want
        print(f"{'OK  ' if got == want else 'FALLO'}  {name}" + ("" if got == want else f": {got} != {want}"))
    sys.exit(0 if ok else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("events", "compare"):
        s = sub.add_parser(name)
        s.add_argument("--camera", required=True)
        s.add_argument("--api", default="http://track.torre")
        if name == "events":
            src = s.add_mutually_exclusive_group(required=True)
            src.add_argument("--tracks", help="fichero MOT")
            src.add_argument("--job", type=int)
            s.add_argument("--gt", help="clip del golden: corta el job a su tramo")
        else:
            s.add_argument("--gt", required=True, help="clip del golden (verdad)")
            s.add_argument("--job", type=int, required=True)
            s.add_argument("--tol", type=int, default=10)
            s.set_defaults(tracks=None)
    sub.add_parser("selftest")
    a = p.parse_args()
    {"events": cmd_events, "compare": cmd_compare, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    main()
