#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["trackeval>=1.3", "numpy"]
# ///
"""B7 — Tesis 27: un video por apertura y tracker, para verlos en track-studio.

`prep` (portátil): de cada corrida de la 17b (`--runs DIR/<tracker>/<video>.txt`, video
entero) saca el tramo de la apertura y lo recorta a la ROI del montaje, con las mismas
funciones que `eval_tracking.py publish`: son exactamente las cajas que se evalúan.
Cada clip sale de su seqinfo.ini (start, seqLength, source), el mismo del golden.

`render` (torre, con el venv de track-studio: opencv + ffmpeg): pinta cada MOT recortado
sobre los frames del clip (los de `data/cvat_import/<clip>/frames/`, que son los del
golden) y escribe un mp4 H.264 que el navegador reproduce.

Después `importar_studio.py --videos OUT` los sube como jobs importados con render.

  uv run scripts/tracking/videos_apertura.py prep --runs data/flow_eval/runs \\
      --seqinfo DIR --clips tm03_1_b,tm07_b,ddr_s6_v18_b --out data/videos_apertura
  ~/Projects/track-studio/.venv/bin/python scripts/tracking/videos_apertura.py render \\
      --out data/videos_apertura --frames-root data/cvat_import
"""
import argparse, colorsys, hashlib, json, pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

# los 3 que compara la tesis (decisión de Camilo, 18-10), con su nombre en el video
TRACKERS = {"bytetrack_27": "ByteTrack (#27)", "botsort_osnet": "BoT-SORT + OSNet",
            "deepocsort_osnet_iou020": "Deep OC-SORT IoU 0,2"}
TRAIL_LENGTH = 30   # centros que dibuja la estela, los mismos que el render de track-studio


def seqinfo(path):
    info = {}
    for line in pathlib.Path(path).read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k.strip().lower()] = v.strip()
    return info


def cmd_prep(a):
    import comparar as C
    import eval_tracking as ET
    out = pathlib.Path(a.out)
    for clip in a.clips.split(","):
        info = seqinfo(pathlib.Path(a.seqinfo) / clip / "seqinfo.ini")
        short = C.VIDEOS[info["source"]]
        start, frames = int(info["start"]), int(info["seqlength"])
        roi = json.loads((C.CAMERAS / C.ROIS[short]).read_text())
        polygon = [tuple(p) for p in roi["polygon"]]
        d = out / clip
        d.mkdir(parents=True, exist_ok=True)
        meta = {"clip": clip, "source": info["source"], "video": short, "start": start, "frames": frames,
                "roi": {"name": pathlib.Path(C.ROIS[short]).stem, "width": roi["width"], "height": roi["height"],
                        "polygon": roi["polygon"]}, "runs": {}}
        for tracker in TRACKERS:
            run = pathlib.Path(a.runs) / tracker / f"{short}.txt"
            data = run.read_bytes()
            lines = [l for l in data.decode().splitlines() if l.strip()]
            kept = ET.inside_roi(ET.cut_lines(lines, start, frames), polygon)
            (d / f"{tracker}.txt").write_text("\n".join(kept) + "\n")
            meta["runs"][tracker] = {"run": str(run), "run_sha256": hashlib.sha256(data).hexdigest(),
                                     "tracks": len({l.split(",")[1] for l in kept}), "boxes": len(kept)}
            print(f"  {clip}/{tracker}: {meta['runs'][tracker]['tracks']} tracks, {len(kept)} cajas")
        (d / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")


def color(track_id):
    r, g, b = colorsys.hsv_to_rgb((track_id * 0.618034) % 1, 0.85, 1.0)
    return int(b * 255), int(g * 255), int(r * 255)  # BGR


def cmd_render(a):
    import cv2
    import numpy as np
    out = pathlib.Path(a.out)
    for meta_path in sorted(out.glob("*/meta.json")):
        meta = json.loads(meta_path.read_text())
        clip = meta["clip"]
        frames_dir = pathlib.Path(a.frames_root) / clip / "frames"
        polygon = np.array(meta["roi"]["polygon"], dtype=np.int32)
        for tracker, label in TRACKERS.items():
            boxes, trails = {}, {}
            for line in (meta_path.parent / f"{tracker}.txt").read_text().splitlines():
                if line.strip():
                    p = line.split(",")
                    boxes.setdefault(int(p[0]), []).append((int(float(p[1])), *(float(v) for v in p[2:6])))
            first = cv2.imread(str(frames_dir / "frame_000001.png"))
            if first is None:
                sys.exit(f"{frames_dir}: no están los frames del clip")
            h, w = first.shape[:2]
            target = meta_path.parent / f"{tracker}.mp4"
            enc = subprocess.Popen(
                ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
                 "-r", "30", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                 "-movflags", "+faststart", str(target)], stdin=subprocess.PIPE)
            for i in range(1, meta["frames"] + 1):
                im = cv2.imread(str(frames_dir / f"frame_{i:06d}.png"))
                cv2.polylines(im, [polygon], True, (255, 255, 255), 1, cv2.LINE_AA)
                for tid, x, y, bw, bh in boxes.get(i, []):
                    c = color(tid)
                    trail = trails.setdefault(tid, [])
                    trail.append((int(x + bw / 2), int(y + bh / 2)))
                    del trail[:-TRAIL_LENGTH]
                    if len(trail) > 1:
                        cv2.polylines(im, [np.array(trail, dtype=np.int32)], False, c, 2, cv2.LINE_AA)
                    cv2.rectangle(im, (int(x), int(y)), (int(x + bw), int(y + bh)), c, 2)
                    cv2.putText(im, str(tid), (int(x), max(12, int(y) - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 1,
                                cv2.LINE_AA)
                head = f"{clip} | {label} | f {meta['start'] + i - 1} ({i}/{meta['frames']})"
                cv2.rectangle(im, (0, 0), (w, 22), (0, 0, 0), -1)
                cv2.putText(im, head, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
                enc.stdin.write(im.tobytes())
            enc.stdin.close()
            if enc.wait() != 0:
                sys.exit(f"ffmpeg falló con {target}")
            print(f"  {target} ({target.stat().st_size // 1024} KB)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("prep", help="recorta las corridas a cada apertura y a la ROI")
    s.add_argument("--runs", required=True)
    s.add_argument("--seqinfo", required=True, help="carpeta con <clip>/seqinfo.ini")
    s.add_argument("--clips", required=True, help="clips separados por comas")
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_prep)
    s = sub.add_parser("render", help="pinta cada MOT recortado sobre los frames del clip")
    s.add_argument("--out", required=True)
    s.add_argument("--frames-root", required=True, help="carpeta con <clip>/frames/frame_NNNNNN.png")
    s.set_defaults(fn=cmd_render)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
