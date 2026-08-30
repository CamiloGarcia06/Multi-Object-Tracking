#!/usr/bin/env python3
"""
Anota un video con el detector de cabezas y escribe un MP4 con cajas + conteo en vivo.

Pensado para DEMO: tomar un video NO usado en entrenamiento y mostrar cómo trabaja
el modelo campeón (MIN5). Corre dentro del contenedor mot-dev (cv2 + ultralytics).

Uso:
  python3 annotate_video.py <video_entrada> [video_salida] [opciones]

Opciones:
  --model RUTA      pesos a usar (default: campeón MIN5)
  --conf F          umbral de confianza (default 0.25, igual que el golden)
  --iou F           IoU de NMS (default 0.5)
  --start SEG       segundo donde empezar (default 0)
  --dur SEG         duración a procesar en segundos (default: todo)
  --label TEXTO     etiqueta del modelo en el overlay (default "MIN5")
  --no-banner       no dibujar el banner superior
Si no se pasa <video_entrada>, lo pregunta de forma interactiva.
"""
import os, sys, argparse, time
import cv2
from ultralytics import YOLO

CHAMPION = "/workspace/outputs/head_detector/yolo-bus-head-min5/weights/best.pt"


def parse_args():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("video", nargs="?", help="ruta del video de entrada")
    ap.add_argument("salida", nargs="?", help="ruta del video de salida (.mp4)")
    ap.add_argument("--model", default=CHAMPION)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--dur", type=float, default=None)
    ap.add_argument("--label", default="MIN5")
    ap.add_argument("--no-banner", action="store_true")
    return ap.parse_args()


def ask(prompt):
    try:
        return input(prompt).strip().strip('"').strip("'")
    except EOFError:
        return ""


def main():
    a = parse_args()

    inp = a.video or ask("📹 Ruta del video SIN etiquetar: ")
    if not inp or not os.path.isfile(inp):
        sys.exit(f"❌ No encuentro el video: {inp!r}")

    if a.salida:
        out = a.salida
    else:
        base = os.path.splitext(os.path.basename(inp))[0]
        out = f"/workspace/outputs/demos/{base}_anotado.mp4"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    print(f"🧠 Modelo:  {a.model}")
    print(f"📥 Entrada: {inp}")
    print(f"📤 Salida:  {out}")
    print(f"⚙️  conf={a.conf}  iou={a.iou}")

    model = YOLO(a.model)

    cap = cv2.VideoCapture(inp)
    if not cap.isOpened():
        sys.exit(f"❌ No pude abrir el video: {inp}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    start_f = int(a.start * fps)
    end_f = total if a.dur is None else min(total, start_f + int(a.dur * fps))
    if start_f > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)

    writer = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    if not writer.isOpened():
        sys.exit("❌ No pude crear el VideoWriter (codec mp4v).")

    n_proc, counts, t0 = 0, [], time.time()
    idx = start_f
    while idx < end_f:
        ok, frame = cap.read()
        if not ok:
            break

        r = model.predict(frame, conf=a.conf, iou=a.iou, verbose=False)[0]
        n = len(r.boxes)
        counts.append(n)

        # cajas
        for b in r.boxes.xyxy.cpu().numpy().astype(int):
            x1, y1, x2, y2 = b
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    
        # banner superior con info de demo
        if not a.no_banner:
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (W, 70), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
            cv2.putText(frame, f"Cabezas: {n}", (15, 48),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 0), 3)
            tag = f"Detector de cabezas {a.label}  |  video NO usado en entrenamiento"
            cv2.putText(frame, tag, (W - 760 if W > 800 else 15, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        writer.write(frame)
        n_proc += 1
        idx += 1
        if n_proc % 50 == 0:
            spd = n_proc / (time.time() - t0)
            print(f"  {n_proc}/{end_f - start_f} frames  ({spd:.1f} f/s)  ult={n}")

    cap.release()
    writer.release()

    if counts:
        avg = sum(counts) / len(counts)
        print(f"\n✅ Listo: {out}")
        print(f"   {n_proc} frames | cabezas/frame  prom={avg:.1f}  máx={max(counts)}  mín={min(counts)}")
    else:
        print("\n⚠️  No se procesó ningún frame.")


if __name__ == "__main__":
    main()
