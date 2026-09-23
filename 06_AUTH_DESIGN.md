# 06. Auth Design

## 1. Goals

- 대학생 인증을 안전하게 수행
- 학교 이메일을 계정 식별 정보로 사용
- 사용자 개인정보를 최소한으로 수집
- 인증 코드 관리와 세션 관리 모두 안전하게 설계

## 2. Authentication flow

```text
Landing
  ↓
Select university
  ↓
Input school email
  ↓
Generate verification token or code
  ↓
Send email
  ↓
User enters code
  ↓
Verify code
  ↓
Create account
  ↓
Issue session/JWT
  ↓
Proceed onboarding
```

## 3. Verification design

### Requirements
- 충분히 긴 랜덤 코드 생성
- 짧은 만료 시간
- 실패 횟수 제한
- rate limit 적용
- 인증 요청한 이메일이 이미 인증된 상태인지 검증
- 인증코드 평문 저장 금지 검토

### Recommended process
- verification_tokens table stores hashed code
- code expires within 5–15 minutes
- codes stored with attempt_count and used_at
- repeated failures trigger temporary lock

## 4. Security controls

- rate limit on verification send requests
- rate limit on verification attempts
- single-use verification code
- prevent duplicate verified email registration
- email address is not displayed publicly
- verification data is stored in private storage layer

## 5. Login design

### Basic flow
- email + password login
- server validates hash and status
- return access token + optional refresh token

### Session strategy
- JWT for API stateless access
- refresh token for rotation if needed
- session invalidation on logout, password change, or ban

### Recommended user status
- PENDING
- ACTIVE
- SUSPENDED
- BANNED
- DELETED

## 6. Password policy

- minimum length requirement
- strong password rules
- password hashing with bcrypt/argon2
- no raw password in logs or DB

## 7. Authorization model

### User roles
- user
- admin with subroles

### Admin subroles
- SUPER_ADMIN
- MODERATOR
- PHOTO_REVIEWER

### Principle
- role-based permission must be evaluated on the server
- no frontend-only access control
- admin permission list is explicit and auditable

## 8. Session and token security

- access token short-lived
- refresh token rotation
- secure HTTP-only cookies optional for browser-based app
- CSRF protection for cookie-based auth
- token revocation on admin or account actions

## 9. University and campus mapping

### universities table
- id
- name
- email_domains
- active

### campuses table
- id
- university_id
- name
- active

### requirement
- one university may have multiple campuses
- one campus may have multiple email domains
- the login flow should validate school email domain against university/campus config

## 10. Auth edge cases

- already verified or already registered email should be rejected
- expired code should be invalidated
- account suspension should block login
- deleted account should not be reusable
- unused verification tokens should be cleaned automatically

## 11. Security warnings

- Do not expose student email in profile endpoints
- Do not store verification codes in logs
- Never trust frontend claims about email verification
- Never use user-supplied domain logic without server-side validation

## 12. Future enhancement

- school-specific re-enrollment verification API integration
- institution-run identity verification integration
- SSO and institutional account linking where allowed by policy

## 13. Auth decision summary

The recommended auth model for MVP is:
- school email verification
- password-based account creation
- server-side JWT/session auth
- separate admin auth and access scopes

This is a practical and secure baseline while still allowing future campus-level identity verification integrations.
