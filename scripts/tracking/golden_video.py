#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pillow>=10.1"]
# ///
"""B3 — video del golden contra un job de track-studio, para VER los errores.

Las metricas de eval_tracking.py dicen cuanto falla un tracker; este video
ensena donde. Sobre los frames del clip (DIR/img1/000001.png...) pinta:
  - verde : cabeza del golden emparejada con una caja del tracker (G = id del golden)
  - azul  : la caja del tracker emparejada (T = id del tracker)
  - rojo  : cabeza del golden que el tracker no tiene (perdida)
  - naranja: caja del tracker sin cabeza en el golden (de mas)
  - magenta: cambio de identidad (IDSW): la persona G pasa de un T a otro
  - gris  : cabeza del golden fuera de la ROI del job (no cuenta, como en publish)

El emparejamiento es el de CLEAR-MOT (IoU >= 0,5, se conserva el par del frame
anterior si sigue valiendo). Los conteos se acercan a los de TrackEval, pero la
cifra oficial es la de eval_tracking.py: esto es para mirar, no para medir.

Uso:
  uv run scripts/tracking/golden_video.py --gt data/tracking_golden/tm07_a --job 23
  -> data/tracking_golden/tm07_a/videos/job23.mp4
"""
import argparse, json, pathlib, subprocess, sys, tempfile

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from eval_tracking import _http, contains, cut_lines, seqinfo  # noqa: E402

IOU_MIN = 0.5
SCALE = 2
GREEN, BLUE, RED, ORANGE, MAGENTA, GRAY = "#22c55e", "#3b82f6", "#ef4444", "#f97316", "#d946ef", "#9ca3af"


def parse(lines):
    """{frame: {id: (x, y, w, h)}} de lineas MOT."""
    out = {}
    for line in lines:
        p = line.split(",")
        out.setdefault(int(float(p[0])), {})[int(float(p[1]))] = tuple(float(v) for v in p[2:6])
    return out


def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    iw = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    ih = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = iw * ih
    return inter / (aw * ah + bw * bh - inter) if inter else 0.0


def match(gt, tr, prev):
    """Pares {gid: tid} de un frame. Primero se conservan los del frame anterior."""
    pairs, used = {}, set()
    for g, t in prev.items():
        if g in gt and t in tr and iou(gt[g], tr[t]) >= IOU_MIN:
            pairs[g] = t
            used.add(t)
    cands = sorted(((iou(gt[g], tr[t]), g, t) for g in gt if g not in pairs for t in tr if t not in used),
                   reverse=True)
    for v, g, t in cands:
        if v < IOU_MIN:
            break
        if g not in pairs and t not in used:
            pairs[g] = t
            used.add(t)
    return pairs


def fetch_job(api, job_id):
    status, body = _http("GET", f"{api}/api/jobs/{job_id}")
    if status != 200:
        sys.exit(f"job {job_id}: HTTP {status}")
    job = json.loads(body)
    status, body = _http("GET", f"{api}/api/jobs/{job_id}/tracks")
    if status != 200:
        sys.exit(f"job {job_id} sin salida MOT: HTTP {status}")
    roi = None
    if job.get("roi"):
        status, rbody = _http("GET", f"{api}/api/jobs/{job_id}/roi")
        if status != 200:
            sys.exit(f"job {job_id}: no se pudo leer la ROI ({status})")
        roi = json.loads(rbody)["polygon"]
    return job, [l for l in body.splitlines() if l.strip()], roi


def label(draw, xy, text, color, font):
    x, y = xy
    l, t, r, b = draw.textbbox((x, y), text, font=font)
    draw.rectangle([l - 2, t - 1, r + 2, b + 1], fill=color)
    draw.text((x, y), text, fill="black", font=font)


def render(args):
    seq_dir = pathlib.Path(args.gt)
    info = seqinfo(seq_dir / "gt" / "gt.txt")
    start, n = int(info["start"]), int(info["seqlength"])
    job, tracks, roi = fetch_job(args.api.rstrip("/"), args.job)
    if pathlib.Path(job["source_name"]).stem != info.get("source"):
        sys.exit(f"el job {args.job} es de {job['source_name']}, el golden de {info.get('source')}")

    gt = parse(l for l in (seq_dir / "gt" / "gt.txt").read_text().splitlines() if l.strip())
    tr = parse(cut_lines(tracks, start, n))
    font = ImageFont.load_default(size=11 * SCALE)
    big = ImageFont.load_default(size=13 * SCALE)

    prev, last_t, flashes = {}, {}, []
    totals = {"perdidas": 0, "de mas": 0, "IDSW": 0}
    out = pathlib.Path(args.out or seq_dir / "videos" / f"job{args.job}.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for f in range(1, n + 1):
            g_all, t_f = gt.get(f, {}), tr.get(f, {})
            def counted(b):
                return roi is None or contains(roi, b[0] + b[2] / 2, b[1] + b[3] / 2)
            g_f = {g: b for g, b in g_all.items() if counted(b)}
            pairs = match(g_f, t_f, prev)
            switched = {g for g, t in pairs.items() if g in last_t and last_t[g] != t}
            for g in switched:
                flashes.append((f, g, last_t[g], pairs[g]))
            last_t.update(pairs)
            prev = pairs
            missed = [g for g in g_f if g not in pairs]
            extra = [t for t in t_f if t not in pairs.values()]
            totals["perdidas"] += len(missed)
            totals["de mas"] += len(extra)
            totals["IDSW"] += len(switched)

            img = Image.open(seq_dir / "img1" / f"{f:06d}.png").convert("RGB")
            img = img.resize((img.width * SCALE, img.height * SCALE))
            d = ImageDraw.Draw(img)
            S = lambda b: [b[0] * SCALE, b[1] * SCALE, (b[0] + b[2]) * SCALE, (b[1] + b[3]) * SCALE]  # noqa: E731
            if roi:
                d.line([(x * SCALE, y * SCALE) for x, y in roi + roi[:1]], fill=GRAY, width=3)
            for g, b in g_all.items():
                if g not in g_f:
                    d.rectangle(S(b), outline=GRAY, width=2)
            for g, t in pairs.items():
                d.rectangle(S(t_f[t]), outline=BLUE, width=3)
                d.rectangle(S(g_f[g]), outline=MAGENTA if g in switched else GREEN, width=4)
                x0, y0 = S(g_f[g])[:2]
                label(d, (x0, y0 - 14 * SCALE), f"G{g}", MAGENTA if g in switched else GREEN, font)
                label(d, (x0 + 26 * SCALE, y0 - 14 * SCALE), f"T{t}", BLUE, font)
            for g in missed:
                d.rectangle(S(g_f[g]), outline=RED, width=4)
                x0, y0 = S(g_f[g])[:2]
                label(d, (x0, y0 - 14 * SCALE), f"G{g} perdida", RED, font)
            for t in extra:
                d.rectangle(S(t_f[t]), outline=ORANGE, width=3)
                x0, y1 = S(t_f[t])[0], S(t_f[t])[3]
                label(d, (x0, y1 + 2), f"T{t} de mas", ORANGE, font)

            head = (f"job #{args.job} {pathlib.Path(job.get('tracker', '')).stem}  |  frame {f}/{n}  |  "
                    f"perdidas {totals['perdidas']}  de mas {totals['de mas']}  IDSW {totals['IDSW']}")
            d.rectangle([0, 0, img.width, 22 * SCALE], fill="black")
            d.text((6, 4 * SCALE), head, fill="white", font=big)
            recent = [x for x in flashes if f - x[0] < args.fps * 2]
            for i, (ff, g, t0, t1) in enumerate(recent):
                label(d, (6, (26 + 16 * i) * SCALE), f"IDSW f{ff}: G{g}  T{t0} -> T{t1}", MAGENTA, big)
            legend = "verde golden  azul tracker  rojo perdida  naranja de mas  magenta IDSW  gris fuera de ROI"
            d.rectangle([0, img.height - 18 * SCALE, img.width, img.height], fill="black")
            d.text((6, img.height - 16 * SCALE), legend, fill="white", font=font)
            img.save(pathlib.Path(tmp) / f"{f:06d}.png")

        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(args.fps),
                        "-i", str(pathlib.Path(tmp) / "%06d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", "18", "-movflags", "+faststart", str(out)], check=True)
    print(f"{out}  (perdidas {totals['perdidas']}, de mas {totals['de mas']}, IDSW {totals['IDSW']})")
    for ff, g, t0, t1 in flashes:
        print(f"  IDSW frame {ff}: G{g} T{t0} -> T{t1}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--gt", required=True, help="carpeta del clip: seqinfo.ini, gt/gt.txt e img1/")
    p.add_argument("--job", type=int, required=True)
    p.add_argument("--api", default="http://track.torre")
    p.add_argument("--fps", type=int, default=5, help="lento a proposito: 100 frames = 20 s")
    p.add_argument("--out")
    render(p.parse_args())


if __name__ == "__main__":
    main()
