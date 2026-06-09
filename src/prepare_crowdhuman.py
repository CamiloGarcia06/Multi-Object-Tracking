"""Prepare the Kaggle yolov4_crowdhuman-416x416 dataset for YOLO head training.

Expected input: a Kaggle zip (somashekar1902/crowdhuman) placed at
data/crowdhuman/raw/archive.zip. It contains images and YOLO labels with two
classes (0=head, 1=full body) plus train.txt / test.txt split files.

This script extracts the zip, splits images/labels into train/val based on
those index files, and rewrites labels keeping only the head class.
"""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

from tqdm import tqdm

SRC_SUBDIR = "content/yolov4_crowdhuman/data/crowdhuman-416x416"
HEAD_CLASS_IN = "0"
HEAD_CLASS_OUT = "0"


def extract_zip(zip_path: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    inner = dest / SRC_SUBDIR
    if inner.exists() and any(inner.glob("*.jpg")):
        print(f"Already extracted at {inner}")
        return inner
    print(f"Extracting {zip_path} -> {dest}")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    return inner


def read_split(index_file: Path) -> list[str]:
    stems: list[str] = []
    for line in index_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        stems.append(Path(line).stem)
    return stems


def filter_label(label_src: Path) -> str:
    out_lines: list[str] = []
    for line in label_src.read_text().splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        if parts[0] != HEAD_CLASS_IN:
            continue
        parts[0] = HEAD_CLASS_OUT
        out_lines.append(" ".join(parts))
    return "\n".join(out_lines)


def materialize_split(
    stems: list[str],
    src_dir: Path,
    out_images: Path,
    out_labels: Path,
) -> int:
    out_images.mkdir(parents=True, exist_ok=True)
    out_labels.mkdir(parents=True, exist_ok=True)
    count = 0
    for stem in tqdm(stems, desc=f"{out_images.parent.name}"):
        img_src = src_dir / f"{stem}.jpg"
        lbl_src = src_dir / f"{stem}.txt"
        if not img_src.exists() or not lbl_src.exists():
            continue
        img_dst = out_images / f"{stem}.jpg"
        if not img_dst.exists():
            shutil.copy2(img_src, img_dst)
        (out_labels / f"{stem}.txt").write_text(filter_label(lbl_src))
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zip",
        type=Path,
        default=Path("/workspace/data/crowdhuman/raw/archive.zip"),
        help="Path to the Kaggle CrowdHuman zip.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("/workspace/data/crowdhuman/yolo"),
        help="Output directory in YOLO layout.",
    )
    parser.add_argument(
        "--extract-dir",
        type=Path,
        default=Path("/workspace/data/crowdhuman/extracted"),
        help="Where to extract the zip.",
    )
    args = parser.parse_args()

    src_dir = extract_zip(args.zip, args.extract_dir)
    train_stems = read_split(src_dir / "train.txt")
    val_stems = read_split(src_dir / "test.txt")
    print(f"train={len(train_stems)}, val={len(val_stems)}")

    train_count = materialize_split(
        train_stems, src_dir, args.out / "images/train", args.out / "labels/train"
    )
    val_count = materialize_split(
        val_stems, src_dir, args.out / "images/val", args.out / "labels/val"
    )
    print(f"Done. train={train_count}, val={val_count}")
    print(f"Dataset ready at {args.out}")


if __name__ == "__main__":
    main()
