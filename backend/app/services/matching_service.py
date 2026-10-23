"""매칭 엔진 (설계도 §18, §19 / 2026-09-30 변경 / 2026-10-24 가중치 추첨으로 재설계).

Stage 1 — Hard Filter: 조건에 맞지 않는 후보 제거 (양쪽 조건을 모두 확인). 차단·매칭·최근 PASS/LIKE는 API에서 뺀다.
Stage 2 — 가중치 추첨 (2026-10-24, 프로젝트 문서 "추천 알고리즘 재설계 (2026-10-24)"):
    조건이 맞는 모든 사람이 추첨 대상. 가중치에 비례해 뽑는다 (가중치가 낮아도 0이 아님).
    가중치 = ① 외모 등급(같음 2.0 / 한 단계 1.4 / 두 단계 1.0)
           × ② 활동(1 + 최근 14일 접속한 날 비율)
           × ③ 나를 좋아요한 횟수(1 + 0.25 × 횟수, 최대 2)
           × ④ 취향(1 + 관심사·완성도·MBTI 점수)
    네 요소 모두 최대 2배로 "고르게" 나눴다. 배수는 .env(REC_*)로 바꿀 수 있다.
    예전 방식(등급 차이로 딱 잘라 줄 세우기 → 뒤쪽 사람은 사실상 안 나옴)은 없앴다.
Stage 3 — 슈퍼 VIP는 페이지 맨 앞 (최대 SUPER_VIP_SLOTS명).

외모 등급과 "나를 좋아요했는지"는 내부 데이터라 이 파일 밖으로(API 응답으로) 절대 나가면 안 된다.

이 파일의 함수는 DB를 모르는 순수 함수라 단위 테스트가 쉽다.
DB에서 데이터를 모으는 부분은 app/services/profile_service.py에 있다.
"""

import random
import uuid
from dataclasses import dataclass, field

TIER_LEVEL = {"LOW": 0, "MID": 1, "HIGH": 2}
MAX_TIER_GAP = 2  # 상↔하


@dataclass
class Preferences:
    preferred_gender: str  # MALE / FEMALE / ANY
    min_age: int | None  # None = 아래쪽 제한 없음
    max_age: int | None  # None = 위쪽 제한 없음 ("35세 이상" 또는 "나이 상관없음")
    campus_mode: str  # MY / ALL / SELECTED
    campus_ids: set[uuid.UUID] = field(default_factory=set)
    exclude_same_department: bool = False
    # SELECTED일 때 고른 캠퍼스들이 속한 학교 (2026-10-24). 슈퍼 VIP도 이 학교 조건은 지킨다 (_school_ok)
    university_ids: set[uuid.UUID] = field(default_factory=set)


@dataclass
class Person:
    user_id: uuid.UUID
    gender: str
    age: int
    campus_id: uuid.UUID
    department_id: uuid.UUID | None
    preferences: Preferences | None
    interests: set[str] = field(default_factory=set)
    mbti: str | None = None
    has_bio: bool = False
    has_ideal_type: bool = False
    # ⑤ 프로필 정성 (2026-10-24): 자기소개·이상형 글자 수(띄어쓰기 제외), 얼굴상·키 입력 여부
    bio_chars: int = 0
    ideal_chars: int = 0
    has_face_type: bool = False
    has_height: bool = False
    tier: str | None = None  # HIGH / MID / LOW (내부 전용)
    # 활동 점수 0~1: 최근 14일 중 접속한 날 수 ÷ 14 (2026-10-01)
    activity: float = 0.0
    # 슈퍼 VIP (2026-10-12, 관리자 지정): 나이·캠퍼스 조건과 무관하게 추천에 나온다 (내부 전용)
    super_vip: bool = False
    # 학교 (2026-10-24 경희대 확장). None = 모름 (예전 테스트처럼 학교를 안 넣은 경우 → 학교 조건을 보지 않음)
    university_id: uuid.UUID | None = None


@dataclass
class Weights:
    interest: float
    completeness: float
    mbti: float
    # (2026-10-24부터 취향 점수에는 넣지 않는다. 활동은 가중치 ②로 따로 곱한다)
    activity: float = 0.0
    # 가중치 추첨 배수 (2026-10-24). 기본값 = 설정 기본값
    tier_same: float = 2.0
    tier_one: float = 1.4
    tier_two: float = 1.0
    activity_max: float = 2.0
    liked_max: float = 2.0
    liked_full: int = 4
    taste_max: float = 2.0
    effort_max: float = 2.0


# ---------- Stage 1: 조건 확인 ----------

def age_in_range(age: int, min_age: int | None, max_age: int | None) -> bool:
    """나이 조건. 비어 있는(None) 쪽은 확인하지 않는다 → 둘 다 None이면 "나이 상관없음"."""
    if min_age is not None and age < min_age:
        return False
    if max_age is not None and age > max_age:
        return False
    return True


def satisfies(viewer: Person, candidate: Person) -> bool:
    """candidate가 viewer의 매칭 조건을 모두 만족하는가? (한 방향)"""
    prefs = viewer.preferences
    if prefs is None:
        return False
    if prefs.preferred_gender != "ANY" and candidate.gender != prefs.preferred_gender:
        return False
    if not age_in_range(candidate.age, prefs.min_age, prefs.max_age):
        return False
    if prefs.campus_mode == "MY" and candidate.campus_id != viewer.campus_id:
        return False
    if prefs.campus_mode == "SELECTED" and candidate.campus_id not in prefs.campus_ids:
        return False
    # 학과가 없는 사람은 후보가 될 수 없다 (학과 필수 — API에서도 막지만 한 번 더 확인)
    if candidate.department_id is None:
        return False
    # 같은 과 제외: 내가 켰고 상대가 나와 같은 과면 제외
    if prefs.exclude_same_department and candidate.department_id == viewer.department_id:
        return False
    return True


def _school_ok(viewer: Person, candidate: Person) -> bool:
    """viewer가 고른 캠퍼스들이 속한 학교에 candidate가 있는가 (캠퍼스는 따지지 않음, 2026-10-24).

    - ALL(모든 캠퍼스): 학교 상관없음
    - MY(내 캠퍼스): 내 학교
    - SELECTED: 고른 캠퍼스들의 학교
    """
    prefs = viewer.preferences
    if prefs is None or candidate.university_id is None:
        return True
    if prefs.campus_mode == "MY":
        return viewer.university_id is None or candidate.university_id == viewer.university_id
    if prefs.campus_mode == "SELECTED" and prefs.university_ids:
        return candidate.university_id in prefs.university_ids
    return True


def _basic_ok(viewer: Person, candidate: Person) -> bool:
    """슈퍼 VIP가 끼어 있을 때도 지키는 조건 (한 방향): 원하는 성별, 학과 있음, 같은 과 제외 (2026-10-12),
    학교 (2026-10-24: "외대만" 고른 사람에게 경희대 슈퍼 VIP가 뜨지 않게).
    나이·캠퍼스는 보지 않는다. 차단은 API(excluded_user_ids)에서 따로 뺀다."""
    prefs = viewer.preferences
    if prefs is None:
        return False
    if prefs.preferred_gender != "ANY" and candidate.gender != prefs.preferred_gender:
        return False
    if not _school_ok(viewer, candidate):
        return False
    if candidate.department_id is None:
        return False
    if prefs.exclude_same_department and candidate.department_id == viewer.department_id:
        return False
    return True


def mutually_compatible(viewer: Person, candidate: Person) -> bool:
    """양쪽 조건을 모두 만족해야 추천한다.

    예) A가 "같은 과 제외"를 켰고 B가 A와 같은 과라면, A에게 B가 안 보이고
        B에게도 A가 보이지 않는다 (B는 스위치를 안 켰어도). 이유는 누구에게도 알려주지 않는다 (설계도 §17).
    """
    if viewer.user_id == candidate.user_id:
        return False
    if viewer.super_vip or candidate.super_vip:
        # 슈퍼 VIP: 상대의 나이·캠퍼스 조건과 무관, 학교 조건은 지킴 (양쪽 모두 같은 규칙 → 슈퍼 VIP를 LIKE한 사람에게 LIKE로 답할 수도 있다)
        return _basic_ok(viewer, candidate) and _basic_ok(candidate, viewer)
    return satisfies(viewer, candidate) and satisfies(candidate, viewer)


# ---------- Stage 2: 가중치 ----------

def tier_gap(a: str | None, b: str | None) -> int:
    """등급 차이 0(같음) / 1(한 단계) / 2(두 단계). 등급을 모르면 가장 뒤로 보낸다."""
    if a not in TIER_LEVEL or b not in TIER_LEVEL:
        return MAX_TIER_GAP + 1
    return abs(TIER_LEVEL[a] - TIER_LEVEL[b])


INTEREST_MAX = 3  # 관심사는 최대 3개 (2026-10-24)


def _interest_similarity(a: set[str], b: set[str]) -> float:
    """겹친 관심사 수 ÷ 3 (2026-10-24). 3개 모두 겹치면 1, 1개 겹치면 1/3.

    - 많이 고른다고 유리하지 않다: 예전에 4개 이상 골라 둔 사람은 분모가 그 사람이 고른 수가 된다
      (10개 중 3개 겹침 = 0.3). 프로필을 다시 저장하면 3개로 줄여야 한다.
    - 1개만 골라서 그게 겹쳐도 1/3 (예전 방식은 "적게 고른 사람 기준"이라 1개만 골라도 만점이 됐다).
    """
    if not a or not b:
        return 0.0
    return len(a & b) / max(INTEREST_MAX, len(a), len(b))


def _mbti_similarity(a: str | None, b: str | None) -> float:
    if not a or not b or len(a) != 4 or len(b) != 4:
        return 0.0
    return sum(1 for x, y in zip(a.upper(), b.upper()) if x == y) / 4


def _completeness(person: Person) -> float:
    """프로필을 얼마나 채웠나.

    - 학과 공개 여부는 넣지 않는다: 공개는 본인 선택이므로 숨겼다고 불이익을 주면 안 된다.
    - MBTI는 넣지 않는다: MBTI 유사도에서 이미 0점이 되므로 두 번 불리하게 하지 않는다.
    """
    checks = [person.has_bio, person.has_ideal_type, len(person.interests) >= 3]
    return sum(checks) / len(checks)


# ⑤ 프로필 정성 기준 (2026-10-24). 글자 수는 띄어쓰기·줄바꿈을 빼고 센다.
BIO_FULL, BIO_HALF = 150, 30  # 자기소개: 150자 이상(휴대폰에서 약 5줄) 만점, 30자 이상 절반
IDEAL_FULL, IDEAL_HALF = 100, 30  # 이상형: 100자 이상(약 3~4줄) 만점, 30자 이상 절반
MIN_DISTINCT_CHARS = 10  # "ㅋㅋㅋㅋ…"처럼 서로 다른 글자가 10개 미만이면 0점
EFFORT_PARTS = {"bio": 0.40, "ideal": 0.30, "mbti": 0.10, "face": 0.10, "height": 0.10}


def text_chars(text: str | None) -> int:
    """정성 점수용 글자 수: 띄어쓰기·줄바꿈 제외. 같은 글자 반복(서로 다른 글자 10개 미만)은 0."""
    if not text:
        return 0
    chars = [c for c in text if not c.isspace()]
    if len(set(chars)) < MIN_DISTINCT_CHARS:
        return 0
    return len(chars)


def _length_score(chars: int, full: int, half: int) -> float:
    if chars >= full:
        return 1.0
    if chars >= half:
        return 0.5
    return 0.0


def effort(person: Person) -> float:
    """⑤ 프로필 정성 0~1. 관심사 개수는 넣지 않는다 (관심사는 ④에서 "겹치는 수"만 본다).
    학과 공개 여부도 넣지 않는다 (공개는 본인 선택)."""
    parts = EFFORT_PARTS
    return round(
        parts["bio"] * _length_score(person.bio_chars, BIO_FULL, BIO_HALF)
        + parts["ideal"] * _length_score(person.ideal_chars, IDEAL_FULL, IDEAL_HALF)
        + parts["mbti"] * (1.0 if person.mbti else 0.0)
        + parts["face"] * (1.0 if person.has_face_type else 0.0)
        + parts["height"] * (1.0 if person.has_height else 0.0),
        6,
    )


def score(viewer: Person, candidate: Person, weights: Weights) -> float:
    """같은 등급 차이 안에서의 세부 점수 (0~1). 가중치는 설정(.env)에서 바꿀 수 있다."""
    total = (
        weights.interest * _interest_similarity(viewer.interests, candidate.interests)
        + weights.completeness * _completeness(candidate)
        + weights.mbti * _mbti_similarity(viewer.mbti, candidate.mbti)
        + weights.activity * min(max(candidate.activity, 0.0), 1.0)
    )
    return round(total, 6)


def taste(viewer: Person, candidate: Person, weights: Weights) -> float:
    """④ 취향 점수 0~1 (관심사가 겹치는 정도·MBTI 비슷한 정도). 활동은 ②, 프로필 정성은 ⑤에서 따로 곱한다.
    (WEIGHT_COMPLETENESS는 2026-10-24부터 기본 0 — 완성도는 ⑤ 프로필 정성으로 옮김)"""
    total = weights.interest + weights.completeness + weights.mbti
    if total <= 0:
        return 0.0
    value = (
        weights.interest * _interest_similarity(viewer.interests, candidate.interests)
        + weights.completeness * _completeness(candidate)
        + weights.mbti * _mbti_similarity(viewer.mbti, candidate.mbti)
    ) / total
    return min(max(value, 0.0), 1.0)


def weight(viewer: Person, candidate: Person, weights: Weights, liked_count: int = 0) -> float:
    """추첨 가중치 = ① 등급 × ② 활동 × ③ 나를 좋아요한 횟수 × ④ 취향 × ⑤ 프로필 정성 (2026-10-24). 항상 0보다 크다."""
    gap = tier_gap(viewer.tier, candidate.tier)
    tier = {0: weights.tier_same, 1: weights.tier_one}.get(gap, weights.tier_two)
    activity = 1 + (weights.activity_max - 1) * min(max(candidate.activity, 0.0), 1.0)
    full = max(weights.liked_full, 1)
    liked = 1 + (weights.liked_max - 1) * min(max(liked_count, 0), full) / full
    pref = 1 + (weights.taste_max - 1) * taste(viewer, candidate, weights)
    care = 1 + (weights.effort_max - 1) * effort(candidate)
    return max(tier, 0.01) * max(activity, 0.01) * max(liked, 0.01) * max(pref, 0.01) * max(care, 0.01)


def draw(
    viewer: Person,
    candidates: list[Person],
    weights: Weights,
    rng: random.Random | None = None,
    liked_counts: dict[uuid.UUID, int] | None = None,
) -> list[Person]:
    """조건이 맞는 사람을 가중치에 비례한 확률로 순서대로 뽑는다 (가중치 랜덤 비복원 추출).

    키 = 난수^(1/가중치) 가 큰 순서 (Efraimidis–Spirakis). 가중치가 2배면 앞에 나올 확률도 그만큼 높다.
    새로고침할 때마다 다시 뽑으므로 가중치가 낮은 사람도 가끔 앞에 나온다.
    """
    rng = rng or random.Random()
    counts = liked_counts or {}
    eligible = [c for c in candidates if mutually_compatible(viewer, c)]
    keyed = [(rng.random() ** (1.0 / weight(viewer, c, weights, counts.get(c.user_id, 0))), c) for c in eligible]
    keyed.sort(key=lambda kc: kc[0], reverse=True)
    return [c for _, c in keyed]


def rank(
    viewer: Person,
    candidates: list[Person],
    weights: Weights,
    limit: int,
    *,
    liked_counts: dict[uuid.UUID, int] | None = None,
    rng: random.Random | None = None,
    super_vip_slots: int = 0,
) -> list[Person]:
    """추천 한 페이지: 가중치 추첨 → 슈퍼 VIP 맨 앞."""
    rng = rng or random.Random()
    ordered = draw(viewer, candidates, weights, rng, liked_counts)
    return _put_super_vip_first(ordered, ordered[:limit], limit, super_vip_slots, rng)


def _put_super_vip_first(ordered: list[Person], page: list[Person], limit: int, slots: int, rng: random.Random) -> list[Person]:
    """슈퍼 VIP를 페이지 맨 앞에 최대 slots명 넣는다 (2026-10-12). 여러 명이면 그중 랜덤으로 고른다.
    조건(성별·같은 과)·차단·PASS 숨김을 통과한 사람만 ordered에 들어 있다."""
    supers = [p for p in ordered if p.super_vip]
    if slots <= 0 or not supers:
        return page
    picked = rng.sample(supers, min(slots, len(supers)))
    picked_ids = {p.user_id for p in picked}
    rest = [p for p in page if p.user_id not in picked_ids]
    return (picked + rest)[:limit]
