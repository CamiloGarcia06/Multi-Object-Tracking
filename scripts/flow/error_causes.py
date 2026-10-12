#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "numpy"]
# ///
"""C6 — por qué se pierde cada persona del golden de eventos.

Para cada subida o bajada del golden que el sistema no cuenta (emparejando por
dirección a ±`--tol` frames, como eval_flow.py), mira qué había cerca del punto
anotado (±`--win` frames, `--radius` px) y le asigna UNA causa, en este orden:

  detector     no hay ninguna detección cerca: el detector no ve la cabeza.
  roi          hay detecciones, pero todas fuera de la ROI del job.
  intermitente la cabeza se detecta en menos de `--min-frames` frames (conf >=
               0,25): ningún tracker abre un track con eso. Es del DETECTOR.
  tracker      hay detecciones suficientes y ningún track: el tracker no las
               confirmó.
  tiempo       el track sí cuenta a la persona, pero a más de ±tol frames de la
               marca (camina despacio entre "llega a la línea" y "el centro la
               cruza"): error de la medida más que del sistema.
  doble        el track de esa persona ya contó a OTRA persona del golden: un
               solo track para dos (cambio de identidad).
  nace-tarde   (sube) el track nace ya pasada la zona de la puerta, o
               (baja) el track no viene del pasillo: solo se la ve en la puerta.
  corto        (sube) el track no llega al pasillo, o (baja) muere antes de
               la zona de la puerta: se rompe a medio camino.
  puerta       el track cumple origen y destino pero nace/muere fuera de los
               intervalos de puerta abierta.
  otra         nada de lo anterior: revisar a mano.

`nace-tarde` mezcla detector (no vio la cabeza en la puerta) y tracker (la vio
pero no abrió track): se separa mirando el video.

Uso:
  uv run scripts/flow/error_causes.py --camera configs/cameras/videoTM_07.yaml \\
      --golden data/flow_golden/videoTM_07.csv --tracks job27.txt --roi-job 27 \\
      --dets dets.npy --door data/flow_videos/puerta_abierta_videoTM_07.json
"""
import argparse, collections, csv, json, pathlib, sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import events as E  # noqa: E402
from baseline import inside_polygon, roi_of_job  # noqa: E402


def spatial_pairs(golden, pred, tracks, tol, win, radius):
    """Parejas (i_golden, j_pred): misma dirección, ±tol frames y el track del evento
    pasa a menos de `radius` px del punto anotado (±`win` frames). Emparejamiento
    máximo (caminos de aumento): solo con el frame no se sabe CUÁL de varias
    personas cercanas es la perdida, y la causa depende de eso.
    """
    cand = [[j for j, (f, tid, k) in enumerate(pred)
             if k == g["direccion"] and abs(f - g["frame"]) <= tol
             and near(tracks[int(tid)], g["frame"], g["x"], g["y"], win, radius)] for g in golden]
    owner = {}

    def augment(i, seen):
        for j in cand[i]:
            if j not in seen:
                seen.add(j)
                if j not in owner or augment(owner[j], seen):
                    owner[j] = i
                    return True
        return False

    for i in range(len(golden)):
        augment(i, set())
    return [(i, j) for j, i in owner.items()]


def near(points, frame, x, y, win, radius):
    return [(f, px, py) for f, px, py in points if abs(f - frame) <= win and np.hypot(px - x, py - y) <= radius]


def classify(cam, t, tracks, track_events, matched_truth, dets, roi, is_open, win, radius, min_frames=3):
    frame, kind, x, y = t["frame"], t["direccion"], t["x"], t["y"]
    zone, aisle = cam["od"]["zona_puerta"], cam["od"]["pasillo"]
    close = {tid: near(pts, frame, x, y, win, radius) for tid, pts in tracks.items()}
    close = {tid: c for tid, c in close.items() if c}
    if not close:
        around = [(f, cx, cy, c) for f, cx, cy, c in dets if abs(f - frame) <= win and np.hypot(cx - x, cy - y) <= radius]
        if not around:
            return "detector", None
        if roi and not any(inside_polygon(roi, cx, cy) for _, cx, cy, _ in around):
            return "roi", None
        if len({f for f, _, _, c in around if c >= 0.25}) < min_frames:
            return "intermitente", None
        return "tracker", None
    tid = min(close, key=lambda i: min(abs(f - frame) + np.hypot(px - x, py - y) / 10 for f, px, py in close[i]))
    pts = tracks[tid]
    for f, k, _ in track_events.get(tid, []):
        if k == kind and any(abs(f - m) <= 30 for m in matched_truth.get((tid, k), [])):
            return "doble", tid
    if any(k == kind for _, k, _ in track_events.get(tid, [])):
        return "tiempo", tid
    d = [E.signed(cam, "inner", px, py) for _, px, py in pts]
    if kind == "sube":
        if d[0] > zone:
            return "nace-tarde", tid
        if max(d) < aisle:
            return "corto", tid
        return ("puerta" if not is_open(pts[0][0]) else "otra"), tid
    if max(d) < aisle:
        return "nace-tarde", tid
    if d[-1] > zone:
        return "corto", tid
    return ("puerta" if not is_open(pts[-1][0]) else "otra"), tid


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--camera", required=True)
    p.add_argument("--golden", required=True)
    p.add_argument("--tracks", required=True, help="MOT del job (frames del video)")
    p.add_argument("--dets", required=True, help="dets.npy de track-studio")
    p.add_argument("--roi-job", type=int)
    p.add_argument("--api", default="http://track.torre")
    p.add_argument("--door")
    p.add_argument("--tol", type=int, default=10)
    p.add_argument("--win", type=int, default=5, help="frames alrededor del punto anotado")
    p.add_argument("--radius", type=float, default=60, help="px alrededor del punto anotado")
    p.add_argument("--conf", type=float, default=0.10, help="conf mínima de las detecciones a mirar")
    p.add_argument("--min-frames", type=int, default=3, help="frames con detección para no ser intermitente")
    p.add_argument("--csv", help="escribe aquí la lista de errores")
    a = p.parse_args()

    cam = E.load_camera(a.camera)
    is_open = E.door_filter(a.door, 0, cam["od"]["holgura"])
    lines = [l for l in pathlib.Path(a.tracks).read_text().splitlines() if l.strip()]
    tracks = E.parse_tracks(lines)
    pred, _ = E.detect(cam, lines, "od", is_open)
    by_track = collections.defaultdict(list)
    for tid, pts in tracks.items():
        by_track[tid] = E.od_events(cam, pts)
    golden = [{"frame": int(r["frame"]), "direccion": r["direccion"], "x": float(r["x"]), "y": float(r["y"]),
               "parada": r["parada_inicio"]} for r in csv.DictReader(open(a.golden)) if r["direccion"] in ("sube", "baja")]
    hits = spatial_pairs(golden, pred, tracks, a.tol, a.win, a.radius)
    hit_ids = {i for i, _ in hits}
    lost = [i for i in range(len(golden)) if i not in hit_ids]
    # personas del golden que SÍ contó cada track: un track que cuenta a una no puede contar a otra cercana
    matched = collections.defaultdict(list)
    for i, j in hits:
        f, tid, k = pred[j]
        matched[(int(tid), k)].append(f)
    roi = roi_of_job(a.api, a.roi_job) if a.roi_job else None
    dets = [(int(f), (x1 + x2) / 2, (y1 + y2) / 2, c) for f, x1, y1, x2, y2, c, *_ in np.load(a.dets) if c >= a.conf]

    rows = []
    for i in lost:
        g = golden[i]
        cause, tid = classify(cam, g, tracks, by_track, matched, dets, roi, is_open, a.win, a.radius, a.min_frames)
        rows.append({**g, "causa": cause, "track": tid if tid is not None else ""})
    total = collections.Counter(r["direccion"] for r in golden)
    print(f"perdidas: {len(rows)} de {len(golden)} (sube {sum(r['direccion'] == 'sube' for r in rows)}/{total['sube']}, "
          f"baja {sum(r['direccion'] == 'baja' for r in rows)}/{total['baja']})")
    for cause, n in collections.Counter(r["causa"] for r in rows).most_common():
        print(f"  {cause:11s} {n:3d}  " + ", ".join(f"{r['frame']}{r['direccion'][0]}" for r in rows if r["causa"] == cause))
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, ["parada", "frame", "direccion", "x", "y", "causa", "track"])
            w.writeheader()
            w.writerows(rows)
    print(json.dumps(collections.Counter(r["causa"] for r in rows)), file=sys.stderr)


if __name__ == "__main__":
    main()
