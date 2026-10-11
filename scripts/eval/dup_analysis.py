#!/usr/bin/env python3
"""A1 — Duplicados y fusiones con cabeza NMS-free.

yolo26 es end-to-end: no hay NMS de post-proceso, asi que el "cero duplicados"
dejo de ser algo CONFIGURABLE (iou=0.5) y paso a ser una propiedad APRENDIDA.
Este script la comprueba en vez de asumirla, y mide tambien el lado espejo
(fusiones), porque al perder la perilla se pierde el control del compromiso
duplicar-vs-fusionar.

Por que importa: una caja duplicada que entra al tracker se vuelve un track
duplicado, y un track duplicado que cruza la puerta es un pasajero fantasma
PERMANENTE en la ocupacion acumulada.

Definiciones (todas sobre el golden v2, 151 frames):
  duplicado_par   par de predicciones con IoU entre si > DUP_IOU
  cabeza_multi    cabeza REAL cubierta por >=2 predicciones con IoU > MATCH_IOU
                  (es el duplicado confirmado contra ground truth)
  fusion          cabeza real SIN prediccion propia cuya area cae >= MERGE_CONT
                  dentro de una prediccion ya asignada a OTRA cabeza

Uso (dentro del contenedor mot-dev):
  python3 /workspace/scripts/eval/dup_analysis.py
  python3 /workspace/scripts/eval/dup_analysis.py --conf 0.25 --dup-iou 0.6
"""
import argparse
import collections
import glob
import json
import os

import cv2
import numpy as np
from ultralytics import YOLO

GOLD = "/workspace/data/golden"
MODELS = {
    "yolo26x": "/workspace/outputs/head_detector/yolo26x-min5/weights/best.pt",
    "MIN5": "/workspace/outputs/head_detector/yolo-bus-head-min5/weights/best.pt",
}
NMS_IOU = 0.5          # el que usa el pipeline historico (inerte en yolo26)
MATCH_IOU = 0.5        # matching pred<->GT, igual que el resto del proyecto
DEFAULT_DUP_IOU = 0.6
MERGE_CONT = 0.70      # fraccion del area de la cabeza dentro de la caja ajena


def iou_mat(a, b):
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    aa = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    bb = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / np.maximum(aa[:, None] + bb[None, :] - inter, 1e-9)


def containment(gt, pred):
    """Fraccion del area de cada caja GT contenida en cada prediccion."""
    if len(gt) == 0 or len(pred) == 0:
        return np.zeros((len(gt), len(pred)))
    x1 = np.maximum(gt[:, None, 0], pred[None, :, 0])
    y1 = np.maximum(gt[:, None, 1], pred[None, :, 1])
    x2 = np.minimum(gt[:, None, 2], pred[None, :, 2])
    y2 = np.minimum(gt[:, None, 3], pred[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area = (gt[:, 2] - gt[:, 0]) * (gt[:, 3] - gt[:, 1])
    return inter / np.maximum(area[:, None], 1e-9)


def load_gt(path, W, H):
    boxes = []
    if not os.path.exists(path):
        return np.zeros((0, 4))
    for ln in open(path):
        p = ln.split()
        if len(p) != 5:
            continue
        _, cx, cy, w, h = map(float, p)
        boxes.append([(cx - w / 2) * W, (cy - h / 2) * H,
                      (cx + w / 2) * W, (cy + h / 2) * H])
    return np.array(boxes) if boxes else np.zeros((0, 4))


def greedy_match(pred, conf, gt, thr):
    """Asigna predicciones a GT por confianza descendente. Devuelve pred_idx->gt_idx."""
    assign = {}
    if len(pred) == 0 or len(gt) == 0:
        return assign
    M = iou_mat(pred, gt)
    used = set()
    for pi in np.argsort(-conf):
        best, best_iou = -1, thr
        for gi in range(len(gt)):
            if gi in used:
                continue
            if M[pi, gi] >= best_iou:
                best, best_iou = gi, M[pi, gi]
        if best >= 0:
            assign[int(pi)] = best
            used.add(best)
    return assign


def nms_posthoc(pred, conf, thr):
    """NMS greedy clasico sobre las predicciones ya emitidas.
    Es lo que habria que agregar aguas abajo si la cabeza end-to-end duplica."""
    if len(pred) == 0:
        return np.zeros((0, 4)), np.zeros(0), 0
    order = np.argsort(-conf)
    keep = []
    for i in order:
        ok = True
        for j in keep:
            if iou_mat(pred[i:i + 1], pred[j:j + 1])[0, 0] > thr:
                ok = False
                break
        if ok:
            keep.append(int(i))
    keep = np.array(sorted(keep))
    return pred[keep], conf[keep], len(pred) - len(keep)


def cam_of(name):
    return name.replace("golden_", "").rsplit("_f", 1)[0]


def analyze(model_path, images, conf, dup_iou):
    model = YOLO(model_path)
    per_cam = collections.defaultdict(lambda: collections.Counter())
    rows = []
    worst = []

    for img_path in images:
        stem = os.path.splitext(os.path.basename(img_path))[0]
        lbl = os.path.join(GOLD, "labels/val", stem + ".txt")
        img = cv2.imread(img_path)
        H, W = img.shape[:2]
        gt = load_gt(lbl, W, H)

        r = model.predict(source=img, conf=conf, iou=NMS_IOU, verbose=False)[0]
        if r.boxes is None or len(r.boxes) == 0:
            pred = np.zeros((0, 4)); pconf = np.zeros(0)
        else:
            pred = r.boxes.xyxy.cpu().numpy()
            pconf = r.boxes.conf.cpu().numpy()

        cam = cam_of(stem)
        c = per_cam[cam]
        c["frames"] += 1
        c["gt"] += len(gt)
        c["pred"] += len(pred)

        # --- (1) pares de predicciones solapadas entre si ---
        dup_pairs = 0
        if len(pred) > 1:
            P = iou_mat(pred, pred)
            np.fill_diagonal(P, 0)
            dup_pairs = int((np.triu(P) > dup_iou).sum())
        c["dup_pairs"] += dup_pairs
        if dup_pairs:
            c["frames_con_dup"] += 1

        # --- (2) cabezas reales cubiertas por >=2 predicciones ---
        multi = 0
        if len(gt) and len(pred):
            M = iou_mat(pred, gt)
            multi = int(((M > MATCH_IOU).sum(axis=0) >= 2).sum())
        c["cabezas_multi"] += multi

        # --- (3) matching greedy: TP / FP / FN ---
        assign = greedy_match(pred, pconf, gt, MATCH_IOU)
        tp = len(assign)
        fp = len(pred) - tp
        fn = len(gt) - tp
        c["tp"] += tp; c["fp"] += fp; c["fn"] += fn
        c["abs_err"] += abs(len(pred) - len(gt))
        c["bias"] += len(pred) - len(gt)

        # --- (4) fusiones: FN contenido en una caja asignada a OTRA cabeza ---
        fusiones = 0
        if fn and len(pred):
            matched_gt = set(assign.values())
            unmatched = [gi for gi in range(len(gt)) if gi not in matched_gt]
            if unmatched:
                C = containment(gt[unmatched], pred)
                for k, gi in enumerate(unmatched):
                    for pi in range(len(pred)):
                        if C[k, pi] >= MERGE_CONT and assign.get(pi, -1) not in (-1, gi):
                            fusiones += 1
                            break
        c["fusiones"] += fusiones

        # --- (5) contrafactico: filtrar duplicados en post-proceso ---
        fpred, fconf, borradas = nms_posthoc(pred, pconf, dup_iou)
        fassign = greedy_match(fpred, fconf, gt, MATCH_IOU)
        ftp = len(fassign)
        c["nms_borradas"] += borradas
        c["nms_tp"] += ftp
        c["nms_fp"] += len(fpred) - ftp
        c["nms_fn"] += len(gt) - ftp
        c["nms_abs_err"] += abs(len(fpred) - len(gt))
        c["nms_bias"] += len(fpred) - len(gt)

        # aglomeracion: duplicados segun cuantas cabezas hay en el frame
        bucket = "0-4" if len(gt) <= 4 else "5-9" if len(gt) <= 9 else "10+"
        c[f"gt_{bucket}_frames"] += 1
        c[f"gt_{bucket}_multi"] += multi
        c[f"gt_{bucket}_gt"] += len(gt)

        rows.append({"frame": stem, "cam": cam, "gt": len(gt), "pred": len(pred),
                     "dup_pairs": dup_pairs, "cabezas_multi": multi,
                     "fusiones": fusiones, "nms_borradas": borradas})
        if dup_pairs or multi:
            worst.append((dup_pairs + multi, stem, len(gt), dup_pairs, multi))

    worst.sort(reverse=True)
    return per_cam, rows, worst[:10]


def totals(per_cam):
    t = collections.Counter()
    for c in per_cam.values():
        t.update(c)
    return t


def show(name, per_cam, worst):
    t = totals(per_cam)
    n = t["frames"]
    print(f"\n{'='*72}\n{name}\n{'='*72}")
    print(f"  frames {n} | cabezas reales {t['gt']} | predicciones {t['pred']}")
    print(f"  P={t['tp']/max(1,t['tp']+t['fp']):.3f}  R={t['tp']/max(1,t['tp']+t['fn']):.3f}"
          f"  MAE={t['abs_err']/max(1,n):.2f}  sesgo={t['bias']/max(1,n):+.2f}")
    print(f"\n  --- DUPLICADOS ---")
    print(f"  pares de predicciones solapadas : {t['dup_pairs']}"
          f"  (en {t['frames_con_dup']} frames de {n})")
    print(f"  cabezas reales con >=2 cajas    : {t['cabezas_multi']}"
          f"  ({100*t['cabezas_multi']/max(1,t['gt']):.2f}% de las cabezas)")
    print(f"\n  --- FUSIONES (lado espejo) ---")
    print(f"  cabezas absorbidas por una caja ajena : {t['fusiones']}"
          f"  ({100*t['fusiones']/max(1,t['gt']):.2f}% de las cabezas)")
    print(f"\n  --- por camara ---")
    print(f"  {'camara':<12} {'frames':>6} {'GT':>5} {'pred':>5} {'pares':>6} {'multi':>6} {'fusion':>7}")
    for cam in sorted(per_cam):
        c = per_cam[cam]
        print(f"  {cam:<12} {c['frames']:>6} {c['gt']:>5} {c['pred']:>5} "
              f"{c['dup_pairs']:>6} {c['cabezas_multi']:>6} {c['fusiones']:>7}")
    print(f"\n  --- CONTRAFACTICO: con NMS post-hoc aplicado ---")
    print(f"  cajas borradas: {t['nms_borradas']}")
    print(f"  antes : P={t['tp']/max(1,t['tp']+t['fp']):.3f} R={t['tp']/max(1,t['tp']+t['fn']):.3f}"
          f" MAE={t['abs_err']/max(1,n):.2f} sesgo={t['bias']/max(1,n):+.2f}")
    print(f"  despues: P={t['nms_tp']/max(1,t['nms_tp']+t['nms_fp']):.3f}"
          f" R={t['nms_tp']/max(1,t['nms_tp']+t['nms_fn']):.3f}"
          f" MAE={t['nms_abs_err']/max(1,n):.2f} sesgo={t['nms_bias']/max(1,n):+.2f}")

    print(f"\n  --- duplicados por nivel de aglomeracion ---")
    print(f"  {'cabezas/frame':<14} {'frames':>6} {'GT':>5} {'cabezas_multi':>14} {'% de GT':>8}")
    for b in ("0-4", "5-9", "10+"):
        f_, g_, m_ = t[f"gt_{b}_frames"], t[f"gt_{b}_gt"], t[f"gt_{b}_multi"]
        if f_:
            print(f"  {b:<14} {f_:>6} {g_:>5} {m_:>14} {100*m_/max(1,g_):>7.2f}%")

    if worst:
        print(f"\n  --- peores frames ---")
        for _, stem, ngt, dp, mu in worst:
            print(f"    {stem:<28} GT={ngt:<3} pares={dp:<3} cabezas_multi={mu}")


def check_iou_inerte(model_path, images, conf):
    """Re-verifica que el parametro iou no tenga efecto en la cabeza end-to-end."""
    model = YOLO(model_path)
    sample = images[:20]
    out = {}
    for v in (0.3, 0.5, 0.7, 0.9):
        tot = 0
        for p in sample:
            r = model.predict(source=p, conf=conf, iou=v, verbose=False)[0]
            tot += 0 if r.boxes is None else len(r.boxes)
        out[v] = tot
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--dup-iou", type=float, default=DEFAULT_DUP_IOU)
    ap.add_argument("--out", default="/workspace/outputs/dup_analysis.json")
    a = ap.parse_args()

    images = sorted(glob.glob(os.path.join(GOLD, "images/val/*.jpg")))
    print(f"Golden: {len(images)} frames | conf={a.conf} | dup_iou={a.dup_iou} "
          f"| match_iou={MATCH_IOU} | contencion fusion={MERGE_CONT}")

    dump = {"conf": a.conf, "dup_iou": a.dup_iou, "modelos": {}}
    for name, path in MODELS.items():
        if not os.path.exists(path):
            print(f"\n!! FALTA {path} — salteo {name}")
            continue
        per_cam, rows, worst = analyze(path, images, a.conf, a.dup_iou)
        show(name, per_cam, worst)
        dump["modelos"][name] = {"totales": dict(totals(per_cam)),
                                 "por_camara": {k: dict(v) for k, v in per_cam.items()},
                                 "frames": rows}

    print(f"\n{'='*72}\nVERIFICACION: el parametro iou en la cabeza NMS-free\n{'='*72}")
    for name, path in MODELS.items():
        if os.path.exists(path):
            res = check_iou_inerte(path, images, a.conf)
            vals = set(res.values())
            estado = "INERTE (mismas cajas)" if len(vals) == 1 else "TIENE EFECTO"
            print(f"  {name:<10} " + "  ".join(f"iou={k}:{v}" for k, v in res.items())
                  + f"   -> {estado}")
            dump.setdefault("iou_sweep", {})[name] = res

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(dump, f, indent=2)
    print(f"\nDetalle por frame -> {a.out}")


if __name__ == "__main__":
    main()
