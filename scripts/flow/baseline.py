#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "numpy"]
# ///
"""C4 — línea base SIN tracking: contar cruces con detecciones de frames consecutivos.

Lo que pide el anteproyecto como comparación: contar sin seguimiento individual.
Para que la ÚNICA diferencia con el sistema sea el tracking, parte de las mismas
detecciones que los jobs (mismo detector, conf, NMS y ROI) y usa la misma puerta:

  1. Cada detección del frame t se empareja con la más cercana del frame t+1
     (emparejamiento voraz y mutuo por distancia entre centros, como mucho
     `--gate` px). Sin memoria: lo que no está en t+1 se olvida.
  2. Un par que pasa la curva interior (d de <= 0 a > 0) es una subida; al
     revés, una bajada. Mismo signo `d` que events.py.
  3. Solo cuentan los cruces con la puerta abierta (`--door`, con la holgura de
     la cámara).

Lo que le falta por no tener memoria, y es justo lo que el tracking aporta:
  - quien oscila sobre la línea cuenta varias veces;
  - si el detector pierde la cabeza en el frame del cruce, no cuenta;
  - no distingue a quien nace dentro del umbral (no hay origen ni destino).

Detecciones: el `dets.npy` de track-studio (tools/sweep_trackers.py detect):
filas [frame, x1, y1, x2, y2, conf, clase], frames desde 1.

Uso:
  uv run scripts/flow/baseline.py selftest
  uv run scripts/flow/baseline.py events --camera configs/cameras/videoTM_07.yaml \\
      --dets dets.npy --roi-job 27 --door data/flow_videos/puerta_abierta_videoTM_07.json
"""
import argparse, collections, csv, json, pathlib, sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import events as E  # noqa: E402


def inside_polygon(poly, x, y):
    """Ray casting, igual que la ROI de track-studio (centro de la caja)."""
    inside, n = False, len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def load_centers(dets, conf, roi=None):
    """{frame: [(cx, cy), ...]} con conf >= `conf` y dentro de la ROI."""
    frames = collections.defaultdict(list)
    for f, x1, y1, x2, y2, c, *_ in dets:
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        if c >= conf and (roi is None or inside_polygon(roi, cx, cy)):
            frames[int(f)].append((float(cx), float(cy)))
    return frames


def pairs(a, b, gate):
    """Emparejamiento voraz y mutuo entre dos listas de centros: [(i, j)]."""
    if not a or not b:
        return []
    d = np.hypot(*(np.array(a)[:, None, :] - np.array(b)[None, :, :]).transpose(2, 0, 1))
    out, used_a, used_b = [], set(), set()
    for k in np.argsort(d, axis=None):
        i, j = divmod(int(k), len(b))
        if d[i, j] > gate:
            break
        if i not in used_a and j not in used_b:
            used_a.add(i), used_b.add(j), out.append((i, j))
    return out


def crossings(cam, frames, gate, is_open=lambda f: True):
    """[(frame, 'sube'|'baja')] de los pares de frames consecutivos que pasan la curva interior."""
    events, dropped = [], 0
    for f in sorted(frames):
        nxt = frames.get(f + 1)
        if not nxt:
            continue
        for i, j in pairs(frames[f], nxt, gate):
            d1 = E.signed(cam, "inner", *frames[f][i])
            d2 = E.signed(cam, "inner", *nxt[j])
            kind = "sube" if d1 <= 0 < d2 else "baja" if d2 <= 0 < d1 else None
            if kind and is_open(f + 1):
                events.append((f + 1, kind))
            elif kind:
                dropped += 1
    return events, dropped


def roi_of_job(api, job):
    status, body = E._http("GET", f"{api.rstrip('/')}/api/jobs/{job}/roi")
    if status != 200:
        sys.exit(f"job {job}: ROI HTTP {status}")
    return [tuple(p) for p in json.loads(body)["polygon"]]


def cmd_events(a):
    cam = E.load_camera(a.camera)
    roi = roi_of_job(a.api, a.roi_job) if a.roi_job else None
    frames = load_centers(np.load(a.dets), a.conf, roi)
    is_open = E.door_filter(a.door, 0, cam["od"]["holgura"])
    events, dropped = crossings(cam, frames, a.gate, is_open)
    w = csv.writer(sys.stdout)
    w.writerow(["frame", "track_id", "direccion"])
    w.writerows((f, -1, k) for f, k in events)
    c = collections.Counter(k for _, k in events)
    print(json.dumps({"sube": c["sube"], "baja": c["baja"], "con_puerta_cerrada": dropped,
                      "conf": a.conf, "gate": a.gate, "roi_job": a.roi_job}), file=sys.stderr)


def cmd_selftest(_):
    """Puerta vertical: curva interior en x=100, pasillo a la izquierda (d = 100 - x)."""
    cam = {"inner": E._curve([(100, 0), (100, 400)]), "inner_sign": 1}
    walk = lambda xs, y=100: {1 + i: [(x, y)] for i, x in enumerate(xs)}  # noqa: E731

    def merge(*ds):
        out = collections.defaultdict(list)
        for d in ds:
            for f, v in d.items():
                out[f] += v
        return out

    cases = [
        ("cruza hacia el pasillo = sube", walk(range(140, 60, -8)), ["sube"]),
        ("cruza hacia el andén = baja", walk(range(60, 140, 8)), ["baja"]),
        ("oscila sobre la línea = CUENTA DE MÁS (sin memoria)", walk([104, 96, 104, 96]), ["sube", "baja", "sube"]),
        ("pierde la cabeza justo al cruzar = no cuenta", {1: [(110, 100)], 2: [(104, 100)], 4: [(94, 100)], 5: [(88, 100)]}, []),
        ("salto mayor que la puerta de 40 px = no cuenta", {1: [(130, 100)], 2: [(70, 100)]}, []),
        ("dos cabezas cruzan a la vez = dos", merge(walk(range(140, 60, -8)), walk(range(140, 60, -8), y=300)), ["sube", "sube"]),
        ("en el pasillo, sin cruzar = nada", walk(range(80, 20, -8)), []),
    ]
    ok = True
    for name, frames, want in cases:
        got = [k for _, k in crossings(cam, frames, 40)[0]]
        ok &= got == want
        print(f"{'OK  ' if got == want else 'FALLO'}  {name}" + ("" if got == want else f": {got} != {want}"))
    shut = crossings(cam, walk(range(140, 60, -8)), 40, lambda f: False)
    ok &= shut == ([], 1)
    print(f"{'OK  ' if shut == ([], 1) else 'FALLO'}  con la puerta cerrada no cuenta (y lo registra)")
    poly = [(0, 0), (10, 0), (10, 10), (0, 10)]
    roi_ok = inside_polygon(poly, 5, 5) and not inside_polygon(poly, 15, 5)
    ok &= roi_ok
    print(f"{'OK  ' if roi_ok else 'FALLO'}  ROI por ray casting")
    sys.exit(0 if ok else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("events")
    s.add_argument("--camera", required=True)
    s.add_argument("--dets", required=True, help="dets.npy de track-studio")
    s.add_argument("--conf", type=float, default=0.25, help="umbral de confianza (ByteTrack inicia tracks a 0,25)")
    s.add_argument("--gate", type=float, default=40, help="px máximos entre frames (p99,9 medido: 48)")
    s.add_argument("--roi-job", type=int, help="aplica la ROI sellada en este job de track-studio")
    s.add_argument("--api", default="http://track.torre")
    s.add_argument("--door", help="JSON de intervalos de puerta abierta (frames del video)")
    sub.add_parser("selftest")
    a = p.parse_args()
    {"events": cmd_events, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    main()
