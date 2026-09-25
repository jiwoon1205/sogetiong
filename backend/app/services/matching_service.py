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
    excluded_department_ids: set[uuid.UUID] = field(default_factory=set)
    preferred_department_ids: set[uuid.UUID] = field(default_factory=set)


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
    preferred_department: float
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
    if candidate.department_id is not None and candidate.department_id in prefs.excluded_department_ids:
        return False
    return True


def mutually_compatible(viewer: Person, candidate: Person) -> bool:
    """양쪽 조건을 모두 만족해야 추천한다.

    예) A가 경영학과를 제외했다면 A에게 경영학과 B가 안 보이고,
        B에게도 A가 보이지 않는다. 이유는 누구에게도 알려주지 않는다 (설계도 §17).
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
        person.shows_department and person.department_id is not None,
    ]
    return sum(checks) / len(checks)


def _appearance(person: Person) -> float:
    if not person.appearance_scores:
        return 0.0
    values = list(person.appearance_scores.values())
    return (sum(values) / len(values)) / 10


def score(viewer: Person, candidate: Person, weights: Weights) -> float:
    """0~1 사이 점수. 가중치는 설정(.env)에서 바꿀 수 있다."""
    prefs = viewer.preferences
    preferred_dept = (
        1.0
        if prefs and candidate.department_id is not None and candidate.department_id in prefs.preferred_department_ids
        else 0.0
    )
    total = (
        weights.interest * _interest_similarity(viewer.interests, candidate.interests)
        + weights.appearance * _appearance(candidate)
        + weights.preferred_department * preferred_dept
        + weights.completeness * _completeness(candidate)
        + weights.mbti * _mbti_similarity(viewer.mbti, candidate.mbti)
    )
    return round(total, 6)


def rank(viewer: Person, candidates: list[Person], weights: Weights, limit: int) -> list[Person]:
    eligible = [c for c in candidates if mutually_compatible(viewer, c)]
    eligible.sort(key=lambda c: score(viewer, c, weights), reverse=True)
    return eligible[:limit]
