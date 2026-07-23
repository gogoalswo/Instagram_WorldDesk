# WORLD DESK

해외 **경제 뉴스**를 인스타그램 릴스용 세로 카드뉴스(1080×1920)로 제작하는 파이프라인.
뉴스 데이터를 코드로 그려서 영상까지 한 번에 렌더한다.

---

## 빠른 시작

```bash
# 1. 의존성
pip install -r requirements.txt

# 2. 시스템 요구사항
#    - ffmpeg (libx264, aac)
#    - Noto Sans CJK KR
#    - DejaVu Sans Mono
#    Ubuntu/Debian:
sudo apt install ffmpeg fonts-noto-cjk fonts-dejavu

#    macOS:
brew install ffmpeg
brew install --cask font-noto-sans-cjk font-dejavu

# 3. 렌더
python3 scripts/render.py     # → out/<날짜>/world-desk-reels-<날짜>.mp4
python3 scripts/profile.py    # → assets/profile-{a,b,c}.png
```

> macOS는 폰트 경로가 다르다. `scripts/render.py` 상단의 `NOTO`, `F_MONO` 상수를 로컬 경로로 바꿀 것.
> `fc-list :lang=ko` 로 경로 확인 가능. Noto CJK의 **KR 서브패밀리는 ttc index=1**.

---

## 디렉터리

```
.
├── docs/HANDOFF.md          제작 규칙·레이아웃 스펙 전문 (작업 전 필독)
├── scripts/
│   ├── render.py            영상 렌더 (PIL 드로잉 → ffmpeg rawvideo 파이프)
│   └── profile.py           프로필 이미지 3안 렌더
├── preview/                 브라우저 프리뷰 HTML (세이프존 토글 · 슬라이드쇼)
├── assets/                  프로필 이미지 등 계정 자산
├── out/<날짜>/              회차별 산출물
└── CHANGELOG.md
```

---

## 제작 규칙 요약

| 항목 | 값 |
|---|---|
| 해상도 | 1080 × 1920 (9:16) |
| 구성 | 뉴스 5장 + 아웃트로 1장 (**표지 없음**) |
| 길이 | 카드당 5초 + 전환 0.35초 → 28.3초 |
| 뉴스 기준일 | **반드시 오늘 날짜에 발행된 뉴스만** 사용 (어제 이전 기사 금지) |
| 날짜 표기 | `YYYY년 M월 D일`로 년·월·일 모두 표기 (`YYYY.MM.DD` 축약 금지) |
| 카드 순서 | **가장 자극적인 기사를 1번**에 |
| 안전영역 | 상단 160 / 하단 480 / 우측 250 px는 인스타 UI — 본문 배치 금지 |
| 이미지 | 무료 라이선스(PD/CC0/CC BY/CC BY-SA) 실사 사진, 인물 우선 · 없으면 회사 로고 나온 건물/제품. 보도사진 금지 |

전체 스펙(절대좌표 레이아웃, 디자인 토큰, 애니메이션 타이밍)은 [`docs/HANDOFF.md`](docs/HANDOFF.md) 참조.

---

## 새 회차 만들기

1. **오늘 날짜에 발행된** 해외 경제 뉴스 5건 수집 (수치·출처 포함, 어제 이전 기사 금지)
2. `scripts/render.py`의 `CARDS` 갱신
   - `tag` 카테고리 / `stat` (라벨, 대형수치, 보조수치, 색) / `h2` **줄바꿈 수동 지정** / `sum` / `date`(`YYYY년 M월 D일`) / `src`
   - 헤드라인 한 줄 최대 폭 756px ≈ 한글 11~12자
3. 뉴스에 맞는 무료 라이선스 사진(인물 우선)을 위키미디어 커먼즈 등에서 찾아
   `assets/photos/`에 저장하고 `assets/photos/CREDITS.md`에 출처·라이선스 기록,
   `v_*()`에서 `photo_bg()`로 연결 (또는 사진이 마땅치 않으면 그래픽 함수 작성)
4. 출력 경로의 날짜 변경 후 렌더
5. `CHANGELOG.md`에 회차 기록

---

## 브랜치 전략 (권장)

```
main          발행 완료분만
feat/<날짜>   회차 작업 → 발행 후 main에 머지
```

영상 파일이 쌓이면 리포지토리가 무거워진다. 회차가 늘면 Git LFS로 전환할 것:

```bash
git lfs install
git lfs track "*.mp4"
git add .gitattributes
```

---

## 라이선스 / 주의

- 보도사진(로이터·AP·게티 등)은 리포지토리에 포함하지 않는다. 모든 시각 요소는 코드로 생성한 것.
- 뉴스 수치는 출처를 카드 하단과 캡션에 반드시 명시한다.
