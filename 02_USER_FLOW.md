# 02. User Flow

## 1. Overall user journey

```text
Landing
  ↓
School selection
  ↓
School email verification
  ↓
Account creation
  ↓
Profile setup
  ↓
Photo submission
  ↓
Admin review queue
  ↓
Matching preferences
  ↓
Discover
  ↓
Like / Pass
  ↓
Match
  ↓
Chat
  ↓
Mutual disclosure (optional)
  ↓
Offline meeting
```

## 2. Registration flow

### Step 1: Landing
- 학교 선택
- 로그인/회원가입 CTA 제공
- 약관 및 개인정보 처리방침 확인

### Step 2: Email verification
- 학교 이메일 입력
- 서버가인증 코드 발송
- 코드 입력 후 인증 완료
- 인증된 이메일은 공개되지 않음

### Step 3: Account creation
- 비밀번호 입력
- 약관 동의
- 계정 생성

### Step 4: Profile setup
필수 공개 정보:
- nickname
- campus
- age
- gender

선택 공개 정보:
- department
- MBTI
- bio
- ideal_type
- interests

### Step 5: Photo submission
- 사용자 사진 업로드
- 서버에서 저장소에 비공개 업로드
- 관리자 리뷰 대기열에 등록
- Workflow: upload -> private object store -> review queue

### Step 6: Matching preferences
- preferred_gender
- preferred_age_range
- preferred_campus
- excluded_departments
- preferred_departments
- blocked_users

### Step 7: Discover entry
- 프로필 공개 여부 확인
- 사진이 승인되기 전까지 추천 잠금 여부 검토
- 관리자 승인 완료 후 탐색 활성화

## 3. Discover flow

### Card UI
- 익명 프로필 카드 중심
- 사용자에게는 얼굴 사진 대신 평가 요약 정보가 표시됨
- 노출 요소 예시:
  - nickname
  - age
  - campus
  - department
  - MBTI
  - appearance summary
  - bio
  - interests

### Action
- Like
- Pass
- Report (optional)

### Recommendation flow
```text
User opens discover
  ↓
Server loads eligible candidates
  ↓
Hard filter applied
  ↓
Scoring applied
  ↓
Recommended list returned
  ↓
User swipes like/pass
```

## 4. Like / Pass / Match flow

### PASS
- like = false
- 추천 목록에서 제외
- 추후 undo 기능을 위해 구조 확장 가능

### LIKE
- from_user, to_user 저장
- 상대가 이미 like 한 상태 확인
- mutual match 생성

### MATCH
- match 생성
- 양쪽 사용자에게 알림
- 채팅방 생성

## 5. Chat flow

```text
Match created
  ↓
Chat room opened
  ↓
Text/emoji message sent
  ↓
Block / report / unmatch available
```

### 제한사항
- 이미지 전송은 MVP에서 제외
- 비공개 정보는 채팅에서 자동 노출하지 않음
- 채팅방 내용은 신고/모더레이션 대상이 될 수 있음

## 6. Block flow

```text
User blocks partner
  ↓
Server stores block relation
  ↓
Candidate exclusion in matching algorithm
  ↓
Existing match/chat handling applied
```

## 7. Report flow

```text
User reports another profile
  ↓
Report reason selected
  ↓
Report stored in private report table
  ↓
Moderator reviews
  ↓
Action: warning / restriction / ban
```

## 8. User settings flow

- 프로필 수정
- 공개 정보 설정 변경
- 부적절한 닉네임 신고/수정 요청
- 차단 목록 관리
- 알림 설정
- 계정 탈퇴/삭제 요청

## 9. Admin flow

```text
Admin login
  ↓
Admin role check
  ↓
Dashboard access
  ↓
Photo review queue
  ↓
Evaluate appearance
  ↓
Save review result
  ↓
Public summary shown to users
```

## 10. Edge conditions

### Candidate shortage
- 조건에 맞는 프로필 부족 시:
  - 캠퍼스 범위 확장 제안
  - 정렬 가중치 또는 조건 범위 완화 제안
- 사용자의 동의 없이 조건을 자동 변경하지 않음

### Empty state
- 추천 후보가 없을 때 사용자에게 안내 메시지 제공
- “매칭 조건을 조금 넓히면 더 많은 사람을 만날 수 있습니다.” 형태로 안내

### account states
- PENDING
- ACTIVE
- SUSPENDED
- BANNED
- DELETED

## 11. Security-sensitive user flow notes

- 이메일 인증코드는 사용자가 직접 확인할 수 있지만, 서버는 코드 생성/검증만 수행
- 사용자 휴대폰 번호, 실명, 학생 ID는 등록 단계에서 비공개 유지
- 관리자 페이지는 일반 사용자에게 노출되지 않도록 API 분리
- 사용자 정보 공개 동의는 향후 선택 기능으로 확장

## 12. Final UX principle

사용자는 상대의 얼굴 사진을 보는 것이 아니라, 이미 관리자가 정의한 외적 특징 정보를 바탕으로 “누군지는 모르지만 어떤 사람인지 충분히 알 수 있는” 경험을 받는다.

이 UX는 단순한 사진 기반 스와이프가 아니라, 안전하고 익명적인 신뢰 기반 매칭 경험으로 설계된다.
