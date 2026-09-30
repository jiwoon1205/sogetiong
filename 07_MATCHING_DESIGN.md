# 07. Matching Design

> **2026-09-30 변경 (현재 기준)** — 아래 "0. 현재 규칙"이 최신이다. 1장 이후는 초기 설계 기록이며, 0장과 다르면 0장을 따른다.

## 0. 현재 규칙 (2026-09-30)

### 가입 · 원하는 성별
- 가입할 때 **성별(남/여)**과 **원하는 성별(남/여/상관없음)**을 필수로 고른다.
- 둘 다 가입 후 본인은 바꿀 수 없다. 잘못 골랐으면 가입한 학교 메일로 운영진에게 요청 → 관리자가 변경 (감사 로그 `USER_GENDER_CHANGE`).
- 원하는 성별은 `private_profiles.preferred_gender`에 저장 (예전 `matching_preferences.preferred_gender`에서 이동). 매칭 조건 화면에서는 보여주기만 한다.

### 외모 등급 (상/중/하)
- 관리자가 사진을 승인하며 4개 점수와 함께 **등급(HIGH/MID/LOW)을 직접 고른다** (필수).
- 등급은 **내부 데이터**: 어떤 사용자 API 응답에도 넣지 않는다 (본인 포함). 4개 점수는 지금처럼 공개.
- 가장 최근 평가의 등급을 쓴다. 등급이 없는 사람(등급 기능 이전 평가)은 추천에 나오지 않고, 본인도 추천을 볼 수 없다(`EVALUATION_REQUIRED`). 관리자가 사용자 상세 화면에서 등급만 채우면 된다.

### 추천 순서
1. **Hard Filter** (양방향, 이전과 같음): 같은 학교, 활성 계정, 사진 승인, 등급 있음, 매칭 조건 있음, 이미 LIKE/PASS/매칭/차단 제외, 성별·나이·캠퍼스·같은 과 제외
2. **등급 차이로 묶기**: 같은 등급 → 한 단계 차이(상↔중, 중↔하) → 두 단계 차이(상↔하, 막지 않고 맨 뒤)
3. **같은 묶음 안 세부 점수** (`WEIGHT_*`):
   - 관심사 60%: 겹친 수 ÷ 둘 중 적게 고른 사람의 관심사 수 (많이 고를수록 유리하던 문제 제거)
   - 프로필 완성도 25%: 소개글, 이상형, 관심사 3개 이상 (학과 공개 여부는 본인 선택이라 넣지 않음, MBTI는 유사도에서만 반영)
   - MBTI 15%: 같은 글자 수 ÷ 4
   - 외모 숫자 점수는 등급과 겹치므로 쓰지 않는다
4. **나를 LIKE한 사람 우대**: 한 페이지(10장)에 최대 2자리, 위치는 매번 랜덤, 30%는 우대 안 함. 등급이 같거나 한 단계 차이인 사람만. 카드에 LIKE 여부는 표시하지 않는다 (매칭 전 LIKE 비공개 원칙 유지).

### 하루 LIKE 한도
- 베타: **하루 5개** (`DAILY_LIKE_LIMIT`), 한국 시간 자정에 충전. 넘으면 429.
- DB의 likes 기록으로 세므로 서버 재시작과 무관. PASS는 하루 한도 없음.
- 추천 화면에 "오늘 남은 좋아요 N/5" 표시.

### 설정값 (.env)
| 이름 | 기본값 | 의미 |
|---|---|---|
| WEIGHT_INTEREST / WEIGHT_COMPLETENESS / WEIGHT_MBTI | 0.60 / 0.25 / 0.15 | 같은 등급 안 세부 점수 가중치 |
| LIKED_ME_SLOTS | 2 | 나를 LIKE한 사람에게 주는 최대 자리 수 |
| LIKED_ME_PROBABILITY | 0.7 | 우대를 적용할 확률 |
| DAILY_LIKE_LIMIT | 5 | 하루 LIKE 수 |

### 이번 범위에서 뺀 것
- 동시에 LIKE했을 때 매칭 누락 가능성 (운영 DB가 SQLite라 쓰기가 한 번에 하나씩 처리되어 실제로는 거의 생기지 않음)
- 빈 추천 화면의 이유 구분("조건이 좁음" / "다 봤음")

## 1. Matching goal

매칭은 단순한 좋아요 기반이 아니라, "사용자가 지정한 필터 + 공개 프로필 요약 + 서버-side score" 조합으로 계산한다.

핵심 규칙:
- 비공개 선호 조건은 공개하지 않음
- 서버에서 hard filter 적용
- 추천 우선순위는 rule-based scoring으로 계산
- 추천 가중치는 DB 또는 설정 파일에서 조정 가능
- 후보 부족 시 사용자에게 명시적으로 안내

## 2. Matching stages

### Stage 1: Hard Filter
다음 조건을 통과해야 추천 후보가 된다.

- same school
- active status
- not blocked
- not already passed
- not already matched
- not same user
- gender match
- age range match
- campus match
- excluded department not matched
- profile approval complete

### Stage 2: Ranking
추천 후보에 대해 점수를 계산한다.

Example fields:
- interest_similarity
- dating_style_similarity
- MBTI_similarity
- ideal_type_match
- appearance_preferences
- profile_completeness

Important rule:
- 외모 점수는 전체 추천 점수에서 과도하게 높은 비중을 차지하지 않음
- 외모는 보조 신호로만 사용하며, 사용자의 성향/매너/관심사와 균형 유지

## 3. Candidate filtering logic

### School constraint
- 기본적으로 같은 학교 사용자만 추천 대상
- 이후 다른 학교 또는 캠퍼스간 교차 추천은 정책별로 확장

### Gender and age
- matching_preferences에 정의된 preferred_gender, min_age, max_age 적용
- 서버에서 유효성 검증 후 필터 적용

### Campus logic
- preferred_campus_mode: 
  - same_campus
  - all_campuses
  - specific_campus

### Department filters
- (베타, 2026-09-29) 학과는 필수이고 "같은 과 제외" 스위치 하나만 쓴다.
  둘 중 한 명이라도 켰고 학과가 같으면 서로 추천되지 않는다. 학과가 없는 사람은 후보에서 빠진다.
- excluded_departments / preferred_departments 테이블은 남겨두지만 베타에서는 쓰지 않는다.
- 선호 학과 가산(15%)은 없애고 나머지에 비율대로 나눔: 관심사 47%, 외적 평가 23%, 프로필 완성도 18%, MBTI 12% (설정값 WEIGHT_*). → 2026-09-30에 0장 방식으로 대체.

## 4. Hard filter pseudocode

```python
eligible = []
for candidate in all_candidates:
    if candidate.user_id == current_user.id:
        continue
    if candidate.status != 'ACTIVE':
        continue
    if is_blocked(current_user.id, candidate.user_id):
        continue
    if has_passed(current_user.id, candidate.user_id):
        continue
    if has_match(current_user.id, candidate.user_id):
        continue
    if candidate.school_id != current_user.school_id:
        continue
    if not gender_match(current_user, candidate):
        continue
    if not age_match(current_user, candidate):
        continue
    if not campus_match(current_user, candidate):
        continue
    if excluded_department(current_user, candidate):
        continue
    eligible.append(candidate)
```

## 5. Ranking rules

Example weighted scoring:

```text
interest_similarity: 20%
dating_style_similarity: 20%
mbti_similarity: 15%
ideal_type_match: 15%
profile_completeness: 15%
appearance_preferences: 10%
account_activity: 5%
```

- All weights are stored in configuration section for easy tuning.
- weight values are auditable and versioned.

## 6. Candidate shortage logic

### Rule
If hard filter results are empty or too few:
- show message to user
- suggest relaxing filters
- never automatically change user filters without consent

Example message:
> 현재 조건으로는 추천 가능한 사람이 없습니다.
> 캠퍼스 범위를 전체 캠퍼스로 변경하면 더 많은 프로필을 볼 수 있습니다.

## 7. Like and pass behavior

### Like
- from_user_id / to_user_id recorded
- if reverse like exists, match created

### Pass
- action recorded as pass
- prevent repeated recommendation until undo or reset policy is enabled

### Match creation
- if both user A and user B like each other, a match is created
- both users are notified
- chat room opens

## 8. Match lifecycle

```text
LikeAtoB
LikeBtoA
  ↓
Match created
  ↓
Chat opened
  ↓
Notification pushed
```

## 9. Safety principles

- Do not expose user’s private preferences to others
- Do not rank based on sensitive traits such as ethnicity, religion, disability, health status, or sexual orientation
- Recommendation auditing log should record policy version and weight changes
- Match fairness monitoring should watch for overexposure or underexposure by demographic groups

## 10. Matching score configuration

Recommended approach:
- config file or DB table for weights
- version history table
- admin page to edit values
- audit record on each change

Example config table:
```text
matching_policy
- id
- version
- interest_weight
- mbti_weight
- ideal_type_weight
- appearance_weight
- profile_completeness_weight
- updated_by_admin_id
- updated_at
```

## 11. Test scenarios

### Scenario A
User A likes User B; B does not like A
- No match generated

### Scenario B
A and B both like each other
- Match created

### Scenario C
A blocks B
- B removed from A’s recommendation list

### Scenario D
A excludes Economics department
- B in Economics is not recommended to A

### Scenario E
A selects Seoul campus only
- B in Global campus is not recommended

## 12. Design decision summary

MVP should use:
- same-school hard filtering
- preference-based personal matching rules
- rule-based scoring with auditable weights
- no ML complexity until scale and retention justify it

This balances safety, speed, and product clarity without sacrificing privacy or fairness.
