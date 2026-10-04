# sogetiong

대학생 전용 익명 데이팅 서비스 (베타 운영 중) — https://private-matching.com

- 학교 이메일 인증을 거친 학생만 가입
- 사진은 외부에 공개되지 않고, 서비스 안에서 관리자가 외모 평가를 한 뒤 그 평가를 바탕으로 상대를 추천
- 설계 문서는 `01_` ~ `13_` 파일 (API 목록 `05_API_SPEC.md`, 로그인 방식 `06_AUTH_DESIGN.md`, 매칭 방식 `07_MATCHING_DESIGN.md`, 배포 `12_DEPLOYMENT.md`)

## 기술 스택

| 구분 | 사용 기술 |
|---|---|
| 화면 (`web/`) | Next.js 16, React 19, TypeScript, Tailwind CSS |
| 서버 (`backend/`) | FastAPI, SQLAlchemy, Alembic, Pydantic |
| DB | 개발·베타: SQLite / 사용자가 크게 늘면 PostgreSQL (코드는 이미 지원) |
| 배포 | Docker Compose + Caddy(HTTPS), GitHub Actions → ghcr.io, GCP e2-micro (서울) |
| 백업 | 매일 새벽 4시, rclone으로 암호화해 구글 드라이브에 저장 |

## 폴더 구조

```text
backend/     FastAPI 서버 (아래 "폴더 구조 (backend)" 참고)
web/         Next.js 화면 (사용자 화면 + 관리자 화면)
deploy/      운영 서버 설정 (Caddyfile, backend.env.example, backup.sh)
.github/     GitHub Actions — 푸시하면 서버용 Docker 이미지를 자동으로 만듦
docker-compose.yml   운영 서버에서 backend·web·caddy를 한 번에 실행
01_ ~ 13_*.md        설계 문서
```

## 내 PC에서 실행하기 (Windows PowerShell 기준)

### 1. 백엔드

```powershell
cd backend

# 1) 가상환경 만들고 패키지 설치
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# 2) 설정 파일 만들기 (처음 한 번)
Copy-Item .env.example .env
#   → .env 안의 SECRET_KEY를 무작위 값으로 바꾼다
#     python -c "import secrets; print(secrets.token_urlsafe(48))"

# 3) DB 준비는 자동입니다 (APP_ENV=dev 이면 서버가 켜질 때 테이블 생성 + 기본 데이터 입력)

# 4) 관리자 계정 만들기 (2단계 인증 비밀키가 출력됨 → Google Authenticator 등에 등록)
python -m app.scripts.create_admin --email admin@example.com --role SUPER_ADMIN

# 5) 서버 실행
uvicorn app.main:app --reload
```

- API 문서/테스트 화면: http://localhost:8000/docs
- `.env`에서 `EMAIL_BACKEND=console`이면 인증번호가 메일 대신 **서버 콘솔에 출력**된다 (개발용).
- 실제 메일을 보내려면 `EMAIL_BACKEND=smtp`와 SMTP 값을 채운다. SMTP 계정에는 앱 비밀번호를 사용한다.
- `/docs`에서 로그인 후 API를 눌러보려면: 로그인 요청에 헤더 `X-Client-Type: app`을 넣어 `session_token`을 받고, 오른쪽 위 **Authorize**에 입력한다.

### 2. 프론트엔드 (web 폴더)

[Node.js](https://nodejs.org) **20.9 이상**이 필요합니다 (22 이상 권장, `node -v`로 확인). **백엔드를 먼저 켜둔 상태**에서 새 PowerShell 창을 열고:

```powershell
cd web
npm install      # 처음 한 번 (패키지 버전을 올린 뒤에도 한 번 다시 실행)
npm run dev
```

- 사용자 화면: http://localhost:3000
- 관리자 화면: http://localhost:3000/admin/login (인증 앱의 6자리 코드 필요)
- 화면의 `/api/...` 요청은 Next.js가 백엔드(http://127.0.0.1:8000)로 넘겨줍니다. 백엔드 주소가 다르면 `BACKEND_URL` 환경변수로 바꿉니다.

## 테스트

```powershell
cd backend
pytest
```

가입 → 사진 → 관리자 평가 → 추천 → 매칭 → 채팅 전체 흐름과, 설계도 §65의 보안 테스트 8개가 포함돼 있다.

## DB 구조를 바꿀 때

`app/models/`를 수정한 뒤:

```powershell
alembic revision --autogenerate -m "무엇을 바꿨는지"
alembic upgrade head
```

운영 서버에서는 새 버전이 켜질 때 DB 변경이 자동으로 적용된다.

## 운영 서버에 배포하기 (요약)

운영 서버(e2-micro, 메모리 1GB)는 직접 빌드를 못 하므로 **이미지는 GitHub가 만들고, 서버는 내려받기만 한다.**

```text
내 PC: git push
   ▼
GitHub Actions (.github/workflows/build-images.yml)
   backend·web 이미지를 만들어 ghcr.io에 올림 (3~5분)
   ▼
서버: docker compose pull → docker compose up -d
```

1. 내 PC에서 `git push`
2. GitHub 저장소 → **Actions** 탭에서 `build-images`가 초록 체크가 될 때까지 기다림
3. 서버(GCP 콘솔 → VM → SSH)에서:
   ```bash
   cd ~/sogetiong
   sudo bash deploy/backup.sh     # 배포 전 백업
   git pull
   docker compose pull
   docker compose up -d
   docker image prune -f          # 예전 이미지 정리
   ```
4. https://private-matching.com/health 확인

- ⚠️ 서버에서 `docker compose up -d --build`는 쓰지 않는다 (서버에서 직접 빌드 → 멈춤).
- 문제가 생기면 예전 버전으로 되돌리기: `IMAGE_TAG=커밋번호7자리 docker compose up -d`
- 처음 서버 준비, 백업·복원, 되돌리기 자세한 방법은 **`12_DEPLOYMENT.md`** 참고.

## 폴더 구조 (backend)

```text
app/
  api/v1/      API 주소별 코드 (auth, profiles(/me), catalog, matching, safety, admin)
  core/        설정, 보안(비밀번호·토큰), 요청 횟수 제한
  db/          DB 연결
  models/      DB 테이블 정의
  schemas/     요청 형식 검사
  services/    핵심 로직 (매칭 엔진, 사진 처리, 세션 등)
  scripts/     seed, create_admin 명령어
migrations/    Alembic DB 변경 이력
tests/         자동 테스트
```

## 참고

- 사진은 개발 중에는 `backend/private_storage/`, 운영 서버에서는 `./data/photos/`에 저장된다 (둘 다 Git 제외).
- 운영 데이터(DB·사진·백업)는 서버의 `./data` 폴더에 있고, 이 폴더가 백업 대상이다.
- 비밀 값(`backend/.env`, `deploy/backend.env`)은 Git에 올리지 않는다.
