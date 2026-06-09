#!/usr/bin/env python3
"""bus_head_v3 = bus_head_v2 + 270 frames corregidos (round3b).
Split temporal 85/15 POR CÁMARA en los frames nuevos (val honesto por cámara nueva)."""
import os, shutil, cv2
import xml.etree.ElementTree as ET
from collections import defaultdict

REPO="/workspace"; H_=f"{REPO}/data/_harvest"
EXP=f"{H_}/round3_export"; SRC_V2=f"{REPO}/data/bus_head_v2"; DST=f"{REPO}/data/bus_head_v3"
W,Hh=640.0,480.0

# 1) v3 = copia de v2
if os.path.exists(DST): shutil.rmtree(DST)
for sp in ("train","val"):
    os.makedirs(f"{DST}/images/{sp}"); os.makedirs(f"{DST}/labels/{sp}")
n2=0
for sp in ("train","val"):
    for fn in os.listdir(f"{SRC_V2}/images/{sp}"):
        shutil.copy2(f"{SRC_V2}/images/{sp}/{fn}", f"{DST}/images/{sp}/{fn}"); n2+=1
    for fn in os.listdir(f"{SRC_V2}/labels/{sp}"):
        shutil.copy2(f"{SRC_V2}/labels/{sp}/{fn}", f"{DST}/labels/{sp}/{fn}")
print(f"v2 copiado: {n2} imágenes")

# 2) parsear xml -> por cámara
root=ET.parse(f"{EXP}/annotations.xml").getroot()
bycam=defaultdict(list)  # cam -> [(name, [boxes])]
for im in root.findall("image"):
    name=im.get("name"); cam=name.rsplit("_f",1)[0]
    boxes=[]
    for b in im.findall("box"):
        if b.get("label")!="head": continue
        x1=float(b.get("xtl")); y1=float(b.get("ytl")); x2=float(b.get("xbr")); y2=float(b.get("ybr"))
        cx=min(max(((x1+x2)/2)/W,0),1); cy=min(max(((y1+y2)/2)/Hh,0),1)
        bw=min(abs(x2-x1)/W,1); bh=min(abs(y2-y1)/Hh,1)
        boxes.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    bycam[cam].append((name, boxes))

# 3) split temporal 85/15 por cámara + copiar imagen + label
def find_img(name):
    for sub in ("images","images/default","."):
        p=f"{EXP}/{sub}/{name}"
        if os.path.exists(p): return p
    # búsqueda recursiva fallback
    for r,_,fs in os.walk(f"{EXP}"):
        if name in fs: return f"{r}/{name}"
    return None

added=defaultdict(lambda:[0,0])
for cam, items in bycam.items():
    items.sort(key=lambda x:x[0])
    cut=int(len(items)*0.85)
    for i,(name,boxes) in enumerate(items):
        sp="train" if i<cut else "val"
        src=find_img(name)
        if not src: print(f"  !! falta imagen {name}"); continue
        shutil.copy2(src, f"{DST}/images/{sp}/{name}")
        stem=name.rsplit(".",1)[0]
        with open(f"{DST}/labels/{sp}/{stem}.txt","w") as fh:
            fh.write("\n".join(boxes)+("\n" if boxes else ""))
        added[cam][0 if sp=="train" else 1]+=1
print("nuevos por cámara (train,val):", {k:tuple(v) for k,v in added.items()})

# 4) resumen + verificación
for sp in ("train","val"):
    print(f"  {sp}: {len(os.listdir(f'{DST}/images/{sp}'))} imgs / {len(os.listdir(f'{DST}/labels/{sp}'))} labels")

# viz una corrección
os.makedirs(f"{H_}/r3b_check",exist_ok=True)
sample=sorted(bycam["v16"])[len(bycam["v16"])//2]
img=cv2.imread(find_img(sample[0]));
for line in sample[1]:
    _,cx,cy,bw,bh=map(float,line.split())
    x1=int((cx-bw/2)*W);y1=int((cy-bh/2)*Hh);x2=int((cx+bw/2)*W);y2=int((cy+bh/2)*Hh)
    cv2.rectangle(img,(x1,y1),(x2,y2),(0,255,0),1)
cv2.putText(img,f"{sample[0]} corregido={len(sample[1])}",(5,15),cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,0,255),1)
cv2.imwrite(f"{H_}/r3b_check/v16_corrected.jpg",img)
print("viz:", f"{H_}/r3b_check/v16_corrected.jpg")
