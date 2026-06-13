# PetWalk — 동네 반려견 산책 메이트 매칭

[![CI](https://github.com/yuneunmi814-cmyk/petwalk/actions/workflows/ci.yml/badge.svg)](https://github.com/yuneunmi814-cmyk/petwalk/actions/workflows/ci.yml)

반경 2km 내 검증된 견주를 매칭해 함께 산책할 메이트를 연결하는 위치 기반 앱.
[PlanForge](../planforge)가 생성한 설계 문서(`planforge/samples/01-petwalk-design.md`)를
그대로 구현한 **build-ready 스펙 → 실제 동작 앱** 예제다.

스택: **React + TypeScript (Vite)** · **FastAPI** · **SQLAlchemy 2.0** · JWT(Access/Refresh) ·
Bcrypt · AES-256-GCM · 로컬은 SQLite(프로덕션은 PostgreSQL + PostGIS로 교체).

---

## 핵심 설계 포인트 (설계 문서 §1~§8 대응)

- **위치 프라이버시** — 정확 GPS는 서버에만 저장하고, 클라이언트에는 **~300m 격자(grid cell)의
  중심 좌표만** 반환한다. 어떤 응답에도 `home_lat/home_lng`가 포함되지 않는다
  (`tests/test_location_privacy.py`로 강제).
- **비동기 매칭** — 산책 요청은 `202 + jobId`로 즉시 반환하고, 적합도 계산(거리·견종 크기·성향
  궁합·시간대 겹침)은 백그라운드 워커가 처리한다. UI는 진행률을 폴링해 보여준다.
- **안전** — 첫 만남은 **공개 장소 목록**에서만 선택 가능. 신고 1회로 **양방향 즉시 차단**되어
  매칭 후보에서 제외된다(재요청 차단).
- **통일된 에러 계약** — 모든 실패는 `{"error":{"code","message"}}`, 상태코드는
  400/401/403/404/409/429/500로 제한. 인증 트래픽은 사용자별 레이트 리밋(429 + Retry-After).
- **Soft Delete & 제약** — 강아지/요청은 `deleted_at`, `reviews(match,rater)`·`users.email` UNIQUE.

### 구현 범위 (MVP)

프로필 · 위치(격자) · 메이트 탐색 · 비동기 요청/수락 · 채팅 · 후기 · 신고/차단 · 관리자 지표.
WebSocket 실시간 채팅, PostGIS 공간쿼리, Redis 캐시/큐, 결제는 설계 문서의 v1/v2 단계로
의도적으로 미룬 부분이며, 코드 구조는 그 교체를 전제로 분리돼 있다.

---

## 실행

### Docker (한 줄, 권장)

```bash
docker compose up --build
# 웹   http://localhost:8080   (nginx가 SPA 서빙 + /api 프록시)
# API  http://localhost:8200/docs
```

직접 실행하려면 — 전제: **Python 3.12+**, **Node 18+**. 백엔드 `:8200`, 프론트 `:5173`(Vite 프록시 `/api` → `:8200`).

### 1) 백엔드

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --port 8200      # 첫 기동 시 데모 견주 + 공개 장소 자동 시드
```

### 2) 프론트엔드

```bash
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

회원가입 시 **“강남 데모 위치로 설정”**을 켜면 시드된 주변 메이트가 바로 보인다.
데모 계정 로그인: `jihu@demo.example.com` 외 / 비밀번호 `demo1234`.

### 테스트

```bash
cd backend && source .venv/bin/activate
pytest                                 # 26 passed — 인증/CRUD/비동기 매칭/프라이버시/신고차단/단위
```

---

## 구조

```
backend/
  app/
    core/        config · database · errors(통일 계약) · security(bcrypt·JWT·AES·grid) · ratelimit · deps
    models.py    users·dogs·walk_requests·match_jobs·matches·messages·reviews·reports·blocks·meeting_places
    schemas.py   camelCase 와이어 모델 (정확 좌표 미노출)
    routers/     auth · dogs · mates · walk_requests · matches · reviews · reports · places · admin
    services/    matching(비동기 적합도 워커) · seed(데모 데이터)
  tests/         pytest (in-process, 임시 파일 SQLite)
frontend/
  src/
    api.ts       토큰 저장 + 타입드 fetch 클라이언트
    tabs/        DogsTab · FindTab(요청→진행률→매칭→수락) · MatchesTab(채팅·후기·신고)
    App.tsx      인증 + 셸 + 탭
```

> 분산 모델(Tauri 사이드카로 로컬 백엔드 번들)은 [PlanForge](../planforge)와 동일 패턴으로 확장 가능.
