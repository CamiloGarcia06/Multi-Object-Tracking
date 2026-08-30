#!/usr/bin/env python3
"""Leaderboard completo del detector de cabezas contra el golden vigente.

Evalua TODOS los modelos con criterio identico y comparable:
  - umbral FIJO (conf=0.25, NMS iou=0.5) para todos
  - matcher greedy por confianza a IoU 0.5 (mismo para todos)
  - P / R / F1 / MAE de conteo / sesgo, global, por camara y por aglomeracion
  - parametros y velocidad de inferencia
  - bootstrap pareado contra el lider + criterios de salida de Fase 1

OJO: NO usa las P/R de `yolo val`, que se reportan en el maximo F1 DE CADA MODELO
(umbrales distintos) y por lo tanto NO son comparables entre modelos.

Uso (dentro de mot-dev):
  python3 /workspace/scripts/eval/leaderboard.py
  python3 /workspace/scripts/eval/leaderboard.py --conf 0.20
"""
import argparse, collections, glob, json, os, time

import cv2
import numpy as np
from ultralytics import YOLO

G = "/workspace/data/golden"
O = "/workspace/outputs/head_detector"
MODELS = [
    ("BASE",          "/workspace/models/yolov5mu-head-base.pt",     "CrowdHuman", "yolov5mu"),
    ("R2",            f"{O}/yolo-bus-head-r2/weights/best.pt",       "CrowdHuman", "yolov5mu"),
    ("R3",            f"{O}/yolo-bus-head-r3/weights/best.pt",       "CrowdHuman", "yolov5mu"),
    ("R4",            f"{O}/yolo-bus-head-r4/weights/best.pt",       "CrowdHuman", "yolov5mu"),
    ("R5",            f"{O}/yolo-bus-head-r5/weights/best.pt",       "CrowdHuman", "yolov5mu"),
    ("MIN5",          f"{O}/yolo-bus-head-min5/weights/best.pt",     "CrowdHuman", "yolov5mu"),
    ("v5mu-coco",     f"{O}/v5mu-coco-min5/weights/best.pt",         "COCO",       "yolov5mu"),
    ("yolo26m",       f"{O}/yolo26m-min5/weights/best.pt",           "COCO",       "yolo26m"),
    ("yolo26x",       f"{O}/yolo26x-min5/weights/best.pt",           "COCO",       "yolo26x"),
]


def iou_mat(a, b):
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    x1 = np.maximum(a[:, None, 0], b[None, :, 0]); y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2]); y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    aa = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1]); bb = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / (aa[:, None] + bb[None, :] - inter + 1e-9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--nms", type=float, default=0.5)
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--boot", type=int, default=20000)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    np.random.seed(0)

    imgs = sorted(glob.glob(f"{G}/images/val/*.jpg"))
    cache = {}
    for p in imgs:
        st = os.path.basename(p)[:-4]
        im = cv2.imread(p); H, W = im.shape[:2]
        g = []
        for ln in open(f"{G}/labels/val/{st}.txt"):
            v = ln.split()
            if len(v) != 5:
                continue
            cx, cy, w, h = (float(x) for x in v[1:])
            g.append([(cx - w / 2) * W, (cy - h / 2) * H, (cx + w / 2) * W, (cy + h / 2) * H])
        cache[p] = (im, np.array(g).reshape(-1, 4), st.split("_f")[0].replace("golden_", ""))
    ngt = sum(len(v[1]) for v in cache.values())
    print(f"Golden: {len(imgs)} frames, {ngt} cabezas | conf={a.conf} nms={a.nms} matching IoU={a.iou}\n")

    res = {}
    for name, mp, base, arch in MODELS:
        if not os.path.isfile(mp):
            print(f"  (falta {name}: {mp})"); continue
        m = YOLO(mp)
        nparam = sum(x.numel() for x in m.model.parameters()) / 1e6
        per_cam = collections.defaultdict(lambda: collections.Counter())
        rows = []; t0 = time.time()
        for p in imgs:
            im, g, cam = cache[p]
            r = m.predict(im, conf=a.conf, iou=a.nms, verbose=False)[0]
            pr = r.boxes.xyxy.cpu().numpy().reshape(-1, 4)
            cf = r.boxes.conf.cpu().numpy()
            M = iou_mat(pr, g); mg, mpd = set(), set()
            if M.size:
                for pi in np.argsort(-cf):
                    cand = [gi for gi in range(len(g)) if gi not in mg and M[pi, gi] >= a.iou]
                    if cand:
                        gi = max(cand, key=lambda x: M[pi, x]); mg.add(gi); mpd.add(int(pi))
            tp, fn, fp = len(mg), len(g) - len(mg), len(pr) - len(mpd)
            per_cam[cam].update({"TP": tp, "FN": fn, "FP": fp})
            rows.append((len(g), len(pr) - len(g), tp, fn, fp))
        ms = (time.time() - t0) / len(imgs) * 1000
        rows = np.array(rows, float)
        tp, fn, fp = rows[:, 2].sum(), rows[:, 3].sum(), rows[:, 4].sum()
        P = tp / max(tp + fp, 1); R = tp / max(tp + fn, 1)
        res[name] = {
            "base": base, "arch": arch, "params": nparam, "ms": ms,
            "P": P, "R": R, "F1": 2 * P * R / max(P + R, 1e-9),
            "MAE": np.abs(rows[:, 1]).mean(), "bias": rows[:, 1].mean(),
            "err": rows[:, 1], "gt": rows[:, 0],
            "cam": {c: (k["TP"], k["FN"], k["FP"]) for c, k in per_cam.items()},
            "cam_mae": {c: np.abs(rows[[i for i, p in enumerate(imgs) if cache[p][2] == c], 1]).mean()
                        for c in per_cam},
        }
        print(f"  evaluado {name:11s} ({nparam:5.1f}M, {ms:5.1f} ms/img)")

    order = sorted(res, key=lambda k: res[k]["MAE"])
    print(f"\n{'='*104}\n{'#':<3}{'modelo':<12}{'base':<11}{'params':>8}{'ms':>7}"
          f"{'P':>8}{'R':>8}{'F1':>8}{'MAE':>8}{'sesgo':>8}{'video02':>9}{'S08':>7}{'v05':>7}{'v16':>7}")
    print("=" * 104)
    for i, k in enumerate(order, 1):
        d = res[k]
        cm = d["cam_mae"]
        print(f"{i:<3}{k:<12}{d['base']:<11}{d['params']:7.1f}M{d['ms']:7.1f}"
              f"{d['P']:8.3f}{d['R']:8.3f}{d['F1']:8.3f}{d['MAE']:8.2f}{d['bias']:+8.2f}"
              f"{cm.get('video02',float('nan')):9.2f}{cm.get('S08',float('nan')):7.2f}"
              f"{cm.get('v05',float('nan')):7.2f}{cm.get('v16',float('nan')):7.2f}")

    lead = order[0]
    print(f"\n--- MAE por aglomeracion ---")
    bins = [(0, 5, "0-4"), (5, 10, "5-9"), (10, 15, "10-14"), (15, 99, "15+")]
    print(f"{'modelo':<12}" + "".join(f"{l:>9}" for _, _, l in bins) + f"{'n frames':>10}")
    for _, _, l in []: pass
    g0 = res[lead]["gt"]
    print(f"{'(frames)':<12}" + "".join(f"{int(((g0>=lo)&(g0<hi)).sum()):>9}" for lo, hi, _ in bins))
    for k in order:
        d = res[k]; g = d["gt"]; e = np.abs(d["err"])
        print(f"{k:<12}" + "".join(f"{e[(g>=lo)&(g<hi)].mean():9.2f}" if ((g>=lo)&(g<hi)).sum() else f"{'-':>9}"
                                   for lo, hi, _ in bins))

    print(f"\n--- significancia del MAE contra el lider ({lead}, MAE {res[lead]['MAE']:.2f}) ---")
    print(f"{'rival':<12}{'dif':>8}{'IC95':>22}{'P(lider mejor)':>16}{'gana/emp/pierde':>18}")
    base_e = np.abs(res[lead]["err"])
    for k in order[1:]:
        d = np.abs(res[k]["err"]) - base_e   # >0 => lider mejor
        B = np.array([d[np.random.randint(0, len(d), len(d))].mean() for _ in range(a.boot)])
        lo, hi = np.percentile(B, [2.5, 97.5])
        print(f"{k:<12}{d.mean():+8.3f}{f'[{lo:+.3f}, {hi:+.3f}]':>22}{(B>0).mean():>16.3f}"
              f"{f'{int((d>0).sum())}/{int((d==0).sum())}/{int((d<0).sum())}':>18}")

    print(f"\n--- criterios de salida de Fase 1 (MAE<=1.5 | no vista<=2.0 | recall>=0.85) ---")
    for k in order:
        d = res[k]; v2 = d["cam_mae"].get("video02", 9)
        ok = lambda b: "OK " if b else "NO "
        print(f"{k:<12} MAE {d['MAE']:.2f} {ok(d['MAE']<=1.5)}| no vista {v2:.2f} {ok(v2<=2.0)}"
              f"| recall {d['R']:.3f} {ok(d['R']>=0.85)}")

    if a.json:
        out = {k: {kk: (vv.tolist() if isinstance(vv, np.ndarray) else vv)
                   for kk, vv in v.items()} for k, v in res.items()}
        open(a.json, "w").write(json.dumps(out, indent=1, default=float))
        print(f"\njson -> {a.json}")


if __name__ == "__main__":
    main()
