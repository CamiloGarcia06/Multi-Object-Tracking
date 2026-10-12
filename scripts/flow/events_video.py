#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "numpy", "pillow>=10.1"]
# ///
"""C2 — video de las subidas y bajadas que cuenta events.py, para VER la regla.

Sobre un tramo del video pinta las dos líneas de la puerta (exterior en rojo,
interior en verde) y cada track con su estado según la regla (`--rule`).

Regla `od` (por defecto), por la distancia d a la curva interior:
  - naranja : zona de la puerta (d <= zona_puerta): de aquí nace quien sube
  - amarillo: entre la zona y el pasillo
  - cian    : pasillo (d >= pasillo)

Regla `curvas`:
  - naranja : FUERA (pasó la línea exterior hacia el andén)
  - amarillo: en el umbral, entre las dos líneas (conserva el lado que tenía)
  - cian    : DENTRO (pasó la línea interior hacia el pasillo)
  - gris    : lejos de la puerta (no cuenta para nada)
Cuando hay evento sale SUBE / BAJA encima de la caja y suben los contadores de
arriba. Los eventos son exactamente los de events.py: se calculan sobre el track
entero, no solo sobre el tramo.

`--golden`: pinta las marcas del golden de eventos (anillo blanco, ±1 s). Con
`--errors` (CSV de error_causes.py), las personas perdidas van en rojo con su causa.

`--video` es el tramo ya recortado (frame 1 del fichero = `--start` del MOT):
  uv run scripts/flow/events_video.py --camera configs/cameras/videoTM_07.yaml \\
      --job 28 --video tramo.mp4 --start 22000 --out bajadas.mp4
"""
import argparse, collections, json, pathlib, subprocess, sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import events as E  # noqa: E402

SCALE = 2
COLOR = {E.OUTSIDE: "#f97316", None: "#facc15", E.INSIDE: "#22d3ee", "lejos": "#9ca3af",
         "puerta": "#f97316", "umbral": "#facc15", "pasillo": "#22d3ee"}
RING = 15  # frames antes y después de la marca del golden en que se ve el anillo
FLASH = 30  # frames que se queda el letrero del evento


def timeline(cam, pts):
    """{frame: estado} y [(frame, tipo)] con la MISMA lógica que E.track_events."""
    states, side, events = {}, None, []
    for f, x, y in pts:
        if not E.at_door(cam, x, y):
            states[f] = "lejos"
            continue
        now = E.side_of(cam, x, y)
        if now is not None:
            if side is not None and now != side:
                events.append((f, "sube" if now == E.INSIDE else "baja"))
            side = now
        states[f] = now
    assert events == E.track_events(cam, pts)
    return states, events


def od_timeline(cam, pts, is_open):
    """{frame: zona} y [(frame, tipo, puerta_abierta)] con la MISMA lógica que E.od_events."""
    zone, aisle = cam["od"]["zona_puerta"], cam["od"]["pasillo"]
    states = {}
    for f, x, y in pts:
        d = E.signed(cam, "inner", x, y)
        states[f] = "puerta" if d <= zone else "pasillo" if d >= aisle else "umbral"
    return states, [(f, k, is_open(g)) for f, k, g in E.od_events(cam, pts)]


def video_info(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                          "stream=width,height,r_frame_rate", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return s["width"], s["height"], float(num) / float(den)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--camera", required=True)
    p.add_argument("--job", type=int, required=True)
    p.add_argument("--api", default="http://track.torre")
    p.add_argument("--video", required=True, help="tramo recortado del video del job")
    p.add_argument("--start", type=int, required=True, help="frame del MOT que es el frame 1 del tramo")
    p.add_argument("--out", required=True)
    p.add_argument("--speed", type=float, default=0.5, help="0,5 = a media velocidad")
    p.add_argument("--door", help="JSON con los intervalos [inicio, fin] de puerta abierta (frames del MOT)")
    p.add_argument("--rule", choices=("od", "curvas"), default="od")
    p.add_argument("--golden", help="CSV del golden de eventos: pinta las marcas")
    p.add_argument("--errors", help="CSV de error_causes.py: las perdidas en rojo con su causa")
    a = p.parse_args()

    cam = E.load_camera(a.camera)
    door = json.loads(pathlib.Path(a.door).read_text()) if a.door else None
    slack = cam["od"]["holgura"] if a.rule == "od" else 0
    is_open = lambda f: door is None or any(lo - slack <= f <= hi + slack for lo, hi in door)  # noqa: E731
    marks = collections.defaultdict(list)
    if a.golden:
        import csv
        lost = {}
        if a.errors:
            lost = {(int(r["frame"]), r["direccion"]): r["causa"] for r in csv.DictReader(open(a.errors))}
        for r in csv.DictReader(open(a.golden)):
            if r["direccion"] in ("sube", "baja"):
                g = int(r["frame"])
                m = (g, float(r["x"]), float(r["y"]), r["direccion"], lost.get((g, r["direccion"])))
                for f in range(g - RING, g + RING + 1):
                    marks[f].append(m)
    status, body = E._http("GET", f"{a.api.rstrip('/')}/api/jobs/{a.job}")
    tracker = pathlib.Path(json.loads(body)["tracker"]).stem if status == 200 else "?"
    a.tracks, a.gt = None, None
    tracks = E.parse_tracks(E.source_lines(a))
    by_frame = collections.defaultdict(list)
    flashes, timelines = collections.defaultdict(list), {}
    for tid, pts in tracks.items():
        if a.rule == "od":
            states, evs = od_timeline(cam, pts, is_open)
        else:
            states, evs = timeline(cam, pts)
            evs = [(f, k, is_open(f)) for f, k in evs]
        timelines[tid] = (pts, states)
        for f, x, y in pts:
            by_frame[f].append((tid, x, y))
        for f, kind, valid in evs:
            flashes[f].append((tid, kind, valid))

    w, h, fps = video_info(a.video)
    if (w, h) != cam["size"]:
        sys.exit(f"el video es {w}x{h} y la cámara {cam['size']}")
    boxes = collections.defaultdict(dict)
    for line in E.source_lines(a):
        q = line.split(",")
        boxes[int(float(q[0]))][int(float(q[1]))] = tuple(float(v) for v in q[2:6])

    font = ImageFont.load_default(size=11 * SCALE)
    big = ImageFont.load_default(size=16 * SCALE)
    W, H = w * SCALE, h * SCALE
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", a.video, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps * a.speed), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-crf", "20", "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
    count, recent, i = {"sube": 0, "baja": 0, "ignorados": 0}, [], 0
    S = lambda x, y: (x * SCALE, y * SCALE)  # noqa: E731
    while raw := dec.stdout.read(w * h * 3):
        f = a.start + i
        i += 1
        img = Image.frombytes("RGB", (w, h), raw).resize((W, H))
        d = ImageDraw.Draw(img)
        for key, col in (("outer", "#ef4444"), ("inner", "#22c55e")):
            d.line([S(x, y) for x, y in cam[key]], fill=col, width=4)
        for tid, kind, valid in flashes.get(f, []):
            count[kind if valid else "ignorados"] += 1
            recent.append((f, tid, kind, valid))
        for g, gx, gy, kind, cause in marks.get(f, []):
            col = "#ef4444" if cause else "white"
            r_ = 22 * SCALE
            d.ellipse([gx * SCALE - r_, gy * SCALE - r_, gx * SCALE + r_, gy * SCALE + r_], outline=col, width=4)
            txt = f"REAL {kind.upper()}" + (f" PERDIDA: {cause}" if cause else "")
            l, t, r, b = d.textbbox((0, 0), txt, font=font, stroke_width=2)
            tx = min(max(gx * SCALE - r_, 4), W - (r - l) - 4)  # que no se salga del cuadro
            ty = gy * SCALE + r_ + 2
            if ty + (b - t) > H - 20 * SCALE:
                ty = gy * SCALE - r_ - (b - t) - 4
            d.text((tx, ty), txt, fill=col, font=font, stroke_width=2, stroke_fill="black")
        for tid, b in boxes.get(f, {}).items():
            pts, states = timelines[tid]
            col = COLOR[states.get(f, "lejos")]
            trail = [S(x, y) for g, x, y in pts if f - 20 <= g <= f]
            if len(trail) > 1:
                d.line(trail, fill=col, width=2)
            d.rectangle([*S(b[0], b[1]), *S(b[0] + b[2], b[1] + b[3])], outline=col, width=3)
            d.text(S(b[0], b[1] - 13), f"{tid}", fill=col, font=font)
        for g, tid, kind, valid in [r for r in recent if f - r[0] < FLASH]:
            b = boxes.get(f, {}).get(tid) or boxes.get(g, {}).get(tid)
            if b:
                txt, col = ("SUBE", "#22c55e") if kind == "sube" else ("BAJA", "#ef4444")
                if not valid:
                    txt, col = f"{txt} (cerrada)", "#9ca3af"
                x0, y0 = S(b[0], b[1] + b[3] + 2)
                l, t, r, bb = d.textbbox((x0, y0), txt, font=big)
                d.rectangle([l - 4, t - 2, r + 4, bb + 2], fill=col)
                d.text((x0, y0), txt, fill="black", font=big)
        d.rectangle([0, 0, W, 26 * SCALE], fill="black")
        d.text((8, 4 * SCALE), f"job #{a.job} {tracker} ({a.rule}) | frame {f} | SUBE {count['sube']}  BAJA {count['baja']}"
               + (f"  ignorados {count['ignorados']}" if door else ""), fill="white", font=big)
        if door:
            txt, col = ("PUERTA ABIERTA", "#22c55e") if is_open(f) else ("PUERTA CERRADA", "#ef4444")
            l, t, r, bb = d.textbbox((0, 0), txt, font=big)
            d.rectangle([W - (r - l) - 24, 30 * SCALE, W - 8, 30 * SCALE + (bb - t) + 12], fill=col)
            d.text((W - (r - l) - 16, 30 * SCALE + 4), txt, fill="black", font=big)
        d.rectangle([0, H - 18 * SCALE, W, H], fill="black")
        legend = ("naranja zona puerta  amarillo entre  cian pasillo" if a.rule == "od"
                  else "naranja fuera  amarillo umbral  cian dentro  gris lejos")
        if marks:
            legend += "  |  anillo: golden (rojo = perdida)"
        d.text((8, H - 16 * SCALE), f"rojo: curva exterior  verde: interior  |  {legend}", fill="white", font=font)
        enc.stdin.write(img.tobytes())
    enc.stdin.close()
    enc.wait()
    dec.wait()
    print(f"{a.out}: {i} frames, SUBE {count['sube']} BAJA {count['baja']} ignorados {count['ignorados']}")


if __name__ == "__main__":
    main()
