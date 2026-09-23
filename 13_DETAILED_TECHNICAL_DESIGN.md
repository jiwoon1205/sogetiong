# 13. Detailed Technical Design

## 1. System objective

This design translates the product requirements into implementation-ready architecture for the MVP. The focus is on:

- role-separated auth
- private photo handling
- anonymous profile flow
- matching logic with hard filters
- admin evaluation workflow
- safe API contracts

## 2. Recommended project structure

### Backend structure
```text
backend/
  app/
    api/
      v1/
        auth/
        users/
        profiles/
        matching/
        chat/
        reports/
        admin/
    core/
      config.py
      security.py
      deps.py
      logging.py
    db/
      base.py
      session.py
      models/
      migrations/
      repositories/
    schemas/
      auth.py
      user.py
      profile.py
      matching.py
      report.py
      admin.py
    services/
      auth_service.py
      profile_service.py
      matching_service.py
      photo_service.py
      admin_service.py
      notification_service.py
    utils/
      email.py
      storage.py
      security.py
      validation.py
```

### Frontend structure
```text
frontend/
  app/
    page.tsx
    auth/
    onboarding/
    discover/
    matches/
    chat/
    profile/
    settings/
    reports/
    admin/
  components/
    ui/
    auth/
    profile/
    cards/
    chat/
    admin/
  lib/
    api.ts
    auth.ts
    utils.ts
  hooks/
    useAuth.ts
    useProfiles.ts
    useMatches.ts
```

## 3. Core technical principles

### 3.1 Data separation
- Public profile data is stored separately from privacy-sensitive records.
- Matching private data is never returned in public APIs.
- Original photo is stored only in private object storage.

### 3.2 Backend authority
- Frontend may validate UX state, but server decides final access and data exposure.
- Authorization must be enforced in backend dependencies and route handlers.

### 3.3 Security-by-default
- File upload validation and signed URL generation are mandatory.
- IDOR prevention is in every route that accepts an ID parameter.

## 4. Authentication and authorization model

### User auth
- school email verification required before account creation
- password-based login with hashed password
- JWT access token for API access
- optional refresh token rotation for future extension

### Admin auth
- separate admin auth domain from user auth
- admin role in separate table with permission scope
- each admin endpoint resolved by permission check

### Role model
```text
SUPER_ADMIN
  - all permissions
MODERATOR
  - report handling
  - user moderation
PHOTO_REVIEWER
  - photo review only
  - no access to unrelated private data
```

## 5. Detailed DB design

### 5.1 users
```text
id uuid pk
email varchar unique
password_hash text
status enum('PENDING','ACTIVE','SUSPENDED','BANNED','DELETED')
email_verified_at timestamptz nullable
created_at timestamptz
updated_at timestamptz
deleted_at timestamptz nullable
```

### 5.2 public_profiles
```text
id uuid pk
user_id uuid unique fk users.id
nickname varchar
campus_id uuid fk campuses.id
age int
gender varchar
department_id uuid nullable fk departments.id
mbti varchar nullable
bio text nullable
ideal_type text nullable
profile_status enum('INCOMPLETE','ACTIVE','HIDDEN')
appearance_summary_json jsonb nullable
created_at timestamptz
updated_at timestamptz
```

### 5.3 private_profiles
```text
id uuid pk
user_id uuid unique fk users.id
real_name varchar nullable
phone_number varchar nullable
student_id varchar nullable
birth_date date nullable
student_email varchar nullable
university_id uuid fk universities.id
campus_id uuid fk campuses.id
department_id uuid nullable fk departments.id
original_photo_storage_key text nullable
verification_data_json jsonb nullable
created_at timestamptz
updated_at timestamptz
```

### 5.4 appearance_evaluations
```text
id uuid pk
user_id uuid fk users.id
overall_impression int
style int
grooming int
photo_vibe int
evaluator_admin_id uuid fk admin_users.id
note text nullable
created_at timestamptz
updated_at timestamptz
```

### 5.5 matching_preferences
```text
id uuid pk
user_id uuid unique fk users.id
preferred_gender varchar
min_age int
max_age int
preferred_campus_mode varchar
preferred_campus_id uuid nullable fk campuses.id
allow_all_campuses bool
discovery_enabled bool
created_at timestamptz
updated_at timestamptz
```

### 5.6 photo_reviews
```text
id uuid pk
user_id uuid fk users.id
storage_key text
status enum('PENDING','IN_REVIEW','APPROVED','REJECTED','EXPIRED','DELETED')
review_version int
reviewed_by_admin_id uuid nullable fk admin_users.id
reviewed_at timestamptz nullable
expires_at timestamptz nullable
created_at timestamptz
updated_at timestamptz
```

### 5.7 likes
```text
id uuid pk
from_user_id uuid fk users.id
to_user_id uuid fk users.id
like_value bool
created_at timestamptz
updated_at timestamptz
```

### 5.8 matches
```text
id uuid pk
user_a_id uuid fk users.id
user_b_id uuid fk users.id
status enum('ACTIVE','UNMATCHED','BLOCKED')
created_at timestamptz
updated_at timestamptz
```

### 5.9 blocks
```text
id uuid pk
blocker_user_id uuid fk users.id
blocked_user_id uuid fk users.id
reason varchar nullable
created_at timestamptz
updated_at timestamptz
```

### 5.10 reports
```text
id uuid pk
reporter_user_id uuid fk users.id
reported_user_id uuid fk users.id
reason varchar
description text
status enum('OPEN','UNDER_REVIEW','RESOLVED','REJECTED')
reviewed_by_admin_id uuid nullable fk admin_users.id
created_at timestamptz
resolved_at timestamptz nullable
```

### 5.11 admin_users
```text
id uuid pk
email varchar unique
password_hash text
role_id uuid fk admin_roles.id
status enum('ACTIVE','DISABLED')
mfa_enabled bool
created_at timestamptz
updated_at timestamptz
```

### 5.12 audit_logs
```text
id uuid pk
admin_id uuid nullable fk admin_users.id
action varchar
target_type varchar
target_id uuid
ip_address inet
user_agent text
metadata_json jsonb
created_at timestamptz
```

## 6. Detailed API design

### 6.1 Auth APIs

#### POST /auth/send-verification
Request:
```json
{
  "school_id": 12,
  "email": "student@university.ac.kr"
}
```

Server behavior:
- validate school domain
- generate short-lived verification session
- send email via provider
- store hashed token only

#### POST /auth/verify
Request:
```json
{
  "email": "student@university.ac.kr",
  "code": "A1B2C3D4"
}
```

Server behavior:
- verify attempt count
- reject expired codes
- establish verified email state

#### POST /auth/register
Request:
```json
{
  "email": "student@university.ac.kr",
  "password": "StrongPass!123",
  "nickname": "익명의 대학생",
  "campus_id": "uuid",
  "gender": "female",
  "age": 21
}
```

Response:
```json
{
  "data": {
    "user_id": "uuid",
    "status": "PENDING"
  }
}
```

#### POST /auth/login
Request:
```json
{
  "email": "student@university.ac.kr",
  "password": "StrongPass!123"
}
```

Server behavior:
- verify password hash
- check status
- issue JWT access token

### 6.2 Profile APIs

#### GET /me
Returns:
- public profile
- settings summary
- account status
- onboarding progress

#### PATCH /me
Accepts change to:
- nickname
- bio
- mbti
- interests
- visibility fields

#### GET /profiles/{id}
Returns only public profile fields.

#### PATCH /preferences
Admin must not be able to see private matching preferences except through internal services.

### 6.3 Matching APIs

#### POST /likes
Request:
```json
{
  "to_user_id": "uuid"
}
```

Server logic:
- check target is eligible
- store like
- if reverse like exists, create match
- update notifications

#### GET /discover
Query:
- page
- limit
- campus_id optional

Server logic:
- apply hard filter
- rank candidates
- return safe public profile cards

### 6.4 Chat APIs

#### GET /matches/{id}/messages
- ensure current user is part of match

#### POST /matches/{id}/messages
Request:
```json
{
  "body": "안녕하세요!"
}
```

### 6.5 Report APIs

#### POST /reports
- validate reporter and target are different users
- store report with reason and optional description
- send notification to moderator queue

## 7. DB access patterns

### Repository design
- users_repository.py
- profile_repository.py
- matching_repository.py
- photo_review_repository.py
- admin_repository.py
- audit_repository.py

### Principles
- repositories only return domain objects and not raw internal secrets
- data retrieval should filter sensitive fields at serializer layer
- all reads of private profile or photo data should require explicit permission

## 8. Business logic services

### AuthService
- send_verification_email
- verify_code
- register_user
- authenticate_user
- issue_tokens

### ProfileService
- create_public_profile
- update_profile
- get_profile_by_id
- calculate_onboarding_progress

### MatchingService
- get_candidate_pool
- apply_hard_filters
- calculate_rank_score
- create_match_if_mutual_like

### PhotoService
- validate_upload
- save_to_private_storage
- create_review_record
- generate_signed_review_url
- delete_expired_photo_after_review

### AdminService
- list_users
- list_photo_reviews
- review_photo
- resolve_report
- update_user_status
- write_audit_log

## 9. Security implementation details

### API security middleware
- JWT validation middleware
- RBAC middleware
- rate limit middleware
- request validation middleware
- audit logging middleware for sensitive endpoints

### Sensitive file handling
- use private object buckets
- signed URL lifetime = 60–300 seconds
- no public read URL
- EXIF stripped on upload
- filename generated server-side randomly

### IDOR prevention patterns
- route check: authenticated user vs target user
- match membership check before chat access
- admin permission check for admin endpoints
- repository methods should not accept untrusted target ids without validation

## 10. Frontend integration design

### Auth state
- session stored securely
- token attached to API requests via interceptor
- protected routes redirect to login if unauthorized

### Data fetching
- use typed API client
- separate user API and admin API clients
- public profile list only exposes safe fields
- no direct access to admin routes in public app

### State model
- auth state
- onboard status
- discover state
- match state
- chat state
- admin moderation state

## 11. Recommended implementation order

1. DB schema and migrations
2. auth and verification APIs
3. user/profile APIs
4. private storage upload and review workflow
5. matching engine with filters
6. like/match/chat APIs
7. admin routes and audit logs
8. security hardening
9. frontend UI integration
10. QA test suite

## 12. Risks and mitigation

### Risk: privacy leakage through serializer layer
Mitigation:
- explicit response schemas
- no generic model serialization for private tables

### Risk: admin access overreach
Mitigation:
- role-specific permission mapping
- per-action audit logs
- signed URL short expiry

### Risk: candidate shortage causing churn
Mitigation:
- empty state and gradual filter relaxation messaging
- no automatic filter mutation without user consent

### Risk: photo metadata leak
Mitigation:
- EXIF stripping, file validation, random storage keys

## 13. Final technical recommendation

For MVP, the most robust architecture is:

- Next.js frontend
- FastAPI backend
- PostgreSQL database
- private object storage for originals
- Redis optional for caching and session assistance
- admin APIs fully isolated from public endpoints
- all sensitive data controlled by explicit backend permission checks

This keeps the system secure, maintainable, and scalable enough for later mobile expansion.
