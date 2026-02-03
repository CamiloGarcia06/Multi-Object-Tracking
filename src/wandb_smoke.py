import os
import wandb


def main():
    mode = os.getenv("WANDB_MODE", "offline")
    project = os.getenv("WANDB_PROJECT", "mot-thesis")
    run = wandb.init(project=project, mode=mode)
    run.log({"smoke": 1})
    run.finish()
    print("W&B smoke test OK (mode=%s)" % mode)


if __name__ == "__main__":
    main()
