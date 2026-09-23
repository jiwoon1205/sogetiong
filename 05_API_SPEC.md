# 05. API Specification

## 1. API style

- REST API
- JSON request/response
- Bearer token authentication for users
- Admin API uses separate token/role validation
- Common error format

## 2. Common response conventions

### Success response
```json
{
  "data": {
    "id": "uuid"
  }
}
```

### Error response
```json
{
  "error": {
    "code": "PROFILE_NOT_FOUND",
    "message": "프로필을 찾을 수 없습니다."
  }
}
```

### HTTP status conventions
- 200 OK: successful retrieval/update
- 201 Created: resource created
- 204 No Content: delete success
- 400 Bad Request: invalid input
- 401 Unauthorized: missing/invalid token
- 403 Forbidden: insufficient access
- 404 Not Found: missing resource
- 409 Conflict: duplicate or invalid state
- 429 Too Many Requests: rate limit hit
- 500 Internal Server Error: server issue

## 3. Authentication endpoints

### POST /auth/send-verification
Request
```json
{
  "school_id": 1,
  "email": "student@university.ac.kr"
}
```

Response
```json
{
  "data": {
    "message": "인증 메일이 발송되었습니다."
  }
}
```

Auth: none
Rate limit: yes

### POST /auth/verify
Request
```json
{
  "email": "student@university.ac.kr",
  "code": "A1B2C3"
}
```

Response
```json
{
  "data": {
    "verified": true
  }
}
```

### POST /auth/register
Request
```json
{
  "email": "student@university.ac.kr",
  "password": "StrongPass!23",
  "nickname": "익명의 대학생",
  "campus_id": 2,
  "gender": "female",
  "age": 21
}
```

Response
```json
{
  "data": {
    "user_id": "uuid",
    "status": "PENDING"
  }
}
```

### POST /auth/login
Request
```json
{
  "email": "student@university.ac.kr",
  "password": "StrongPass!23"
}
```

Response
```json
{
  "data": {
    "access_token": "jwt",
    "refresh_token": "refresh-token"
  }
}
```

### POST /auth/logout
Auth: required

## 4. User profile endpoints

### GET /me
Auth: required

Response includes only safe fields.

### PATCH /me
Auth: required

Request example
```json
{
  "nickname": "커피를 좋아하는 사람",
  "bio": "카페와 영화를 좋아해요.",
  "mbti": "INTP"
}
```

### GET /profiles
Query params:
- campus_id
- gender
- age_min
- age_max
- page
- limit

Auth: required

### GET /profiles/{id}
Auth: required

Returns public profile only. Does not include private data.

### PATCH /preferences
Auth: required

Request example
```json
{
  "preferred_gender": "female",
  "min_age": 20,
  "max_age": 27,
  "preferred_campus_mode": "all",
  "excluded_department_ids": [5, 7]
}
```

## 5. Matching endpoints

### POST /likes
Auth: required

Request
```json
{
  "to_user_id": "uuid"
}
```

Response
```json
{
  "data": {
    "liked": true,
    "matched": false,
    "match_id": null,
    "chat_room_id": null
  }
}
```

When both users have liked each other, `matched` is `true` and `match_id` is
returned. The `match_id` is also the private chat room identifier. Messages
can only be read or sent by the two users in that match.

### DELETE /likes/{id}
Auth: required

### GET /matches
Auth: required

### GET /matches/{id}
Auth: required

### GET /matches/{id}/messages
Auth: required, match member only

### POST /matches/{id}/messages
Auth: required, match member only

Request
```json
{
  "body": "안녕하세요!"
}
```

## 6. Block and report endpoints

### POST /blocks
Request
```json
{
  "blocked_user_id": "uuid",
  "reason": "inappropriate_behavior"
}
```

### DELETE /blocks/{id}

### POST /reports
Request
```json
{
  "reported_user_id": "uuid",
  "reason": "harassment",
  "description": "불쾌한 발언을 했습니다."
}
```

## 7. Admin endpoints

### GET /admin/users
Auth: admin required

### GET /admin/photo-reviews
Auth: admin required, photo reviewer scope

### GET /admin/photo-reviews/{id}
Auth: admin required

### POST /admin/photo-reviews/{id}
Request
```json
{
  "overall_impression": 8,
  "style": 7,
  "grooming": 8,
  "photo_vibe": 9,
  "note": "전반적으로 깔끔한 인상입니다."
}
```

### GET /admin/reports
Auth: admin required

### PATCH /admin/reports/{id}
Request
```json
{
  "status": "RESOLVED",
  "resolution_note": "경고 조치"
}
```

### PATCH /admin/users/{id}/status
Request
```json
{
  "status": "SUSPENDED",
  "reason": "신고 누적"
}
```

## 8. Authorization requirements

### User endpoints
- only authenticated user can access own profile
- matches and chat are restricted to participants only
- public profile reads can be open to other active users only

### Admin endpoints
- role-specific permissions enforced at server level
- photo reviewers cannot access all private profiles
- super admin only can assign roles or change global settings

## 9. Rate limits

- email verification request: 3 requests/hour per user
- verification code check: 10 attempts per code
- login: 10 attempts per 15 minutes per account
- report submission: 5/hour per user
- like action: moderate burst protection
- admin sensitive endpoints: stricter limit and logging

## 10. Response contract notes

- All API output should exclude raw DB errors
- Sensitive data fields should be omitted by serializer layer
- Internal exceptions should map to generic user-facing error codes

## 11. Example access control rules

### IDOR prevention
- /profiles/{id} must check whether the user is the owner or a permitted viewer
- /matches/{id} and /chat/{matchId} must confirm membership
- /admin/users/{id} must verify admin role and permission scope

## 12. API testing expectations

- Unit tests for scoring and filter logic
- Integration tests for register, verify, profile, photo review, match, chat, report
- Security tests for IDOR, admin bypass, XSS, SQLi, upload exploit

## 13. Governance

- API contract versioning recommended after product stabilization
- Request validation at server boundary is mandatory
- Public vs private schema separation should be enforced by pydantic/typing models
