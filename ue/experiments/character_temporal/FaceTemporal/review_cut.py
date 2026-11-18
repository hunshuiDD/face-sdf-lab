"""Build a 40-second review from viewport sequences and matching references."""
from pathlib import Path
import os
import json
import subprocess
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).resolve().parent
outline=root.parent/"FaceOutline"
out=root/"evidence"
face=json.loads((out/"metrics.json").read_text())["by_softness"]
edge=json.loads((outline/"evidence/metrics.json").read_text())
font=lambda n:ImageFont.truetype(os.environ.get("FACE_REVIEW_FONT", "msyh.ttc"), n)
big,small,label=font(38),font(22),font(21)
blocks=[
    ("侧光下移动镜头","CC0 头模，固定 +90° 主光。每步平移 0.055 cm，32 帧往返复播。",root,
     ["hard_off","hard_on","hard_ref4"],["硬边","解析宽度","4 倍边长参考"],False),
    ("局部放大 · 眼、鼻、嘴","固定取样区，框内采用最近邻放大。引擎 AA 关闭，比较材质边界。",root,
     ["hard_off","hard_on","hard_ref4"],["硬边","解析宽度","超采样参考"],True),
    ("默认 3° 软边与 TSR",f"同轨迹下，开启现有材质解析宽度后，面部误差闪烁上升 {abs(face['production']['tsr_off_to_tsr_on']['face']):.2f}%。",root,
     ["production_tsr_off","production_tsr_on","production_ref4"],["TSR · 材质开关关","TSR · 材质开关开","超采样参考"],True),
    ("试验材质 · 线性像素覆盖","保留相机和输入纹理；硬阈值改用线性覆盖，对有角度宽度的软边做像素积分。",outline,
     ["linear_hard_off","linear_hard_on","linear_hard_ref4"],["硬阈值","线性覆盖","超采样参考"],True),
    ("轮廓在什么时候进入 TSR","同一头模的三条真实渲染路径。洋红用作诊断色，观察外轮廓和耳缘。",outline,
     ["shell_tsr","before_tsr","after_tsr"],["法线外扩反面壳","模板轮廓 · TSR 前","模板轮廓 · TSR 后"],False)]
ff=os.environ.get("FFMPEG_EXE", "ffmpeg")
dest=out/"face_temporal_review.mp4"
enc=subprocess.Popen([str(ff),"-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s","1280x640","-r","24","-i","pipe:0",
    "-c:v","libx264","-preset","veryfast","-crf","18","-pix_fmt","yuv420p","-movflags","+faststart",str(dest)],stdin=subprocess.PIPE)
shots=[]
for title,note,folder,groups,captions,zoom in blocks:
    cache=[]
    for i in range(32):
        panel=Image.new("RGB",(1280,640),"#182328")
        draw=ImageDraw.Draw(panel)
        draw.text((39,16),title,font=big,fill="#f0f4ef")
        draw.text((40,76),note,font=small,fill="#c5d8d5")
        for j,group in enumerate(groups):
            p=folder/"runs"/group/f"frame_{i:03d}.png"
            with Image.open(p) as src:
                image=src.convert("RGB")
            if image.width!=384:image=image.resize((384,384),Image.Resampling.BOX)
            if zoom:image=image.crop((126,145,281,323)).resize((310,356),Image.Resampling.NEAREST)
            x=40+j*410
            panel.paste(image,(x+(384-image.width)//2,139+(384-image.height)//2))
            draw.text((x,536),captions[j],font=label,fill="white")
        draw.line((40,586,1240,586),fill="#5f7778")
        draw.text((40,597),f"UE 5.8.3  ·  DX12 / SM6  ·  固定相位 {i+1:02d}/32  ·  面部时域实验",font=small,fill="#b2c5c6")
        cache.append(panel.tobytes())
    for t in range(192):
        i=t%62
        enc.stdin.write(cache[i if i<32 else 62-i])
    shots.append({"title":title,"cases":groups,"duration":8,"roi_zoom":zoom})
enc.stdin.close()
assert enc.wait()==0
read=subprocess.run([str(ff),"-v","error","-i",str(dest),"-progress","pipe:1","-f","null","-"],capture_output=True,text=True,check=True)
assert "frame=960" in read.stdout
(out/"edit_list.json").write_text(json.dumps({"seconds":40,"fps":24,"decoded":960,"shots":shots,
    "credit":"Blender Studio Human Base Meshes, CC0"},ensure_ascii=False,indent=2),encoding="utf8")
