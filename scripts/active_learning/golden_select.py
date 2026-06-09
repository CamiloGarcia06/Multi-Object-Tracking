#!/usr/bin/env python3
"""Selecciona frames para el GOLDEN TEST SET (representativo, sin fuga de datos).
- video02: 100 frames (cámara NO vista) estratificados por nivel de gente y tiempo.
- video05/16/18(1): ~17 c/u, en frames LEJOS (>200) de los usados en train.
Salida: data/golden/candidates/*.jpg + manifest.csv + golden_to_annotate.zip-ready dir.
"""
import os, glob, cv2, csv
import numpy as np
from ultralytics import YOLO

R3="/workspace/outputs/head_detector/yolo-bus-head-r3/weights/best.pt"
V3="/workspace/data/bus_head_v3"
OUT="/workspace/data/golden/candidates"
os.makedirs(OUT, exist_ok=True)
m=YOLO(R3)

# 1) frames YA usados en train/val, por archivo de video (para evitar fuga)
TAG2VID={"v05":"videoTM_05.mkv","v16":"videoTM_16.mkv","v18S08":"videoTM_18(1).mkv",
         "v04":"videoTM_04.mkv","v16b":"videoTM_16(1).mkv","v10b":"videoTM_10(1).mkv"}
used={v:set() for v in set(TAG2VID.values())}
for sp in ("train","val"):
    for p in glob.glob(f"{V3}/images/{sp}/*.jpg"):
        name=os.path.basename(p)
        for tag,vid in TAG2VID.items():
            if name.startswith(tag+"_f"):
                try: used[vid].add(int(name.split("_f")[1].split(".")[0]))
                except: pass
                break

def far_from_used(idx, vid, gap=200):
    return all(abs(idx-u)>gap for u in used.get(vid, set()))

# 2) recolectar candidatos (bright + con gente), con conteo R3
def collect(fn, step, need_far=None):
    cap=cv2.VideoCapture(f"/videos/{fn}"); idx=0; out=[]
    while True:
        ret,img=cap.read()
        if not ret: break
        if idx%step==0 and img.mean()>=60:
            if need_far is None or far_from_used(idx, need_far):
                n=len(m.predict(img,conf=0.25,iou=0.5,verbose=False)[0].boxes)
                if n>=2: out.append((idx,n,float(img.mean()),img.copy()))
        idx+=1
    cap.release(); return out

# 3) selección estratificada por nivel de gente + reparto temporal
def stratify(cands, target):
    bins={"baja":[c for c in cands if 2<=c[1]<=4],
          "media":[c for c in cands if 5<=c[1]<=8],
          "alta":[c for c in cands if c[1]>=9]}
    per=max(1,target//3); sel=[]
    for b,items in bins.items():
        items.sort(key=lambda x:x[0])
        if not items: continue
        k=min(per,len(items)); stepf=len(items)/k
        sel+=[items[int(i*stepf)] for i in range(k)]
    # completar si faltó
    if len(sel)<target:
        extra=sorted([c for c in cands if c not in sel], key=lambda x:x[0])
        sel+=extra[:target-len(sel)]
    return sel[:target]

PLAN=[("video02","videoTM_02.mkv",15,None,100),
      ("v05","videoTM_05.mkv",20,"videoTM_05.mkv",17),
      ("v16","videoTM_16.mkv",20,"videoTM_16.mkv",17),
      ("S08","videoTM_18(1).mkv",20,"videoTM_18(1).mkv",17)]

rows=[]
for tag,fn,step,far,target in PLAN:
    c=collect(fn,step,far)
    sel=stratify(c,target)
    for idx,n,lum,img in sorted(sel,key=lambda x:x[0]):
        stem=f"golden_{tag}_f{idx:06d}"
        cv2.imwrite(f"{OUT}/{stem}.jpg",img)
        rows.append([stem,tag,idx,n,f"{lum:.0f}"])
    print(f"{tag}: candidatos={len(c)} seleccionados={len(sel)} "
          f"(baja={sum(1 for _,n,_,_ in sel if n<=4)} media={sum(1 for _,n,_,_ in sel if 5<=n<=8)} alta={sum(1 for _,n,_,_ in sel if n>=9)})")

with open(f"{OUT}/../manifest.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["stem","camara","frame","R3_count","luminancia"]); w.writerows(rows)
print(f"\nTOTAL golden: {len(rows)} frames en {OUT}")
