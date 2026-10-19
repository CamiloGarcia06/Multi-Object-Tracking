#!/usr/bin/env python3
"""Tarea 4 — inventario de videos por congestión, para elegir clips de prueba y el golden de otra cámara.

Por cada video, 1 frame por segundo (900 en 15 min):
  luminancia mediana (gris)                 -> diurno / nocturno
  cabezas por frame (yolo26x-min5, conf 0,25, NMS post-hoc 0,6, frame entero, sin ROI)
      p50, p90, máximo y % de segundos con >= `--lleno` cabezas  -> congestión
y dos miniaturas (minuto 7,5 y el segundo con más cabezas) en una hoja de contacto.

El ESTADO de cada video (entrenado / nunca visto / reservado) sale de las fuentes de
`bus_head_v5_min5` y de `data/golden/DO_NOT_TRAIN.txt`; lo marcado "inferido" no está
escrito en ningún sitio: s03 = videoTM_10 (golden_baseline.md), v10b = videoTM_10(1) y
v18S08 = videoTM_18(1) se deducen por descarte.

Necesita ultralytics: en la torre con el venv de track-studio.
  ~/Projects/track-studio/.venv/bin/python inventario_camaras.py ~/videos/bus OUT

Recorre `<src>/<cam>/bus_<cam>_s<seq>_v<NN>.mkv` (nombres de la tarea 13); el ESTADO se cruza
por la columna `copia_local_antigua` de `<src>/nombres.csv`. Si se corta, se reanuda: lo ya
escrito en `OUT/inventario.jsonl` no se repite.
"""
import csv, json, sys
from pathlib import Path

import numpy as np

TS = Path.home() / "Projects/track-studio"
sys.path.insert(0, str(TS / "src"))
from track_studio.jobs.infrastructure.tracking.ultralytics_tracker import nms_posthoc  # noqa: E402

WEIGHTS = TS / "models/yolo26x-min5-best.pt"
CONF, IMGSZ, NMS_IOU, STEP = 0.25, 640, 0.6, 30
LLENO = 8

ESTADO = {
    **{v: "entrenado" for v in ("04", "04(1)", "04(2)", "05", "05(1)", "11", "12", "14", "16", "16(1)")},
    "10": "entrenado (s03)", "10(1)": "entrenado (v10b, inferido)", "18(1)": "entrenado (v18S08, inferido)",
    **{v: "nunca visto" for v in ("03", "03(1)", "08", "17", "intelC1", "intelC36", "18", "29")},
    "02": "reservado: golden de detección", "07": "reservado: evaluación de eventos",
    "13": "nunca visto (pruebas de track-studio)",
}


def scan(model, path):
    import cv2

    cap = cv2.VideoCapture(str(path))
    lum, heads, frames, n = [], [], {}, 0
    while cap.grab():
        n += 1
        if (n - 1) % STEP:
            continue
        ok, frame = cap.retrieve()
        if not ok:
            break
        lum.append(float(np.median(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))))
        boxes = model.predict(source=frame, conf=CONF, imgsz=IMGSZ, verbose=False)[0].boxes
        k = 0 if boxes is None or len(boxes) == 0 else len(nms_posthoc(boxes.data.cpu().numpy(), NMS_IOU))
        heads.append(k)
        if n == 13501 or k >= max(heads):
            frames["medio" if n == 13501 else "max"] = (n, frame.copy(), k)
    cap.release()
    h = np.array(heads)
    stats = {"frames": n, "lum_mediana": round(float(np.median(lum)), 1),
             "cabezas_p50": float(np.percentile(h, 50)), "cabezas_p90": float(np.percentile(h, 90)),
             "cabezas_max": int(h.max()), "pct_lleno": round(float((h >= LLENO).mean() * 100), 1)}
    return stats, frames


def main():
    import cv2
    from ultralytics import YOLO

    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    antigua = {}
    with open(src / "nombres.csv") as f:
        for r in csv.DictReader(f):
            if r["copia_local_antigua"]:
                antigua[r["nombre"]] = Path(r["copia_local_antigua"]).stem.removeprefix("videoTM_")
    log = out / "inventario.jsonl"
    hechos = {json.loads(l)["video"] for l in log.read_text().splitlines()} if log.exists() else set()
    model = YOLO(str(WEIGHTS))
    for path in sorted(src.glob("*/bus_*.mkv")):
        if path.name in hechos:
            continue
        stats, frames = scan(model, path)
        key = antigua.get(path.name)
        estado = ESTADO.get(key, "?") if key else "nunca visto (sin copia antigua)"
        row = {"video": path.name, "camara": path.parent.name, "antiguo": key, "estado": estado, **stats}
        tiles = []
        for name in ("medio", "max"):
            if name in frames:
                f, img, k = frames[name]
                img = cv2.resize(img, (320, 240))
                cv2.putText(img, f"{name} f{f} {k} cab", (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
                tiles.append(img)
        if tiles:
            cv2.imwrite(str(out / f"{path.stem}.jpg"), np.hstack(tiles))
        with open(log, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps(row, ensure_ascii=False), flush=True)
    rows = [json.loads(l) for l in log.read_text().splitlines()]
    (out / "inventario.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
