#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "numpy"]
# ///
"""C9 — Tesis 27: un video por video etiquetado y tracker, con todas sus subidas y bajadas.

Pega una tras otra las aperturas del golden de eventos que tienen alguna subida o bajada
(con `MARGEN` frames a cada lado, el mismo margen con que eval_flow.py asigna un evento a
su apertura), con:
  - las cajas e IDs del tracker (la corrida del video entero, la misma de la 17b);
  - los eventos del golden (punto donde la cabeza alcanza la curva interior);
  - los que cuenta el tracker con la regla `od` y la puerta de door.py, como el sistema;
  - los contadores de la apertura (real / contado), y al final un cartel con la Tabla I.

Los números salen de eval_flow.evaluate con TODAS las aperturas del golden (también las que
no tienen eventos, donde solo puede haber falsos positivos): con ByteTrack son los de la
Tabla I. Nada se ajusta con estos videos: solo se enseña.

`prep` (portátil) escribe OUT/<collage>/{meta.json,<tracker>.txt}; `render` (torre, venv de
track-studio) lee los tramos del video original y escribe <tracker>.mp4. Luego
`importar_studio.py --videos OUT` los sube a track-studio, un job por video y tracker.

  uv run scripts/flow/collage_eventos.py prep --out data/collage_eventos
  ~/Projects/track-studio/.venv/bin/python scripts/flow/collage_eventos.py render \\
      --out data/collage_eventos --videos ~/videos
"""
import argparse, collections, csv, hashlib, json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "flow"))

MARGEN = 60      # = --margin de eval_flow.py
TOL = 10         # = --tol de eval_flow.py
TITULO = 30      # frames del cartel de cada apertura
FINAL = 120      # frames del cartel final
VIVO = 30        # frames que se ve la marca de un evento

# video etiquetado -> (corrida en runs/, cámara, ROI, fichero del video en la torre relativo a --videos)
VIDEOS = {
    "videoTM_07": ("07", "videoTM_07.yaml", "roi_videoTM_07.json", "videoTM_07.mkv"),
    "videoTM_02": ("02", "videoTM_02.yaml", "roi_videoTM_07.json", "videoTM_02.mkv"),
    "videoTM_03_1": ("03_1", "videoTM_03_1.yaml", "roi_videoTM_03_1.json", "videoTM_03(1).mkv"),
    "bus_ddr_s6_v18": ("bus_ddr_s6_v18", "bus_ddr_s6.yaml", "roi_bus_ddr_s6.json", "bus/ddr/bus_ddr_s6_v18.mkv"),
    "bus_sdr_s1_v08": ("bus_sdr_s1_v08", "bus_sdr_s1.yaml", "roi_bus_sdr_s1.json", "bus/sdr/bus_sdr_s1_v08.mkv"),
}
TRACKERS = {"bytetrack_27": "ByteTrack (#27)", "botsort_osnet": "BoT-SORT + OSNet",
            "deepocsort_osnet_iou020": "Deep OC-SORT IoU 0,2"}
KINDS = ("sube", "baja")


def cmd_prep(a):
    import events as EV
    import eval_flow as EF
    out = pathlib.Path(a.out)
    for video, (run, cam_file, roi_file, _) in VIDEOS.items():
        golden_path = ROOT / "data/flow_golden" / f"{video}.csv"
        golden = EF.load_golden(golden_path)
        points = [r for r in csv.DictReader(open(golden_path)) if r["direccion"] in (*KINDS, "raro")]
        stops = [(lo, hi) for (lo, hi), ev in golden.items() if ev]
        cam = EV.load_camera(ROOT / "configs/cameras" / cam_file)
        door = ROOT / "data/flow_videos" / f"puerta_abierta_{video}.json"
        is_open = EV.door_filter(door, 0, cam["od"]["holgura"])
        roi = json.loads((ROOT / "configs/cameras" / roi_file).read_text())

        # tramos del collage: un cartel y la apertura con su margen, uno tras otro
        segments, offset = [], 0
        for k, (lo, hi) in enumerate(stops, 1):
            seg_lo, seg_hi = max(1, lo - MARGEN), hi + MARGEN
            segments.append({"k": k, "lo": lo, "hi": hi, "seg_lo": seg_lo, "seg_hi": seg_hi,
                             "titulo": offset + 1, "inicio": offset + TITULO + 1,
                             "golden": [{"frame": int(r["frame"]), "dir": r["direccion"], "x": float(r["x"]),
                                         "y": float(r["y"])} for r in points
                                        if (int(r["parada_inicio"]), int(r["parada_fin"])) == (lo, hi)]})
            offset += TITULO + seg_hi - seg_lo + 1
        frames = offset + FINAL

        d = out / f"eventos_{video}"
        d.mkdir(parents=True, exist_ok=True)
        meta = {"clip": d.name, "source": video, "video": VIDEOS[video][3], "start": 1, "frames": frames,
                "golden": str(golden_path.relative_to(ROOT)), "door": str(door.relative_to(ROOT)),
                "curvas": {"outer": cam["outer"].tolist() if hasattr(cam["outer"], "tolist") else cam["outer"],
                           "inner": cam["inner"].tolist() if hasattr(cam["inner"], "tolist") else cam["inner"]},
                "roi": {"name": pathlib.Path(roi_file).stem, "width": roi["width"], "height": roi["height"],
                        "polygon": roi["polygon"]},
                "aperturas_sin_eventos": len(golden) - len(stops), "segments": segments, "runs": {}, "tabla": {}}
        for tracker in TRACKERS:
            run_path = ROOT / "data/flow_eval/runs" / tracker / f"{run}.txt"
            data = run_path.read_bytes()
            lines = [l for l in data.decode().splitlines() if l.strip()]
            evs, _ = EV.detect(cam, lines, "od", is_open)
            table = EF.evaluate(golden, {tracker: evs}, TOL, MARGEN)[tracker]
            meta["tabla"][tracker] = {
                ("total" if key == "total" else f"{key[0]}-{key[1]}"): {k: list(v[k]) for k in KINDS}
                for key, v in table.items()}
            meta["runs"][tracker] = {"run": str(run_path.relative_to(ROOT)),
                                     "run_sha256": hashlib.sha256(data).hexdigest(),
                                     "eventos": [[f, str(t), kind] for f, t, kind in evs]}
            # MOT del collage: cada tramo, renumerado a los frames del collage
            kept, ids = [], set()
            for s in segments:
                for line in lines:
                    f = int(float(line.split(",", 1)[0]))
                    if s["seg_lo"] <= f <= s["seg_hi"]:
                        p = line.split(",")
                        kept.append((s["inicio"] + f - s["seg_lo"], ",".join([str(s["inicio"] + f - s["seg_lo"])] + p[1:])))
                        ids.add(p[1])
            kept.sort(key=lambda t: t[0])
            (d / f"{tracker}.txt").write_text("\n".join(l for _, l in kept) + "\n")
            meta["runs"][tracker]["tracks"] = len(ids)
            tot = table["total"]
            print(f"  {video} {tracker}: " + "  ".join(
                f"{k} {tot[k][1]}/{tot[k][0]} ({(tot[k][1] - tot[k][0]) / tot[k][0]:+.0%})" if tot[k][0] else f"{k} —"
                for k in KINDS) + f"  · {len(stops)} aperturas, {frames} f")
        meta["origen"] = (f"collage de las {len(stops)} aperturas con eventos de {video} "
                          f"(golden {meta['golden']}, puerta {meta['door']})")
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False) + "\n")


def pct(n, d):
    return f"{n / d:+.0%}" if d else "-"


def cmd_render(a):
    import cv2
    import numpy as np
    GREEN, ORANGE, GREY, WHITE = (90, 200, 60), (40, 150, 255), (170, 170, 170), (255, 255, 255)
    COLOR = {"sube": GREEN, "baja": ORANGE, "raro": GREY}
    FONT = cv2.FONT_HERSHEY_SIMPLEX

    def text(im, s, org, scale=0.5, color=WHITE, thick=1):
        cv2.putText(im, s, org, FONT, scale, (0, 0, 0), thick + 2, cv2.LINE_AA)
        cv2.putText(im, s, org, FONT, scale, color, thick, cv2.LINE_AA)

    def tid_color(tid):
        import colorsys
        r, g, b = colorsys.hsv_to_rgb((int(tid) * 0.618034) % 1, 0.7, 1.0)
        return int(b * 255), int(g * 255), int(r * 255)

    for meta_path in sorted(pathlib.Path(a.out).glob("eventos_*/meta.json")):
        meta = json.loads(meta_path.read_text())
        video = str(pathlib.Path(a.videos) / meta["video"])
        curves = [np.array(meta["curvas"][k], dtype=np.int32) for k in ("outer", "inner")]
        roi = np.array(meta["roi"]["polygon"], dtype=np.int32)
        n_stops = len(meta["segments"])
        for tracker, label in TRACKERS.items():
            boxes = collections.defaultdict(list)   # frame del collage -> cajas
            for line in (meta_path.parent / f"{tracker}.txt").read_text().splitlines():
                if line.strip():
                    p = line.split(",")
                    boxes[int(p[0])].append((p[1], *(float(v) for v in p[2:6])))
            evs = meta["runs"][tracker]["eventos"]
            table = meta["tabla"][tracker]
            target = meta_path.parent / f"{tracker}.mp4"
            cap = cv2.VideoCapture(video)
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            enc = subprocess.Popen(
                ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
                 "-r", "30", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21",
                 "-movflags", "+faststart", str(target)], stdin=subprocess.PIPE)

            def card(lines, n):
                im = np.zeros((h, w, 3), np.uint8)
                y = 60
                for s, scale, color in lines:
                    text(im, s, (30, y), scale, color, 1 if scale < 0.7 else 2)
                    y += int(40 * max(scale, 0.6))
                for _ in range(n):
                    enc.stdin.write(im.tobytes())

            for s in meta["segments"]:
                key = f"{s['lo']}-{s['hi']}"
                real = {k: table[key][k][0] for k in KINDS}
                got = {k: table[key][k][1] for k in KINDS}
                card([(f"{meta['source']} | {label}", 0.7, WHITE),
                      (f"apertura {s['k']}/{n_stops}  -  frames {s['lo']}-{s['hi']}", 0.7, WHITE),
                      (f"real:    {real['sube']} suben, {real['baja']} bajan", 0.6, WHITE),
                      (f"contado: {got['sube']} suben, {got['baja']} bajan", 0.6, WHITE),
                      ("circulo = real (golden)   +1 = lo cuenta el tracker", 0.5, GREY),
                      ("verde = sube   naranja = baja", 0.5, GREY)], TITULO)
                stop_evs = [(f, t, k) for f, t, k in evs if s["lo"] - MARGEN <= f <= s["hi"] + MARGEN]
                cap.set(cv2.CAP_PROP_POS_FRAMES, s["seg_lo"] - 1)
                for f in range(s["seg_lo"], s["seg_hi"] + 1):
                    ok, im = cap.read()
                    if not ok:
                        sys.exit(f"{video}: se acaba en el frame {f - 1}")
                    c = s["inicio"] + f - s["seg_lo"]
                    cv2.polylines(im, [roi], True, (200, 200, 200), 1, cv2.LINE_AA)
                    cv2.polylines(im, curves[:1], False, (255, 200, 120), 1, cv2.LINE_AA)
                    cv2.polylines(im, curves[1:], False, (120, 255, 255), 1, cv2.LINE_AA)
                    here = {}
                    for tid, x, y, bw, bh in boxes.get(c, []):
                        col = tid_color(tid)
                        cv2.rectangle(im, (int(x), int(y)), (int(x + bw), int(y + bh)), col, 2)
                        text(im, tid, (int(x), max(34, int(y) - 4)), 0.45, col)
                        here[tid] = (int(x), int(y))
                    for g in s["golden"]:   # verdad: círculo donde la cabeza alcanza la curva
                        if g["frame"] - 5 <= f <= g["frame"] + VIVO:
                            cv2.circle(im, (int(g["x"]), int(g["y"])), 14, COLOR[g["dir"]], 2, cv2.LINE_AA)
                            text(im, f"real {g['dir']}", (int(g["x"]) - 30, int(g["y"]) + 30), 0.45, COLOR[g["dir"]])
                    for ef, tid, kind in stop_evs:   # lo que cuenta el tracker
                        if ef <= f <= ef + VIVO:
                            bx, by = here.get(tid, (w // 2 - 60, 60))
                            text(im, f"+1 {kind} #{tid}", (bx, max(44, by - 20)), 0.5, COLOR[kind], 2)
                    sofar_g = collections.Counter(g["dir"] for g in s["golden"] if g["frame"] <= f)
                    sofar_t = collections.Counter(k for ef, _, k in stop_evs if ef <= f)
                    cv2.rectangle(im, (0, 0), (w, 24), (0, 0, 0), -1)
                    text(im, f"{meta['source']} | {label} | apertura {s['k']}/{n_stops} | f {f}", (6, 17), 0.48)
                    cv2.rectangle(im, (0, h - 26), (w, h), (0, 0, 0), -1)
                    text(im, f"real {sofar_g['sube']} suben {sofar_g['baja']} bajan", (6, h - 8), 0.5)
                    text(im, f"contado {sofar_t['sube']} suben {sofar_t['baja']} bajan", (w // 2, h - 8), 0.5)
                    enc.stdin.write(im.tobytes())
            tot = table["total"]
            lines = [(f"{meta['source']} | {label}", 0.7, WHITE),
                     (f"{n_stops} aperturas con eventos (+{meta['aperturas_sin_eventos']} sin eventos)", 0.55, GREY)]
            for k in KINDS:
                r, g, hits = tot[k]
                lines += [(f"{k}: real {r}, contado {g}, error {pct(g - r, r)}", 0.6, COLOR[k]),
                          (f"   recall {hits / r:.2f}  precision {hits / g:.2f}" if r and g else "   -", 0.55, WHITE)]
            lines.append(("sin corregir; regla od + puerta door.py (eval_flow.py)", 0.5, GREY))
            card(lines, FINAL)
            enc.stdin.close()
            cap.release()
            if enc.wait() != 0:
                sys.exit(f"ffmpeg falló con {target}")
            print(f"  {target} ({target.stat().st_size // 1024} KB)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("prep", help="cuenta eventos por tracker y arma el MOT de cada collage")
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_prep)
    s = sub.add_parser("render", help="pinta cada collage desde el video original")
    s.add_argument("--out", required=True)
    s.add_argument("--videos", required=True, help="carpeta de los videos (~/videos en la torre)")
    s.set_defaults(fn=cmd_render)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
