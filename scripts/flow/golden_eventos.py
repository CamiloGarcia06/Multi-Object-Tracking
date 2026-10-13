#!/usr/bin/env python3
"""Prepara la tarea de CVAT de un golden de EVENTOS: un job por apertura de puerta.

Mismo formato que el golden de videoTM_07 (12-10): imágenes `fNNNNNN.jpg` con N = frame
del video contado desde 1 (como el MOT), con las curvas de la puerta pintadas (interior
verde, exterior roja) y una cabecera "frame N PUERTA ABIERTA/cerrada". Etiquetas de
punto `sube` / `baja` / `raro` (con nota), sin pre-anotar.

Las aperturas se pasan A MANO (`--aperturas`), revisadas a ojo, y NO salen de door.py: así
el golden no depende del detector de puerta que se evalúa. Cada job cubre la apertura
con `--margen` frames antes y después.

Salida en OUT: img/, task.json y data.json (job_file_mapping), listos para el
`crear_tarea.sh` de data/cvat_import/eventos_videoTM_07/.

Necesita opencv: en la torre con el venv de track-studio.
  ~/Projects/track-studio/.venv/bin/python golden_eventos.py --camera videoTM_03.yaml \\
      --video ~/videos/videoTM_03.mkv --aperturas 6673-7000,9361-9487 --out DIR
"""
import argparse, json
from pathlib import Path

import cv2
import numpy as np
import yaml

LABELS = [{"name": "sube", "type": "points", "color": "#22c55e"},
          {"name": "baja", "type": "points", "color": "#ef4444"},
          {"name": "raro", "type": "points", "color": "#facc15",
           "attributes": [{"name": "nota", "mutable": False, "input_type": "text",
                           "values": [""], "default_value": ""}]}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--aperturas", required=True, help="a-b,c-d,... en frames contados desde 1")
    ap.add_argument("--margen", type=int, default=60)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    door = yaml.safe_load(open(a.camera))["door"]
    curves = [(np.array(door["inner"], np.int32), (0, 200, 0)), (np.array(door["outer"], np.int32), (0, 0, 220))]
    opens = [tuple(map(int, r.split("-"))) for r in a.aperturas.split(",")]
    jobs = [(max(1, s - a.margen), e + a.margen) for s, e in opens]
    out = Path(a.out)
    (out / "img").mkdir(parents=True, exist_ok=True)

    cap, mapping = cv2.VideoCapture(a.video), []
    for start, stop in jobs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start - 1)
        names = []
        for n in range(start, stop + 1):
            ok, im = cap.read()
            if not ok:
                break
            for pts, color in curves:
                cv2.polylines(im, [pts], False, color, 1, cv2.LINE_AA)
            is_open = any(s <= n <= e for s, e in opens)
            text = f"frame {n} " + ("PUERTA ABIERTA" if is_open else "puerta cerrada")
            (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(im, (0, 0), (w + 6, h + 8), (40, 140, 40) if is_open else (60, 60, 60), -1)
            cv2.putText(im, text, (3, h + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            name = f"f{n:06d}.jpg"
            cv2.imwrite(str(out / "img" / name), im, [cv2.IMWRITE_JPEG_QUALITY, 95])
            names.append(name)
        mapping.append(names)
    cap.release()

    video = Path(a.video).stem
    (out / "task.json").write_text(json.dumps(
        {"name": f"golden eventos {video} (una apertura por job)", "labels": LABELS}, ensure_ascii=False))
    (out / "data.json").write_text(json.dumps(
        {"image_quality": 95, "upload_file_order": [n for g in mapping for n in g], "job_file_mapping": mapping}))
    print(json.dumps({"video": video, "jobs": [[g[0], g[-1], len(g)] for g in mapping],
                      "imagenes": sum(map(len, mapping))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
