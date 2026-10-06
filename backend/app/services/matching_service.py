"""매칭 엔진 (설계도 §18, §19 / 2026-09-30 변경).

Stage 1 — Hard Filter: 조건에 맞지 않는 후보 제거 (양쪽 조건을 모두 확인)
Stage 2 — 정렬:
    ① 외모 등급(상/중/하)이 나와 같은 사람 → 한 단계 차이 → 두 단계 차이 순서
    ② 같은 등급 차이 안에서는 세부 점수(관심사·프로필 완성도·MBTI·활동)로 정렬
    ③ 점수까지 같으면 랜덤 (2026-10-01: 예전에는 DB에서 꺼낸 순서 = 가입 순서가 그대로 남아서
       먼저 가입한 사람이 항상 먼저 떴다)
Stage 3 — 나를 LIKE한 사람 우대: 한 페이지에 최대 N자리, 위치는 랜덤, 가끔은 우대 안 함
          (항상 같은 자리에 넣으면 "이 카드 = 나를 좋아하는 사람"이라고 티가 난다)

외모 등급은 내부 데이터라 이 파일 밖으로(API 응답으로) 절대 나가면 안 된다.

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
    tier: str | None = None  # HIGH / MID / LOW (내부 전용)
    # 활동 점수 0~1: 최근 14일 중 접속한 날 수 ÷ 14 (2026-10-01)
    activity: float = 0.0


@dataclass
class Weights:
    interest: float
    completeness: float
    mbti: float
    # 자주 접속하는 사람을 앞으로 (2026-10-01). 너무 크면 관심사가 맞는 사람보다
    # "자주 오는 사람"만 뜨므로 .env(WEIGHT_ACTIVITY)로 조정한다.
    activity: float = 0.0


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


def mutually_compatible(viewer: Person, candidate: Person) -> bool:
    """양쪽 조건을 모두 만족해야 추천한다.

    예) A가 "같은 과 제외"를 켰고 B가 A와 같은 과라면, A에게 B가 안 보이고
        B에게도 A가 보이지 않는다 (B는 스위치를 안 켰어도). 이유는 누구에게도 알려주지 않는다 (설계도 §17).
    """
    if viewer.user_id == candidate.user_id:
        return False
    return satisfies(viewer, candidate) and satisfies(candidate, viewer)


# ---------- Stage 2: 정렬 ----------

def tier_gap(a: str | None, b: str | None) -> int:
    """등급 차이 0(같음) / 1(한 단계) / 2(두 단계). 등급을 모르면 가장 뒤로 보낸다."""
    if a not in TIER_LEVEL or b not in TIER_LEVEL:
        return MAX_TIER_GAP + 1
    return abs(TIER_LEVEL[a] - TIER_LEVEL[b])


def _interest_similarity(a: set[str], b: set[str]) -> float:
    """겹친 관심사 수 ÷ 둘 중 적게 고른 사람의 관심사 수.

    (예전 방식은 관심사를 많이 체크할수록 점수가 올라가서, "비슷한 사람"이 아니라
    "많이 고른 사람"이 유리했다.)
    """
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


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


def score(viewer: Person, candidate: Person, weights: Weights) -> float:
    """같은 등급 차이 안에서의 세부 점수 (0~1). 가중치는 설정(.env)에서 바꿀 수 있다."""
    total = (
        weights.interest * _interest_similarity(viewer.interests, candidate.interests)
        + weights.completeness * _completeness(candidate)
        + weights.mbti * _mbti_similarity(viewer.mbti, candidate.mbti)
        + weights.activity * min(max(candidate.activity, 0.0), 1.0)
    )
    return round(total, 6)


def order(
    viewer: Person,
    candidates: list[Person],
    weights: Weights,
    rng: random.Random | None = None,
    seen_before: set[uuid.UUID] | dict[uuid.UUID, float] | None = None,
    cannot_like: set[uuid.UUID] | None = None,
) -> list[Person]:
    """조건을 통과한 후보를 처음 보는 사람 먼저 → 등급 차이 → 세부 점수 순으로 정렬. 점수가 같으면 랜덤.

    seen_before: 예전에 PASS했다가 48시간이 지나 다시 나온 사람. 처음 보는 사람을 다 본 뒤에 나온다 (2026-10-02).
      - set으로 주면: 다시 나온 사람끼리는 등급 차이 → 점수 순서 (일반 사용자)
      - dict(user_id → PASS한 시각 숫자)로 주면: 다시 나온 사람끼리는 **PASS한 지 오래된 사람부터**
        (VIP 테스트 계정, 2026-10-02 — 새로고침할 때마다 같은 10명만 나오지 않고 돌아가며 나오게)

    cannot_like: 지금 LIKE를 보낼 수 없는 사람 (무료 체험 LIKE를 다 썼거나 이용권이 끝남, 2026-10-06).
      같은 등급 차이 안에서 뒤로 보낸다 (빼지는 않음) → 돈 낸 사람의 LIKE가 답을 못 받는 일을 줄인다.
      등급보다 앞에 두지 않는 이유: 유료 시작 뒤에는 이런 사람이 많을 수 있어서, 등급이 안 맞는 사람만 잔뜩 뜰 수 있다.

    먼저 섞은 뒤 정렬한다. 파이썬 정렬은 "같은 값이면 원래 순서 유지"라서,
    섞어 두면 점수가 같은 사람끼리는 랜덤 순서가 된다 (가입 순서가 결과에 영향을 주지 않음).
    """
    eligible = [c for c in candidates if mutually_compatible(viewer, c)]
    (rng or random.Random()).shuffle(eligible)
    seen = seen_before or set()
    pass_order = seen if isinstance(seen, dict) else {}
    blocked_likes = cannot_like or set()
    eligible.sort(
        key=lambda c: (
            c.user_id in seen,
            pass_order.get(c.user_id, 0.0),  # dict일 때만 의미 있음: 오래 전에 PASS한 사람이 앞
            tier_gap(viewer.tier, c.tier),
            c.user_id in blocked_likes,
            -score(viewer, c, weights),
        )
    )
    return eligible


# ---------- Stage 3: 나를 LIKE한 사람 우대 ----------

def _boost_liked_me(
    viewer: Person,
    ordered: list[Person],
    liked_me: set[uuid.UUID],
    limit: int,
    slots: int,
    probability: float,
    rng: random.Random,
) -> list[Person]:
    page = ordered[:limit]
    if slots <= 0 or not liked_me or rng.random() >= probability:
        return page

    already = sum(1 for p in page if p.user_id in liked_me)
    room = slots - already
    if room <= 0:
        return page
    # 등급이 같거나 한 단계 차이인 사람만 우대 (두 단계 차이는 일반 순서대로)
    extra = [
        c for c in ordered[limit:]
        if c.user_id in liked_me and tier_gap(viewer.tier, c.tier) <= 1
    ][:room]
    if not extra:
        return page

    # 자리를 만들기 위해 페이지 뒤쪽의 (나를 LIKE하지 않은) 사람을 빼고, 랜덤한 위치에 끼워 넣는다
    keep = list(page)
    for _ in extra:
        if len(keep) + len(extra) <= limit:
            break
        for i in range(len(keep) - 1, -1, -1):
            if keep[i].user_id not in liked_me:
                keep.pop(i)
                break
    for person in extra:
        keep.insert(rng.randint(0, len(keep)), person)
    return keep[:limit]


def rank(
    viewer: Person,
    candidates: list[Person],
    weights: Weights,
    limit: int,
    *,
    liked_me: set[uuid.UUID] | None = None,
    liked_me_slots: int = 0,
    liked_me_probability: float = 0.0,
    rng: random.Random | None = None,
    seen_before: set[uuid.UUID] | dict[uuid.UUID, float] | None = None,
    cannot_like: set[uuid.UUID] | None = None,
) -> list[Person]:
    rng = rng or random.Random()
    ordered = order(viewer, candidates, weights, rng, seen_before, cannot_like)
    return _boost_liked_me(
        viewer,
        ordered,
        liked_me or set(),
        limit,
        liked_me_slots,
        liked_me_probability,
        rng,
    )
