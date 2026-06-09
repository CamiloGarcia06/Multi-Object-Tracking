import os, glob, shutil
import xml.etree.ElementTree as ET
EXP="/workspace/data/golden/golden_export"; DST="/workspace/data/golden"; W,H=640.0,480.0
os.makedirs(f"{DST}/images/val",exist_ok=True); os.makedirs(f"{DST}/labels/val",exist_ok=True)
# limpiar previos
for d in (f"{DST}/images/val",f"{DST}/labels/val"):
    for f in glob.glob(f"{d}/*"): os.remove(f)
def findimg(name):
    for r,_,fs in os.walk(EXP):
        if name in fs: return f"{r}/{name}"
    return None
root=ET.parse(f"{EXP}/annotations.xml").getroot(); n=0
for im in root.findall("image"):
    name=im.get("name"); src=findimg(name)
    if not src: print("falta",name); continue
    shutil.copy2(src,f"{DST}/images/val/{name}")
    stem=name.rsplit(".",1)[0]
    with open(f"{DST}/labels/val/{stem}.txt","w") as fh:
        for b in im.findall("box"):
            if b.get("label")!="head": continue
            x1,y1,x2,y2=float(b.get("xtl")),float(b.get("ytl")),float(b.get("xbr")),float(b.get("ybr"))
            cx=min(max((x1+x2)/2/W,0),1); cy=min(max((y1+y2)/2/H,0),1)
            bw=min(abs(x2-x1)/W,1); bh=min(abs(y2-y1)/H,1)
            fh.write(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
    n+=1
print(f"golden construido: {n} frames")
