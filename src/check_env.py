import os
import torch


def main():
    print("PyTorch:", torch.__version__)
    cuda_available = torch.cuda.is_available()
    print("CUDA available:", cuda_available)
    if cuda_available:
        print("CUDA device count:", torch.cuda.device_count())
        print("CUDA device name:", torch.cuda.get_device_name(0))
    try:
        import trackeval  # noqa: F401
        print("TrackEval: import OK")
    except Exception as exc:
        print("TrackEval: import FAILED")
        raise

    print("WANDB_MODE:", os.getenv("WANDB_MODE"))
    print("MLFLOW_TRACKING_URI:", os.getenv("MLFLOW_TRACKING_URI"))


if __name__ == "__main__":
    main()
