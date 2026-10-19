#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["trackeval>=1.3", "numpy"]
# ///
"""B7 — Tesis 26: lleva a track-studio las corridas de la 17b y las evalúa contra los 5 goldens.

Cada `--runs DIR/<tracker>/<video>.txt` (MOT del video ENTERO, las mismas que lee comparar.py) entra
en track-studio como job importado (`POST /api/jobs/import`): terminado, sin render, con el tracker,
el detector (conf 0,10, NMS 0,6, imgsz 640) y la ROI del montaje sellados, y con su procedencia
(commit de la tesis, ruta y sha256 del MOT). Después cada job se evalúa con `eval_tracking.py publish`
contra los clips de su video, así que las tablas de la web salen de los mismos ficheros que la 17b.

No repite: si ya hay un job con el mismo sha256 en su procedencia, lo reutiliza (y vuelve a publicar
su evaluación, que sustituye a la anterior).

Con `--videos DIR` sube en cambio los videos por apertura de `videos_apertura.py` (Tesis 27): un job
por clip y tracker, con el MOT recortado a la apertura y a la ROI y su render. No se evalúan: son
para verlos (la evaluación es la del video entero).

  TRACK_STUDIO_TOKEN=... uv run scripts/tracking/importar_studio.py --runs data/flow_eval/runs \\
      --gt data/tracking_golden [--api http://track.torre] [--dry-run]
  TRACK_STUDIO_TOKEN=... uv run scripts/tracking/importar_studio.py --videos data/videos_apertura
"""
import argparse, hashlib, json, os, pathlib, subprocess, sys, urllib.error, urllib.request, uuid

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import comparar as C  # noqa: E402
import eval_tracking as ET  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
# nombre de la corrida en runs/ -> yaml del tracker en track-studio (trackers/)
YAML = {"bytetrack_27": "bytetrack_buffer90_match09.yaml", "botsort_osnet": "botsort_osnet.yaml",
        "deepocsort_osnet": "deepocsort_osnet.yaml", "deepocsort_osnet_iou020": "deepocsort_osnet_iou020.yaml",
        "ocsort": "ocsort.yaml"}
SOURCE = {short: video for video, short in C.VIDEOS.items()}   # 02 -> videoTM_02, ...
DETECTOR = {"conf": "0.1", "nms_iou": "0.6", "imgsz": "640"}   # det_video.py: campeón, conf 0,10, NMS post-hoc 0,6


def multipart(fields, file_field, file_name, data, render=None):
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{file_name}"\r\n'
                 f'Content-Type: text/plain\r\n\r\n'.encode() + data + b"\r\n")
    if render is not None:   # (nombre, bytes) del mp4
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="render"; filename="{render[0]}"\r\n'
                     f'Content-Type: video/mp4\r\n\r\n'.encode() + render[1] + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def post_import(api, token, fields, name, data, render=None):
    body, ctype = multipart(fields, "tracks", name, data, render)
    req = urllib.request.Request(f"{api}/api/jobs/import", method="POST", data=body)
    req.add_header("Content-Type", ctype)
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def roi_json(short):
    roi = json.loads((C.CAMERAS / C.ROIS[short]).read_text())
    return json.dumps({"name": pathlib.Path(C.ROIS[short]).stem, "width": roi["width"], "height": roi["height"],
                       "polygon": roi["polygon"]})


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs")
    p.add_argument("--gt")
    p.add_argument("--videos", help="carpeta de videos_apertura.py: sube los videos por apertura")
    p.add_argument("--api", default="http://track.torre")
    p.add_argument("--token", help="por defecto, TRACK_STUDIO_TOKEN")
    p.add_argument("--dry-run", action="store_true", help="dice qué haría, sin importar ni publicar")
    a = p.parse_args()
    api = a.api.rstrip("/")
    token = a.token or os.environ.get("TRACK_STUDIO_TOKEN", "")
    if not token and not a.dry_run:
        sys.exit("falta el token de escritura: --token o TRACK_STUDIO_TOKEN")
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                         cwd=ROOT).stdout.strip() or "sin-git"

    status, body = ET._http("GET", f"{api}/api/jobs")
    if status != 200:
        sys.exit(f"{api}: HTTP {status}")
    known = {}
    for job in json.loads(body):
        origin = job.get("imported_from") or ""
        if "sha256=" in origin:
            known[origin.rsplit("sha256=", 1)[1]] = job["id"]

    if a.videos:
        return import_videos(a, api, token, sha, known)
    if not (a.runs and a.gt):
        sys.exit("hacen falta --runs y --gt (o --videos)")
    runs = pathlib.Path(a.runs)
    jobs = []
    for tracker in sorted(d for d in runs.iterdir() if d.is_dir()):
        if tracker.name not in YAML:
            sys.exit(f"{tracker.name}: no sé con qué yaml de track-studio se corresponde (YAML)")
        for mot in sorted(tracker.glob("*.txt")):
            short = mot.stem
            if short not in SOURCE:
                sys.exit(f"{mot}: video desconocido (comparar.VIDEOS)")
            data = mot.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            frames = max(int(l.split(",", 1)[0]) for l in data.decode().splitlines() if l.strip())
            rel = mot.resolve().relative_to(ROOT) if mot.resolve().is_relative_to(ROOT) else mot
            origin = f"tesis {sha}: {rel} sha256={digest}"
            if digest in known:
                print(f"  {tracker.name}/{short}: ya es el job #{known[digest]}")
                jobs.append(known[digest])
                continue
            fields = {"source_name": f"{SOURCE[short]}.mkv", "tracker": f"trackers/{YAML[tracker.name]}",
                      "frames": str(frames), "imported_from": origin, "roi": roi_json(short), **DETECTOR}
            if a.dry_run:
                print(f"  {tracker.name}/{short}: se importaría como {fields['source_name']} "
                      f"({fields['tracker']}, {frames} frames, ROI {C.ROIS[short]})")
                continue
            status, job = post_import(api, token, fields, mot.name, data)
            if status != 201:
                sys.exit(f"{mot}: track-studio respondió HTTP {status} {str(job)[:300]}")
            print(f"  {tracker.name}/{short}: job #{job['id']} ({job['tracks']} tracks)")
            jobs.append(job["id"])

    for job in jobs:
        print(f"== job #{job}")
        ET.cmd_publish(argparse.Namespace(api=api, token=token, job=job, gt=a.gt, dry_run=a.dry_run))


def import_videos(a, api, token, sha, known):
    for meta_path in sorted(pathlib.Path(a.videos).glob("*/meta.json")):
        meta = json.loads(meta_path.read_text())
        clip, end = meta["clip"], meta["start"] + meta["frames"] - 1
        for tracker, run in meta["runs"].items():
            data = (meta_path.parent / f"{tracker}.txt").read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest in known:
                print(f"  {clip}/{tracker}: ya es el job #{known[digest]}")
                continue
            origin = (f"tesis {sha}: {clip} = {meta['source']} {meta['start']}–{end}, {run['run']} "
                      f"(sha256 {run['run_sha256'][:12]}) recortado a la apertura y a la ROI sha256={digest}")
            fields = {"source_name": f"{clip}.mp4", "tracker": f"trackers/{YAML[tracker]}",
                      "frames": str(meta["frames"]), "imported_from": origin,
                      "roi": json.dumps(meta["roi"]), **DETECTOR}
            render = meta_path.parent / f"{tracker}.mp4"
            if a.dry_run:
                print(f"  {clip}/{tracker}: se importaría con {render.name} ({run['tracks']} tracks)")
                continue
            status, job = post_import(api, token, fields, f"{tracker}.txt", data, (render.name, render.read_bytes()))
            if status != 201:
                sys.exit(f"{clip}/{tracker}: track-studio respondió HTTP {status} {str(job)[:300]}")
            print(f"  {clip}/{tracker}: job #{job['id']} ({job['tracks']} tracks) -> {api}/jobs/{job['id']}")


if __name__ == "__main__":
    main()
