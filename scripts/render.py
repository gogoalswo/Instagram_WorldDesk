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

def v_rate():
    c=Cv(); c.grad((42,12,14),(10,16,24))
    for y in (300,500,700): c.line([(0,y),(1080,y)],(74,42,42),2)
    c.rect(230,700,190,120,MUTE,200); c.line([(325,700),(325,644)],MUTE,5)
    c.rect(660,468,190,352,DOWN,255); c.line([(755,468),(755,388)],DOWN,5)
    c.line([(420,690),(660,478)],DOWN,7)
    c.ell(660,478,15,15,fill=DOWN); c.grain(); return c.img

def v_kospi():
    c=Cv(); c.grad((10,30,22),(9,15,24))
    for y in (300,500,700): c.line([(0,y),(1080,y)],(42,74,58),2)
    bars=[(150,540,60,UP),(268,492,108,UP),(386,430,170,UP),(504,368,232,UP),
          (622,314,286,UP),(740,252,348,UP),(858,198,402,UP)]
    for x,y,h,col in bars:
        c.rect(x,y,56,h,col); c.line([(x+28,y-30),(x+28,y+h+18)],col,5)
    c.grain(); return c.img

def v_oil2():
    c=Cv(); c.grad((58,34,8),(10,16,23),True)
    for y in (260,460,660): c.line([(0,y),(1080,y)],(74,58,34),2)
    pts=[(0,760),(135,706),(270,668),(405,616),(540,566),(675,522),(810,468),(945,428),(1080,390)]
    c.poly(pts+[(1080,880),(0,880)],AMBER,34); c.line(pts,AMBER,9)
    c.ell(1030,402,20,20,fill=AMBER); c.grain(); return c.img

def v_googl():
    c=Cv(); c.grad((8,22,40),(10,54,64),True)
    for p in [[(410,240),(670,240)],[(670,240),(670,500)],[(670,500),(410,500)],[(410,500),(410,240)]]:
        c.line(p,UP,4,a=130)
    for p in [[(455,240),(455,150)],[(540,240),(540,120)],[(625,240),(625,150)],
              [(455,500),(455,590)],[(540,500),(540,620)],[(625,500),(625,590)],
              [(410,285),(310,285)],[(410,370),(280,370)],[(410,455),(310,455)],
              [(670,285),(770,285)],[(670,370),(800,370)],[(670,455),(770,455)]]:
        c.line(p,UP,4,a=130)
    c.rect(462,292,156,156,UP,50)
    for x,y,h in ((250,560,40),(356,492,108),(462,396,204),(568,308,292),(674,216,384),(780,144,456)):
        c.rect(x,y,66,h,UP,230)
    c.grain(); return c.img

def v_airbus():
    c=Cv(); c.grad((16,26,46),(8,14,24),True)
    pts=[(0,780),(200,712),(400,616),(600,486),(800,352),(1000,236),(1080,196)]
    c.poly(pts+[(1080,880),(0,880)],UP,26); c.line(pts,UP,9)
    c.ell(1055,208,22,22,fill=UP)
    for rx in (60,100,140): c.ell(1055,208,rx,rx,outline=UP,w_=2,a=70)
    c.grain(); return c.img

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
