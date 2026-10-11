#!/usr/bin/env python3
"""A2 — Throughput del pipeline de deteccion+tracking.

El sistema es BATCH por decision de producto, asi que el FPS no define la
arquitectura: define el costo. Este script no emite veredicto, produce numeros.

Mide por separado, porque el techo real lo pone el mas lento:
  1. decode del .mkv (leer y decodificar frames)
  2. inferencia del modelo (FP32 / FP16, batch 1 / 8 / 16)
  3. NMS post-hoc a 0.6 (el filtro de duplicados de A1)
  4. tracking (model.track vs model.predict sobre los mismos frames)

MEDICION AUTORITATIVA = la seccion END-TO-END contra reloj de pared. Los
micro-benchmarks de predict() cuadro a cuadro ENGANAN: ultralytics reconstruye el
predictor en cada llamada, asi que miden overhead de setup y no inferencia (dan
~59 FPS cuando el pipeline real hace 83). Se conservan solo como desglose.

Uso (dentro del contenedor mot-dev, con /videos montado):
  python3 /workspace/scripts/eval/bench_throughput.py
  python3 /workspace/scripts/eval/bench_throughput.py --video /videos/videoTM_17.mkv -n 600
"""
import argparse
import time

import cv2
import numpy as np
import torch
from ultralytics import YOLO

MODELS = {
    "yolo26x (59.0M)": "/workspace/outputs/head_detector/yolo26x-min5/weights/best.pt",
    "MIN5 (25.1M)": "/workspace/outputs/head_detector/yolo-bus-head-min5/weights/best.pt",
}
CONF = 0.25
NMS_IOU = 0.5
DUP_IOU = 0.6


def sync():
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def read_frames(path, n):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = []
    while len(frames) < n:
        ok, img = cap.read()
        if not ok:
            break
        frames.append(img)
    cap.release()
    return frames, fps


def bench_decode(path, n):
    """Decode puro: leer y decodificar, sin tocar la GPU."""
    cap = cv2.VideoCapture(path)
    # descartar el primer read (abre el archivo, cachea)
    cap.read()
    t0 = time.perf_counter()
    c = 0
    while c < n:
        ok, _ = cap.read()
        if not ok:
            break
        c += 1
    dt = time.perf_counter() - t0
    cap.release()
    return c / dt


def bench_infer(model, frames, batch, half, warmup=10):
    for i in range(0, warmup, batch):
        model.predict(source=frames[i:i + batch], conf=CONF, iou=NMS_IOU,
                      half=half, verbose=False)
    sync()
    t0 = time.perf_counter()
    n = 0
    for i in range(0, len(frames), batch):
        chunk = frames[i:i + batch]
        model.predict(source=chunk, conf=CONF, iou=NMS_IOU, half=half, verbose=False)
        n += len(chunk)
    sync()
    return n / (time.perf_counter() - t0)


def iou_pair(a, b):
    x1 = max(a[0], b[0]); y1 = max(a[1], b[1])
    x2 = min(a[2], b[2]); y2 = min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / ua if ua > 0 else 0


def nms_posthoc(pred, conf, thr=DUP_IOU):
    if len(pred) == 0:
        return pred
    keep = []
    for i in np.argsort(-conf):
        if all(iou_pair(pred[i], pred[j]) <= thr for j in keep):
            keep.append(int(i))
    return pred[sorted(keep)]


def bench_nms(model, frames, half):
    dets = []
    for i in range(0, len(frames), 16):
        for r in model.predict(source=frames[i:i+16], conf=CONF, iou=NMS_IOU,
                               half=half, verbose=False):
            if r.boxes is None or len(r.boxes) == 0:
                dets.append((np.zeros((0, 4)), np.zeros(0)))
            else:
                dets.append((r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy()))
    t0 = time.perf_counter()
    for p, c in dets:
        nms_posthoc(p, c)
    return len(dets) / (time.perf_counter() - t0)


def bench_track(model, frames, half, tracker="bytetrack.yaml"):
    # warmup CON track(): la primera llamada importa lap y construye el tracker.
    for f in frames[:15]:
        model.track(source=f, conf=CONF, iou=NMS_IOU, half=half,
                    tracker=tracker, persist=True, verbose=False)
    sync()
    t0 = time.perf_counter()
    for f in frames:
        model.track(source=f, conf=CONF, iou=NMS_IOU, half=half,
                    tracker=tracker, persist=True, verbose=False)
    sync()
    return len(frames) / (time.perf_counter() - t0)


def fmt_video(fps_pipeline, video_min=15, video_fps=30):
    total = video_min * 60 * video_fps
    seg = total / max(fps_pipeline, 1e-9)
    return f"{seg/60:.1f} min", f"{seg/(video_min*60):.2f}x"


def bench_e2e(weights, frames_n, video, half=True, do_track=True, do_dedup=True):
    """Reloj de pared sobre el trabajo real: decode -> modelo -> [tracker] -> [dedup]."""
    m = YOLO(weights)
    cap = cv2.VideoCapture(video)
    for _ in range(20):
        ok, f = cap.read()
        if ok:
            (m.track(source=f, conf=CONF, iou=NMS_IOU, half=half,
                     tracker="bytetrack.yaml", persist=True, verbose=False) if do_track
             else m.predict(source=f, conf=CONF, iou=NMS_IOU, half=half, verbose=False))
    cap.release()
    sync()

    cap = cv2.VideoCapture(video)
    ids, ndet, nf, ndrop = set(), 0, 0, 0
    t0 = time.perf_counter()
    while nf < frames_n:
        ok, f = cap.read()
        if not ok:
            break
        r = (m.track(source=f, conf=CONF, iou=NMS_IOU, half=half,
                     tracker="bytetrack.yaml", persist=True, verbose=False)[0] if do_track
             else m.predict(source=f, conf=CONF, iou=NMS_IOU, half=half, verbose=False)[0])
        if r.boxes is not None and len(r.boxes):
            p_ = r.boxes.xyxy.cpu().numpy(); c_ = r.boxes.conf.cpu().numpy()
            if do_dedup:
                n0 = len(p_); p_ = nms_posthoc(p_, c_); ndrop += n0 - len(p_)
            ndet += len(p_)
            if do_track and r.boxes.id is not None:
                ids.update(r.boxes.id.cpu().numpy().astype(int).tolist())
        nf += 1
    sync()
    dt = time.perf_counter() - t0
    cap.release()
    return {"fps": nf / dt, "seg": dt, "frames": nf, "cajas": ndet,
            "ids": len(ids), "borradas": ndrop}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="/videos/videoTM_17.mkv")
    ap.add_argument("-n", type=int, default=600)
    a = ap.parse_args()

    dev = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    print(f"GPU: {dev} | torch {torch.__version__}")
    print(f"Video: {a.video} | {a.n} frames\n")

    print("=" * 74)
    print("1. DECODE (CPU, sin GPU)")
    print("=" * 74)
    d_fps = bench_decode(a.video, a.n)
    print(f"  decode puro: {d_fps:7.1f} FPS   <- techo del pipeline si el modelo es mas rapido")

    frames, native_fps = read_frames(a.video, a.n)
    h, w = frames[0].shape[:2]
    print(f"  video nativo: {w}x{h} @ {native_fps:.0f} fps, {len(frames)} frames leidos\n")

    print("=" * 74)
    print("2. INFERENCIA (FPS de frames procesados)")
    print("=" * 74)
    print(f"  {'modelo':<18} {'precision':<10} {'batch':>6} {'FPS':>9}")
    results = {}
    for name, path in MODELS.items():
        model = YOLO(path)
        for half in (False, True):
            batches = (1, 8, 16) if "yolo26x" in name else (1,)
            for b in batches:
                try:
                    f = bench_infer(model, frames, b, half)
                except Exception as e:
                    print(f"  {name:<18} {'FP16' if half else 'FP32':<10} {b:>6}   ERROR {e}")
                    continue
                results[(name, half, b)] = f
                print(f"  {name:<18} {'FP16' if half else 'FP32':<10} {b:>6} {f:>9.1f}")

    print()
    print("=" * 74)
    print("3. NMS POST-HOC (el filtro de duplicados de A1) y 4. TRACKING")
    print("=" * 74)
    mx = YOLO(MODELS["yolo26x (59.0M)"])
    n_fps = bench_nms(mx, frames[:200], half=True)
    print(f"  NMS post-hoc a {DUP_IOU} (CPU)      : {n_fps:8.1f} FPS")
    t_fps = bench_track(mx, frames[:200], half=True)
    print(f"  model.track() ByteTrack FP16 b=1 : {t_fps:8.1f} FPS")
    base = results.get(("yolo26x (59.0M)", True, 1))
    if base:
        print(f"  (predict FP16 b=1 era {base:.1f} FPS -> el tracker cuesta "
              f"{100*(1-t_fps/base):+.0f}%)")

    print()
    print("=" * 74)
    print("4b. DONDE SE VA EL TIEMPO (ms por frame, segun ultralytics)")
    print("=" * 74)
    print(f"  {'modelo':<18} {'prec':<6} {'batch':>6} {'pre':>7} {'infer':>8} {'post':>7} {'total':>8}")
    for name, path in MODELS.items():
        m2 = YOLO(path)
        for half in (False, True):
            for b in ((1, 16) if "yolo26x" in name else (1,)):
                m2.predict(source=frames[:b], conf=CONF, half=half, verbose=False)
                sync()
                acc = {"preprocess": 0.0, "inference": 0.0, "postprocess": 0.0}
                nb = 0
                for i in range(0, 160, b):
                    rs = m2.predict(source=frames[i:i+b], conf=CONF, iou=NMS_IOU,
                                    half=half, verbose=False)
                    for k in acc:
                        acc[k] += rs[0].speed[k]
                    nb += 1
                pre, inf, post = (acc[k]/nb for k in ("preprocess", "inference", "postprocess"))
                print(f"  {name:<18} {'FP16' if half else 'FP32':<6} {b:>6} "
                      f"{pre:>7.2f} {inf:>8.2f} {post:>7.2f} {pre+inf+post:>8.2f}")
    print("  (los ms de ultralytics son POR IMAGEN del lote, no por lote)")

    print()
    print("=" * 74)
    print("5. END-TO-END contra reloj de pared  <- LA MEDICION QUE VALE")
    print("=" * 74)
    n_e2e = min(900, a.n)
    escen = [
        ("yolo26x  detect FP16 (sin tracker, sin dedup)", MODELS["yolo26x (59.0M)"], False, False),
        ("yolo26x  detect FP16 + dedup", MODELS["yolo26x (59.0M)"], False, True),
        ("yolo26x  TRACK ByteTrack + dedup  <- pasada causal", MODELS["yolo26x (59.0M)"], True, True),
        ("MIN5     TRACK ByteTrack + dedup  (referencia)", MODELS["MIN5 (25.1M)"], True, True),
    ]
    print(f"  {'escenario':<52} {'FPS':>7} {'video 15min':>12} {'vs real':>8}")
    e2e = {}
    for label, wpath, tk, dd in escen:
        r = bench_e2e(wpath, n_e2e, a.video, half=True, do_track=tk, do_dedup=dd)
        e2e[label] = r
        t, x = fmt_video(r["fps"])
        print(f"  {label:<52} {r['fps']:>7.1f} {t:>12} {x:>8}")
    print(f"\n  control de salida ({n_e2e} frames):")
    for label, r in e2e.items():
        print(f"    {label[:44]:<46} cajas={r['cajas']:<6} IDs={r['ids']:<5} "
              f"dedup_borro={r['borradas']:<5} ({100*r['borradas']/max(1,r['cajas']+r['borradas']):.1f}%)")

    print()
    print("=" * 74)
    print("6. COSTO OPERATIVO — un video de 15 min (27.000 frames)")
    print("=" * 74)
    print(f"  {'escenario':<44} {'FPS':>8} {'tiempo':>10} {'vs real':>9}")
    escenarios = [
        ("decode solo (techo fisico)", d_fps),
        ("yolo26x FP32 batch 1", results.get(("yolo26x (59.0M)", False, 1))),
        ("yolo26x FP16 batch 1", results.get(("yolo26x (59.0M)", True, 1))),
        ("yolo26x FP16 batch 8", results.get(("yolo26x (59.0M)", True, 8))),
        ("yolo26x FP16 batch 16", results.get(("yolo26x (59.0M)", True, 16))),
        ("MIN5 FP16 batch 1 (referencia)", results.get(("MIN5 (25.1M)", True, 1))),
        ("yolo26x track() FP16 (pasada causal)", t_fps),
    ]
    for label, f in escenarios:
        if not f:
            continue
        t, x = fmt_video(f)
        print(f"  {label:<44} {f:>8.1f} {t:>10} {x:>9}")

    b16 = results.get(("yolo26x (59.0M)", True, 16))
    if b16:
        real = min(b16, d_fps)
        t, x = fmt_video(real)
        print(f"\n  PIPELINE REAL (decode + inferencia en lote, el mas lento manda):")
        print(f"    min({b16:.1f} inferencia, {d_fps:.1f} decode) = {real:.1f} FPS -> {t} por video ({x} el tiempo real)")


if __name__ == "__main__":
    main()
