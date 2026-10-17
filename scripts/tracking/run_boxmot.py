#!/usr/bin/env python3
"""B4 — corre un tracker de BoxMOT (DeepOC, OC-SORT, BoT-SORT) sobre detecciones cacheadas.

Lo mismo que hace `BoxmotTracker` de track-studio en un job, pero sin volver a pasar el
detector: parte del `dets.npy` de `scripts/flow/det_video.py` (conf 0,10, NMS post-hoc
0,6), filtra por la ROI con la regla de track-studio (centro de la caja) y le da al
tracker el frame del video, que los de apariencia necesitan. Sirve para comparar
trackers en videos sin job (02, 03(1)); ByteTrack va por `scripts/flow/diag_bytetrack.py run`.

Control: sobre videoTM_07 con `deepocsort_osnet_iou020.yaml` y la ROI del job tiene que
reproducir el MOT del job #28 (`check`). Si no cuadra, las corridas no valen.

Necesita boxmot y opencv: en la torre con el venv de track-studio.
  ~/Projects/track-studio/.venv/bin/python run_boxmot.py run --dets dets_02.npy \\
      --video ~/videos/videoTM_02.mkv --roi roi27.json \\
      --tracker ~/Projects/track-studio/trackers/ocsort.yaml --out runs/ocsort/test02.txt
  ... check --dets dets.npy --video ~/videos/videoTM_07.mkv --roi roi27.json \\
      --tracker ~/Projects/track-studio/trackers/deepocsort_osnet_iou020.yaml --mot job28.txt
"""
import argparse, json, sys
from pathlib import Path

import numpy as np

TS = Path.home() / "Projects/track-studio"
sys.path.insert(0, str(TS / "src"))
from track_studio.jobs.infrastructure.tracking.boxmot_tracker import (  # noqa: E402
    TRACKER_CLASSES, IdMap, read_tracker_config, to_rows, write_rows)
from track_studio.jobs.infrastructure.tracking.roi import contains  # noqa: E402


def build(tracker_yaml):
    import boxmot
    import torch

    config = read_tracker_config(tracker_yaml)
    params = dict(config.get("params") or {})
    if "reid_weights" in params:   # rutas relativas a track-studio, como en la cola
        params["reid_weights"] = Path(TS / params["reid_weights"])
        params.setdefault("device", "cuda:0" if torch.cuda.is_available() else "cpu")
    return getattr(boxmot, TRACKER_CLASSES[config["tracker_type"]])(**params)


def run(a, out):
    import cv2

    polygon = [tuple(p) for p in json.load(open(a.roi))["polygon"]]
    dets = np.load(a.dets)
    by_frame = {int(f): dets[dets[:, 0] == f, 1:7].astype(np.float32) for f in np.unique(dets[:, 0])}
    tracker, ids = build(a.tracker), IdMap()
    cap, n = cv2.VideoCapture(a.video), 0
    empty = np.empty((0, 6), np.float32)
    with open(out, "w") as handle:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            n += 1
            d = by_frame.get(n, empty)
            if len(d):
                d = d[[contains(polygon, (b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in d]]
            write_rows(handle, n, to_rows(tracker.update(d, frame), ids))
    cap.release()
    return n, len(ids)


def cmd_run(a):
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    frames, tracks = run(a, a.out)
    print(json.dumps({"frames": frames, "tracks": tracks, "out": a.out}))


def cmd_check(a):
    out = Path(a.mot).with_suffix(".check.txt")
    run(a, out)
    load = lambda p: sorted(tuple(round(float(v), 1) for v in l.split(",")[:6]) for l in open(p) if l.strip())
    mine, job = load(out), load(a.mot)
    same = len(mine) == len(job) and all(abs(x - y) <= 0.1 for r, s in zip(mine, job) for x, y in zip(r, s))
    print(json.dumps({"filas": len(mine), "filas_job": len(job), "iguales": same}))
    sys.exit(0 if same else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("run", cmd_run), ("check", cmd_check)):
        s = sub.add_parser(name)
        s.add_argument("--dets", required=True)
        s.add_argument("--video", required=True)
        s.add_argument("--roi", required=True, help="JSON con 'polygon' (GET /api/jobs/{id}/roi)")
        s.add_argument("--tracker", required=True, help="yaml de trackers/ de track-studio (backend boxmot)")
        if name == "run":
            s.add_argument("--out", required=True)
        else:
            s.add_argument("--mot", required=True, help="MOT del job (GET /api/jobs/{id}/tracks)")
        s.set_defaults(fn=fn)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
