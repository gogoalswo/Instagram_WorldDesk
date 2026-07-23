import os, re, math, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
VH = 1440                # 그래픽(사진) 영역 높이 — 하단 안전영역(480px) 위까지 꽉 채움
FPS, DUR = 30, 3.0       # 카드당 길이(초)
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
    return photo_bg("airbus_a350.jpg", fx=0.43, fy=0.48, dark=0.22) # AIRBUS A350 기체 (CC BY-SA 2.0)

def v_smci():
    return photo_bg("smci_campus.jpg", fx=0.53, fy=0.5, dark=0.38, top_fade=340)  # Supermicro 캠퍼스 (CC BY-SA 4.0)

def v_tesla2():
    return photo_bg("musk.jpg", fx=0.5, fy=0.3, dark=0.18)          # 일론 머스크 · 테슬라 CEO (CC BY 4.0)

def v_tariff():
    return photo_bg("von_der_leyen.jpg", fx=0.5, fy=0.25, dark=0.34, top_fade=340)  # 우르줄라 폰데어라이엔 · EU 집행위원장 (CC BY 4.0)

def v_gold():
    return photo_bg("gold_bars.jpg", fx=0.5, fy=0.5, dark=0.30)     # 금괴 (CC0)

def v_europe():
    return photo_bg("frankfurt_bull_bear.jpg", fx=0.52, fy=0.5, dark=0.28)  # 프랑크푸르트 증권거래소 황소·곰 동상 (CC BY-SA 2.5)

# ─────────── 오버레이 ───────────
# 사진이 카드 전체(안전영역 위까지)를 채우므로, 텍스트가 얹히는 구간마다 어둡기를
# 다르게 줘서 "스탯 숫자 위는 사진이 좀 보이되, 본문 아래로 갈수록 완전히 어두워짐"을 만든다.
_FADE_PTS = [(560, 0), (700, 30), (824, 85), (900, 100), (1000, 118),
             (1180, 140), (1300, 165), (1440, 210)]

def _fade_alpha(y):
    if y <= _FADE_PTS[0][0]: return _FADE_PTS[0][1]
    if y >= _FADE_PTS[-1][0]: return _FADE_PTS[-1][1]
    for (y0, a0), (y1, a1) in zip(_FADE_PTS, _FADE_PTS[1:]):
        if y0 <= y <= y1:
            t = (y - y0) / (y1 - y0)
            return a0 + (a1 - a0) * t
    return 255

def bg_layer():
    l=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(l)
    d.rectangle([0,_FADE_PTS[-1][0],W,H],fill=INK+(255,))
    for y in range(_FADE_PTS[0][0], _FADE_PTS[-1][0]):
        d.line([(0,y),(W,y)],fill=INK+(int(_fade_alpha(y)),))
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
 dict(v=v_smci,tag="AI INFRA",stat=("SMCI · 슈퍼마이크로","+19.84%","신규수주 600억 달러",UP),
      h2=[[("AI 서버 수주가",FG)],[("하루 새 20% 터졌다",AMBER)]],
      sum="슈퍼마이크로컴퓨터가 4분기 신규수주 600억 달러 돌파 소식에 하루 만에 19.84% 급등했다.",
      date="2026년 7월 23일",src="뉴스핌"),
 dict(v=v_tesla2,tag="EARNINGS",stat=("TSLA · 시간외","-2%","매출 282억 달러 · +26%",DOWN),
      h2=[[("매출은 사상 최대인데",FG)],[("마진은 반토막",AMBER)]],
      sum="테슬라 2분기 매출은 282억 달러로 26% 늘었지만 영업이익률은 1.4%로 주저앉았고, 잉여현금흐름은 11억 달러 적자로 돌아섰다.",
      date="2026년 7월 23일",src="Tesla IR · 뉴스핌"),
 dict(v=v_tariff,tag="TRADE",stat=("EU 대미 자동차관세","15%","기존 27.5% · 즉시 발효",UP),
      h2=[[("자동차 관세 27.5%,",FG)],[("15%로 확정",AMBER)]],
      sum="미국-EU 무역협정이 발효돼 자동차 관세가 27.5%에서 15%로 낮아졌다. 항공기·의약품은 0%, 철강은 50%로 유지됐다.",
      date="2026년 7월 23일",src="뉴스핌 · Deccan Herald"),
 dict(v=v_gold,tag="GOLD",stat=("GOLD · 온스당","$4,151.90","+1.9% · 2주 최고",UP),
      h2=[[("불안할수록 산다,",FG)],[("금값 2주 최고",AMBER)]],
      sum="중동 리스크와 금리 불확실성이 겹치며 금값이 온스당 4,151.90달러로 2주 만에 최고치를 찍었다.",
      date="2026년 7월 23일",src="뉴스핌 · Reuters"),
 dict(v=v_europe,tag="EUROPE",stat=("STOXX 600","646.93","+0.58% · 최고치",UP),
      h2=[[("유럽 증시 랠리,",FG)],[("일제히 최고치",AMBER)]],
      sum="독일 DAX, 영국 FTSE, 프랑스 CAC 등 유럽 주요 지수가 일제히 상승했다. 항공우주·방산 업종이 2.6% 오르며 상승을 이끌었다.",
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
    first=(i==0)  # 첫 카드는 이탈 방어를 위해 텍스트를 페이드 없이 즉시 노출
    def gen(big=big,tl=tl,bl=bl,zin=zin,BW=BW,BH=BH,first=first):
        for n in range(NF):
            t=n/(NF-1)
            wf=K-(K-1.0)*t if zin else 1.0+(K-1.0)*t
            cw,ch=W*wf,VH*wf
            x0,y0=(BW-cw)/2,(BH-ch)/2
            vis=big.crop((int(x0),int(y0),int(x0+cw),int(y0+ch))).resize((W,VH),Image.LANCZOS)
            fr=Image.new("RGBA",(W,H),INK+(255,)); fr.paste(vis,(0,0))
            fr=Image.alpha_composite(fr,BG)
            a1=1 if first else min(1,n/12)
            fr=Image.alpha_composite(fr,fade(tl,ease(a1)))
            a2=1 if first else min(1,max(0,(n-9)/18))
            dy=0 if first else int(26*(1-ease(a2)))
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
