#!/usr/bin/env python3
"""Ronda 7 — minado de frames de PUERTA para reentrenar el detector.

Ataca la causa B del diagnóstico de la puerta (docs/diagnostico-bytetrack-puerta.md):
cabezas que el detector pierde unos frames al cruzar la puerta. Corre el campeón
(yolo26x-min5, NMS post-hoc 0,6) sobre TODOS los frames de cada video y puntúa
cada frame por lo que pasa en la zona de la puerta. La cámara NO está montada igual en
todos los buses: la puerta (letrero rojo "PUERTAS CERRADAS" y hojas negras) cae a la
derecha en unos videos y a la izquierda en otros (`SIDE`, comprobado a ojo el 12-10).
Zona: x >= 430 si está a la derecha (como videoTM_07), x <= 210 si está a la izquierda.


  parpadeo   cabeza detectada (>= 0,25) en t-1 y t+1 a < 30 px y ausente en t:
             el detector la pierde estando ahí -> el frame más valioso
  duda       detecciones de la puerta con conf 0,10–0,40
  puerta     cabezas de la puerta (>= 0,25)

score = 3·parpadeo + 2·duda + 0,5·puerta. Por video se toman los PER_VIDEO frames de
mayor score separados >= GAP frames y a > 200 frames de cualquier frame del golden
de detección o de un dataset previo de la misma cámara (las dos verificaciones del
frame-miner).

Solo videos de ENTRENAMIENTO: 02, 03, 03(1) y 08 quedan reservados para prueba y
validación, 07 es de evaluación de eventos, y los nocturnos quedan fuera.

Salida (`OUT`): img/<cam>_fNNNNNN.jpg (frame contado desde 0, como bus_head_v*),
preanotacion.json (cajas del campeón >= 0,25 por imagen), seleccion.csv.

Necesita ultralytics: en la torre con el venv de track-studio.
  ~/Projects/track-studio/.venv/bin/python mine_door.py ~/videos ~/Multi-Object-Tracking OUT
"""
import csv, json, re, sys
from pathlib import Path

import numpy as np

TS = Path.home() / "Projects/track-studio"
sys.path.insert(0, str(TS / "src"))
from track_studio.jobs.infrastructure.tracking.ultralytics_tracker import nms_posthoc  # noqa: E402

WEIGHTS = TS / "models/yolo26x-min5-best.pt"
CONF_MIN, CONF, NMS_IOU, IMGSZ = 0.10, 0.25, 0.6, 640
DOOR_RIGHT, DOOR_LEFT, NEAR, PER_VIDEO, GAP, LEAK = 430, 210, 30.0, 20, 45, 200

# nombre corto (el de los stems de bus_head_v*) -> fichero de video
VIDEOS = {
    "v04": "videoTM_04.mkv", "v04_1": "videoTM_04(1).mkv", "v04_2": "videoTM_04(2).mkv",
    "v05": "videoTM_05.mkv", "v05_1": "videoTM_05(1).mkv", "s03": "videoTM_10.mkv",
    "v10b": "videoTM_10(1).mkv", "v11": "videoTM_11.mkv", "v12": "videoTM_12.mkv",
    "videoTM_14": "videoTM_14.mkv", "v16": "videoTM_16.mkv", "v16b": "videoTM_16(1).mkv",
    "v18S08": "videoTM_18(1).mkv",
}
SIDE = {c: "der" for c in ("v04_1", "v05_1", "s03", "videoTM_14", "v16", "v18S08")}
SIDE.update({c: "izq" for c in ("v04", "v04_2", "v05", "v10b", "v11", "v12", "v16b")})
GOLDEN_CAM = {"v05": "v05", "v16": "v16", "S08": "v18S08", "video02": None}


def used_frames(repo):
    """{cam: array de frames ya usados} (golden + todos los bus_head_v*)."""
    used = {c: [] for c in VIDEOS}
    for r in csv.DictReader(open(repo / "data/golden/manifest.csv")):
        cam = GOLDEN_CAM.get(r["camara"], r["camara"])
        if cam in used:
            used[cam].append(int(r["frame"]))
    for p in (repo / "data").glob("bus_head_v*/images/*/*"):
        m = re.match(r"(.+)_f(\d+)$", p.stem)
        if m and m.group(1) in used:
            used[m.group(1)].append(int(m.group(2)))
    return {c: np.array(sorted(set(v))) for c, v in used.items()}


def detect_all(model, path):
    import cv2

    cap, dets = cv2.VideoCapture(str(path)), []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        b = model.predict(source=frame, conf=CONF_MIN, imgsz=IMGSZ, verbose=False)[0].boxes
        d = np.zeros((0, 6)) if b is None or len(b) == 0 else b.data.cpu().numpy()
        dets.append(d[nms_posthoc(d, NMS_IOU)] if len(d) else d)
    cap.release()
    return dets


def scores(dets, side):
    def door(d, lo, hi):
        cx, cy = (d[:, 0] + d[:, 2]) / 2, (d[:, 1] + d[:, 3]) / 2
        at_door = cx >= DOOR_RIGHT if side == "der" else cx <= DOOR_LEFT
        m = at_door & (d[:, 4] >= lo) & (d[:, 4] < hi)
        return np.stack([cx[m], cy[m]], 1)

    hi = [door(d, CONF, 1.01) for d in dets]
    out = np.zeros(len(dets))
    for t in range(1, len(dets) - 1):
        blink = 0
        for p in hi[t - 1]:
            near = lambda q: len(q) and np.min(np.hypot(*(q - p).T)) < NEAR
            if near(hi[t + 1]) and not near(hi[t]):
                blink += 1
        unsure = len(door(dets[t], CONF_MIN, 0.40))
        out[t] = 3 * blink + 2 * unsure + 0.5 * len(hi[t])
    return out


def pick(score, used):
    chosen = []
    for t in np.argsort(-score):
        if score[t] <= 0 or len(chosen) >= PER_VIDEO:
            break
        if len(used) and np.min(np.abs(used - t)) <= LEAK:
            continue
        if all(abs(t - c) >= GAP for c in chosen):
            chosen.append(int(t))
    return sorted(chosen)


def main():
    import cv2
    from ultralytics import YOLO

    videos, repo, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    (out / "img").mkdir(parents=True, exist_ok=True)
    used, model = used_frames(repo), YOLO(str(WEIGHTS))
    pre, rows = {}, []
    for cam, fname in VIDEOS.items():
        cache = out / f"dets_{cam}.npy"
        if cache.exists():
            dets = list(np.load(cache, allow_pickle=True))
        else:
            dets = detect_all(model, videos / fname)
            np.save(cache, np.array(dets, dtype=object), allow_pickle=True)
        sc = scores(dets, SIDE[cam])
        chosen = pick(sc, used[cam])
        cap = cv2.VideoCapture(str(videos / fname))
        for t in chosen:
            cap.set(cv2.CAP_PROP_POS_FRAMES, t)
            ok, img = cap.read()
            if not ok:
                continue
            name = f"{cam}_f{t:06d}.jpg"
            cv2.imwrite(str(out / "img" / name), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            keep = dets[t][dets[t][:, 4] >= CONF]
            pre[name] = [[round(float(v), 1) for v in b[:4]] for b in keep]
            rows.append({"imagen": name, "video": fname, "frame": t, "score": round(float(sc[t]), 1),
                         "cajas_preanotadas": len(keep)})
        cap.release()
        print(json.dumps({"cam": cam, "puerta": SIDE[cam], "frames": len(dets), "elegidos": len(chosen),
                          "score_medio": round(float(np.mean([sc[t] for t in chosen])), 1) if chosen else 0}),
              flush=True)
    (out / "preanotacion.json").write_text(json.dumps(pre))
    with open(out / "seleccion.csv", "w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"HECHO {len(rows)} imágenes", flush=True)


if __name__ == "__main__":
    main()
