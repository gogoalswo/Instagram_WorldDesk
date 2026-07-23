import os, re, math, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
VH = 880                 # 그래픽 영역 높이
FPS, DUR = 30, 5.0
NF = int(FPS * DUR)
K = 1.09                 # 켄번스 오버스캔

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATE = "2026-07-23"      # 회차 날짜 (출력 경로 · 카드 date 필드와 맞출 것)
OUT_DIR = os.path.join(ROOT, "out", DATE)
os.makedirs(OUT_DIR, exist_ok=True)
OUT = tempfile.mkdtemp(prefix="world-desk-seg-")
PHOTO_DIR = os.path.join(ROOT, "assets", "photos")

INK=(8,13,24); LINE=(30,46,74); AMBER=(242,179,61); UP=(55,217,160)
DOWN=(255,91,110); FG=(238,243,250); MUTE=(124,144,172); SUB=(195,210,228)

NOTO="/usr/share/fonts/opentype/noto/"
F_BLACK=NOTO+"NotoSansCJK-Black.ttc"; F_BOLD=NOTO+"NotoSansCJK-Bold.ttc"
F_MED=NOTO+"NotoSansCJK-Medium.ttc"; F_REG=NOTO+"NotoSansCJK-Regular.ttc"
F_MONO="/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
_fc={}
def f(path,size,idx=1):
    k=(path,size,idx)
    if k not in _fc: _fc[k]=ImageFont.truetype(path,size,index=idx) if path.endswith(".ttc") else ImageFont.truetype(path,size)
    return _fc[k]
def has_cjk(s): return any(ord(c)>0x2E80 for c in s)
def mono(s,size): return f(F_BOLD,size) if has_cjk(s) else f(F_MONO,size,0)

def tracked(d,xy,text,font,fill,sp=0):
    x,y=xy
    for ch in text:
        d.text((x,y),ch,font=font,fill=fill); x+=font.getlength(ch)+sp
    return x

def wrap(text,font,maxw):
    lines,cur=[],""
    for w_ in text.split(" "):
        t=(cur+" "+w_).strip()
        if font.getlength(t)<=maxw: cur=t
        else: lines.append(cur); cur=w_
    if cur: lines.append(cur)
    return lines

# ─────────── 그래픽 영역 (좌표는 1080x880 기준, K배로 확대 렌더) ───────────
class Cv:
    def __init__(s):
        s.img=Image.new("RGB",(int(W*K),int(VH*K)),INK); s.d=ImageDraw.Draw(s.img)
    def S(s,v): return v*K
    def rect(s,x,y,w,h,fill,a=255):
        if a<255:
            ov=Image.new("RGBA",s.img.size,(0,0,0,0)); ImageDraw.Draw(ov).rectangle(
                [s.S(x),s.S(y),s.S(x+w),s.S(y+h)],fill=fill+(a,))
            s.img=Image.alpha_composite(s.img.convert("RGBA"),ov).convert("RGB"); s.d=ImageDraw.Draw(s.img)
        else: s.d.rectangle([s.S(x),s.S(y),s.S(x+w),s.S(y+h)],fill=fill)
    def line(s,pts,fill,w_=3,a=255):
        p=[(s.S(x),s.S(y)) for x,y in pts]
        if a<255:
            ov=Image.new("RGBA",s.img.size,(0,0,0,0)); ImageDraw.Draw(ov).line(p,fill=fill+(a,),width=int(w_*K),joint="curve")
            s.img=Image.alpha_composite(s.img.convert("RGBA"),ov).convert("RGB"); s.d=ImageDraw.Draw(s.img)
        else: s.d.line(p,fill=fill,width=int(w_*K),joint="curve")
    def poly(s,pts,fill,a=60):
        ov=Image.new("RGBA",s.img.size,(0,0,0,0))
        ImageDraw.Draw(ov).polygon([(s.S(x),s.S(y)) for x,y in pts],fill=fill+(a,))
        s.img=Image.alpha_composite(s.img.convert("RGBA"),ov).convert("RGB"); s.d=ImageDraw.Draw(s.img)
    def ell(s,cx,cy,rx,ry,outline=None,fill=None,w_=3,a=255):
        ov=Image.new("RGBA",s.img.size,(0,0,0,0))
        ImageDraw.Draw(ov).ellipse([s.S(cx-rx),s.S(cy-ry),s.S(cx+rx),s.S(cy+ry)],
            outline=(outline+(a,)) if outline else None, fill=(fill+(a,)) if fill else None,
            width=int(w_*K))
        s.img=Image.alpha_composite(s.img.convert("RGBA"),ov).convert("RGB"); s.d=ImageDraw.Draw(s.img)
    def grad(s,c0,c1,diag=False):
        bw,bh=s.img.size; g=Image.new("RGB",(bw,bh))
        gd=ImageDraw.Draw(g)
        for i in range(bh):
            t=i/bh
            gd.line([(0,i),(bw,i)],fill=tuple(int(c0[j]+(c1[j]-c0[j])*t) for j in range(3)))
        if diag:
            g2=Image.new("L",(bw,bh)); g2d=ImageDraw.Draw(g2)
            for i in range(bw): g2d.line([(i,0),(i,bh)],fill=int(255*i/bw))
            g=Image.composite(Image.new("RGB",(bw,bh),c1),g,g2)
        s.img=g; s.d=ImageDraw.Draw(s.img)
    def grain(s):
        ov=Image.new("RGBA",s.img.size,(0,0,0,0)); od=ImageDraw.Draw(ov)
        for y in range(0,s.img.size[1],5): od.rectangle([0,y,s.img.size[0],y+2],fill=(255,255,255,9))
        s.img=Image.alpha_composite(s.img.convert("RGBA"),ov).convert("RGB")

# ─────────── 실사 이미지 (무료 라이선스 인물/건물 사진) ───────────
def cover_crop(im, tw, th, fx=0.5, fy=0.5):
    """im을 (tw,th)를 꽉 채우도록 확대 후, (fx,fy) 지점을 중심으로 크롭."""
    im = im.convert("RGB")
    sw, sh = im.size
    scale = max(tw / sw, th / sh)
    nw, nh = max(tw, round(sw * scale)), max(th, round(sh * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    cx, cy = nw * fx, nh * fy
    x0 = min(max(0, cx - tw / 2), nw - tw)
    y0 = min(max(0, cy - th / 2), nh - th)
    return im.crop((int(x0), int(y0), int(x0 + tw), int(y0 + th)))

def photo_bg(name, fx=0.5, fy=0.3, dark=0.28, top_fade=280):
    """뉴스 관련 인물/건물 실사 사진을 그래픽 영역(W*K x VH*K)에 맞춰 브랜드 톤으로 보정."""
    im = Image.open(os.path.join(PHOTO_DIR, name))
    tw, th = int(W * K), int(VH * K)
    im = cover_crop(im, tw, th, fx, fy)
    im = Image.blend(im, Image.new("RGB", im.size, INK), dark)          # 브랜드 다크톤 통일
    grad = Image.new("L", im.size, 0); gd = ImageDraw.Draw(grad)
    tf = int(top_fade * K)
    for y in range(tf):
        gd.line([(0, y), (im.size[0], y)], fill=int(255 * (1 - y / tf) ** 1.05))
    im = Image.composite(Image.new("RGB", im.size, (0, 0, 0)), im, grad)  # 상단 인스타 UI 존 대비 확보
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    for y in range(0, im.size[1], 5): od.rectangle([0, y, im.size[0], y + 2], fill=(255, 255, 255, 6))
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")

# 출처·라이선스 전문은 assets/photos/CREDITS.md 참조 (전부 PD 또는 CC-BY 계열, 보도사진 아님)
def v_rate():
    return photo_bg("powell.jpg", fx=0.5, fy=0.28, dark=0.34)      # 제롬 파월 · 연준 의장 (PD)

def v_kospi():
    return photo_bg("lee_jaeyong.jpg", fx=0.5, fy=0.26, dark=0.32, top_fade=340)  # 이재용 · 삼성전자 회장 (CC BY-SA 3.0)

def v_oil2():
    return photo_bg("refinery.jpg", fx=0.5, fy=0.55, dark=0.08)     # 미나 알아흐마디 정유시설 야경 (PD)

def v_googl():
    return photo_bg("pichai.jpg", fx=0.5, fy=0.26, dark=0.30)       # 순다르 피차이 · 알파벳/구글 CEO (CC BY 4.0)

def v_airbus():
    return photo_bg("airbus_a350.jpg", fx=0.58, fy=0.48, dark=0.22) # AIRBUS A350 기체 (CC BY-SA 2.0)

# ─────────── 오버레이 ───────────
def bg_layer():
    l=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(l)
    d.rectangle([0,VH,W,H],fill=INK+(255,))
    for i in range(300):
        y=VH-300+i; d.line([(0,y),(W,y)],fill=INK+(int(255*(i/300)**1.7),))
    return l

def top_layer(card,idx):
    l=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(l)
    d.ellipse([74,238-72,85,249-72],fill=AMBER+(255,))
    tracked(d,(99,172-14),card["tag"],f(F_BOLD,28),AMBER+(255,),7)
    n=f"{idx+1:02d} / 05"; fo=f(F_MONO,29,0)
    tracked(d,(W-74-fo.getlength(n)-9*(len(n)-1),172-14),n,fo,MUTE+(255,),9)
    seg=(W-148-8*4)/5
    for i in range(5):
        x=74+i*(seg+8)
        d.rectangle([x,236,x+seg,241],fill=(AMBER+(255,)) if i==idx else ((37,52,76,255)))
    # stat
    lab,big,small,bc=card["stat"]
    tracked(d,(74,602),lab,mono(lab,30),MUTE+(255,),6)
    d.text((74,640),big,font=f(F_BLACK,132),fill=bc+(255,))
    tracked(d,(74,640+128+22),small,mono(small,34),bc+(255,),1)
    return l

def body_layer(card):
    l=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(l)
    y=910
    for ln in card["h2"]:
        x=74
        for txt,col in ln:
            d.text((x,y),txt,font=f(F_BLACK,76),fill=col+(255,)); x+=f(F_BLACK,76).getlength(txt)
        y+=87
    y+=26
    fs=f(F_REG,38)
    for ln in wrap(card["sum"],fs,700):
        d.text((74,y),ln,font=fs,fill=SUB+(255,)); y+=57
    d.rectangle([74,1384,W-74,1386],fill=LINE+(255,))
    d.text((74,1400),card["date"],font=mono(card["date"],28),fill=MUTE+(255,))
    src=card["src"]; fo=mono(src,28)
    d.text((W-74-fo.getlength(src)-f(F_MONO,28,0).getlength("SOURCE ")),1400) if False else None
    lbl="SOURCE "; fl=f(F_MONO,28,0)
    total=fl.getlength(lbl)+fo.getlength(src)
    d.text((W-74-total,1400),lbl,font=fl,fill=(159,178,202,255))
    d.text((W-74-total+fl.getlength(lbl),1400),src,font=fo,fill=MUTE+(255,))
    return l

def outro_frames():
    base=Image.new("RGB",(W,H),INK); d=ImageDraw.Draw(base)
    for i in range(H):
        t=i/H; c0,c1=(58,42,8),(10,21,38)
        d.line([(0,i),(W,i)],fill=tuple(int(c1[j]+(c0[j]-c1[j])*(1-t)) for j in range(3)))
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); od=ImageDraw.Draw(ov)
    for r in (230,380,530): od.ellipse([540-r,800-r,540+r,800+r],outline=AMBER+(42,),width=3)
    for y in range(0,H,5): od.rectangle([0,y,W,y+2],fill=(255,255,255,9))
    base=Image.alpha_composite(base.convert("RGBA"),ov)
    txt=Image.new("RGBA",(W,H),(0,0,0,0)); td=ImageDraw.Draw(txt)
    tracked(td,(74,560),"WORLD DESK",f(F_MONO,32,0),AMBER+(255,),11)
    td.text((74,650),"내일도",font=f(F_BLACK,126),fill=FG+(255,))
    td.text((74,650+130),"같은 시간",font=f(F_BLACK,126),fill=FG+(255,))
    td.rectangle([74,970,234,978],fill=AMBER+(255,))
    td.text((74,1040),"해외 경제, 하루 ",font=f(F_BOLD,56),fill=(220,231,244,255))
    x=74+f(F_BOLD,56).getlength("해외 경제, 하루 ")
    td.text((x,1040),"5개",font=f(F_BLACK,56),fill=AMBER+(255,))
    td.text((x+f(F_BLACK,56).getlength("5개"),1040),"로 정리합니다.",font=f(F_BOLD,56),fill=(220,231,244,255))
    td.text((74,1116),"팔로우하고 놓치지 마세요.",font=f(F_BOLD,56),fill=(220,231,244,255))
    return base,txt

def ease(t): return 1-(1-t)**3

CARDS=[
 dict(v=v_rate,tag="RATES",stat=("FED HIKE ODDS","32%","1주 전 10.7% · 3배 급등",DOWN),
      h2=[[("금리 인상 확률,",FG)],[("일주일 만에 3배",AMBER)]],
      sum="미 2년물 국채금리가 17개월 만에 최고치. 유가 급등이 물가를 자극하며 7월 금리 인상 가능성이 커졌다.",
      date="2026년 7월 23일",src="CME FedWatch · 뉴스핌"),
 dict(v=v_kospi,tag="KOREA",stat=("KOSPI","+2.88%","6,993.34 · 7000 목전",UP),
      h2=[[("반도체가 끌어올린",FG)],[("코스피 7000 코앞",AMBER)]],
      sum="삼성전자 +3.26%, SK하이닉스 +4.26%. AI 인프라 투자 기대감에 반도체주가 지수를 밀어올렸다.",
      date="2026년 7월 23일",src="국제뉴스"),
 dict(v=v_oil2,tag="ENERGY",stat=("BRENT CRUDE","$91.01","+2.0% · 6주 최고",UP),
      h2=[[("중동 리스크에",FG)],[("유가 6주 최고",AMBER)]],
      sum="브렌트유가 배럴당 91달러를 돌파했다. WTI도 84.91달러로 함께 뛰며 인플레이션 우려를 자극했다.",
      date="2026년 7월 23일",src="뉴스핌 · Reuters"),
 dict(v=v_googl,tag="EARNINGS",stat=("GOOGLE CLOUD","+82%","백로그 514억 달러",UP),
      h2=[[("알파벳 매출 24%↑",FG)],[("클라우드는 82%↑",AMBER)]],
      sum="알파벳 2분기 매출 1,198억 달러. AI 인프라 수요로 클라우드가 급증했지만 자본지출도 전년의 2배로 늘었다.",
      date="2026년 7월 23일",src="Alphabet IR · 한국경제"),
 dict(v=v_airbus,tag="AVIATION",stat=("AIRBUS","+7%","자사주 매입 50억 유로",UP),
      h2=[[("에어버스, 목표 올리고",FG)],[("자사주 매입까지",AMBER)]],
      sum="2029년 핵심이익 목표를 최대 130억 유로로 높이고 50억 유로 자사주 매입을 발표하며 주가가 뛰었다.",
      date="2026년 7월 23일",src="뉴스핌 · Reuters"),
]

def encode(path,gen):
    p=subprocess.Popen(["ffmpeg","-y","-loglevel","error","-f","rawvideo","-pix_fmt","rgb24",
        "-s",f"{W}x{H}","-r",str(FPS),"-i","-","-c:v","libx264","-preset","medium","-crf","18",
        "-pix_fmt","yuv420p",path],stdin=subprocess.PIPE)
    for im in gen: p.stdin.write(im.tobytes())
    p.stdin.close(); p.wait()

def fade(layer,a):
    if a>=1: return layer
    l=layer.copy(); al=l.split()[3].point(lambda v:int(v*a)); l.putalpha(al); return l

BG=bg_layer()
segs=[]
for i,c in enumerate(CARDS):
    big=c["v"](); BW,BH=big.size
    tl=top_layer(c,i); bl=body_layer(c); zin=(i%2==0)
    def gen(big=big,tl=tl,bl=bl,zin=zin,BW=BW,BH=BH):
        for n in range(NF):
            t=n/(NF-1)
            wf=K-(K-1.0)*t if zin else 1.0+(K-1.0)*t
            cw,ch=W*wf,VH*wf
            x0,y0=(BW-cw)/2,(BH-ch)/2
            vis=big.crop((int(x0),int(y0),int(x0+cw),int(y0+ch))).resize((W,VH),Image.LANCZOS)
            fr=Image.new("RGBA",(W,H),INK+(255,)); fr.paste(vis,(0,0))
            fr=Image.alpha_composite(fr,BG)
            a1=min(1,n/12); fr=Image.alpha_composite(fr,fade(tl,ease(a1)))
            a2=min(1,max(0,(n-9)/18)); dy=int(26*(1-ease(a2)))
            b=fade(bl,ease(a2))
            if dy: b=b.transform((W,H),Image.AFFINE,(1,0,0,0,1,-dy))
            fr=Image.alpha_composite(fr,b)
            yield fr.convert("RGB")
    pth=f"{OUT}/s{i}.mp4"; encode(pth,gen()); segs.append(pth); print("seg",i,"done",flush=True)

ob,ot=outro_frames()
def gen_out():
    for n in range(NF):
        a=min(1,max(0,(n-6)/20)); fr=Image.alpha_composite(ob,fade(ot,ease(a)))
        yield fr.convert("RGB")
pth=f"{OUT}/s5.mp4"; encode(pth,gen_out()); segs.append(pth); print("outro done",flush=True)

# xfade 체인
XF=0.35
inp=[]
for s in segs: inp+=["-i",s]
fc=[]; prev="[0:v]"; off=DUR-XF
for i in range(1,6):
    lab=f"[x{i}]"
    fc.append(f"{prev}[{i}:v]xfade=transition=fade:duration={XF}:offset={off:.2f}{lab}")
    prev=lab; off+=DUR-XF
filt=";".join(fc)
out_path = os.path.join(OUT_DIR, f"world-desk-reels-{DATE.replace('-', '')}.mp4")
subprocess.run(["ffmpeg","-y","-loglevel","error",*inp,"-f","lavfi","-t","30","-i","anullsrc=r=44100:cl=stereo",
    "-filter_complex",filt,"-map",prev,"-map","6:a","-shortest",
    "-c:v","libx264","-preset","slow","-crf","18","-pix_fmt","yuv420p","-r","30",
    "-c:a","aac","-b:a","96k","-movflags","+faststart",
    out_path],check=True)
print("OK ->", out_path)
