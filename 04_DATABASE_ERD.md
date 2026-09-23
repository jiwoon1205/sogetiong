# 04. Database ERD

## 1. Design principles

- 개인정보와 공개정보를 분리한다.
- 관리자 전용 데이터는 별도 table 또는 별도 schema로 구분한다.
- 사용자는 공개 정보를 중심으로 프로필을 가지되, 비공개 정보는 별도 private_profiles 테이블로 관리한다.
- 추천 엔진은 내부 preferences와 relation tables를 기반으로 계산한다.
- 고정된 Many-to-Many 관계는 junction table을 사용한다.
- 모든 timestamp는 UTC 기준으로 저장한다.

## 2. Core table list

### 2.1 users
```text
users
- id (PK)
- email (unique, nullable after registration)
- password_hash
- status
- email_verified_at
- created_at
- updated_at
- deleted_at
```

### 2.2 universities
```text
universities
- id (PK)
- name
- active
- created_at
- updated_at
```

### 2.3 campuses
```text
campuses
- id (PK)
- university_id (FK)
- name
- code
- active
- created_at
- updated_at
```

### 2.4 departments
```text
departments
- id (PK)
- campus_id (FK)
- name
- code
- active
- created_at
- updated_at
```

### 2.5 public_profiles
```text
public_profiles
- id (PK)
- user_id (FK unique)
- nickname
- campus_id (FK)
- age
- gender
- department_id (FK nullable)
- mbti
- bio
- ideal_type
- profile_status
- appearance_summary_json
- created_at
- updated_at
```

### 2.6 private_profiles
```text
private_profiles
- id (PK)
- user_id (FK unique)
- real_name
- phone_number
- student_id
- birth_date
- student_email
- university_id (FK)
- campus_id (FK)
- department_id (FK nullable)
- original_photo_storage_key
- verification_data_json
- created_at
- updated_at
```

### 2.7 appearance_evaluations
```text
appearance_evaluations
- id (PK)
- user_id (FK)
- overall_impression
- style
- grooming
- photo_vibe
- evaluator_admin_id (FK)
- evaluation_note
- created_at
- updated_at
```

### 2.8 photo_reviews
```text
photo_reviews
- id (PK)
- user_id (FK)
- storage_key
- status
- review_version
- reviewed_by_admin_id (FK nullable)
- reviewed_at
- expires_at
- created_at
- updated_at
```

### 2.9 matching_preferences
```text
matching_preferences
- id (PK)
- user_id (FK unique)
- preferred_gender
- min_age
- max_age
- preferred_campus_mode
- preferred_campus_id nullable
- allow_all_campuses
- created_at
- updated_at
```

### 2.10 excluded_departments
```text
excluded_departments
- id (PK)
- user_id (FK)
- department_id (FK)
- created_at
```

### 2.11 preferred_departments
```text
preferred_departments
- id (PK)
- user_id (FK)
- department_id (FK)
- created_at
```

### 2.12 interests
```text
interests
- id (PK)
- name
- created_at
```

### 2.13 user_interests
```text
user_interests
- id (PK)
- user_id (FK)
- interest_id (FK)
- created_at
```

### 2.14 likes
```text
likes
- id (PK)
- from_user_id (FK)
- to_user_id (FK)
- like_value
- created_at
- updated_at
```

### 2.15 matches
```text
matches
- id (PK)
- user_a_id (FK)
- user_b_id (FK)
- status
- created_at
- updated_at
```

### 2.16 messages
```text
messages
- id (PK)
- match_id (FK)
- sender_user_id (FK)
- body
- message_type
- created_at
- updated_at
```

### 2.17 blocks
```text
blocks
- id (PK)
- blocker_user_id (FK)
- blocked_user_id (FK)
- reason
- created_at
- updated_at
```

### 2.18 reports
```text
reports
- id (PK)
- reporter_user_id (FK)
- reported_user_id (FK)
- reason
- description
- status
- reviewed_by_admin_id (FK nullable)
- created_at
- resolved_at
```

### 2.19 notifications
```text
notifications
- id (PK)
- user_id (FK)
- type
- title
- body
- read_at
- created_at
```

### 2.20 admin_users
```text
admin_users
- id (PK)
- email
- password_hash
- role_id (FK)
- status
- mfa_enabled
- created_at
- updated_at
```

### 2.21 admin_roles
```text
admin_roles
- id (PK)
- name
- permissions_json
- created_at
```

### 2.22 audit_logs
```text
audit_logs
- id (PK)
- admin_id (FK nullable)
- action
- target_type
- target_id
- ip_address
- user_agent
- metadata_json
- created_at
```

### 2.23 verification_tokens
```text
verification_tokens
- id (PK)
- user_id (FK nullable)
- email
- code_hash
- expires_at
- attempt_count
- used_at
- created_at
```

## 3. Relationship summary

### User to profile
- users 1:1 public_profiles
- users 1:1 private_profiles
- users 1:N photo_reviews
- users 1:N appearance_evaluations
- users 1:1 matching_preferences

### User to relations
- users 1:N likes (as sender)
- users 1:N likes (as receiver)
- users 1:N blocks
- users 1:N reports (as reporter)
- users 1:N reports (as reported)
- users 1:N notifications
- users 1:N messages

### University/campus/department
- universities 1:N campuses
- campuses 1:N departments
- campuses 1:N public_profiles
- campuses 1:N private_profiles
- departments 1:N excluded_departments
- departments 1:N preferred_departments

## 4. Key constraints

- email unique on users
- unique index on public_profiles.user_id
- unique index on private_profiles.user_id
- unique index on matching_preferences.user_id
- unique constraint on likes from_user_id + to_user_id
- unique constraint on blocks blocker_user_id + blocked_user_id
- unique constraint on user_interests (user_id, interest_id)
- check constraint on genders
- check constraint on age range
- check constraint on statuses and review states

## 5. ERD notes

```text
users
 ├─ 1:1 public_profiles
 ├─ 1:1 private_profiles
 ├─ 1:N photo_reviews
 ├─ 1:N appearance_evaluations
 ├─ 1:1 matching_preferences
 ├─ 1:N likes
 ├─ 1:N blocks
 ├─ 1:N reports
 └─ 1:N notifications

universities
 └─ 1:N campuses

campuses
 └─ 1:N departments
```

## 6. Soft delete / retention policy

- users.deleted_at used for logical deletion
- reports are not hard-deleted immediately; resolution history is preserved
- photo_reviews may retain expired review records for audit
- admin audit logs are append-only

## 7. Data retention recommendation

- verification_tokens: short-lived, e.g. 10–15 minutes
- original photo: minimum retention period, then deletion
- report records: retention per policy and security review
- audit_logs: retained according to internal compliance policy

## 8. Design trade-offs

- Public/private split increases complexity but drastically reduces privacy risk.
- Using JSON for evaluation metadata is acceptable for flexible scoring, but schema validation should be enforced.
- Matching preferences should remain detachable from public profile to prevent accidental exposure.
