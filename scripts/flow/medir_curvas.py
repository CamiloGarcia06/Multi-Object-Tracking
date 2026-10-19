#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pyyaml", "pillow"]
# ///
"""¿Están bien puestas las curvas de la puerta? Método del 07, medido con detecciones.

Con la puerta CERRADA (lejos ±150 f de toda apertura) todas las cabezas son de pasajeros
que van dentro: ninguna debería pasar la curva exterior, y la interior va pegada a las
que más se acercan a la puerta (en el 07: "abajo llegan a x≈480, pegadas a la interior").

  margen: cuántas cabezas pasan cada curva (conf 0,1 / 0,3 / 0,5) y percentiles 0,1/1/5 de
          su distancia a la interior (px; negativo = más allá, hacia la puerta).
  mapa:   densidad de cabezas sobre un frame: azul = puerta cerrada, rojo = abierta, con
          la curva interior (verde) y la exterior (magenta).

Detecciones: salida de det_video.py (frame desde 1, x1, y1, x2, y2, conf, cls).
Aperturas: JSON de door.py detect. Las curvas se leen de `door` en el yaml de la cámara.
  uv run scripts/flow/medir_curvas.py margen --dets D.npy --camera C.yaml --puerta P.json
  uv run scripts/flow/medir_curvas.py mapa --dets D.npy --camera C.yaml --puerta P.json --fondo F.png --out M.png
"""
import argparse, json

import numpy as np
import yaml

LEJOS = 150  # frames alrededor de cada apertura que no cuentan como "cerrada"


def cargar(a):
    d = np.load(a.dets)
    door = yaml.safe_load(open(a.camera))["door"]
    iv = json.load(open(a.puerta))
    f, cx, cy, c = d[:, 0], (d[:, 1] + d[:, 3]) / 2, (d[:, 2] + d[:, 4]) / 2, d[:, 5]
    abierta, lejos = np.zeros(len(d), bool), np.ones(len(d), bool)
    for s, e in iv:
        abierta |= (f >= s) & (f <= e)
        lejos &= ~((f >= s - LEJOS) & (f <= e + LEJOS))
    return door, cx, cy, c, abierta, lejos


def distancia(door, k, cx, cy):
    p = np.array(door[k], float)
    return cx - np.interp(cy, p[:, 1], p[:, 0])  # puerta a la IZQUIERDA del frame


def cmd_margen(a):
    door, cx, cy, c, _, lejos = cargar(a)
    signo = -1 if a.puerta_derecha else 1
    for conf in (0.1, 0.3, 0.5):
        m = lejos & (c >= conf)
        txt = " · ".join(f"{k}: {int((signo * distancia(door, k, cx[m], cy[m]) < 0).sum())}" for k in ("inner", "outer"))
        print(f"conf≥{conf}: {int(m.sum())} cabezas con la puerta cerrada · pasan {txt}")
    m = lejos & (c >= 0.3)
    print("distancia a la interior (px), percentiles 0,1/1/5:",
          np.percentile(signo * distancia(door, "inner", cx[m], cy[m]), [0.1, 1, 5]).round(1))


def cmd_mapa(a):
    from PIL import Image, ImageDraw
    door, cx, cy, c, abierta, lejos = cargar(a)
    m = c >= 0.3
    img = np.asarray(Image.open(a.fondo).convert("RGB"), float) * 0.45

    def capa(sel, color):
        h, _, _ = np.histogram2d(cy[sel], cx[sel], bins=[96, 128], range=[[0, 480], [0, 640]])
        h = np.log1p(h)
        return np.kron(h / max(h.max(), 1), np.ones((5, 5)))[..., None] * np.array(color, float)

    img = np.clip(img + capa(m & lejos, (90, 160, 255)) + capa(m & abierta, (255, 60, 60)), 0, 255)
    im = Image.fromarray(img.astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.line([tuple(p) for p in door["inner"]], fill=(0, 255, 80), width=2)
    d.line([tuple(p) for p in door["outer"]], fill=(255, 0, 200), width=2)
    im.save(a.out)
    print(a.out)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("margen", "mapa"):
        s = sub.add_parser(name)
        s.add_argument("--dets", required=True)
        s.add_argument("--camera", required=True)
        s.add_argument("--puerta", required=True, help="JSON de door.py detect")
        s.add_argument("--puerta-derecha", action="store_true", help="montaje del 07: la puerta a la DERECHA")
        if name == "mapa":
            s.add_argument("--fondo", required=True)
            s.add_argument("--out", required=True)
    a = p.parse_args()
    {"margen": cmd_margen, "mapa": cmd_mapa}[a.cmd](a)


if __name__ == "__main__":
    main()
