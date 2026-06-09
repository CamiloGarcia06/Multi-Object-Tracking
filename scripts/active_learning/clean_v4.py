#!/usr/bin/env python3
"""bus_head_v4 = bus_head_v3 con etiquetas DEDUPLICADAS.
Clusters de cajas con IoU>0.5 se fusionan en una sola caja (promedio)."""
import os, shutil, glob

SRC="/workspace/data/bus_head_v3"; DST="/workspace/data/bus_head_v4"
THR=0.5

def iou(a,b):
    ax1,ay1,ax2,ay2=a; bx1,by1,bx2,by2=b
    ix1,iy1=max(ax1,bx1),max(ay1,by1); ix2,iy2=min(ax2,bx2),min(ay2,by2)
    iw,ih=max(0,ix2-ix1),max(0,iy2-iy1); inter=iw*ih
    ua=(ax2-ax1)*(ay2-ay1)+(bx2-bx1)*(by2-by1)-inter
    return inter/ua if ua>0 else 0

def dedup(boxes):
    n=len(boxes); parent=list(range(n))
    def find(x):
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    for i in range(n):
        for j in range(i+1,n):
            if iou(boxes[i],boxes[j])>THR: parent[find(i)]=find(j)
    clusters={}
    for i in range(n): clusters.setdefault(find(i),[]).append(boxes[i])
    out=[]
    for cl in clusters.values():
        if len(cl)==1: out.append(cl[0])
        else:
            x1=sum(b[0] for b in cl)/len(cl); y1=sum(b[1] for b in cl)/len(cl)
            x2=sum(b[2] for b in cl)/len(cl); y2=sum(b[3] for b in cl)/len(cl)
            out.append((x1,y1,x2,y2))
    return out

if os.path.exists(DST): shutil.rmtree(DST)
for sp in ("train","val"):
    os.makedirs(f"{DST}/images/{sp}"); os.makedirs(f"{DST}/labels/{sp}")

removed=0; affected=0; total_in=0; total_out=0
for sp in ("train","val"):
    for img in os.listdir(f"{SRC}/images/{sp}"):
        shutil.copy2(f"{SRC}/images/{sp}/{img}", f"{DST}/images/{sp}/{img}")
    for lf in glob.glob(f"{SRC}/labels/{sp}/*.txt"):
        boxes=[]
        for ln in open(lf):
            p=ln.split()
            if len(p)!=5: continue
            _,cx,cy,w,h=map(float,p)
            boxes.append((cx-w/2,cy-h/2,cx+w/2,cy+h/2))
        total_in+=len(boxes)
        ded=dedup(boxes)
        total_out+=len(ded)
        if len(ded)<len(boxes): affected+=1; removed+=len(boxes)-len(ded)
        with open(f"{DST}/labels/{sp}/{os.path.basename(lf)}","w") as fh:
            for x1,y1,x2,y2 in ded:
                cx=min(max((x1+x2)/2,0),1); cy=min(max((y1+y2)/2,0),1)
                w=min(x2-x1,1); h=min(y2-y1,1)
                fh.write(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

print(f"cajas: {total_in} -> {total_out}  (eliminadas {removed} duplicadas en {affected} frames)")
for sp in ("train","val"):
    print(f"  {sp}: {len(os.listdir(f'{DST}/images/{sp}'))} imgs / {len(os.listdir(f'{DST}/labels/{sp}'))} labels")
