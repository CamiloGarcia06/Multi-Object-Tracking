"""Fine-tune YOLO26 on CrowdHuman heads using the local GPU."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from ultralytics import YOLO, settings

settings.update({"mlflow": True})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default="yolo26m.pt",
        help="Base model checkpoint (yolo26n/s/m/l/x.pt). Defaults to yolo26m for 16GB GPUs.",
    )
    parser.add_argument(
        "--data",
        default="/workspace/data/crowdhuman_head.yaml",
        help="Path to dataset YAML.",
    )
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument(
        "--batch",
        type=float,
        default=0.85,
        help="Batch size. If <1.0, interpreted as target GPU memory fraction (0.85 ≈ 14/16 GB on a 16 GB GPU).",
    )
    parser.add_argument(
        "--cache",
        default="disk",
        choices=["ram", "disk", "false"],
        help="Cache images on disk (low RAM) or RAM (fast, needs lots of RAM).",
    )
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--name", default="yolo26m-crowdhuman-head")
    parser.add_argument(
        "--project",
        default="/workspace/outputs/head_detector",
        help="Where to save run artifacts.",
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available — refusing to train on CPU.")
    print(f"Training on {torch.cuda.get_device_name(0)} ({torch.cuda.device_count()} GPU)")

    Path(args.project).mkdir(parents=True, exist_ok=True)

    batch = int(args.batch) if args.batch >= 1 else args.batch

    model = YOLO(args.model)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=batch,
        device=0,
        project=args.project,
        name=args.name,
        resume=args.resume,
        amp=True,
        cache=False if args.cache == "false" else args.cache,
        workers=args.workers,
        patience=15,
    )


if __name__ == "__main__":
    main()
