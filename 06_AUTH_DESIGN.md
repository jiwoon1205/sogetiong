# 06. Auth Design

> 2026-09-25 개정: JWT(localStorage) → **서버 세션 + HttpOnly 쿠키**로 변경.

## 1. 목표

- 학교 구성원만 가입 (학교 이메일 인증)
- 로그인 정보를 브라우저 스크립트가 훔쳐갈 수 없게
- 로그아웃·정지 시 **즉시** 무효화
- 나중에 모바일 앱에서도 같은 백엔드 사용

## 2. 가입 흐름

```text
학교 이메일 입력
  ↓  POST /auth/email/send-code
6자리 인증번호 메일 발송 (10분 유효, DB에는 해시만 저장)
  ↓  POST /auth/email/verify
인증번호 확인 → 가입용 1회 티켓 발급 (30분 유효)
  ↓  POST /auth/register (티켓 + 비밀번호 + 기본 정보 + 동의)
계정·공개 프로필·비공개 프로필 생성 → 바로 로그인
```

보안 장치
- 인증번호: `secrets` 모듈로 생성, HMAC-SHA256 해시로 저장, 5회 오답 시 폐기, 발송 횟수 제한
- 가입 여부 노출 방지: 이미 가입된 주소도 같은 응답 (코드는 발송하지 않음)
- 학교 도메인은 `universities.email_domain`과 **정확히** 일치해야 함 (`x@evilhufs.ac.kr` 거부)
- 티켓은 1회용, 이메일 인증 없이 가입 불가
- 만 19세 미만 가입 거부 (정확한 기준은 법률 검토 필요, 설계도 §44)
- 필수 동의: 이용약관, 개인정보 처리, **외적 평가 점수 공개**. 동의 시각은 private profile에 기록

## 3. 로그인 방식: 서버 세션 + HttpOnly 쿠키

```text
로그인 성공
  → 서버가 무작위 세션 ID(입장권)와 CSRF 토큰 생성
  → DB user_sessions에는 둘의 해시만 저장
  → 브라우저에 쿠키 2개 전달
       session     : HttpOnly (JS가 못 읽음) — 입장권
       csrf_token  : JS가 읽을 수 있음 — 요청 헤더에 넣을 값
```

| 항목 | 값 |
|---|---|
| 쿠키 속성 | `HttpOnly`(session만), `Secure`, `SameSite=Lax`, `Path=/` |
| 사용자 세션 유효기간 | 14일, 사용할 때마다 연장 |
| Session Rotation | 로그인할 때마다 새 세션 발급, 이전 세션 폐기 |
| 로그아웃 | DB에서 세션 삭제 → 즉시 무효 |
| 정지·차단·탈퇴 | 해당 사용자의 모든 세션 삭제 |
| 비밀번호 저장 | Argon2id |
| 비밀번호 규칙 | 8자 이상, 숫자만/영문만 불가 |

### CSRF 방어
쿠키로 로그인한 상태에서 데이터를 바꾸는 요청(POST/PUT/PATCH/DELETE)은 `X-CSRF-Token` 헤더가 필요하다.
프론트엔드는 `csrf_token` 쿠키 값을 읽어서 헤더에 넣는다. 다른 사이트는 이 쿠키를 읽을 수 없으므로 요청을 위조할 수 없다.

```ts
// Next.js 예시
const csrf = document.cookie.match(/(?:^|; )csrf_token=([^;]+)/)?.[1];
await fetch("/api/v1/me/profile", {
  method: "PATCH",
  credentials: "include",
  headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf ?? "" },
  body: JSON.stringify({ bio: "안녕하세요" }),
});
```

### 같은 주소로 서비스 (권장)
Next.js `rewrites`로 `/api/*` 요청을 FastAPI로 넘긴다. 브라우저 입장에서는 화면과 API가 같은 주소라서 쿠키가 자연스럽게 전달되고 CORS 설정이 필요 없다.

```js
// next.config.js
module.exports = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: "http://localhost:8000/api/:path*" }];
  },
};
```

### 모바일 앱 (향후)
요청 헤더 `X-Client-Type: app`으로 로그인하면 쿠키 대신 응답 body에 `session_token`을 준다.
이후 `Authorization: Bearer <session_token>`으로 보내면 된다. 이 방식은 쿠키가 아니므로 CSRF 헤더가 필요 없다.

## 4. 관리자 로그인

```text
POST /admin/auth/login (이메일 + 비밀번호)
  → admin_session 쿠키 발급 (아직 2단계 인증 전 → 관리자 API 사용 불가)
POST /admin/auth/2fa (인증 앱의 6자리 코드, TOTP)
  → 세션에 인증 완료 표시 → 관리자 API 사용 가능
```

- 사용자와 **별도 쿠키·별도 테이블**(`admin_sessions`). 사용자 세션으로는 관리자 API에 접근할 수 없다.
- 관리자 세션 8시간, 2단계 인증 필수.
- 관리자 계정은 화면이 아니라 서버 명령어로만 만든다: `python -m app.scripts.create_admin --email ... --role ...`
- 권한은 역할별 권한 목록(RBAC)으로 확인 (`05_API_SPEC.md` §8).
- TODO(운영 전): TOTP 비밀키 암호화 저장, 관리자 접속 IP 제한 검토.

## 5. 비밀번호 재설정

```text
/forgot-password 화면
  ↓  POST /auth/password/reset-request (학교 이메일)
  ↓     → 가입된 ACTIVE 계정이면 6자리 코드 메일 (10분 유효)
  ↓     → 아니면 메일 없음. 응답은 항상 같음
  ↓  POST /auth/password/reset (이메일 + 코드 + 새 비밀번호)
  ↓     → 비밀번호 변경, 모든 세션 삭제, 변경 안내 메일
로그인 화면으로 이동 (새 비밀번호로 로그인)
```

- 코드는 `verification_tokens`에 해시로 저장, `purpose=PASSWORD_RESET`으로 가입용과 구분.
- 새 코드를 요청하면 이전 코드는 쓸 수 없다 (항상 가장 최근 코드만 확인).
- 정지(SUSPENDED/BANNED)·탈퇴 계정에는 코드를 보내지 않는다.

## 6. 계정 상태

`ACTIVE`(이용 가능) / `SUSPENDED`(일시 정지) / `BANNED`(영구 정지) / `DELETED`(탈퇴)

`PENDING`은 현재 사용하지 않는다 (이메일 인증이 끝나야 계정이 만들어지므로).

## 7. 남은 과제

- 로그인한 상태에서 비밀번호 바꾸기 (설정 화면, 현재 비밀번호 확인)
- 요청 횟수 제한을 Redis로 이전
- 만 나이 기준·동의 문구 법률 검토
