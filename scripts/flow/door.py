#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "numpy"]
# ///
"""C1 — cuándo está abierta la puerta, a partir del video.

Idea: con la puerta CERRADA los marcos de los vidrios están siempre en el mismo
sitio; al abrirse, las hojas se desplazan y esos bordes desaparecen. Se mide
cuánto se parecen los bordes de cada frame a los de la puerta cerrada:

  1. Recorte de la zona de la puerta (`crop`), en gris y reducido (`scale`),
     una muestra cada `step` frames (ffmpeg).
  2. Mapa de bordes: magnitud del gradiente. El brillo cambia con el sol y
     las sombras; los bordes de los marcos no.
  3. Referencia: MEDIANA de los mapas de bordes de `closed_frames`, frames
     elegidos a mano con la puerta cerrada (la mediana quita al que pasaba).
     O `closed_ref`: esa mediana guardada en .npy (subcomando `ref`), que vale
     para TODOS los videos del mismo montaje: probado el 18-10 en DDR s6, la
     referencia del v11 da en el v18 las mismas 11 aperturas que la propia.
  4. Similitud: correlación cruzada normalizada (NCC) de cada muestra con la
     referencia. Cerrada 0,6–0,95; abierta 0,05–0,2.
  5. Mediana móvil de `smooth` muestras, umbral `threshold` (abierta si la
     similitud es menor) y tramos de al menos `min_frames`.
  6. `exclude`: intervalos revisados a mano y descartados (falsos positivos).
  7. `min_brightness`: si el recorte está casi negro (túnel) no hay bordes que
     comparar y la muestra cuenta como cerrada.

Límite: no sabe qué es una puerta, solo que los bordes de la zona cambiaron.
Lo que se ve a través del vidrio (un bus rojo fuera) o gente de pie delante
puede engañarlo. Todo se ajusta por cámara en `configs/cameras/<cámara>.yaml`.
Solo `closed_frames` es de un video concreto; con `closed_ref` la config es del montaje.

Frames: numerados desde 1, como el MOT (frame 1 = primer frame del video).

Uso:
  uv run scripts/flow/door.py selftest
  uv run scripts/flow/door.py detect --camera configs/cameras/videoTM_07.yaml \\
      --video ~/videos/videoTM_07.mkv --out data/flow_videos/puerta_abierta_videoTM_07.json
  # el video vive en la torre: extraer allí y procesar aquí
  ssh torre "$(uv run scripts/flow/door.py ffmpeg --camera C --video /home/camilo-cachy/videos/videoTM_07.mkv)" > door.raw
  uv run scripts/flow/door.py detect --camera C --raw door.raw --out ...
  # referencia de la puerta cerrada para todo el montaje (closed_frames de ESE video)
  uv run scripts/flow/door.py ref --camera C --raw door.raw --frames 20701 21601 --out configs/cameras/door_ref_X.npy
"""
import argparse, json, pathlib, shlex, subprocess, sys

import numpy as np
import yaml


def load_config(path):
    cfg = yaml.safe_load(pathlib.Path(path).read_text()).get("door_open")
    if not cfg:
        sys.exit(f"{path}: falta la sección door_open")
    if cfg.get("closed_ref"):  # relativa al yaml
        cfg["closed_ref"] = str(pathlib.Path(path).parent / cfg["closed_ref"])
    return cfg


def ffmpeg_args(cfg, video):
    x, y, w, h = cfg["crop"]
    sw, sh = cfg["scale"]
    vf = f"select=not(mod(n\\,{cfg['step']})),crop={w}:{h}:{x}:{y},scale={sw}:{sh},format=gray"
    return ["ffmpeg", "-nostdin", "-v", "error", "-i", video, "-vf", vf,
            "-fps_mode", "passthrough", "-f", "rawvideo", "-"]


def read_samples(cfg, raw):
    sw, sh = cfg["scale"]
    return np.frombuffer(raw, np.uint8).reshape(-1, sh, sw).astype(np.float32)


def edges(a):
    """Magnitud del gradiente por diferencias centrales (bordes a 0)."""
    gx, gy = np.zeros_like(a), np.zeros_like(a)
    gx[..., :, 1:-1] = a[..., :, 2:] - a[..., :, :-2]
    gy[..., 1:-1, :] = a[..., 2:, :] - a[..., :-2, :]
    return np.hypot(gx, gy)


def ncc(stack, ref):
    a = stack.reshape(len(stack), -1)
    a = a - a.mean(1, keepdims=True)
    r = ref.ravel() - ref.mean()
    return (a @ r) / (np.linalg.norm(a, axis=1) * np.linalg.norm(r) + 1e-6)


def similarity(cfg, samples):
    """Similitud de cada muestra con la puerta cerrada. Las muestras casi negras (túnel:
    brillo medio < `min_brightness`) no tienen bordes que comparar: cuentan como cerradas."""
    g = edges(samples)
    ref = np.load(cfg["closed_ref"]) if cfg.get("closed_ref") else closed_reference(cfg, g, cfg["closed_frames"])
    sim = ncc(g, ref)
    sim[samples.mean((1, 2)) < cfg.get("min_brightness", 0)] = 1.0
    return sim


def closed_reference(cfg, g, frames):
    """Mediana de los mapas de bordes `g` en los frames dados (puerta cerrada)."""
    idx = [(f - 1) // cfg["step"] for f in frames]
    if max(idx) >= len(g):
        sys.exit(f"closed_frames: el video solo tiene {len(g) * cfg['step']} frames")
    return np.median(g[idx], 0)


def intervals(cfg, sim):
    """[[inicio, fin], ...] en frames con la puerta abierta, sin los excluidos."""
    step, k = cfg["step"], cfg["smooth"]
    smooth = np.array([np.median(sim[max(0, i - k // 2):i + k // 2 + 1]) for i in range(len(sim))])
    open_ = smooth < cfg["threshold"]
    out, i = [], 0
    while i < len(open_):
        if not open_[i]:
            i += 1
            continue
        j = i
        while j < len(open_) and open_[j]:
            j += 1
        if (j - i) * step >= cfg["min_frames"]:
            out.append([step * i + 1, step * (j - 1) + 1])
        i = j
    drop = [list(e) for e in cfg.get("exclude") or []]
    return [iv for iv in out if iv not in drop]


def cmd_ffmpeg(a):
    print(shlex.join(ffmpeg_args(load_config(a.camera), a.video)))


def samples_of(cfg, a):
    if a.raw:
        raw = pathlib.Path(a.raw).read_bytes()
    else:
        raw = subprocess.run(ffmpeg_args(cfg, a.video), capture_output=True, check=True).stdout
    return read_samples(cfg, raw)


def cmd_ref(a):
    cfg = load_config(a.camera)
    ref = closed_reference(cfg, edges(samples_of(cfg, a)), a.frames or cfg["closed_frames"])
    np.save(a.out, ref.astype(np.float32))
    print(f"{a.out}: referencia {ref.shape} de {len(a.frames or cfg['closed_frames'])} frames", file=sys.stderr)


def cmd_detect(a):
    cfg = load_config(a.camera)
    sim = similarity(cfg, samples_of(cfg, a))
    iv = intervals(cfg, sim)
    pathlib.Path(a.out).write_text(json.dumps(iv) + "\n")
    secs = sum(b - a_ for a_, b in iv) / cfg.get("fps", 30)
    print(f"{a.out}: {len(iv)} intervalos, {secs:.0f} s de puerta abierta "
          f"({len(sim)} muestras; similitud cerrada≈{np.median(sim):.2f})", file=sys.stderr)


def cmd_selftest(_):
    """Video sintético: marcos verticales fijos (cerrada) que desaparecen (abierta)."""
    cfg = {"scale": [34, 60], "step": 3, "smooth": 10, "threshold": 0.35, "min_frames": 45,
           "min_brightness": 40, "closed_frames": [1, 31, 61], "exclude": []}
    rng = np.random.default_rng(0)
    closed = np.full((60, 34), 80.0)
    closed[:, 8:10] = closed[:, 22:24] = 200  # marcos de los vidrios
    n = 600  # muestras = 1.800 frames
    frames = np.stack([closed + rng.normal(0, 3, closed.shape) for _ in range(n)])
    frames[200:300] = rng.normal(120, 25, (100, 60, 34))  # abierta: sin marcos, andén con textura
    frames[400:405] = rng.normal(120, 25, (5, 60, 34))  # alguien pasa 0,5 s: no es apertura
    frames[450:452, 20:40] = 255  # destello en dos muestras
    frames[500:540] = rng.normal(8, 3, (40, 60, 34))  # túnel 4 s: oscuro, sin marcos
    sim = similarity(cfg, frames)
    got = intervals(cfg, sim)
    ok = True
    checks = [
        ("una sola apertura", len(got) == 1),
        ("empieza donde se abre (±1 s)", got and abs(got[0][0] - (3 * 200 + 1)) <= 30),
        ("acaba donde se cierra (±1 s)", got and abs(got[0][1] - (3 * 299 + 1)) <= 30),
        ("cerrada se parece a la referencia (>0,6)", np.median(sim[:200]) > 0.6),
        ("abierta no se parece (<0,35)", np.median(sim[200:300]) < 0.35),
        ("el túnel no es apertura", all(b < 3 * 500 or a_ > 3 * 540 for a_, b in got)),
        ("exclude quita un intervalo", intervals({**cfg, "exclude": got}, sim) == []),
    ]
    # closed_ref: la referencia guardada da lo mismo que closed_frames
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".npy") as f:
        np.save(f.name, closed_reference(cfg, edges(frames), cfg["closed_frames"]))
        same = intervals(cfg, similarity({**cfg, "closed_ref": f.name}, frames)) == got
    checks.append(("closed_ref equivale a closed_frames", same))
    for name, cond in checks:
        ok &= bool(cond)
        print(f"{'OK  ' if cond else 'FALLO'}  {name}")
    sys.exit(0 if ok else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("detect")
    s.add_argument("--camera", required=True)
    src = s.add_mutually_exclusive_group(required=True)
    src.add_argument("--video")
    src.add_argument("--raw", help="salida de `door.py ffmpeg` ya extraída (p. ej. en la torre)")
    s.add_argument("--out", required=True)
    s = sub.add_parser("ref", help="guarda la referencia de puerta cerrada (.npy) para todo el montaje")
    s.add_argument("--camera", required=True)
    src = s.add_mutually_exclusive_group(required=True)
    src.add_argument("--video")
    src.add_argument("--raw")
    s.add_argument("--frames", type=int, nargs="+", help="frames con la puerta cerrada (por defecto closed_frames)")
    s.add_argument("--out", required=True)
    s = sub.add_parser("ffmpeg", help="imprime el comando de extracción, para correrlo donde está el video")
    s.add_argument("--camera", required=True)
    s.add_argument("--video", required=True)
    sub.add_parser("selftest")
    a = p.parse_args()
    {"detect": cmd_detect, "ref": cmd_ref, "ffmpeg": cmd_ffmpeg, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    main()
