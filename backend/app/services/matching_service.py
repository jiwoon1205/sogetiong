"""매칭 엔진 (설계도 §18, §19).

Stage 1 — Hard Filter: 조건에 맞지 않는 후보 제거 (양쪽 조건을 모두 확인)
Stage 2 — Ranking: 남은 후보를 점수로 정렬 (외적 평가는 일부만 반영)

이 파일의 함수는 DB를 모르는 순수 함수라 단위 테스트가 쉽다.
DB에서 데이터를 모으는 부분은 app/services/profile_service.py에 있다.
"""

import uuid
from dataclasses import dataclass, field


@dataclass
class Preferences:
    preferred_gender: str  # MALE / FEMALE / ANY
    min_age: int
    max_age: int
    campus_mode: str  # MY / ALL / SELECTED
    campus_ids: set[uuid.UUID] = field(default_factory=set)
    exclude_same_department: bool = False


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
    shows_department: bool = False
    appearance_scores: dict[str, int] | None = None


@dataclass
class Weights:
    interest: float
    appearance: float
    completeness: float
    mbti: float


def satisfies(viewer: Person, candidate: Person) -> bool:
    """candidate가 viewer의 매칭 조건을 모두 만족하는가? (한 방향)"""
    prefs = viewer.preferences
    if prefs is None:
        return False
    if prefs.preferred_gender != "ANY" and candidate.gender != prefs.preferred_gender:
        return False
    if not (prefs.min_age <= candidate.age <= prefs.max_age):
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


def mutually_compatible(viewer: Person, candidate: Person) -> bool:
    """양쪽 조건을 모두 만족해야 추천한다.

    예) A가 "같은 과 제외"를 켰고 B가 A와 같은 과라면, A에게 B가 안 보이고
        B에게도 A가 보이지 않는다 (B는 스위치를 안 켰어도). 이유는 누구에게도 알려주지 않는다 (설계도 §17).
    """
    if viewer.user_id == candidate.user_id:
        return False
    return satisfies(viewer, candidate) and satisfies(candidate, viewer)


def _interest_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _mbti_similarity(a: str | None, b: str | None) -> float:
    if not a or not b or len(a) != 4 or len(b) != 4:
        return 0.0
    return sum(1 for x, y in zip(a.upper(), b.upper()) if x == y) / 4


def _completeness(person: Person) -> float:
    checks = [
        person.has_bio,
        person.has_ideal_type,
        person.mbti is not None,
        len(person.interests) >= 3,
        person.shows_department,
    ]
    return sum(checks) / len(checks)


def _appearance(person: Person) -> float:
    if not person.appearance_scores:
        return 0.0
    values = list(person.appearance_scores.values())
    return (sum(values) / len(values)) / 10


def score(viewer: Person, candidate: Person, weights: Weights) -> float:
    """0~1 사이 점수. 가중치는 설정(.env)에서 바꿀 수 있다."""
    total = (
        weights.interest * _interest_similarity(viewer.interests, candidate.interests)
        + weights.appearance * _appearance(candidate)
        + weights.completeness * _completeness(candidate)
        + weights.mbti * _mbti_similarity(viewer.mbti, candidate.mbti)
    )
    return round(total, 6)


def rank(viewer: Person, candidates: list[Person], weights: Weights, limit: int) -> list[Person]:
    eligible = [c for c in candidates if mutually_compatible(viewer, c)]
    eligible.sort(key=lambda c: score(viewer, c, weights), reverse=True)
    return eligible[:limit]
