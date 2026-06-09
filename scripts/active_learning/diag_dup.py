#!/usr/bin/env python3
"""Diagnóstico de duplicados: (A) cajas casi-duplicadas en labels de v3,
(B) efecto del umbral NMS (iou) en inferencia R3 sobre frames problemáticos."""
import os, glob, cv2, numpy as np
from ultralytics import YOLO

DST="/workspace/data/bus_head_v3"

def iou(a,b):
    ax1,ay1,ax2,ay2=a; bx1,by1,bx2,by2=b
    ix1,iy1=max(ax1,bx1),max(ay1,by1); ix2,iy2=min(ax2,bx2),min(ay2,by2)
    iw,ih=max(0,ix2-ix1),max(0,iy2-iy1); inter=iw*ih
    ua=(ax2-ax1)*(ay2-ay1)+(bx2-bx1)*(by2-by1)-inter
    return inter/ua if ua>0 else 0

# ---- (A) auditar labels ----
print("=== (A) Cajas casi-duplicadas en bus_head_v3 (IoU intra-frame) ===")
for thr in (0.5,0.7):
    files=glob.glob(f"{DST}/labels/train/*.txt")+glob.glob(f"{DST}/labels/val/*.txt")
    dup_pairs=0; frames_with_dup=0; total_boxes=0
    for f in files:
        boxes=[]
        for ln in open(f):
            p=ln.split()
            if len(p)!=5: continue
            _,cx,cy,w,h=map(float,p)
            boxes.append((cx-w/2,cy-h/2,cx+w/2,cy+h/2))
        total_boxes+=len(boxes)
        fd=0
        for i in range(len(boxes)):
            for j in range(i+1,len(boxes)):
                if iou(boxes[i],boxes[j])>thr: fd+=1
        if fd: frames_with_dup+=1; dup_pairs+=fd
    print(f"  IoU>{thr}: {dup_pairs} pares duplicados en {frames_with_dup} frames "
          f"(de {len(files)} frames, {total_boxes} cajas)")

# ---- (B) efecto del NMS iou en R3 ----
print("\n=== (B) Efecto del umbral NMS (iou) en R3 — frames problemáticos ===")
r3=YOLO("/workspace/outputs/head_detector/yolo-bus-head-r3/weights/best.pt")
VIDEO="/videos/videoTM_02.mkv"
TARGETS=[1480,3280,9360]
cap=cv2.VideoCapture(VIDEO); frames={}; idx=0
while True:
    ret,img=cap.read()
    if not ret: break
    if idx in TARGETS: frames[idx]=img.copy()
    idx+=1
    if idx>max(TARGETS): break
cap.release()

colors=[(0,255,0),(0,200,255),(255,150,0)]
for fi,img in frames.items():
    print(f"\n frame {fi}:")
    panels=[]
    for k,iouv in enumerate([0.7,0.5,0.45]):
        im=img.copy()
        r=r3.predict(im,conf=0.25,iou=iouv,verbose=False)[0]
        b=r.boxes.xyxy.cpu().numpy() if r.boxes is not None else []
        for x1,y1,x2,y2 in b:
            cv2.rectangle(im,(int(x1),int(y1)),(int(x2),int(y2)),colors[k],2)
        cv2.rectangle(im,(0,0),(im.shape[1],26),(0,0,0),-1)
        cv2.putText(im,f"iou={iouv}: {len(b)}",(6,18),cv2.FONT_HERSHEY_SIMPLEX,0.6,colors[k],2)
        panels.append(im); print(f"   iou={iouv} -> {len(b)} cajas")
    cv2.imwrite(f"/workspace/data/_harvest/nms_{fi}.jpg",np.hstack(panels))
