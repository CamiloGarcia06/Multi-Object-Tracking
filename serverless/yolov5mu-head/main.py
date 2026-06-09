import base64
import io
import json

import yaml
from PIL import Image
from ultralytics import YOLO


def init_context(context):
    context.logger.info("Init context...  0%")

    with open("/opt/nuclio/function.yaml", "rb") as function_file:
        functionconfig = yaml.safe_load(function_file)

    labels_spec = functionconfig["metadata"]["annotations"]["spec"]
    labels = {item["id"]: item["name"] for item in json.loads(labels_spec)}

    model = YOLO("/opt/nuclio/best.pt")

    context.user_data.model = model
    context.user_data.labels = labels

    context.logger.info("Init context...100%")


def handler(context, event):
    context.logger.info("Run YOLOv5mu head detector")
    data = event.body
    buf = io.BytesIO(base64.b64decode(data["image"]))
    threshold = float(data.get("threshold", 0.25))
    image = Image.open(buf).convert("RGB")

    predictions = context.user_data.model.predict(
        source=image, conf=threshold, verbose=False
    )

    results = []
    labels = context.user_data.labels
    for pred in predictions:
        if pred.boxes is None:
            continue
        for box in pred.boxes:
            cls_id = int(box.cls[0].item())
            if cls_id not in labels:
                continue
            xyxy = box.xyxy[0].tolist()
            results.append(
                {
                    "confidence": str(float(box.conf[0].item())),
                    "label": labels[cls_id],
                    "points": [float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])],
                    "type": "rectangle",
                }
            )

    return context.Response(
        body=json.dumps(results),
        headers={},
        content_type="application/json",
        status_code=200,
    )
