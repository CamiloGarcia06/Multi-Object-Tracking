#!/usr/bin/env python3
"""Auditoría de etiquetas de un dataset YOLO de cabezas, por video de origen.

Por imagen: etiquetas vs detecciones del campeón (conf 0,10, NMS 0,6), emparejadas por IoU >= 0,3.
  det_sin_etiqueta  detección con conf >= 0,5 sin etiqueta  -> posible cabeza SIN anotar
  etiqueta_sin_det  etiqueta que el detector no cubre       -> posible caja de más o mal puesta
  iou_med           IoU mediano de las parejas              -> cajas flojas / desplazadas
El campeón se entrenó con estas imágenes, así que tiende a darles la razón: las discrepancias
son una cota INFERIOR de los errores y lo útil es comparar entre videos.

Escribe OUT/auditoria.json (por video), OUT/imagenes.jsonl (por imagen) y OUT/peores_<video>.jpg:
las 12 imágenes con más discrepancias (verde = etiqueta emparejada, amarillo = etiqueta sin
detección, rojo = detección >= 0,5 sin etiqueta, con su confianza).

  ~/Projects/track-studio/.venv/bin/python scripts/dataset/auditar_etiquetas.py data/bus_head_v5_min5 OUT
"""
import json, sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
from recall_por_camara import IMGSZ, NMS_IOU, WEIGHTS, iou, match, nms_posthoc  # noqa: E402

CONF, CONF_ALTA, IOU_MIN = 0.10, 0.5, 0.3


def load_labels(path, w, h):
    if not path.exists():
        return np.zeros((0, 4))
    rows = [list(map(float, l.split()[1:5])) for l in path.read_text().splitlines() if l.strip()]
    a = np.array(rows).reshape(-1, 4)
    return np.c_[(a[:, 0] - a[:, 2] / 2) * w, (a[:, 1] - a[:, 3] / 2) * h,
                 (a[:, 0] + a[:, 2] / 2) * w, (a[:, 1] + a[:, 3] / 2) * h]


def main():
    import cv2
    from ultralytics import YOLO

    ds, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(WEIGHTS))
    per_img = []
    for split in ("train", "val"):
        for img_path in sorted((ds / "images" / split).glob("*.jpg")):
            img = cv2.imread(str(img_path))
            h, w = img.shape[:2]
            lab = load_labels(ds / "labels" / split / f"{img_path.stem}.txt", w, h)
            boxes = model.predict(source=img, conf=CONF, imgsz=IMGSZ, verbose=False)[0].boxes
            data = np.zeros((0, 6)) if boxes is None or len(boxes) == 0 else boxes.data.cpu().numpy()
            det = data[nms_posthoc(data, NMS_IOU)] if len(data) else data
            lm, dm = match(lab, det[:, :4], IOU_MIN)
            ious = []
            if lm.any():
                m = iou(lab[lm], det[dm, :4])
                ious = m.max(axis=1).tolist()
            miss = det[(~dm) & (det[:, 4] >= CONF_ALTA)]
            per_img.append({"img": img_path.name, "split": split, "video": img_path.stem.rsplit("_f", 1)[0],
                            "etiquetas": len(lab), "dets": int((det[:, 4] >= 0.25).sum()),
                            "det_sin_etiqueta": len(miss), "etiqueta_sin_det": int((~lm).sum()),
                            "iou_med": round(float(np.median(ious)), 3) if ious else None,
                            "_lab": lab.tolist(), "_lm": lm.tolist(), "_miss": miss[:, :5].tolist()})
    by = defaultdict(list)
    for r in per_img:
        by[r["video"]].append(r)
    resumen = []
    for v, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        n_lab = sum(r["etiquetas"] for r in rs)
        ious = [r["iou_med"] for r in rs if r["iou_med"] is not None]
        resumen.append({"video": v, "imgs": len(rs), "etiquetas": n_lab,
                        "det_sin_etiqueta_por_100_etiq": round(100 * sum(r["det_sin_etiqueta"] for r in rs) / max(n_lab, 1), 1),
                        "etiqueta_sin_det_pct": round(100 * sum(r["etiqueta_sin_det"] for r in rs) / max(n_lab, 1), 1),
                        "imgs_con_cabeza_sin_anotar_pct": round(100 * sum(r["det_sin_etiqueta"] > 0 for r in rs) / len(rs), 1),
                        "iou_mediano": round(float(np.median(ious)), 3) if ious else None})
        print(json.dumps(resumen[-1]), flush=True)
        peores = sorted(rs, key=lambda r: -(r["det_sin_etiqueta"] + r["etiqueta_sin_det"]))[:12]
        tiles = []
        for r in peores:
            img = cv2.imread(str(ds / "images" / r["split"] / r["img"]))
            for b, ok in zip(r["_lab"], r["_lm"]):
                cv2.rectangle(img, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), (0, 200, 0) if ok else (0, 255, 255), 2)
            for b in r["_miss"]:
                cv2.rectangle(img, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), (0, 0, 255), 2)
                cv2.putText(img, f"{b[4]:.2f}", (int(b[0]), int(b[1]) - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            img = cv2.resize(img, (400, 300))
            cv2.putText(img, r["img"], (5, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            tiles.append(img)
        while len(tiles) % 4:
            tiles.append(np.zeros_like(tiles[0]))
        sheet = np.vstack([np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)])
        cv2.imwrite(str(out / f"peores_{v}.jpg"), sheet)
    (out / "auditoria.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1))
    with open(out / "imagenes.jsonl", "w") as f:
        for r in per_img:
            f.write(json.dumps({k: v for k, v in r.items() if not k.startswith("_")}) + "\n")


if __name__ == "__main__":
    main()
