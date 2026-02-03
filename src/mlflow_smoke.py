import os
import mlflow


def main():
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("mot-smoke")
    with mlflow.start_run(run_name="smoke"):
        mlflow.log_param("smoke", "true")
        mlflow.log_metric("metric", 1.0)
    print("MLflow smoke test OK ->", tracking_uri)


if __name__ == "__main__":
    main()
