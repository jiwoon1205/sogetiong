# 05. API Specification

> 2026-09-25 개정: 새 API 주소 기준 반영. 실제 동작은 백엔드 실행 후 `http://localhost:8000/docs`에서 직접 눌러볼 수 있다.

## 1. 공통 규칙

- 모든 주소는 `/api/v1`로 시작한다.
- 명사(자원) 중심 주소 + HTTP 메서드로 동작 표현 (GET 조회, POST 생성, PUT 전체 교체, PATCH 일부 수정, DELETE 삭제).
- **내 정보는 전부 `/me` 아래**에 둔다.
- **다른 사람 프로필은 `/discover`와 `/matches`로만** 볼 수 있다. `/profiles/{id}` 같은 직접 조회 API는 두지 않는다 (ID를 바꿔가며 긁어가는 공격 차단).
- 다른 사람을 가리킬 때는 내부 `user_id` 대신 공개 **`profile_id`**를 쓴다.
- 로그인 방식은 `06_AUTH_DESIGN.md` 참고. 브라우저는 쿠키로 자동 인증되고, 데이터를 바꾸는 요청(POST/PUT/PATCH/DELETE)에는 `X-CSRF-Token` 헤더가 필요하다.

### 에러 응답
```json
{ "detail": "사람이 읽을 수 있는 메시지 또는 코드" }
```

| 상태 코드 | 의미 |
|---|---|
| 400 | 입력값이 규칙에 맞지 않음 |
| 401 | 로그인이 필요하거나 만료됨 |
| 403 | 권한 없음 / CSRF 토큰 없음 / 이용 제한 계정 |
| 404 | 없음 (남의 자원도 404로 응답해 존재 여부를 숨김) |
| 409 | 현재 상태에서 할 수 없음 (예: `PREFERENCES_REQUIRED`) |
| 422 | 요청 형식 오류 (필드 누락, 길이 초과 등) |
| 429 | 요청 횟수 초과 |

## 2. 가입·로그인 (`/auth`) — 로그인 불필요

| 메서드 | 주소 | 설명 |
|---|---|---|
| POST | /auth/email/send-code | 학교 이메일로 6자리 인증번호 발송 |
| POST | /auth/email/verify | 인증번호 확인 → 가입용 1회 티켓 발급 |
| POST | /auth/register | 가입 + 자동 로그인 |
| POST | /auth/login | 로그인 |
| POST | /auth/logout | 로그아웃 (로그인 필요) |
| POST | /auth/password/reset-request | 비밀번호 재설정 인증번호 발송 |
| POST | /auth/password/reset | 인증번호 + 새 비밀번호로 변경 |

**send-code** `{ "email": "student@hufs.ac.kr" }` → `202 { "message": "..." }`
- 등록된 학교 도메인이 아니면 400.
- 이미 가입된 주소여도 **똑같은 응답**을 준다 (가입 여부 노출 방지).

**verify** `{ "email": "...", "code": "123456" }` → `{ "verification_ticket": "...", "expires_in_minutes": 30 }`
- 5번 틀리면 해당 인증번호는 폐기.

**register**
```json
{
  "verification_ticket": "...",
  "password": "8자 이상, 영문+숫자/기호",
  "nickname": "익명의 대학생",
  "gender": "MALE | FEMALE",
  "birth_date": "2003-05-01",
  "campus_id": "uuid",
  "real_name": "(선택)",
  "student_id": "(선택)",
  "agree_terms": true,
  "agree_privacy": true,
  "agree_appearance_public": true
}
```
→ `201 { "message": "...", "csrf_token": "..." }` + 로그인 쿠키
- 만 19세 미만 거부. 외적 평가 공개 동의 필수.
- **재가입 제한** (verify와 register 둘 다에서 확인, 403): 같은 메일의 예전 계정이 영구 정지(BANNED)면 가입 불가, 탈퇴 후 `REJOIN_COOLDOWN_DAYS`(기본 7일) 동안 가입 불가. 메일 주인임이 확인된 뒤라서 이유를 알려준다.
- 재가입하면 예전 계정의 차단 관계(내가 차단한 사람, 나를 차단한 사람)를 새 계정으로 이어받는다.

**login** `{ "email", "password" }` → `{ "message", "csrf_token" }` + 로그인 쿠키
- 모바일 앱은 헤더 `X-Client-Type: app` → 쿠키 대신 body에 `session_token`.

**password/reset-request** `{ "email": "student@hufs.ac.kr" }` → `202 { "message": "..." }`
- 등록된 학교 도메인이 아니면 400.
- 가입 여부·계정 상태와 상관없이 **똑같은 응답**. 실제 메일은 이용 가능(ACTIVE)한 계정에만 보낸다.
- 메일은 응답을 보낸 뒤 발송한다 (응답 시간 차이로 가입 여부를 알 수 없게). 발송 실패도 서버 로그에만 남긴다.

**password/reset** `{ "email", "code": "123456", "new_password": "8자 이상, 영문+숫자/기호" }` → `{ "message": "..." }`
- 코드가 틀리거나 만료되면 400 (이유는 구분하지 않음). 5번 틀리면 해당 코드 폐기.
- 성공하면: 비밀번호 변경 → **모든 기기 로그아웃** → "비밀번호 변경됨" 안내 메일. 자동 로그인은 하지 않는다.
- 가입용 인증번호와 재설정 인증번호는 서로 바꿔 쓸 수 없다 (`verification_tokens.purpose`).

## 3. 학교 정보 — 로그인 불필요

| 메서드 | 주소 |
|---|---|
| GET | /universities |
| GET | /universities/{university_id}/campuses |
| GET | /campuses/{campus_id}/departments |
| GET | /interests |
| GET | /support | 문의 메일 주소 `{ "email" }` (학과 변경 요청, 학과 추가 요청) |

## 4. 내 정보 (`/me`)

| 메서드 | 주소 | 설명 |
|---|---|---|
| GET | /me | 내 이메일, 계정 상태, 온보딩 진행 상태 |
| DELETE | /me | 탈퇴 `{ "password" }` |
| GET | /me/profile | 내 공개 카드 + 편집용 값 |
| PATCH | /me/profile | 공개 프로필 수정 (보낸 항목만) |
| GET | /me/preferences | 내 매칭 조건 |
| PUT | /me/preferences | 매칭 조건 전체 저장 |
| POST | /me/photos | 사진 제출 (multipart `file`) |
| GET | /me/photos | 사진 검수 상태 |
| GET | /me/evaluation | 내 외적 평가 점수 |

**PATCH /me/profile**
```json
{
  "nickname": "새닉네임",
  "department_id": "uuid",
  "show_campus": true,
  "show_department": true,
  "mbti": "INTP",
  "bio": "최대 500자",
  "ideal_type": "최대 300자",
  "interests": ["카페", "영화"]
}
```
- 성별·생년월일·캠퍼스는 가입 후 변경 불가. 관심사는 `/interests` 목록 안에서 최대 10개.
- **학과는 필수, 처음 한 번만 정할 수 있다.** 이미 정한 뒤 다른 학과를 보내면 409 (운영진 메일 안내 문구). 잘못 골랐으면 가입한 학교 메일로 요청 → 관리자가 `PATCH /admin/users/{user_id}/department`로 변경.
- 학과를 처음 정할 때 `show_campus`·`show_department`를 함께 보내야 한다 (기본값 없이 직접 선택). 공개 여부는 이후 언제든 변경 가능.
- 응답에는 카드 값 외에 `department_name`, `campus_name`, `show_campus`, `show_department`, `department_locked`가 온다.

**PUT /me/preferences**
```json
{
  "preferred_gender": "MALE | FEMALE | ANY",
  "min_age": 20,
  "max_age": 27,
  "campus_mode": "MY | ALL | SELECTED",
  "campus_ids": [],
  "exclude_same_department": false
}
```
- 같은 과 제외: 둘 중 한 명이라도 켰고 학과가 같으면 서로 추천되지 않는다 (Hard Filter, 양방향).
- 베타에서는 임의 학과 제외·선호 학과 가산을 쓰지 않는다 (DB 테이블만 남겨둠).
- 처음 저장 이후에는 24시간에 3번까지만 바꿀 수 있다 (429). 내용이 같으면 세지 않는다. GET 응답의 `changes_left_today`로 남은 횟수 확인.

**POST /me/photos** → `201 { "photo_id", "review_status": "PENDING" }`
- jpg/png/webp, 5MB 이하. 서버가 새 JPEG로 다시 저장하면서 EXIF·GPS를 지운다.
- 평가를 받은 뒤 30일 안에는 재제출 불가 (429).

**GET /me/evaluation** → `{ "evaluated": true, "scores": { "overall_impression": 8, "style": 7, "grooming": 8, "photo_vibe": 9 } }`

## 5. 추천·LIKE·PASS

| 메서드 | 주소 | 설명 |
|---|---|---|
| GET | /discover?limit=10 | 추천 카드 (최대 20) |
| POST | /likes | `{ "profile_id" }` → `{ "matched", "match_id" }` |
| POST | /passes | `{ "profile_id" }` |
| DELETE | /passes/{profile_id} | PASS 취소 (향후 Undo용) |

**GET /discover** → `{ "profiles": [카드...], "empty": false }`

공개 카드 형식 (다른 사용자에게 보내는 유일한 형식):
```json
{
  "profile_id": "uuid",
  "nickname": "익명의 대학생",
  "age": 21,
  "gender": "FEMALE",
  "campus": "서울캠퍼스 또는 null(비공개)",
  "department": "경영학부 또는 null(비공개)",
  "mbti": "INTP",
  "bio": "...",
  "ideal_type": "...",
  "interests": ["카페", "영화"],
  "appearance": { "overall_impression": 8, "style": 7, "grooming": 8, "photo_vibe": 9 }
}
```
- 추천 전 필요 조건: 공개 프로필, 매칭 조건, 승인된 사진. 없으면 409 + `PROFILE_REQUIRED` / `PREFERENCES_REQUIRED` / `PHOTO_APPROVAL_REQUIRED`.
- 조건은 **양방향**으로 확인한다 (내 조건에 맞고, 상대 조건에도 내가 맞아야 추천).
- 후보가 없으면 `empty: true`. 조건을 자동으로 넓히지 않는다.
- LIKE도 같은 조건을 확인하므로 profile_id를 직접 넣어도 조건 밖의 사람에게는 LIKE할 수 없다(404).
- 사용자가 외적 점수로 필터·정렬하는 기능은 없다. 점수는 서버 추천 순위에 일부(기본 20%, 상한 30%)만 반영된다.

## 6. 매칭·채팅

| 메서드 | 주소 | 설명 |
|---|---|---|
| GET | /matches | 진행 중인 매칭 + 상대 카드 + 마지막 메시지 |
| GET | /matches/{match_id} | 매칭 상세 |
| DELETE | /matches/{match_id} | 매칭 해제 |
| GET | /matches/{match_id}/messages?before=&limit=50 | 메시지 조회 (최신 50개, 이전은 before) |
| POST | /matches/{match_id}/messages | `{ "body": "1~1000자" }` |

메시지 형식: `{ "message_id", "body", "is_mine", "sent_at" }` — 상대의 내부 ID는 보내지 않는다.
MVP는 폴링(몇 초마다 조회) 방식. 사용자 증가 후 WebSocket 검토 (설계도 §51).

## 7. 안전·알림

| 메서드 | 주소 | 설명 |
|---|---|---|
| POST | /blocks | `{ "profile_id" }` 차단 (진행 중 매칭은 BLOCKED로 종료) |
| GET | /blocks | 내가 차단한 목록 |
| DELETE | /blocks/{profile_id} | 차단 해제 (끝난 매칭은 복구하지 않음) |
| POST | /reports | `{ "profile_id", "reason", "description", "match_id" }` |
| GET | /notifications?unread_only=false | 알림 목록 |
| PATCH | /notifications/{notification_id} | `{ "read": true }` |

신고 사유(reason): `SEXUAL_HARASSMENT, ABUSIVE_LANGUAGE, THREAT, STALKING, OBSCENE_CONTENT, IMPERSONATION, MONEY_REQUEST, PERSONAL_INFO_REQUEST, SPAM, OTHER`

## 8. 관리자 (`/admin`)

관리자 쿠키는 사용자와 별개(`admin_session`). 모든 API는 로그인 + 2단계 인증 + 권한 확인.

| 메서드 | 주소 | 필요 권한 |
|---|---|---|
| POST | /admin/auth/login | - (비밀번호 확인) |
| POST | /admin/auth/2fa | - (`{ "code": "123456" }` 인증 앱 코드) |
| POST | /admin/auth/logout | - |
| GET | /admin/me | - |
| GET | /admin/dashboard | dashboard:read |
| GET | /admin/photo-reviews?status=PENDING | photos:read |
| GET | /admin/photo-reviews/{photo_id} | photos:read |
| GET | /admin/photo-reviews/{photo_id}/image | photos:read |
| PUT | /admin/photo-reviews/{photo_id}/evaluation | photos:evaluate |
| GET | /admin/users?status=&nickname= | users:read |
| GET | /admin/users/{user_id}?include_private=false | users:read (+ users:private:read) |
| PATCH | /admin/users/{user_id}/status | users:status |
| GET | /admin/reports?status=OPEN | reports:read |
| PATCH | /admin/reports/{report_id} | reports:update |
| GET | /admin/users/{user_id}/matches | chats:read |
| GET | /admin/matches/{match_id}/messages?before=&limit=200 | chats:read |
| GET | /admin/audit-logs | audit:read |

**PUT /admin/photo-reviews/{photo_id}/evaluation**
```json
{
  "decision": "APPROVED | REJECTED",
  "overall_impression": 8,
  "style": 7,
  "grooming": 8,
  "photo_vibe": 9,
  "note": "관리자 전용 메모",
  "reject_reason": "반려 시 사용자에게 보여줄 사유"
}
```
- 승인 시 4개 점수(1~10) 필수, 반려 시 사유 필수. 수정할 때마다 이력이 쌓이고 감사 로그에 이전/새 점수가 남는다.
- 사진 이미지는 서버가 직접 전달(영구 URL 없음), 캐시 금지, 조회한 관리자 이메일·시각 워터마크, 조회 기록.
- PHOTO_REVIEWER는 사진과 가명 코드(`U1A2B3C`)만 본다.

**PATCH /admin/users/{user_id}/status** `{ "status": "ACTIVE | SUSPENDED | BANNED | DELETED", "reason": "..." }` — 정지 시 즉시 로그아웃.
- 탈퇴한 계정은 `BANNED`(재가입 차단) ↔ `DELETED`(정지 해제)만 가능. 멀쩡한 계정을 `DELETED`로 바꿀 수는 없다 (탈퇴는 본인만).
- `GET /admin/users/{user_id}` 응답에 `deleted_at`, `linked_accounts`(같은 학교 메일로 가입했던 다른 계정, 이메일 제외)가 포함된다.

**PATCH /admin/reports/{report_id}** `{ "status": "IN_REVIEW | RESOLVED | DISMISSED", "admin_note": "..." }`

**대화 열람** (운영 정책: 권한이 있으면 신고 여부와 상관없이 모든 대화를 볼 수 있다)
- `GET /admin/users/{user_id}/matches` → 이 사용자의 모든 대화방(끝난 대화 포함) 목록. 상대 가명 코드·닉네임, 메시지 수, 마지막 메시지 시각. 내용은 없음.
- `GET /admin/matches/{match_id}/messages` → 대화 내용 (최신 200개, `before`로 이전 것). 보낸 사람은 가명 코드로 표시, 이메일 없음.
- 대화 내용을 열 때마다 감사 로그 `CHAT_VIEW` (관리자·시각·IP·대화방)가 남는다.
- 메시지는 매칭 해제·차단·탈퇴 후에도 삭제하지 않고 보관한다.

### 역할별 권한

| 권한 | SUPER_ADMIN | MODERATOR | PHOTO_REVIEWER |
|---|:-:|:-:|:-:|
| dashboard:read | ✅ | ✅ | ✅ |
| photos:read / photos:evaluate | ✅ | | ✅ |
| users:read / users:status | ✅ | ✅ | |
| users:private:read (실명·이메일 등) | ✅ | | |
| reports:read / reports:update | ✅ | ✅ | |
| chats:read (모든 대화 열람) | ✅ | ✅ | |
| audit:read | ✅ | | |

## 9. 요청 횟수 제한

| 대상 | 제한 |
|---|---|
| 인증번호 발송 | 이메일당 3회/시간, IP당 10회/시간 |
| 인증번호 확인 | IP당 20회/10분, 코드당 5회 오답 |
| 가입 | IP당 10회/시간 |
| 로그인 | 이메일당 10회/15분, IP당 30회/15분 |
| 비밀번호 재설정 코드 발송 | 이메일당 3회/시간, IP당 10회/시간 |
| 비밀번호 재설정 | IP당 20회/10분, 코드당 5회 오답 |
| 관리자 로그인 / 2FA | IP당 10회/15분 / 5회/5분 |
| 사진 업로드 | 5회/시간 |
| 추천 | 60회/분 |
| LIKE | 60회/분, 300회/일 |
| 메시지 | 30회/분 |
| 신고 | 5회/시간 |

현재는 서버 메모리에 저장한다. 서버가 여러 대가 되면 Redis로 옮긴다.
