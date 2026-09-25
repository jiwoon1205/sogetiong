# sogetiong

대학생 전용 익명 데이팅 서비스. 설계 문서는 `01_` ~ `13_` 파일, API 목록은 `05_API_SPEC.md`, 로그인 방식은 `06_AUTH_DESIGN.md`.

## 백엔드 처음 실행하기 (Windows PowerShell 기준)

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

## 프론트엔드 실행 (web 폴더, Next.js)

[Node.js](https://nodejs.org) 20 이상이 필요합니다 (`node -v`로 확인). **백엔드를 먼저 켜둔 상태**에서 새 PowerShell 창을 열고:

```powershell
cd web
npm install      # 처음 한 번
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

## 폴더 구조 (backend)

```text
app/
  api/v1/      API 주소별 코드 (auth, profiles(/me), catalog, matching, safety, admin)
  core/        설정, 보안(비밀번호·토큰), 요청 횟수 제한
  models/      DB 테이블 정의
  schemas/     요청 형식 검사
  services/    핵심 로직 (매칭 엔진, 사진 처리, 세션 등)
  scripts/     seed, create_admin 명령어
migrations/    Alembic DB 변경 이력
tests/         자동 테스트
```

## 참고

- 새 화면은 `web/`(Next.js)에 있다. 예전 `frontend/`(HTML/JS)는 더 이상 쓰지 않으므로 지워도 된다.
- 사진은 개발 중에는 `backend/private_storage/`에 저장된다 (Git 제외). 운영 전에 R2/S3 private bucket으로 바꿔야 한다.
