"""유령회원 (2026-10-24): 오래 안 들어온 사람도 활성 회원과 같은 조건으로 추천에 나온다.

예전에는 활동 점수(최근 14일 접속 일수, 비중 0.20) 때문에 같은 등급 안에서 늘 맨 뒤로 밀려 사실상 안 나왔다.
지금은 기본 비중이 0이라 접속 빈도가 순서에 영향을 주지 않는다 (점수가 같으면 랜덤).
"""

from datetime import timedelta

from app.core.time import utcnow
from app.models.user import User, UserDailyVisit
from app.services import profile_service
from tests.conftest import admin_login, discover_ids, ready_user


def test_activity_weight_is_off_by_default():
    assert profile_service.matching_weights().activity == 0


def test_ghost_member_shows_and_is_not_always_last(sent_codes, db):
    admin = admin_login(db)
    viewer = ready_user(sent_codes, db, admin, "v@hufs.ac.kr", gender="MALE", want="FEMALE")
    active = ready_user(sent_codes, db, admin, "act@hufs.ac.kr", gender="FEMALE", want="MALE")
    ghost = ready_user(sent_codes, db, admin, "ghost@hufs.ac.kr", gender="FEMALE", want="MALE")
    # 유령회원: 최근 접속 기록 없음, 마지막 접속 30일 전
    g = db.query(User).filter(User.email == "ghost@hufs.ac.kr").one()
    db.query(UserDailyVisit).filter(UserDailyVisit.user_id == g.id).delete()
    g.last_active_at = utcnow() - timedelta(days=30)
    db.commit()

    firsts = set()
    for _ in range(25):
        ids = discover_ids(viewer)
        assert ghost.profile_id in ids and active.profile_id in ids
        firsts.add(ids[0])
    # 점수가 같으면 랜덤이라, 유령회원이 맨 앞에 나오는 때도 있다
    assert ghost.profile_id in firsts and active.profile_id in firsts
