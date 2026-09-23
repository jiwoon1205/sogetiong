# 08. Privacy and Security

## 1. Purpose

본 서비스는 개인 정보와 사진을 다루는 데이트 서비스이므로, 개인정보 보호와 접근 제어를 최우선 설계 요소로 삼는다.

## 2. Privacy 3-layer model

### Layer 1: Public profile
User-visible data only.

- nickname
- campus
- age
- gender
- department_public
- mbti
- bio
- ideal_type
- interests
- appearance_evaluation summary

### Layer 2: Matching private data
Used internally for recommendation logic only.

- preferred_gender
- preferred_age_range
- preferred_campus
- excluded_departments
- preferred_departments
- blocked_users

### Layer 3: Highly private data
Admin/system exclusive.

- real_name
- student_email
- phone_number
- student_id
- birth_date
- original_photo
- verification_data
- report_data

## 3. Access control rules

- Public API must never return Layer 3 data
- Matching private data must not be exposed to other users
- Layer 3 data is only available in restricted admin routes or internal service calls
- All DB queries must use server-side authorization checks

## 4. Photo upload security

### Required controls
- MIME type validation
- extension validation
- file size limit
- image format validation
- malicious file scanning
- EXIF metadata stripping
- server-generated file names
- random storage path
- no public URL exposure
- no direct object URL in API response

### Additional requirement
- EXIF GPS information must be removed before storage
- original photo should be private object storage only
- if admin reviews are complete, delete original photo automatically after retention period

## 5. Object storage strategy

Recommended strategy:
- Store original files in private bucket
- Keep temporary signed URLs only for admin review sessions
- Never expose direct public file URLs to browser or API clients
- Use short-lived signed URLs with access logging

## 6. IDOR prevention

### Mandatory rules
- User ID in path must be validated against authenticated user
- Match and chat endpoints must verify membership
- Admin endpoints must verify admin role and scope
- No generic lookup pattern that exposes private records by raw ID

### Bad examples to avoid
- /users/123
- /admin/photos/{id} without scope validation
- /profiles/{id} where any user can fetch another user’s private details

## 7. Logging and monitoring

### Must avoid logs containing
- password
- verification codes
- original photo URL
- phone number
- real name

### Log allowed
- admin action type
- target id
- timestamp
- IP
- role
- result status

## 8. Security controls checklist

- Authentication required on all user API
- Authorization required on all protected routes
- Input validation enforced on every request
- Rate limiting on email auth, login, report, and like actions
- CSRF protection for cookie-based auth
- CORS restrictions
- SQL injection prevention via parameterized queries
- XSS prevention via output encoding and safe frontend rendering
- File upload validation
- Session security and token rotation

## 9. Law and compliance notes

Before launch, the service should consult current official guidance on:

- personal data processing basis
- privacy policy
- consent/notice requirements
- retention and deletion schedule
- user rights access, correction, deletion
- breach response
- outsourced processor handling
- photo data handling
- underage use rules
- school identity verification processing

Important:
- legal interpretation should not be guessed
- official public guidance and legal review should be used

## 10. Age policy

MVP should define a clear age threshold such as:
- 19 years old or older

This should be documented in policy and aligned with legal review.

## 11. Admin and photo risk management

- admin are allowed to see original photos but must be trained and constrained
- download attempts should be logged
- screenshots and external sharing are not fully preventable
- 2FA recommended for admin accounts
- read-only or scoped roles should be enforced

## 12. Security test list

- another user’s private profile access attempt
- admin endpoint access by a non-admin user
- IDOR exploitation
- XSS payload via profile field
- SQL injection payload via user inputs
- upload exploit by renamed files or malformed MIME
- rate limit bypass attempt

## 13. Security principle summary

This service must treat personal data as a high-risk asset. The privacy model is not optional; it is the foundation of the product.

The safe default is:
- least access
- least retention
- least exposure
- strong admin segregation
- strict backend enforcement
