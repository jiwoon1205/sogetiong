"""매칭 엔진 단위 테스트 (DB 없이)."""

import random
import uuid

from app.services.matching_service import Person, Preferences, Weights, draw, mutually_compatible, rank, score, taste, tier_gap, weight

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


# ---------- 가중치 추첨 (2026-10-24 재설계) ----------
# 가중치 = ① 등급(같음 2.0 / 한 단계 1.4 / 두 단계 1.0) × ② 활동(1~2) × ③ 나를 좋아요한 횟수(1~2) × ④ 취향(1~2)


def test_tier_gap():
    assert tier_gap("MID", "MID") == 0
    assert tier_gap("HIGH", "MID") == 1
    assert tier_gap("LOW", "HIGH") == 2
    assert tier_gap(None, "MID") == 3  # 등급을 모르면 가장 먼 것으로


def _plain(**kw):
    """다른 요소가 모두 최소(1배)인 사람: 활동 0, 관심사·소개·MBTI 없음."""
    return person(**kw)


def test_tier_factor():
    viewer = person(tier="HIGH")
    assert weight(viewer, _plain(tier="HIGH"), W) == 2.0
    assert abs(weight(viewer, _plain(tier="MID"), W) - 1.4) < 1e-9
    assert weight(viewer, _plain(tier="LOW"), W) == 1.0


def test_activity_factor():
    viewer = person(tier="LOW")
    assert weight(viewer, _plain(tier="HIGH", activity=0.0), W) == 1.0  # 유령회원도 0이 아님
    assert weight(viewer, _plain(tier="HIGH", activity=0.5), W) == 1.5
    assert weight(viewer, _plain(tier="HIGH", activity=1.0), W) == 2.0


def test_liked_count_factor():
    viewer = person(tier="LOW")
    c = _plain(tier="HIGH")
    assert [weight(viewer, c, W, n) for n in range(6)] == [1.0, 1.25, 1.5, 1.75, 2.0, 2.0]  # 4번에서 최대


def test_taste_factor():
    viewer = person(tier="LOW", interests={"카페", "영화", "여행"}, mbti="ENFP")
    best = _plain(tier="HIGH", interests={"카페", "영화", "여행"}, mbti="ENFP", has_bio=True, has_ideal_type=True)
    assert taste(viewer, best, W) == 1.0
    assert weight(viewer, best, W) == 2.0
    assert taste(viewer, _plain(tier="HIGH"), W) == 0.0


def test_four_factors_are_balanced_max_16_min_1():
    viewer = person(tier="HIGH", interests={"카페", "영화", "여행"}, mbti="ENFP")
    top = person(tier="HIGH", activity=1.0, interests={"카페", "영화", "여행"}, mbti="ENFP", has_bio=True, has_ideal_type=True)
    bottom = person(tier="LOW")
    assert weight(viewer, top, W, 4) == 16.0
    assert weight(viewer, bottom, W, 0) == 1.0


def test_draw_frequency_follows_weights():
    """가중치 2 대 1이면 맨 앞에 나오는 비율도 약 2/3 대 1/3."""
    viewer = person(tier="HIGH")
    heavy, light = person(tier="HIGH"), person(tier="LOW")
    rng = random.Random(7)
    firsts = [draw(viewer, [light, heavy], W, rng)[0] is heavy for _ in range(6000)]
    share = sum(firsts) / len(firsts)
    assert 0.63 < share < 0.70


def test_everyone_can_come_first():
    """가중치가 가장 낮은 사람도 가끔은 맨 앞에 나온다 (줄 세우기와 다른 점)."""
    viewer = person(tier="HIGH")
    top = [person(tier="HIGH", activity=1.0, has_bio=True, has_ideal_type=True) for _ in range(3)]
    low = person(tier="LOW")
    rng = random.Random(3)
    assert any(draw(viewer, top + [low], W, rng)[0] is low for _ in range(2000))


def test_liked_me_appears_more_often():
    viewer = person()
    fan, other = person(), person()
    rng = random.Random(11)
    fan_first = sum(draw(viewer, [other, fan], W, rng, {fan.user_id: 4})[0] is fan for _ in range(4000))
    assert fan_first / 4000 > 0.6  # 2 대 1


def test_draw_still_needs_hard_filters():
    viewer = person(want="MALE")
    fan = person(gender="FEMALE")  # 원하는 성별이 아님
    assert rank(viewer, [fan], W, 5, liked_counts={fan.user_id: 4}) == []


def test_page_is_limited_and_random_each_time():
    viewer = person()
    pool = [person() for _ in range(15)]
    pages = [tuple(p.user_id for p in rank(viewer, pool, W, 5, rng=random.Random(seed))) for seed in range(10)]
    assert all(len(p) == 5 for p in pages)
    assert len(set(pages)) > 1


def test_picking_many_interests_is_not_an_advantage():
    # 예전 방식(합집합으로 나눔)은 관심사를 많이 고를수록 유리했다
    viewer = person(interests={"카페", "영화", "여행"})
    focused = person(interests={"카페", "영화", "여행"})
    everything = person(interests={"카페", "영화", "여행", "게임", "요리", "사진", "전시", "공연", "맛집", "등산"})
    assert score(viewer, focused, W) == score(viewer, everything, W)
    assert taste(viewer, focused, W) == taste(viewer, everything, W)


def test_hiding_department_or_mbti_is_not_penalized_twice():
    viewer = person()
    a = person(interests={"카페", "영화", "여행"}, has_bio=True)
    b = person(interests={"카페", "영화", "여행"}, has_bio=True)
    # 학과 공개 여부는 Person에 없고(점수에 안 씀), MBTI가 없으면 MBTI 유사도만 0
    assert score(viewer, a, W) == score(viewer, b, W)


def test_default_weights_sum_to_one():
    from app.core.config import Settings

    # .env 파일 값이 아니라 코드에 적힌 기본값을 확인한다
    d = {name: f.default for name, f in Settings.model_fields.items()}
    assert abs(d["weight_interest"] + d["weight_completeness"] + d["weight_mbti"] - 1.0) < 1e-9
    assert d["daily_like_limit"] == 5
    # 네 요소 모두 최대 2배 (2026-10-24 "고르게")
    assert d["rec_tier_same"] == d["rec_activity_max"] == d["rec_liked_max"] == d["rec_taste_max"] == 2.0
    assert d["like_repeat_hours"] == 48 and d["like_repeat_match_count"] == 5
