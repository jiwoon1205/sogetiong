"""매칭 엔진 단위 테스트 (DB 없이)."""

import random
import uuid

from app.services.matching_service import Person, Preferences, Weights, mutually_compatible, rank, score, tier_gap

CAMPUS_A, CAMPUS_B = uuid.uuid4(), uuid.uuid4()
DEPT_BIZ, DEPT_CS = uuid.uuid4(), uuid.uuid4()
W = Weights(interest=0.60, completeness=0.25, mbti=0.15)


def person(gender="FEMALE", age=22, campus=CAMPUS_A, dept=DEPT_CS, tier="MID", **prefs_kw) -> Person:
    prefs = Preferences(
        preferred_gender=prefs_kw.pop("want", "ANY"),
        min_age=prefs_kw.pop("min_age", 19),
        max_age=prefs_kw.pop("max_age", 30),
        campus_mode=prefs_kw.pop("campus_mode", "ALL"),
        campus_ids=prefs_kw.pop("campus_ids", set()),
        exclude_same_department=prefs_kw.pop("exclude_same", False),
    )
    return Person(user_id=uuid.uuid4(), gender=gender, age=age, campus_id=campus, department_id=dept, preferences=prefs, tier=tier, **prefs_kw)


def test_self_is_never_compatible():
    a = person()
    assert not mutually_compatible(a, a)


def test_gender_must_match_both_ways():
    woman = person("FEMALE", want="MALE")
    straight_man = person("MALE", want="FEMALE")
    gay_man = person("MALE", want="MALE")
    assert mutually_compatible(woman, straight_man)
    assert not mutually_compatible(woman, gay_man)


def test_age_range():
    viewer = person(max_age=23)
    assert not mutually_compatible(viewer, person(age=24))
    assert mutually_compatible(viewer, person(age=23))


def test_age_range_is_checked_both_ways():
    """내 범위에 상대가 들어가도, 상대 범위에 내가 안 들어가면 추천되지 않는다 (양쪽 모두에게)."""
    me = person(age=26, min_age=20, max_age=30)
    younger_only = person(age=22, min_age=19, max_age=24)  # 나(26)는 상대 범위 밖
    assert not mutually_compatible(me, younger_only)
    assert not mutually_compatible(younger_only, me)


def test_age_boundaries_are_inclusive():
    viewer = person(min_age=22, max_age=25)
    assert mutually_compatible(viewer, person(age=22))
    assert mutually_compatible(viewer, person(age=25))
    assert not mutually_compatible(viewer, person(age=21))
    assert not mutually_compatible(viewer, person(age=26))


def test_age_any_passes_every_age_but_other_side_still_applies():
    """"나이 상관없음"(둘 다 None)이어도, 상대가 정한 나이 범위에 내가 들어가야 한다."""
    anyone = person(age=31, min_age=None, max_age=None)
    assert mutually_compatible(anyone, person(age=19, max_age=None))
    assert mutually_compatible(anyone, person(age=45, max_age=None))
    picky = person(age=22, min_age=20, max_age=25)  # 31살인 anyone은 이 사람 범위 밖
    assert not mutually_compatible(anyone, picky)
    assert not mutually_compatible(picky, anyone)


def test_open_ended_max_age_means_no_upper_limit():
    """"35세 이상" = max_age None → 35살 넘는 사람도 포함."""
    viewer = person(min_age=27, max_age=None)
    assert mutually_compatible(viewer, person(age=41, max_age=None))
    assert not mutually_compatible(viewer, person(age=26))


def test_campus_modes():
    assert not mutually_compatible(person(campus_mode="MY"), person(campus=CAMPUS_B))
    assert mutually_compatible(person(campus_mode="SELECTED", campus_ids={CAMPUS_B}), person(campus=CAMPUS_B))
    assert not mutually_compatible(person(campus_mode="SELECTED", campus_ids={CAMPUS_B}), person(campus=CAMPUS_A))


def test_same_department_exclusion_hides_both_ways():
    # A만 "같은 과 제외"를 켰어도, 같은 과인 B와는 서로 안 보인다
    a = person(dept=DEPT_BIZ, exclude_same=True)
    b = person(dept=DEPT_BIZ)
    assert not mutually_compatible(a, b)
    assert not mutually_compatible(b, a)


def test_same_department_exclusion_does_not_affect_other_departments():
    a = person(dept=DEPT_BIZ, exclude_same=True)
    assert mutually_compatible(a, person(dept=DEPT_CS))


def test_same_department_is_fine_when_nobody_turns_it_on():
    assert mutually_compatible(person(dept=DEPT_BIZ), person(dept=DEPT_BIZ))


def test_person_without_department_is_never_matched():
    no_dept = person(dept=None)
    assert not mutually_compatible(person(), no_dept)
    assert not mutually_compatible(no_dept, person())


def test_candidate_without_preferences_is_skipped():
    a = person()
    b = person()
    b.preferences = None
    assert not mutually_compatible(a, b)


# ---------- 정렬: 외모 등급이 1순위 ----------

def test_tier_gap():
    assert tier_gap("MID", "MID") == 0
    assert tier_gap("HIGH", "MID") == 1
    assert tier_gap("LOW", "HIGH") == 2
    assert tier_gap(None, "MID") == 3  # 등급을 모르면 가장 뒤


def test_same_tier_comes_first_even_with_fewer_shared_interests():
    viewer = person(tier="MID", interests={"카페", "영화", "여행"})
    same_tier = person(tier="MID", interests={"게임"})
    other_tier_similar = person(tier="HIGH", interests={"카페", "영화", "여행"})
    assert rank(viewer, [other_tier_similar, same_tier], W, 10) == [same_tier, other_tier_similar]


def test_tier_order_same_then_one_step_then_two_steps():
    viewer = person(tier="HIGH")
    low, mid, high = person(tier="LOW"), person(tier="MID"), person(tier="HIGH")
    assert rank(viewer, [low, mid, high], W, 10) == [high, mid, low]


def test_within_same_tier_shared_interests_win():
    viewer = person(interests={"카페", "영화", "여행"})
    similar = person(interests={"카페", "영화", "여행"})
    different = person(interests={"게임"})
    assert rank(viewer, [different, similar], W, 10) == [similar, different]


def test_picking_many_interests_is_not_an_advantage():
    # 예전 방식(합집합으로 나눔)은 관심사를 많이 고를수록 유리했다
    viewer = person(interests={"카페", "영화", "여행"})
    focused = person(interests={"카페", "영화", "여행"})
    everything = person(interests={"카페", "영화", "여행", "게임", "요리", "사진", "전시", "공연", "맛집", "등산"})
    assert score(viewer, focused, W) == score(viewer, everything, W)


def test_hiding_department_or_mbti_is_not_penalized_twice():
    viewer = person()
    a = person(interests={"카페", "영화", "여행"}, has_bio=True)
    b = person(interests={"카페", "영화", "여행"}, has_bio=True)
    # 학과 공개 여부는 Person에 없고(점수에 안 씀), MBTI가 없으면 MBTI 유사도만 0
    assert score(viewer, a, W) == score(viewer, b, W)


# ---------- 나를 LIKE한 사람 우대 ----------

def _pool(n, tier="MID"):
    return [person(tier=tier) for _ in range(n)]


def test_liked_me_gets_a_slot_on_the_first_page():
    viewer = person()
    pool = _pool(15)
    fan = pool[-1]  # 원래 순서로는 1페이지(5명)에 못 들어가는 사람
    page = rank(viewer, pool, W, 5, liked_me={fan.user_id}, liked_me_slots=2, liked_me_probability=1.0, rng=random.Random(1))
    assert fan in page
    assert len(page) == 5


def test_liked_me_slots_are_limited():
    viewer = person()
    # 점수가 같으면 순서가 랜덤이라, 1페이지 5명은 점수를 높여서 확실히 앞에 오게 한다
    top = [person(has_bio=True, has_ideal_type=True) for _ in range(5)]
    pool = top + _pool(10)
    fans = {p.user_id for p in pool[5:]}
    page = rank(viewer, pool, W, 5, liked_me=fans, liked_me_slots=2, liked_me_probability=1.0, rng=random.Random(1))
    assert sum(1 for p in page if p.user_id in fans) == 2


def test_liked_me_position_is_random():
    viewer = person()
    pool = _pool(15)
    fan = pool[-1]
    positions = {
        rank(viewer, pool, W, 5, liked_me={fan.user_id}, liked_me_slots=1, liked_me_probability=1.0, rng=random.Random(seed)).index(fan)
        for seed in range(30)
    }
    assert len(positions) > 1


def test_liked_me_boost_is_sometimes_skipped():
    viewer = person()
    pool = _pool(15)
    fan = pool[-1]
    shown = [
        fan in rank(viewer, pool, W, 5, liked_me={fan.user_id}, liked_me_slots=1, liked_me_probability=0.7, rng=random.Random(seed))
        for seed in range(200)
    ]
    assert 0 < sum(shown) < len(shown)


def test_liked_me_two_tiers_away_is_not_boosted():
    viewer = person(tier="HIGH")
    pool = _pool(10, tier="HIGH")
    fan = person(tier="LOW")
    page = rank(viewer, pool + [fan], W, 5, liked_me={fan.user_id}, liked_me_slots=2, liked_me_probability=1.0, rng=random.Random(1))
    assert fan not in page


def test_liked_me_still_needs_hard_filters():
    viewer = person(want="MALE")
    fan = person(gender="FEMALE")  # 원하는 성별이 아님
    page = rank(viewer, [fan], W, 5, liked_me={fan.user_id}, liked_me_slots=2, liked_me_probability=1.0)
    assert page == []


def test_default_weights_sum_to_one():
    from app.core.config import Settings

    # .env 파일 값이 아니라 코드에 적힌 기본값을 확인한다
    d = {name: f.default for name, f in Settings.model_fields.items()}
    assert abs(d["weight_interest"] + d["weight_completeness"] + d["weight_mbti"] - 1.0) < 1e-9
    assert d["daily_like_limit"] == 5


# ---------- 활동 점수·같은 점수일 때 랜덤 (2026-10-01) ----------

W_ACT = Weights(interest=0.60, completeness=0.25, mbti=0.15, activity=0.20)


def test_frequent_visitor_comes_first_when_other_scores_tie():
    viewer = person()
    rare = person(activity=1 / 14)
    frequent = person(activity=10 / 14)
    # 가입 순서(목록 순서)와 상관없이 자주 오는 사람이 먼저
    for seed in range(20):
        assert rank(viewer, [rare, frequent], W_ACT, 10, rng=random.Random(seed)) == [frequent, rare]


def test_activity_does_not_beat_tier():
    viewer = person(tier="HIGH")
    same_tier_inactive = person(tier="HIGH", activity=0.0)
    other_tier_daily = person(tier="MID", activity=1.0)
    assert rank(viewer, [other_tier_daily, same_tier_inactive], W_ACT, 10) == [same_tier_inactive, other_tier_daily]


def test_activity_weight_zero_means_no_effect():
    viewer = person()
    a, b = person(activity=0.0), person(activity=1.0)
    assert score(viewer, a, W) == score(viewer, b, W)


def test_ties_are_random_not_signup_order():
    viewer = person()
    pool = _pool(10)  # 점수가 모두 같은 사람들 (목록 순서 = 가입 순서라고 가정)
    firsts = {rank(viewer, pool, W_ACT, 10, rng=random.Random(seed))[0].user_id for seed in range(30)}
    assert len(firsts) > 1  # 먼저 가입한 사람이 항상 1등이 아니다
