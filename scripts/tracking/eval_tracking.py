#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["trackeval>=1.3", "numpy"]
# ///
"""B3 — evalua trackers contra el golden de tracking con TrackEval.

Compara N trackers sobre las MISMAS secuencias anotadas y saca una tabla con:
  - HOTA  = sqrt(DetA * AssA): la metrica principal. Separa cuanto del error es
            de deteccion (DetA) y cuanto de asociacion (AssA).
  - IDF1  : que fraccion de las cajas lleva el ID correcto de principio a fin.
  - MOTA  : dominada por la deteccion; se reporta por convencion, no decide.
  - IDSW  : cambios de identidad. Frag: veces que un track real se interrumpe.

Como el detector es el mismo para todos los trackers, DetA sale casi igual y lo
que decide es AssA / IDF1 / IDSW.

OJO: sin golden anotado esto NO se puede correr. Las estadisticas de continuidad
(tracks, mediana, p90) NO lo sustituyen: un intercambio de identidad las mejora.

Estructura esperada:
  --gt   DIR/<secuencia>/gt/gt.txt      (lo que exporta CVAT como "MOT 1.1")
  --runs DIR/<tracker>/<secuencia>.txt  (frame,id,x,y,w,h,conf,-1,-1,-1)
Los frames de las dos partes van numerados desde 1 sobre el MISMO clip. Si la
corrida es del video entero y el golden es un tramo, recortar antes con `cut`.

Uso (autocontenido, sin contenedor):
  uv run scripts/tracking/eval_tracking.py selftest
  uv run scripts/tracking/eval_tracking.py cut --tracks full.txt --start 3600 --frames 300 --out runs/bytetrack/tm07_a.txt
  uv run scripts/tracking/eval_tracking.py eval --gt data/tracking_golden --runs runs --md docs/tracking_baseline.md
"""
import argparse, configparser, pathlib, shutil, sys, tempfile

import numpy as np

BENCH, SPLIT, CLS = "BUS", "golden", "pedestrian"   # 'pedestrian' es solo la etiqueta interna de TrackEval
COLS = ["HOTA", "DetA", "AssA", "IDF1", "MOTA", "IDSW", "Frag", "GT_IDs", "IDs"]


def last_frame(path):
    frames = [int(float(l.split(",")[0])) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]
    return max(frames, default=0)


def find_sequences(gt_dir):
    """{secuencia: ruta al gt.txt}. Acepta <seq>/gt/gt.txt (CVAT) y <seq>/gt.txt."""
    seqs = {}
    for d in sorted(p for p in pathlib.Path(gt_dir).iterdir() if p.is_dir()):
        for cand in (d / "gt" / "gt.txt", d / "gt.txt"):
            if cand.is_file():
                seqs[d.name] = cand
                break
    return seqs


def seq_length(seq_dir, files):
    """seqinfo.ini manda si existe; si no, el ultimo frame que aparezca en cualquier fichero."""
    ini = pathlib.Path(seq_dir) / "seqinfo.ini"
    if ini.is_file():
        cp = configparser.ConfigParser(); cp.read(ini)
        return int(cp["Sequence"]["seqLength"])
    return max(last_frame(f) for f in files)


def build_layout(root, seqs, runs):
    """Arma en `root` el arbol que espera TrackEval (MOTChallenge) con copias."""
    gt_root = root / "gt" / f"{BENCH}-{SPLIT}"
    tr_root = root / "trackers" / f"{BENCH}-{SPLIT}"
    (root / "gt" / "seqmaps").mkdir(parents=True)
    (root / "gt" / "seqmaps" / f"{BENCH}-{SPLIT}.txt").write_text("name\n" + "\n".join(seqs) + "\n")
    for seq, gt in seqs.items():
        files = [gt] + [r / f"{seq}.txt" for r in runs.values()]
        n = seq_length(gt.parent.parent if gt.parent.name == "gt" else gt.parent, files)
        (gt_root / seq / "gt").mkdir(parents=True)
        shutil.copy(gt, gt_root / seq / "gt" / "gt.txt")
        (gt_root / seq / "seqinfo.ini").write_text(f"[Sequence]\nname={seq}\nseqLength={n}\n")
        for name, run in runs.items():
            (tr_root / name / "data").mkdir(parents=True, exist_ok=True)
            shutil.copy(run / f"{seq}.txt", tr_root / name / "data" / f"{seq}.txt")


def evaluate(seqs, runs):
    """-> {tracker: {secuencia | 'TODAS': {columna: valor}}}"""
    import trackeval

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        build_layout(root, seqs, runs)
        ecfg = trackeval.Evaluator.get_default_eval_config()
        ecfg.update(USE_PARALLEL=False, BREAK_ON_ERROR=True, PRINT_RESULTS=False, PRINT_CONFIG=False,
                    TIME_PROGRESS=False, DISPLAY_LESS_PROGRESS=True, OUTPUT_SUMMARY=False,
                    OUTPUT_DETAILED=False, PLOT_CURVES=False, OUTPUT_EMPTY_CLASSES=False)
        dcfg = trackeval.datasets.MotChallenge2DBox.get_default_dataset_config()
        # DO_PREPROC=False: el preproceso de MOTChallenge quita "distractores" (ciclistas,
        # reflejos...) por id de clase; aqui hay una sola clase y no hay nada que quitar.
        dcfg.update(GT_FOLDER=str(root / "gt"), TRACKERS_FOLDER=str(root / "trackers"),
                    OUTPUT_FOLDER=str(root / "out"), BENCHMARK=BENCH, SPLIT_TO_EVAL=SPLIT,
                    TRACKERS_TO_EVAL=list(runs), DO_PREPROC=False, PRINT_CONFIG=False)
        mcfg = {"THRESHOLD": 0.5, "PRINT_CONFIG": False}
        metrics = [trackeval.metrics.HOTA(mcfg), trackeval.metrics.CLEAR(mcfg), trackeval.metrics.Identity(mcfg)]
        res, _ = trackeval.Evaluator(ecfg).evaluate([trackeval.datasets.MotChallenge2DBox(dcfg)], metrics)

    out = {}
    for name in runs:
        out[name] = {}
        for seq, per_cls in res["MotChallenge2DBox"][name].items():
            m = per_cls[CLS]
            out[name]["TODAS" if seq == "COMBINED_SEQ" else seq] = {
                "HOTA": 100 * float(np.mean(m["HOTA"]["HOTA"])),
                "DetA": 100 * float(np.mean(m["HOTA"]["DetA"])),
                "AssA": 100 * float(np.mean(m["HOTA"]["AssA"])),
                "IDF1": 100 * float(m["Identity"]["IDF1"]),
                "MOTA": 100 * float(m["CLEAR"]["MOTA"]),
                "IDSW": int(m["CLEAR"]["IDSW"]),
                "Frag": int(m["CLEAR"]["Frag"]),
                "GT_IDs": int(m["Count"]["GT_IDs"]) if "Count" in m else int(m["HOTA"].get("GT_IDs", 0)),
                "IDs": int(m["Count"]["IDs"]) if "Count" in m else int(m["HOTA"].get("IDs", 0)),
            }
    return out


def table(results, seq):
    rows = ["| tracker | " + " | ".join(COLS) + " |", "|---|" + "---|" * len(COLS)]
    order = sorted(results, key=lambda t: -results[t][seq]["HOTA"])
    for name in order:
        r = results[name][seq]
        cells = [f"{r[c]:.1f}" if isinstance(r[c], float) else str(r[c]) for c in COLS]
        rows.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def report(results, seqs):
    parts = ["# Comparacion de trackers contra el golden de tracking\n",
             f"Secuencias: {', '.join(seqs)}. Ordenado por HOTA. IoU 0,5 para MOTA/IDF1; HOTA promedia 0,05-0,95.\n",
             "## Todas las secuencias\n", table(results, "TODAS")]
    for seq in seqs:
        parts += [f"\n## {seq}\n", table(results, seq)]
    return "\n".join(parts) + "\n"


def cmd_eval(a):
    seqs = find_sequences(a.gt)
    if not seqs:
        sys.exit(f"no hay secuencias con gt.txt en {a.gt}")
    runs = {d.name: d for d in sorted(pathlib.Path(a.runs).iterdir()) if d.is_dir()}
    for name, d in list(runs.items()):
        missing = [s for s in seqs if not (d / f"{s}.txt").is_file()]
        if missing:   # comparar trackers sobre secuencias distintas no es comparar
            sys.exit(f"al tracker '{name}' le faltan secuencias: {', '.join(missing)}")
    if not runs:
        sys.exit(f"no hay carpetas de tracker en {a.runs}")
    results = evaluate(seqs, runs)
    if any(r["TODAS"]["GT_IDs"] == 0 for r in results.values()):
        # TrackEval descarta en silencio las filas de gt cuya 7a columna no es 1
        sys.exit("el golden quedo vacio: la 7a columna de gt.txt debe ser 1 (asi lo exporta CVAT)")
    text = report(results, list(seqs))
    print(text)
    if a.md:
        pathlib.Path(a.md).write_text(text)


def cmd_cut(a):
    """Recorta [start, start+frames) de una corrida y renumera desde 1."""
    kept = []
    for line in pathlib.Path(a.tracks).read_text().splitlines():
        parts = line.split(",")
        f = int(float(parts[0]))
        if a.start <= f < a.start + a.frames:
            kept.append(",".join([str(f - a.start + 1)] + parts[1:]))
    out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(kept) + "\n")
    print(f"{len(kept)} cajas, frames {a.start}-{a.start + a.frames - 1} -> 1-{a.frames}: {out}")


def cmd_selftest(_):
    """Evaluacion real sobre un caso minimo con respuesta conocida (lo pedia B0).

    Dos cabezas, 100 frames. Si TrackEval o este script estuvieran mal montados,
    alguna de estas cuentas no saldria.
    """
    def box(f, i):   # cabeza i: 40x40, se mueve 2 px/frame, a 200 px de la otra
        return (f, 100 + 2 * f, 100 + 200 * i, 40, 40)

    def write(path, rows, gt=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        tail = "1,1,1" if gt else "0.9,-1,-1,-1"
        path.write_text("".join(f"{f},{i},{x},{y},{w},{h},{tail}\n" for i, (f, x, y, w, h) in rows))

    F = range(1, 101)
    cases = {
        "perfecto": [(i + 1, box(f, i)) for f in F for i in (0, 1)],
        # a mitad del clip los dos IDs se cruzan: deteccion perfecta, identidad rota
        "intercambio": [((i if f <= 50 else 1 - i) + 1, box(f, i)) for f in F for i in (0, 1)],
        # a la cabeza 0 le cambian el numero a mitad: fragmentacion
        "fragmentado": [((3 if (i == 0 and f > 50) else i + 1), box(f, i)) for f in F for i in (0, 1)],
        # la cabeza 1 no se detecta la segunda mitad: error de deteccion puro
        "pierde_media": [(i + 1, box(f, i)) for f in F for i in (0, 1) if not (i == 1 and f > 50)],
    }
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        write(tmp / "gt" / "sintetica" / "gt" / "gt.txt", cases["perfecto"], gt=True)
        for name, rows in cases.items():
            write(tmp / "runs" / name / "sintetica.txt", rows)
        res = evaluate(find_sequences(tmp / "gt"), {n: tmp / "runs" / n for n in cases})
    print(table(res, "TODAS"))
    r = {n: res[n]["TODAS"] for n in cases}
    checks = [
        ("perfecto: HOTA 100, IDF1 100, 0 IDSW", r["perfecto"]["HOTA"] > 99.9 and r["perfecto"]["IDF1"] > 99.9 and r["perfecto"]["IDSW"] == 0),
        ("intercambio: DetA 100 pero AssA cae", r["intercambio"]["DetA"] > 99.9 and r["intercambio"]["AssA"] < 60),
        ("intercambio: 2 IDSW e IDF1 = 50", r["intercambio"]["IDSW"] == 2 and abs(r["intercambio"]["IDF1"] - 50) < 0.1),
        ("fragmentado: 1 IDSW, DetA 100, AssA < 100", r["fragmentado"]["IDSW"] == 1 and r["fragmentado"]["DetA"] > 99.9 and r["fragmentado"]["AssA"] < 99),
        ("pierde_media: 0 IDSW y DetA 75 (se pierde 1 de cada 4 cajas)", r["pierde_media"]["IDSW"] == 0 and abs(r["pierde_media"]["DetA"] - 75) < 0.1),
        ("el intercambio puntua peor que la fragmentacion", r["intercambio"]["HOTA"] < r["fragmentado"]["HOTA"]),
    ]
    for label, ok in checks:
        print(("OK   " if ok else "FALLA"), label)
    sys.exit(0 if all(ok for _, ok in checks) else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval", help="tabla HOTA/IDF1/MOTA/IDSW de cada tracker")
    e.add_argument("--gt", required=True); e.add_argument("--runs", required=True)
    e.add_argument("--md", help="escribe tambien la tabla en este .md")
    e.set_defaults(fn=cmd_eval)
    c = sub.add_parser("cut", help="recorta un tramo de una corrida y renumera los frames desde 1")
    c.add_argument("--tracks", required=True); c.add_argument("--start", type=int, required=True)
    c.add_argument("--frames", type=int, required=True); c.add_argument("--out", required=True)
    c.set_defaults(fn=cmd_cut)
    s = sub.add_parser("selftest", help="comprueba TrackEval con un caso de respuesta conocida")
    s.set_defaults(fn=cmd_selftest)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
