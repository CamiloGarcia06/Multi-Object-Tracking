#!/usr/bin/env python3
"""C7 — por qué ByteTrack no da ID a detecciones buenas en la puerta.

Repite el ByteTrack de un job (el MISMO código de ultralytics que corre en
track-studio) sobre las detecciones cacheadas (`dets.npy`, ya con el NMS
post-hoc), filtradas por la ROI del job, y anota el destino de cada detección
en cada frame:

  sigue N     1.ª/2.ª asociación con el track confirmado N
  recupera N  re-encuentra el track perdido N
  confirma N  empareja con el track sin confirmar N, que pasa a confirmado
  nuevo N     abre el track sin confirmar N: este frame NO sale en el MOT
  <new        sin emparejar y score < new_track_thresh: no abre track
  baja        score bajo (low < s < high) sin emparejar
  fuera       score <= track_low_thresh: el tracker ni la mira

y cada track sin confirmar que se borra, con la detección del frame que más se
le parecía (IoU) y quién se la quedó.

Necesita ultralytics: se corre en la torre con el venv de track-studio.

  check    reproduce el MOT del job; si no cuadra, el diagnóstico no vale.
  explain  línea de tiempo de las detecciones cerca de cada error revisado.
  run      escribe el MOT del tracker con parámetros cambiados (`--set clave=valor`),
           para barrer candidatos sin crear jobs; `--interp saltos.csv` = candidato 3c.

Uso (torre):
  ~/Projects/track-studio/.venv/bin/python diag_bytetrack.py check \\
      --dets dets.npy --roi roi27.json --tracker bytetrack_buffer90_match09.yaml --mot job27.txt
  ... explain --errors errores_job27_revisados.csv --paradas 5347 22018
"""
import argparse, collections, csv, json, sys
from types import SimpleNamespace

import numpy as np
import yaml

SHAPE = (480, 640)


def inside_polygon(poly, x, y):
    """Ray casting, igual que la ROI de track-studio (centro de la caja)."""
    inside, n = False, len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def iou(a, b):
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = w * h
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def load_frames(path, poly):
    """Lista por frame (índice 0 = frame 1) de arrays (N, 6) dentro de la ROI."""
    flat = np.load(path)
    total = int(flat[:, 0].max())
    keep = [inside_polygon(poly, (r[1] + r[3]) / 2, (r[2] + r[4]) / 2) for r in flat]
    flat = flat[np.array(keep, dtype=bool)]
    flat = flat[np.argsort(flat[:, 0], kind="stable")]
    cuts = np.searchsorted(flat[:, 0], np.arange(1, total + 2))
    return [flat[cuts[i]:cuts[i + 1], 1:] for i in range(total)]


def make_tracker(params):
    from ultralytics.trackers.byte_tracker import BYTETracker, STrack

    class Traced(BYTETracker):
        """BYTETracker que deja en `self.fates` el destino de cada detección del frame."""

        def update(self, results, img=None, feats=None, **kw):
            before = {t.track_id: ("sin-confirmar" if not t.is_activated else "activo")
                      for t in self.tracked_stracks}
            before.update({t.track_id: "perdido" for t in self.lost_stracks})
            self.removed_now, self.boxes_now = [], np.asarray(results.xyxy)
            out = super().update(results, img, feats, **kw)
            fates = {}
            for t in self.tracked_stracks:
                if t.frame_id != self.frame_id:
                    continue
                prev = before.get(t.track_id)
                kind = {"sin-confirmar": "confirma", "perdido": "recupera", "activo": "sigue"}.get(prev, "nuevo")
                fates[int(t.idx)] = (kind, t.track_id)
            for i, s in enumerate(np.asarray(results.conf)):
                if i in fates:
                    continue
                if s <= self.args.track_low_thresh:
                    fates[i] = ("fuera", None)
                elif s < self.args.track_high_thresh:
                    fates[i] = ("baja", None)
                else:
                    fates[i] = ("<new", None)
            self.fates = fates
            return out

        def _unconfirmed_association(self, unconfirmed, u_detection, detections, activated, removed):
            n = len(removed)
            res = super()._unconfirmed_association(unconfirmed, u_detection, detections, activated, removed)
            for t in removed[n:]:
                pred = t.xyxy  # caja predicha por el Kalman en este frame
                ious = [iou(pred, b) for b in self.boxes_now]
                best = int(np.argmax(ious)) if ious else None
                self.removed_now.append((t.track_id, best, ious[best] if ious else 0.0))
            return res

    STrack.reset_id()
    return Traced(SimpleNamespace(**params))


def replay(frames, params):
    """Corre el tracker frame a frame. Devuelve (mot, log): mot = {frame: [(tid, caja)]},
    log = {frame: (dets, fates, borrados)}."""
    from ultralytics.engine.results import Boxes

    tracker = make_tracker(params)
    mot, log = {}, {}
    for f, dets in enumerate(frames, start=1):
        # ultralytics 8.4 llama al tracker también con 0 cajas (la ROI deja muchos frames vacíos)
        tracks = tracker.update(Boxes(dets.reshape(-1, 6), SHAPE), None)
        mot[f] = [(int(t[4]), t[:4].astype(float)) for t in tracks]
        log[f] = (dets, tracker.fates, tracker.removed_now)
    return mot, log


def read_mot(path):
    out = collections.defaultdict(list)
    for r in np.loadtxt(path, delimiter=",", ndmin=2):
        f, tid, x, y, w, h = r[:6]
        out[int(f)].append((int(tid), np.array([x, y, x + w, y + h])))
    return out


def id_map(mine, job):
    """{tid de la repetición: tid del job}, emparejando cajas idénticas frame a frame."""
    votes = collections.Counter()
    for f, rows in job.items():
        for tj, bj in rows:
            for tm, bm in mine.get(f, []):
                if np.abs(bm - bj).max() < 0.05:
                    votes[tm, tj] += 1
    out = {}
    for (tm, tj), _ in votes.most_common():
        out.setdefault(tm, tj)
    return out


def setup(a):
    poly = json.load(open(a.roi))["polygon"]
    params = yaml.safe_load(open(a.tracker))
    return load_frames(a.dets, poly), params


def cmd_check(a):
    frames, params = setup(a)
    mine, _ = replay(frames, params)
    job = read_mot(a.mot)
    ids = id_map(mine, job)
    n_job = sum(len(v) for v in job.values())
    n_mine = sum(len(v) for v in mine.values())
    same = sum(1 for f, rows in mine.items() for tm, bm in rows
               if any(ids.get(tm) == tj and np.abs(bm - bj).max() < 0.05 for tj, bj in job.get(f, [])))
    print(json.dumps({"cajas_job": n_job, "cajas_repeticion": n_mine, "identicas_con_mismo_id": same,
                      "ids_job": len({t for v in job.values() for t, _ in v}), "ids_mapeados": len(ids)}))


def cmd_explain(a):
    frames, params = setup(a)
    mine, log = replay(frames, params)
    ids = id_map(mine, read_mot(a.mot))
    jid = lambda t: f"#{ids[t]}" if t in ids else f"r{t}"  # r = id que el job nunca sacó
    errors = list(csv.DictReader(open(a.errors)))
    for e in errors:
        if a.paradas and e["parada"] not in a.paradas:
            continue
        f0, x0, y0 = int(e["frame"]), float(e["x"]), float(e["y"])
        print(f"\n=== parada {e['parada']} frame {f0} {e['direccion']} ({x0:.0f},{y0:.0f}) "
              f"revisión {e['revision']} causa {e['causa']} track {e['track'] or '-'}")
        for f in range(f0 - a.before, f0 + a.after + 1):
            if f not in log:
                continue
            dets, fates, removed = log[f]
            parts = []
            for i, d in enumerate(dets):
                cx, cy = (d[0] + d[2]) / 2, (d[1] + d[3]) / 2
                if np.hypot(cx - x0, cy - y0) > a.radius:
                    continue
                kind, tid = fates[i]
                parts.append(f"({cx:.0f},{cy:.0f}) {d[4]:.2f} {kind}{' ' + jid(tid) if tid else ''}")
            for tid, best, v in removed:
                if best is None:
                    parts.append(f"BORRA r{tid} (frame vacío)")
                    continue
                d = dets[best]
                cx, cy = (d[0] + d[2]) / 2, (d[1] + d[3]) / 2
                if np.hypot(cx - x0, cy - y0) <= a.radius:
                    kind, owner = fates[best]
                    parts.append(f"BORRA r{tid}: mejor IoU {v:.2f} con ({cx:.0f},{cy:.0f}) -> {kind}"
                                 f"{' ' + jid(owner) if owner else ''}")
            mark = "*" if f == f0 else " "
            print(f"{mark}{f}: " + (" | ".join(parts) if parts else "—"))


def interpolate_jumps(frames, jumps, gate=80.0):
    """3c: en cada salto (frame j) el frame j-1 es una copia congelada del j-2. Sus
    detecciones pasan a ser el punto medio entre las de j-2 y j, emparejadas por
    cercanía (voraz, < `gate` px); las de j-2 sin pareja se quedan como estaban."""
    out = list(frames)
    for j in jumps:
        if j < 3 or j > len(frames):
            continue
        prev, nxt = frames[j - 3], frames[j - 1]
        c = lambda d: ((d[:, 0] + d[:, 2]) / 2, (d[:, 1] + d[:, 3]) / 2)
        if len(prev) == 0 or len(nxt) == 0:
            continue
        (px, py), (nx, ny) = c(prev), c(nxt)
        dist = np.hypot(px[:, None] - nx[None], py[:, None] - ny[None])
        used_p, used_n, rows = set(), set(), []
        for k in np.argsort(dist, axis=None):
            i, m = np.unravel_index(k, dist.shape)
            if dist[i, m] > gate:
                break
            if i in used_p or m in used_n:
                continue
            used_p.add(i); used_n.add(m)
            mid = (prev[i] + nxt[m]) / 2
            mid[5] = prev[i][5]
            rows.append(mid)
        rows += [prev[i] for i in range(len(prev)) if i not in used_p]
        out[j - 2] = np.array(rows, dtype=prev.dtype).reshape(-1, 6)
    return out


def cmd_run(a):
    frames, params = setup(a)
    if a.interp:
        jumps = [int(l.split(",")[0]) for l in open(a.interp) if ",salto," in l]
        frames = interpolate_jumps(frames, jumps)
    for kv in a.set:
        k, v = kv.split("=", 1)
        params[k] = yaml.safe_load(v)
    mine, _ = replay(frames, params)
    with open(a.out, "w") as h:
        for f in sorted(mine):
            for tid, b in mine[f]:
                h.write(f"{f},{tid},{b[0]:.2f},{b[1]:.2f},{b[2] - b[0]:.2f},{b[3] - b[1]:.2f},1,-1,-1,-1\n")
    print(json.dumps({"out": a.out, "set": a.set, "ids": len({t for v in mine.values() for t, _ in v}),
                      "cajas": sum(len(v) for v in mine.values())}))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("check", "explain", "run"):
        s = sub.add_parser(name)
        s.add_argument("--dets", required=True)
        s.add_argument("--roi", required=True, help="JSON de GET /api/jobs/{id}/roi")
        s.add_argument("--tracker", required=True, help="yaml del tracker del job")
        if name == "run":
            s.add_argument("--set", action="append", default=[], help="clave=valor del yaml del tracker")
            s.add_argument("--out", required=True)
            s.add_argument("--interp", help="CSV de frame_jumps.py: interpola el frame congelado de cada salto (3c)")
        else:
            s.add_argument("--mot", required=True, help="MOT del job, para comprobar y mapear ids")
        if name == "explain":
            s.add_argument("--errors", required=True)
            s.add_argument("--paradas", nargs="*", default=[])
            s.add_argument("--before", type=int, default=20)
            s.add_argument("--after", type=int, default=10)
            s.add_argument("--radius", type=float, default=70)
    a = p.parse_args()
    {"check": cmd_check, "explain": cmd_explain, "run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
