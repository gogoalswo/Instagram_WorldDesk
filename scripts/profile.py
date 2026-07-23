import os
from PIL import Image, ImageDraw, ImageFont
S=1080
INK=(8,13,24); AMBER=(242,179,61); FG=(238,243,250); UP=(55,217,160); DOWN=(255,91,110)
N="/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
M="/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
fb=lambda s: ImageFont.truetype(N,s,index=1)
fm=lambda s: ImageFont.truetype(M,s)
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(ROOT,"assets")
os.makedirs(OUT,exist_ok=True)

def base(c0,c1):
    im=Image.new("RGB",(S,S),c0); d=ImageDraw.Draw(im)
    for y in range(S):
        t=y/S; d.line([(0,y),(S,y)],fill=tuple(int(c0[i]+(c1[i]-c0[i])*t) for i in range(3)))
    return im
def grain(im):
    ov=Image.new("RGBA",(S,S),(0,0,0,0)); od=ImageDraw.Draw(ov)
    for y in range(0,S,5): od.rectangle([0,y,S,y+2],fill=(255,255,255,8))
    return Image.alpha_composite(im.convert("RGBA"),ov).convert("RGB")
def ctext(d,cy,txt,font,fill,sp):
    w=sum(font.getlength(c)+sp for c in txt)-sp; x=(S-w)/2
    for c in txt: d.text((x,cy),c,font=font,fill=fill,anchor="lm"); x+=font.getlength(c)+sp

def var_a():
    im=base((18,34,62),(8,13,24)); d=ImageDraw.Draw(im)
    for i in range(1,4):
        d.line([(0,i*S/4),(S,i*S/4)],fill=(30,46,74),width=3)
        d.line([(i*S/4,0),(i*S/4,S)],fill=(30,46,74),width=3)
    d.ellipse([70,70,S-70,S-70],outline=AMBER,width=14)
    d.text((S/2,455),"WD",font=fb(380),fill=FG,anchor="mm")
    d.rectangle([S/2-95,655,S/2+95,668],fill=AMBER)
    ctext(d,730,"GLOBAL ECONOMY",fm(42),AMBER,14)
    return grain(im)

def var_b():
    im=base((11,18,32),(6,10,18)); d=ImageDraw.Draw(im)
    d.ellipse([46,46,S-46,S-46],outline=(30,46,74),width=10)
    cands=[(375,360,150,UP),(485,310,140,UP),(595,290,150,DOWN),(705,340,220,DOWN)]
    for x,y,h,c in cands:
        d.line([(x,y-58),(x,y+h+58)],fill=c,width=12)
        d.rectangle([x-38,y,x+38,y+h],fill=c)
    d.rectangle([S/2-150,668,S/2+150,681],fill=AMBER)
    ctext(d,760,"WORLD DESK",fb(70),FG,5)
    return grain(im)

def var_c():
    im=base((246,192,79),(224,152,36)); d=ImageDraw.Draw(im)
    d.ellipse([64,64,S-64,S-64],outline=INK,width=12)
    d.text((S/2,430),"W",font=fb(400),fill=INK,anchor="mm")
    d.line([(320,680),(420,640),(520,690),(620,590),(700,630),(770,548)],fill=INK,width=16,joint="curve")
    ctext(d,790,"WORLD DESK",fm(46),INK,15)
    return grain(im)

for n,fn in [("a",var_a),("b",var_b),("c",var_c)]:
    fn().save(f"{OUT}/profile-{n}.png")

mask=Image.new("L",(S,S),0); ImageDraw.Draw(mask).ellipse([0,0,S,S],fill=255)
pv=Image.new("RGB",(1180,560),(5,8,15)); pd=ImageDraw.Draw(pv)
for i,n in enumerate(["a","b","c"]):
    im=Image.open(f"{OUT}/profile-{n}.png").convert("RGB"); im.putalpha(mask)
    x=70+i*360
    big=im.resize((300,300),Image.LANCZOS); pv.paste(big,(x,90),big)
    for j,sz in enumerate([110,56,32]):
        s=im.resize((sz,sz),Image.LANCZOS); pv.paste(s,(x+j*115,470-sz//2),s)
    pd.text((x,45),f"{n.upper()}",font=fb(30),fill=FG)
pv.save(os.path.join(OUT,"profile-preview.png"))
print("ok")
