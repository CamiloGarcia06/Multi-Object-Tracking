#!/usr/bin/env python3
"""B5 — prepara un clip del golden de TRACKING para CVAT, como el de tm07_a (05-10).

Del video saca `--frames` frames desde `--start` (contado desde 1, como el MOT) y del
MOT de un tracker la pre-anotación del mismo tramo: frames renumerados desde 1 e IDs
renumerados 1..N por orden de aparición, en MOT 1.1 (gt/gt.txt + gt/labels.txt), que
es lo que CVAT importa como tracks. Camilo corrige en CVAT cajas e IDs; lo que exporta
es la verdad. Sesgo a declarar: la pre-anotación sale de ByteTrack; solo no le da
ventaja si se revisa el clip entero, frame a frame, y no solo los errores que saltan.

Salida en OUT: frames/frame_NNNNNN.png, <name>_preanotacion.zip, seqinfo.ini.
Necesita opencv: en la torre con el venv de track-studio.
  ~/Projects/track-studio/.venv/bin/python golden_clip.py --video ~/videos/videoTM_02.mkv \\
      --start 3241 --frames 200 --mot test02/base.txt --name tm02_a --out DIR
"""
import argparse, io, json, zipfile
from pathlib import Path

import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--start", type=int, required=True, help="frame del video (desde 1) donde empieza el clip")
    ap.add_argument("--frames", type=int, required=True)
    ap.add_argument("--mot", required=True, help="MOT del tracker sobre el video entero (pre-anotación)")
    ap.add_argument("--name", required=True)
    ap.add_argument("--source", help="nombre del video en seqinfo.ini (por defecto, el del fichero)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    (out / "frames").mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(a.video)
    cap.set(cv2.CAP_PROP_POS_FRAMES, a.start - 1)
    for i in range(1, a.frames + 1):
        ok, im = cap.read()
        if not ok:
            raise SystemExit(f"el video se acaba en el frame {a.start + i - 2}")
        cv2.imwrite(str(out / "frames" / f"frame_{i:06d}.png"), im)
    cap.release()

    ids, rows = {}, []
    for line in open(a.mot):
        p = line.strip().split(",")
        if not p[0]:
            continue
        f = int(float(p[0]))
        if a.start <= f < a.start + a.frames:
            tid = ids.setdefault(int(float(p[1])), len(ids) + 1)
            rows.append((f - a.start + 1, tid, *(float(v) for v in p[2:6])))
    rows.sort()
    gt = "".join(f"{f},{t},{x:.2f},{y:.2f},{w:.2f},{h:.2f},1,1,1.0\n" for f, t, x, y, w, h in rows)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("gt/gt.txt", gt)
        z.writestr("gt/labels.txt", "head\n")
    (out / f"{a.name}_preanotacion.zip").write_bytes(buf.getvalue())

    source = a.source or Path(a.video).stem
    (out / "seqinfo.ini").write_text(
        f"[Sequence]\nname={a.name}\nseqLength={a.frames}\nsource={source}\nstart={a.start}\n")
    print(json.dumps({"clip": a.name, "frames": a.frames, "start": a.start, "tracks": len(ids), "cajas": len(rows)}))


if __name__ == "__main__":
    main()
