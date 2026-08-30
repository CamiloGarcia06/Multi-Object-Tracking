#!/usr/bin/env python3
"""Genera el paquete de VERIFICACION MANUAL de Precision y Recall.

Toma una muestra estratificada de 20 frames del golden test set (5 por camara,
cubriendo poca/media/mucha aglomeracion), dibuja el ground-truth en VERDE y las
predicciones del modelo campeon en ROJO -- cada caja numerada -- y deja una
planilla CSV vacia para contar TP / FP / FN a mano.

Uso (dentro del contenedor mot-dev):
  python3 /workspace/scripts/eval/make_manual_audit.py --out /out/verificacion_manual_PR
"""
import argparse, csv, glob, os, sys

import cv2
import numpy as np

REPO = "/workspace"
GOLD = f"{REPO}/data/golden"
MODEL = f"{REPO}/outputs/head_detector/yolo-bus-head-min5/weights/best.pt"
MODEL_NAME = "MIN5 (campeon)"
CONF, NMS = 0.25, 0.5
PER_CAM = 5

GREEN = (0, 200, 0)
RED = (0, 0, 235)


def load_gt(stem, w, h):
    """Lee el label YOLO y devuelve cajas xyxy en pixeles."""
    boxes = []
    with open(f"{GOLD}/labels/val/{stem}.txt") as fh:
        for ln in fh:
            p = ln.split()
            if len(p) != 5:
                continue
            cx, cy, bw, bh = (float(v) for v in p[1:])
            boxes.append([(cx - bw / 2) * w, (cy - bh / 2) * h,
                          (cx + bw / 2) * w, (cy + bh / 2) * h])
    return np.array(boxes, dtype=float).reshape(-1, 4)


def cam_of(stem):
    return stem.split("_f")[0].replace("golden_", "")


def pick_sample():
    """5 frames por camara repartidos por nivel de aglomeracion (deterministico)."""
    by_cam = {}
    for lf in sorted(glob.glob(f"{GOLD}/labels/val/*.txt")):
        stem = os.path.basename(lf)[:-4]
        n = sum(1 for ln in open(lf) if len(ln.split()) == 5)
        by_cam.setdefault(cam_of(stem), []).append((n, stem))
    sample = []
    for cam in sorted(by_cam):
        frames = sorted(by_cam[cam])  # ordenados por cantidad de cabezas
        idx = np.linspace(0, len(frames) - 1, PER_CAM).round().astype(int)
        for i in dict.fromkeys(idx):  # sin repetir si la camara tiene pocos frames
            sample.append((cam, frames[i][1], frames[i][0]))
    return sample


def draw(img, boxes, color, prefix, above):
    for i, (x1, y1, x2, y2) in enumerate(boxes, 1):
        p1, p2 = (int(x1), int(y1)), (int(x2), int(y2))
        cv2.rectangle(img, p1, p2, color, 2)
        tag = f"{prefix}{i}"
        ty = p1[1] - 5 if above else p2[1] + 16
        ty = max(14, min(img.shape[0] - 4, ty))
        (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(img, (p1[0], ty - th - 3), (p1[0] + tw + 4, ty + 3), color, -1)
        cv2.putText(img, tag, (p1[0] + 2, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 1, cv2.LINE_AA)


def banner(img, line1, n_gt, n_pred):
    strip = np.full((44, img.shape[1], 3), 30, np.uint8)
    cv2.putText(strip, line1, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(strip, f"G verde = ground-truth ({n_gt})", (8, 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, GREEN, 1, cv2.LINE_AA)
    cv2.putText(strip, f"P rojo = prediccion ({n_pred})", (250, 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, RED, 1, cv2.LINE_AA)
    return np.vstack([strip, img])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()

    from ultralytics import YOLO

    fotos = os.path.join(args.out, "fotos")
    os.makedirs(fotos, exist_ok=True)
    model = YOLO(args.model)

    sample = pick_sample()
    rows = []
    for k, (cam, stem, n_gt) in enumerate(sample, 1):
        img = cv2.imread(f"{GOLD}/images/val/{stem}.jpg")
        h, w = img.shape[:2]
        gt = load_gt(stem, w, h)
        pred = model.predict(img, conf=CONF, iou=NMS, verbose=False)[0].boxes
        pb = pred.xyxy.cpu().numpy().reshape(-1, 4)
        order = np.argsort(-pred.conf.cpu().numpy()) if len(pb) else []
        pb = pb[order] if len(pb) else pb

        draw(img, gt, GREEN, "G", above=True)
        draw(img, pb, RED, "P", above=False)
        img = banner(img, f"#{k:02d}  {stem}  |  modelo {MODEL_NAME}  conf={CONF} nms={NMS}",
                     len(gt), len(pb))
        name = f"{k:02d}_{cam}_{stem}.jpg"
        cv2.imwrite(os.path.join(fotos, name), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        rows.append([k, name, cam, len(gt), len(pb), "", "", "", "", ""])
        print(f"  [{k:02d}/20] {name}  GT={len(gt)} PRED={len(pb)}")

    planilla = os.path.join(args.out, "planilla_conteo_manual.csv")
    with open(planilla, "w", newline="") as fh:
        wcsv = csv.writer(fh)
        wcsv.writerow(["n", "archivo", "camara", "GT_cajas_verdes", "PRED_cajas_rojas",
                       "TP", "FP", "FN", "GT_omitido", "observaciones"])
        wcsv.writerows(rows)
        wcsv.writerow([])
        wcsv.writerow(["TOTAL", "", "", f"=SUM(D2:D{len(rows)+1})", f"=SUM(E2:E{len(rows)+1})",
                       f"=SUM(F2:F{len(rows)+1})", f"=SUM(G2:G{len(rows)+1})",
                       f"=SUM(H2:H{len(rows)+1})", f"=SUM(I2:I{len(rows)+1})", ""])
        wcsv.writerow(["PRECISION", "=F{r}/(F{r}+G{r})".format(r=len(rows) + 3)])
        wcsv.writerow(["RECALL", "=F{r}/(F{r}+H{r})".format(r=len(rows) + 3)])
        wcsv.writerow(["F1", "=2*B{p}*B{q}/(B{p}+B{q})".format(p=len(rows) + 4, q=len(rows) + 5)])

    print(f"\nOK -> {args.out}\n  fotos/ ({len(rows)})\n  {os.path.basename(planilla)}")


if __name__ == "__main__":
    sys.exit(main())
