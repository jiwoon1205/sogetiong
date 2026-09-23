# 03. Information Architecture

## 1. IA goals

서비스의 정보 구조는 다음 기준을 따른다.

- 사용자와 관리자 경로를 엄격히 분리
- 공개 정보와 비공개 정보를 명확히 구분
- 모바일-first 웹에서 빠르게 탐색 가능하도록 구조화
- onboarding, discover, match, chat, profile, settings로 단계를 구성

## 2. User IA

### Primary navigation
- Landing
- Sign in / Register
- Onboarding
- Discover
- Matches
- Chat
- Profile
- Settings
- Report

### Secondary navigation
- My profile
- Matching preferences
- Block list
- Notification center
- Account security

## 3. Page structure

### Public pages
- /
- /auth
- /auth/register
- /auth/verify

### Onboarding pages
- /onboarding/profile
- /onboarding/photo
- /onboarding/preferences

### Core app pages
- /discover
- /matches
- /chat/[matchId]
- /profile
- /settings
- /reports

### Admin pages
- /admin
- /admin/users
- /admin/photos
- /admin/reports
- /admin/settings
- /admin/universities
- /admin/campuses
- /admin/departments
- /admin/matching-settings

## 4. Information hierarchy

### 4.1 Landing
Elements:
- service intro
- school selection
- login CTA
- policy link
- FAQ

### 4.2 Auth
- school email input
- verification code input
- login form
- password reset (later)

### 4.3 Onboarding
- school verification status
- profile summary
- upload status
- preference completion checklist
- validation messages

### 4.4 Discover
- card list
- filter summary
- candidate count
- empty state message
- pass / like actions

### 4.5 Matches
- active matches list
- new match banner
- pending chat status
- unmatch action

### 4.6 Chat
- match header
- message list
- input composer
- block/report controls

### 4.7 Profile
- public profile card
- self summary
- appearance summary
- interests
- privacy settings

### 4.8 Settings
- account details
- notification controls
- preference management
- privacy controls
- security / session management

## 5. Admin IA

### Admin homepage
- summary cards
- users count
- pending review count
- open reports
- system health

### User management
- user list
- filter by status
- search by nickname or email hash
- view private profile status
- suspend / ban actions

### Photo review
- review queue list
- photo detail
- evaluation form
- approval/rejection actions
- audit trail display

### Report management
- open report list
- report detail
- investigation notes
- resolution status

### System settings
- matching weight config
- universities/campuses/departments management
- role assignment
- policy/config revision history

## 6. Site map

```text
ROOT
├── Landing
├── Auth
│   ├── Register
│   ├── Verify
│   └── Login
├── Onboarding
│   ├── Profile
│   ├── Photo
│   └── Preferences
├── App
│   ├── Discover
│   ├── Matches
│   ├── Chat
│   ├── Profile
│   ├── Settings
│   └── Reports
└── Admin
    ├── Dashboard
    ├── Users
    ├── Photos
    ├── Reports
    ├── Universities
    ├── Campuses
    ├── Departments
    ├── Matching Settings
    └── System Logs
```

## 7. Data classification in IA

### Public
- nickname
- campus
- age
- gender
- department_public
- MBTI
- bio
- ideal_type
- interests
- appearance summary

### Matching private
- preferred gender
- preferred age range
- preferred campus
- excluded departments
- preferred departments
- block list

### Highly private
- real_name
- student_email
- phone_number
- student_id
- birth_date
- original_photo
- verification data
- report data
- audit records

## 8. Rule of access

- White-list access by role and context
- Public API cannot return private data
- Matching private should not be visible to any other user
- Admin pages must verify role and scope
- Even admin roles are segmented by capability

## 9. UX navigation principles

- Keep user actions within 2–3 taps from discover to chat
- Use progress indicators in onboarding
- Keep recommendation cards as primary action area
- Put safety and reporting actions in clear but non-intrusive locations
- Never expose private or sensitive fields in page metadata or DOM

## 10. IA decisions

1. User-facing pages are intentionally simplified to avoid exposing sensitive data.
2. Matching logic is server-side and hidden from frontend.
3. Admin routes are isolated from public frontend.
4. Every sensitive page is protected by route-level access controls and backend validation.
5. Empty states and candidate shortage states are designed to reduce confusion and improve retention.
