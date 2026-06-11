#!/usr/bin/env python3
"""Comparativa BASE vs R2 vs R3 vs R4 vs R5 en frames NO vistos y llenos (videoTM_02).
Config = la desplegada: conf=0.25, NMS iou=0.5. Selector de frames = R5 (campeón)."""
import cv2, numpy as np
from ultralytics import YOLO

VIDEO = "/videos/videoTM_02.mkv"   # cámara unseen (golden source, no se entrena con ella)
CONF, IOU = 0.25, 0.5
MODELS = [
    ("BASE (CrowdHuman)", "/workspace/models/yolov5mu-head-base.pt",                       (170,170,170)),
    ("R2",                "/workspace/outputs/head_detector/yolo-bus-head-r2/weights/best.pt", (0,165,255)),
    ("R3",                "/workspace/outputs/head_detector/yolo-bus-head-r3/weights/best.pt", (0,255,0)),
    ("R4",                "/workspace/outputs/head_detector/yolo-bus-head-r4/weights/best.pt", (255,200,0)),
    ("R5 (desplegado)",   "/workspace/outputs/head_detector/yolo-bus-head-r5/weights/best.pt", (255,0,255)),
]
models = [(n, YOLO(p), c) for n,p,c in MODELS]
sel = models[-1][1]  # R5 como selector

# 1) frames brillantes y MUY concurridos según R5
cap = cv2.VideoCapture(VIDEO); idx=0; cands=[]
while True:
    ret,img=cap.read()
    if not ret: break
    if idx%40==0 and img.mean()>=70:
        n=len(sel.predict(img,conf=CONF,iou=IOU,verbose=False)[0].boxes)
        cands.append((n,idx,img.copy()))
    idx+=1
cap.release()
cands.sort(reverse=True, key=lambda t:t[0])
picks=[]; used=[]
for n,i,img in cands:
    if all(abs(i-u)>800 for u in used):
        picks.append((i,img)); used.append(i)
    if len(picks)==3: break
print("frames elegidos:", [i for i,_ in picks])

# 2) panel por modelo
def draw(img, model, color, name):
    im=img.copy()
    r=model.predict(im,conf=CONF,iou=IOU,verbose=False)[0]
    boxes=r.boxes.xyxy.cpu().numpy() if r.boxes is not None else []
    for b in boxes:
        x1,y1,x2,y2=map(int,b); cv2.rectangle(im,(x1,y1),(x2,y2),color,2)
    cv2.rectangle(im,(0,0),(im.shape[1],26),(0,0,0),-1)
    cv2.putText(im,f"{name}: {len(boxes)} cabezas",(6,18),cv2.FONT_HERSHEY_SIMPLEX,0.6,color,2)
    return im

for k,(i,img) in enumerate(picks):
    panels=[draw(img,m,c,n) for n,m,c in models]
    out=np.hstack(panels)
    p=f"/workspace/data/_harvest/cmp_all_{k+1}_f{i:06d}.jpg"
    cv2.imwrite(p,out); print("guardado",p)
