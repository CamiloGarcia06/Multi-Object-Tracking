#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""3b — une trozos de track DESPUÉS del tracker (candidato C del diagnóstico de la puerta).

El detector deja huecos de 8–25 frames en la puerta y ByteTrack, que recupera solo
por IoU contra el Kalman, abre un ID nuevo. Aquí un track A que muere y un track B
que nace después se unen (B pasa a llamarse A) si:

  hueco      1 <= B.inicio - A.fin <= --max-gap
  distancia  |A.fin - B.inicio| <= --r0 + --speed * hueco   (px; tope --r-max)
  dirección  si los dos se mueven (> --min-move px/frame), el ángulo entre la
             velocidad final de A y la inicial de B es < 90°

Emparejamiento voraz por distancia/hueco, uno a uno, iterado hasta que no cambia
(una cadena A -> B -> C se une entera).

3d — con `--feats` (de reid_feats.py) además hace falta que el final de A se PAREZCA al
inicio de B: distancia coseno <= --max-dist con el descriptor --desc (osnet | hsv), y
el voraz ordena por esa distancia. Es lo que le faltaba a la 3b, que encadenaba la cola
de personas que bajan en fila. --max-dist se ajusta en videoTM_03 (validación).

Parámetros FIJADOS A PRIORI (no ajustados con el golden de videoTM_07, que es de
evaluación): max-gap 30 (huecos medidos de 8–25 f), speed 15 px/f (cabezas de
~51 px que se mueven 10–30 px/f en la puerta), r0 20, r-max 250.

  uv run scripts/flow/stitch.py job27.txt > job27_stitch.txt
  uv run scripts/flow/stitch.py selftest
"""
import argparse, collections, sys

import numpy as np


def load(lines):
    tracks = collections.defaultdict(list)
    for l in lines:
        q = l.split(",")
        f, t, x, y, w, h = int(q[0]), int(q[1]), *map(float, q[2:6])
        tracks[t].append((f, x + w / 2, y + h / 2, l))
    return {t: sorted(v) for t, v in tracks.items()}


def velocity(pts, end, k=5):
    sel = pts[-k:] if end else pts[:k]
    if len(sel) < 2:
        return np.zeros(2)
    (f0, x0, y0, _), (f1, x1, y1, _) = sel[0], sel[-1]
    return np.array([x1 - x0, y1 - y0]) / max(f1 - f0, 1)


def links(tracks, a, app=None):
    cand = []
    for ta, pa in tracks.items():
        fa, xa, ya, _ = pa[-1]
        va = velocity(pa, end=True)
        for tb, pb in tracks.items():
            fb, xb, yb, _ = pb[0]
            gap = fb - fa
            if tb == ta or not 1 <= gap <= a.max_gap:
                continue
            d = float(np.hypot(xb - xa, yb - ya))
            if d > min(a.r0 + a.speed * gap, a.r_max):
                continue
            vb = velocity(pb, end=False)
            if np.linalg.norm(va) > a.min_move and np.linalg.norm(vb) > a.min_move and va @ vb <= 0:
                continue
            if app is None:
                cand.append((d / gap, ta, tb))
                continue
            dist = 1.0 - float(app["fin"][ta] @ app["ini"][tb])
            if dist <= a.max_dist:
                cand.append((dist, ta, tb))
    cand.sort()
    used_a, used_b, out = set(), set(), {}
    for _, ta, tb in cand:
        if ta in used_a or tb in used_b:
            continue
        used_a.add(ta); used_b.add(tb); out[tb] = ta
    return out


def load_feats(path, desc):
    z = np.load(path)
    ids = [int(t) for t in z["ids"]]
    return {e: dict(zip(ids, z[f"{desc}_{e}"])) for e in ("ini", "fin")}


def stitch(lines, a, app=None):
    tracks = load(lines)
    total = 0
    while True:
        m = links(tracks, a, app)
        if not m:
            break
        total += len(m)
        for tb, ta in sorted(m.items(), key=lambda kv: -tracks[kv[0]][0][0]):
            if tb in tracks and ta in tracks:
                tracks[ta] = sorted(tracks[ta] + tracks.pop(tb))
                if app is not None:
                    app["fin"][ta] = app["fin"][tb]  # la cadena termina como termina B
    rows = []
    for t, pts in tracks.items():
        for f, *_, l in pts:
            q = l.split(","); q[1] = str(t); rows.append((f, t, ",".join(q)))
    return [r[2] for r in sorted(rows)], total


def cmd_selftest(a):
    # A camina a la derecha 10 px/f y se corta 12 f; B sigue igual -> se unen.
    # C va a la izquierda desde donde nace B -> dirección contraria, no se une con A.
    mk = lambda f, t, x, y: f"{f},{t},{x - 25},{y - 25},50,50,1,-1,-1,-1"
    lines = [mk(f, 1, 100 + 10 * f, 200) for f in range(1, 11)]
    lines += [mk(f, 2, 100 + 10 * f, 200) for f in range(23, 33)]
    lines += [mk(f, 3, 330 - 10 * (f - 23), 260) for f in range(23, 33)]
    out, n = stitch(lines, a)
    ids = {int(l.split(",")[1]) for l in out}
    assert n == 1 and ids == {1, 3}, (n, ids)
    a2 = argparse.Namespace(**{**vars(a), "max_gap": 5})
    assert stitch(lines, a2)[1] == 0  # el hueco de 12 f supera max-gap
    # 3d: con apariencia, A y B distintos (coseno 0) no se unen aunque cuadre el resto
    e = np.eye(3)
    a3 = argparse.Namespace(**{**vars(a), "max_dist": 0.3})
    same = {"ini": {1: e[0], 2: e[0], 3: e[2]}, "fin": {1: e[0], 2: e[0], 3: e[2]}}
    diff = {"ini": {1: e[0], 2: e[1], 3: e[2]}, "fin": {1: e[0], 2: e[1], 3: e[2]}}
    assert stitch(lines, a3, same)[1] == 1 and stitch(lines, a3, diff)[1] == 0
    print("selftest OK")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mot", help="fichero MOT, o 'selftest'")
    p.add_argument("--max-gap", type=int, default=30)
    p.add_argument("--speed", type=float, default=15.0)
    p.add_argument("--r0", type=float, default=20.0)
    p.add_argument("--r-max", type=float, default=250.0)
    p.add_argument("--min-move", type=float, default=2.0)
    p.add_argument("--feats", help="npz de reid_feats.py (3d)")
    p.add_argument("--desc", default="osnet", choices=["osnet", "hsv"])
    p.add_argument("--max-dist", type=float, default=0.3, help="distancia coseno máxima (3d)")
    a = p.parse_args()
    if a.mot == "selftest":
        return cmd_selftest(a)
    app = load_feats(a.feats, a.desc) if a.feats else None
    out, n = stitch([l for l in open(a.mot) if l.strip()], a, app)
    sys.stdout.write("\n".join(out) + "\n")
    print(f"uniones: {n}", file=sys.stderr)


if __name__ == "__main__":
    main()
