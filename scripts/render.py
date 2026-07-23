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

def v_tesla():
    c=Cv(); c.grad((49,18,31),(10,16,24))
    for y in (300,500,700): c.line([(0,y),(1080,y)],(42,58,82),2)
    bars=[(150,500,130,UP),(268,452,112,UP),(386,424,96,UP),(504,404,80,UP),
          (622,396,108,DOWN),(740,430,204,DOWN),(858,498,256,DOWN)]
    for x,y,h,col in bars:
        c.rect(x,y,56,h,col); c.line([(x+28,y-36),(x+28,y+h+40)],col,5)
    c.grain(); return c.img

def v_wb():
    c=Cv(); c.grad((16,31,62),(8,14,24),True)
    for rx in (270,216,120): c.ell(540,420,rx,270,outline=(46,68,104),w_=3,a=210)
    c.line([(270,420),(810,420)],(46,68,104),2); c.line([(330,285),(750,285)],(46,68,104),2)
    c.line([(330,555),(750,555)],(46,68,104),2)
    for x,y,h,col,a in ((300,640,140,UP,220),(446,686,94,MUTE,170),(592,724,56,DOWN,230),(738,748,32,DOWN,255)):
        c.rect(x,y,86,h,col,a)
    c.grain(); return c.img

def v_oil():
    c=Cv(); c.grad((58,34,8),(10,16,23),True)
    for y in (260,460,660): c.line([(0,y),(1080,y)],(74,58,34),2)
    pts=[(0,680),(135,664),(270,690),(405,630),(540,580),(675,598),(810,462),(945,388),(1080,312)]
    c.poly(pts+[(1080,880),(0,880)],AMBER,34); c.line(pts,AMBER,9)
    c.ell(1030,326,20,20,fill=AMBER); c.grain(); return c.img

def v_japan():
    c=Cv(); c.grad((43,18,32),(9,15,24))
    c.ell(540,250,78,78,fill=DOWN,a=205)
    c.line([(120,560),(960,560)],(90,110,140),4)
    for x,y,h,col,a in ((200,470,90,UP,220),(366,506,54,UP,140),(532,560,106,DOWN,190),(698,560,222,DOWN,255)):
        c.rect(x,y,104,h,col,a)
    c.grain(); return c.img

def v_semi():
    c=Cv(); c.grad((7,24,42),(11,58,68),True)
    c.rect(410,240,260,260,(11,58,68),0)
    for p in [[(410,240),(670,240)],[(670,240),(670,500)],[(670,500),(410,500)],[(410,500),(410,240)]]:
        c.line(p,UP,4,a=130)
    for p in [[(455,240),(455,150)],[(540,240),(540,120)],[(625,240),(625,150)],
              [(455,500),(455,590)],[(540,500),(540,620)],[(625,500),(625,590)],
              [(410,285),(310,285)],[(410,370),(280,370)],[(410,455),(310,455)],
              [(670,285),(770,285)],[(670,370),(800,370)],[(670,455),(770,455)]]:
        c.line(p,UP,4,a=130)
    c.rect(462,292,156,156,UP,50)
    for x,y,h in ((250,720,60),(356,676,104),(462,624,156),(568,580,200),(674,504,276),(780,436,344)):
        c.rect(x,y,66,h,UP,230)
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
 dict(v=v_tesla,tag="EARNINGS",stat=("TSLA · 시간외","-3%","EPS $0.33 · 컨센 $0.53",DOWN),
      h2=[[("사상 최대 매출인데",FG)],[("이익은 반 토막",AMBER)]],
      sum="테슬라 2분기 매출 282억 달러, 26% 증가. 그런데 잉여현금흐름은 11억 달러 적자로 돌아섰다.",
      date="2026년 7월 22일",src="Tesla IR · CNBC"),
 dict(v=v_wb,tag="OUTLOOK",stat=("GLOBAL GROWTH","1.3%","최악 시나리오 · 전년 2.9%",DOWN),
      h2=[[("세계은행 ",FG),("“성장률",AMBER)],[("반 토막”",AMBER),(" 경고",FG)]],
      sum="미국·이란 충돌이 커지면 물가가 다시 뛰고 금리가 밀려 올라간다. 성장률은 2.9%에서 1.3%까지.",
      date="2026년 7월 22일",src="World Bank · Reuters"),
 dict(v=v_oil,tag="ENERGY",stat=("BRENT CRUDE","$94.07","+3.4% · 한 달 최고",UP),
      h2=[[("브렌트유 ",FG),("94달러",AMBER)],[("돌파",FG)]],
      sum="미국의 대이란 공습이 11차례 이어지며 급등. WTI도 3% 올라 86.83달러로 마감했다.",
      date="2026년 7월 22일",src="CNBC · Reuters"),
 dict(v=v_japan,tag="JAPAN",stat=("TRADE BALANCE · JUN","-4,069억엔","예상 -1,200억엔",DOWN),
      h2=[[("수출 19% 늘었는데",FG)],[("적자는 3배",AMBER)]],
      sum="일본 6월 무역수지가 두 달 연속 마이너스. 수출은 3개월 만의 최고치를 찍었는데도 적자가 커졌다.",
      date="2026년 7월 22일",src="일본 재무성"),
 dict(v=v_semi,tag="SEMICONDUCTOR",stat=("KOREA CHIP EXPORTS","약 3배","7월 초 · 전년 대비",UP),
      h2=[[("한국·대만 수출이",FG)],[("월가를 되살렸다",AMBER)]],
      sum="AI 수요 둔화 우려로 3거래일 밀렸던 미 증시가 아시아 수출 지표에 반도체주 중심으로 반등했다.",
      date="2026년 7월 22일",src="Rio Times Briefing"),
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
