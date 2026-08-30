#!/usr/bin/env python3
"""Parte el lote de revisión v6 en 2 paquetes disjuntos 50/50 (alineado a jobs de 300)
para repartir entre 2 revisores en CVAT locales separados. Merge final por nombre de frame.
Cada paquete: <pkg>_images.zip (plano) + <pkg>_annotations.zip (CVAT-for-images 1.1)."""
import os, glob, zipfile, shutil
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

H = "/home/camilo-pc/Multi-Object-Tracking/data/_harvest"
SRC = f"{H}/v6_full"
IMG = f"{SRC}/images"
SPLIT = 1200  # frames 0..1199 -> A (jobs 1-4) ; resto -> B (jobs 5-9)
W, Hh = 640, 480

# 1) parsear xml -> dict name->boxes (cada box: (xtl,ytl,xbr,ybr,source))
root = ET.parse(f"{SRC}/annotations.xml").getroot()
byname = {}
for im in root.findall("image"):
    boxes = []
    for b in im.findall("box"):
        boxes.append((b.get("xtl"), b.get("ytl"), b.get("xbr"), b.get("ybr"), b.get("source", "manual")))
    byname[im.get("name")] = boxes

# 2) orden global lexicográfico (igual que CVAT) y split
names = sorted(byname.keys())
groups = {"A": names[:SPLIT], "B": names[SPLIT:]}

def write_xml(path, group):
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<annotations>', '  <version>1.1</version>',
             '  <meta><task><labels><label><name>head</name><type>rectangle</type><attributes></attributes></label></labels></task></meta>']
    for idx, name in enumerate(group):
        lines.append(f'  <image id="{idx}" name="{escape(name)}" width="{W}" height="{Hh}">')
        for xtl, ytl, xbr, ybr, src in byname[name]:
            lines.append(f'    <box label="head" source="{src}" occluded="0" '
                         f'xtl="{xtl}" ytl="{ytl}" xbr="{xbr}" ybr="{ybr}" z_order="0"></box>')
        lines.append('  </image>')
    lines.append('</annotations>')
    open(path, "w").write("\n".join(lines))

for tag, group in groups.items():
    pkg = f"{H}/v6_pkg{tag}"
    nb = sum(len(byname[n]) for n in group)
    # zip imágenes plano
    with zipfile.ZipFile(f"{pkg}_images.zip", "w", zipfile.ZIP_STORED) as z:
        for n in group:
            z.write(f"{IMG}/{n}", n)
    # xml + zip anotaciones
    xmlp = f"{H}/_ann_{tag}.xml"; write_xml(xmlp, group)
    with zipfile.ZipFile(f"{pkg}_annotations.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(xmlp, "annotations.xml")
    os.remove(xmlp)
    print(f"Paquete {tag}: {len(group)} frames | {nb} cajas -> v6_pkg{tag}_images.zip + v6_pkg{tag}_annotations.zip")

# verificación disjuntos
inter = set(groups["A"]) & set(groups["B"])
union = set(groups["A"]) | set(groups["B"])
print(f"Disjuntos: {'OK' if not inter else 'SOLAPE!'} | cobertura: {len(union)}/{len(names)} frames")
