#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["trackeval>=1.3", "numpy"]
# ///
"""B6 — compara trackers por NIVEL DE CONGESTIÓN contra los clips del golden de tracking (OE3, OE4).

Cada clip (`data/tracking_golden/<clip>/`) dice en su seqinfo.ini de qué video sale
(`source`) y dónde empieza (`start`). Las corridas son del video ENTERO:
`--runs DIR/<tracker>/<video>.txt` (video = 07, 02, 03_1). Para cada clip, este script
recorta cada corrida a su tramo y recorta golden y corrida a la ROI del montaje (centro
de la caja, la regla de track-studio, igual que `eval_tracking.py publish`), y pasa
todo a TrackEval con el mismo `evaluate` de eval_tracking.py. Una tabla por clip, que
es un nivel de congestión: tm07_a baja, tm03_1_a media, tm02_a alta.

Uso:
  uv run scripts/tracking/comparar.py --golden data/tracking_golden --runs data/flow_eval/runs \\
      [--md docs/comparacion-trackers.md]
"""
import argparse, configparser, json, pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import eval_tracking as ET  # noqa: E402

CAMERAS = pathlib.Path(__file__).resolve().parents[2] / "configs" / "cameras"
VIDEOS = {"videoTM_07": "07", "videoTM_02": "02", "videoTM_03(1)": "03_1"}
ROIS = {"07": "roi_videoTM_07.json", "02": "roi_videoTM_07.json", "03_1": "roi_videoTM_03_1.json"}   # 02 = montaje del 07
LEVEL = {"07": "baja", "03_1": "media", "02": "alta"}


def lines(path):
    return [l for l in pathlib.Path(path).read_text().splitlines() if l.strip()]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--golden", required=True)
    p.add_argument("--runs", required=True)
    p.add_argument("--md")
    a = p.parse_args()

    seqs = ET.find_sequences(a.golden)
    trackers = sorted(d for d in pathlib.Path(a.runs).iterdir() if d.is_dir())
    with tempfile.TemporaryDirectory() as tmp:
        gt_dir, run_dir = pathlib.Path(tmp, "gt"), pathlib.Path(tmp, "runs")
        clips, levels = {}, {}
        for seq, gt in seqs.items():
            info = ET.seqinfo(gt)
            video, start, n = VIDEOS[info["source"]], int(info["start"]), int(info["seqlength"])
            polygon = [tuple(q) for q in json.loads((CAMERAS / ROIS[video]).read_text())["polygon"]]
            missing = [t.name for t in trackers if not (t / f"{video}.txt").is_file()]
            if missing:
                sys.exit(f"{seq}: falta la corrida de {video} en {', '.join(missing)}")
            (gt_dir / seq).mkdir(parents=True)
            (gt_dir / seq / "gt.txt").write_text("\n".join(ET.inside_roi(lines(gt), polygon)) + "\n")
            (gt_dir / seq / "seqinfo.ini").write_text(f"[Sequence]\nname={seq}\nseqLength={n}\n")
            for t in trackers:
                (run_dir / t.name).mkdir(parents=True, exist_ok=True)
                cut = ET.inside_roi(ET.cut_lines(lines(t / f"{video}.txt"), start, n), polygon)
                (run_dir / t.name / f"{seq}.txt").write_text("\n".join(cut) + "\n")
            clips[seq] = gt_dir / seq / "gt.txt"
            levels[seq] = LEVEL[video]
        results = ET.evaluate(clips, {t.name: run_dir / t.name for t in trackers})

    order = sorted(clips, key=lambda s: ["baja", "media", "alta"].index(levels[s]))
    parts = ["# Trackers por nivel de congestión (golden de tracking)\n",
             "Mismas detecciones (campeón, NMS post-hoc 0,6) y misma ROI para todos: solo cambia la asociación. "
             "Ordenado por HOTA. IoU 0,5 para MOTA/IDF1.\n"]
    for seq in order:
        parts += [f"\n## {seq} — congestión {levels[seq]}\n", ET.table(results, seq)]
    parts += ["\n## Todos los clips\n", ET.table(results, "TODAS")]
    text = "\n".join(parts) + "\n"
    print(text)
    if a.md:
        pathlib.Path(a.md).write_text(text)


if __name__ == "__main__":
    main()
