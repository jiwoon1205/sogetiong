"""매칭 엔진 단위 테스트 (DB 없이)."""

import uuid

from app.services.matching_service import Person, Preferences, Weights, mutually_compatible, rank, score

CAMPUS_A, CAMPUS_B = uuid.uuid4(), uuid.uuid4()
DEPT_BIZ, DEPT_CS = uuid.uuid4(), uuid.uuid4()
W = Weights(interest=0.47, appearance=0.23, completeness=0.18, mbti=0.12)


def person(gender="FEMALE", age=22, campus=CAMPUS_A, dept=DEPT_CS, **prefs_kw) -> Person:
    prefs = Preferences(
        preferred_gender=prefs_kw.pop("want", "ANY"),
        min_age=prefs_kw.pop("min_age", 19),
        max_age=prefs_kw.pop("max_age", 30),
        campus_mode=prefs_kw.pop("campus_mode", "ALL"),
        campus_ids=prefs_kw.pop("campus_ids", set()),
        exclude_same_department=prefs_kw.pop("exclude_same", False),
    )
    return Person(user_id=uuid.uuid4(), gender=gender, age=age, campus_id=campus, department_id=dept, preferences=prefs, **prefs_kw)


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


def test_ranking_prefers_shared_interests_over_appearance():
    viewer = person(interests={"카페", "영화", "여행"})
    similar = person(interests={"카페", "영화", "여행"}, appearance_scores={"a": 5, "b": 5, "c": 5, "d": 5})
    attractive = person(interests={"게임"}, appearance_scores={"a": 10, "b": 10, "c": 10, "d": 10})
    assert rank(viewer, [attractive, similar], W, 10) == [similar, attractive]


def test_appearance_is_only_partially_reflected():
    viewer = person()
    low = person(appearance_scores={"a": 1, "b": 1, "c": 1, "d": 1})
    high = person(appearance_scores={"a": 10, "b": 10, "c": 10, "d": 10})
    gap = score(viewer, high, W) - score(viewer, low, W)
    assert 0 < gap <= W.appearance


def test_default_weights_sum_to_one():
    from app.core.config import Settings

    # .env 파일 값이 아니라 코드에 적힌 기본값을 확인한다
    d = {name: f.default for name, f in Settings.model_fields.items()}
    assert abs(d["weight_interest"] + d["weight_appearance"] + d["weight_completeness"] + d["weight_mbti"] - 1.0) < 1e-9
    assert d["weight_appearance"] <= d["weight_appearance_max"]
