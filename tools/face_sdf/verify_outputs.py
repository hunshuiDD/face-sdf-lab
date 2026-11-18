"""Independent disk readback of PNG16 channel contracts and source protection."""
import hashlib
import json
import struct
import zlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

root=Path(__file__).resolve().parent
out=root/"PublicHead"

def decode_png16(path):
    blob=path.read_bytes()
    assert blob[:8]==b"\x89PNG\r\n\x1a\n"
    offset=8;compressed=b"";header=None
    while offset<len(blob):
        size=struct.unpack(">I",blob[offset:offset+4])[0]
        kind=blob[offset+4:offset+8]
        data=blob[offset+8:offset+8+size]
        crc=struct.unpack(">I",blob[offset+8+size:offset+12+size])[0]
        assert zlib.crc32(kind+data)&0xffffffff==crc
        if kind==b"IHDR": header=struct.unpack(">IIBBBBB",data)
        if kind==b"IDAT": compressed+=data
        offset+=size+12
    width,height,depth,color,comp,filter_,interlace=header
    assert (depth,comp,filter_,interlace)==(16,0,0,0)
    channels={0:1,6:4}[color]
    rows=np.frombuffer(zlib.decompress(compressed),np.uint8).reshape(height,width*channels*2+1)
    assert not rows[:,0].any(),"This writer emits filter zero"
    return rows[:,1:].copy().view(">u2").astype(np.uint16).reshape(height,width,channels)

checks={}
for tag,npz in [("","threshold_variants.npz"),("cycles_","cycles_threshold_variants.npz")]:
    fields=np.load(out/npz)
    original=decode_png16(out/f"T_PublicHead_{tag}raw_gray16.png")[...,0]
    protect=fields["protection"]
    for variant in ["raw","light","medium","strong"]:
        prefix=f"T_PublicHead_{tag}{variant}"
        rgba=decode_png16(out/(prefix+"_project_RGBA16.png"))
        gray=decode_png16(out/(prefix+"_gray16.png"))[...,0]
        assert rgba.shape==(1024,1024,4)
        assert np.array_equal(rgba[...,1],gray)
        assert np.array_equal(rgba[...,0],gray[:,::-1])
        assert np.array_equal(rgba[...,2],fields["coverage"].astype(np.uint16)*65535)
        assert (rgba[...,3]==65535).all()
        assert np.array_equal(gray[protect],original[protect])
        checks[prefix]=dict(shape=list(rgba.shape),bit_depth=16,protected_pixels=int(protect.sum()),
            protected_changed=0,sha256=hashlib.sha256((out/(prefix+"_project_RGBA16.png")).read_bytes()).hexdigest())
source=root/"inputs/human_base_meshes_bundle.blend"
source_bundle_present=source.exists()
if source_bundle_present:
    assert hashlib.sha256(source.read_bytes()).hexdigest()=="3c121505651140ceb4d69fd1d8923f7788ffadd81672f5be14845a5f2c75c137"
else:
    source=root/"inputs/PublicHead.blend"
    expected=json.loads((root/"inputs/source_provenance.json").read_text())["extracted_head_sha256"]
    assert hashlib.sha256(source.read_bytes()).hexdigest()==expected
angles=[0,45,90,-45,-90,135]
images=[]
for folder in ["renders","renders_cycles"]:
    board=Image.new("RGB",(1536,1420),(24,28,34))
    draw=ImageDraw.Draw(board)
    alpha=None
    for row,variant in enumerate(["visibility","raw","light","medium","strong"]):
        for col,angle in enumerate(angles):
            path=out/folder/f"{variant}_{col+1:02d}_{angle:+04d}.png"
            with Image.open(path) as image:
                image.load()
                a=np.asarray(image)
                if alpha is None: alpha=a[...,3]
                assert np.array_equal(a[...,3],alpha)
                assert (a[...,3]>0).sum()>10000
                background=Image.new("RGBA",image.size,(31,35,42,255))
                background.alpha_composite(image)
                board.paste(background.convert("RGB").resize((256,256)),(col*256,row*284+24))
                images.append(dict(file=str(path.relative_to(root)),shape=list(a.shape),alpha_pixels=int((a[...,3]>0).sum())))
            draw.text((col*256+8,row*284+6),f"{variant} | {angle:+d} deg",fill="white")
    board.save(out/(folder+"_ContactSheet.png"))
(out/"validation.json").write_text(json.dumps(dict(png_contracts=checks,rendered_images=images,
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),source_bundle_present=source_bundle_present,
    source_unchanged=True),indent=2),encoding="utf8")
print(json.dumps(dict(png16_projects=len(checks),fixed_camera_renders=len(images),source_unchanged=True)))
