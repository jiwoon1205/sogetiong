# 07. Matching Design

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
- 선호 학과 가산(15%)은 없애고 나머지에 비율대로 나눔: 관심사 47%, 외적 평가 23%, 프로필 완성도 18%, MBTI 12% (설정값 WEIGHT_*).

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
