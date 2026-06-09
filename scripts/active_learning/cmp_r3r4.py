import cv2, numpy as np
from ultralytics import YOLO
R3=YOLO("/workspace/outputs/head_detector/yolo-bus-head-r3/weights/best.pt")
R4=YOLO("/workspace/outputs/head_detector/yolo-bus-head-r4/weights/best.pt")
cap=cv2.VideoCapture("/videos/videoTM_02.mkv"); idx=0; cands=[]
while True:
    ret,img=cap.read()
    if not ret: break
    if idx%40==0 and img.mean()>=75:
        n=len(R3.predict(img,conf=0.25,iou=0.5,verbose=False)[0].boxes)
        cands.append((n,idx,img.copy()))
    idx+=1
cap.release()
cands.sort(reverse=True)
picks=[]; used=[]
for n,i,img in cands:
    if all(abs(i-u)>900 for u in used): picks.append((i,img)); used.append(i)
    if len(picks)==4: break
def draw(img,model,color,name):
    im=img.copy(); r=model.predict(im,conf=0.25,iou=0.5,verbose=False)[0]
    b=r.boxes.xyxy.cpu().numpy() if r.boxes is not None else []
    for x1,y1,x2,y2 in b: cv2.rectangle(im,(int(x1),int(y1)),(int(x2),int(y2)),color,2)
    cv2.rectangle(im,(0,0),(im.shape[1],26),(0,0,0),-1)
    cv2.putText(im,f"{name}: {len(b)} cabezas",(6,18),cv2.FONT_HERSHEY_SIMPLEX,0.6,color,2)
    return im
for k,(i,img) in enumerate(picks):
    out=np.hstack([draw(img,R3,(0,255,0),"R3"),draw(img,R4,(0,200,255),"R4")])
    cv2.imwrite(f"/workspace/data/_harvest/r3r4_{k+1}_f{i:06d}.jpg",out)
    print(f"frame {i}: guardado")
