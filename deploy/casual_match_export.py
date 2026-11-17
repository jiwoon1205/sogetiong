"""캐주얼한 만남을 고른 사람과 매칭된, 캐주얼한 만남을 고르지 않은 사람 내보내기 (2026-11-17, 관리자 전용).

서버에서 실행 (백엔드 컨테이너 안에서 돌린다. 회원코드를 만들려면 서버 비밀키가 필요해서):
    cd ~/sogetiong
    docker compose exec -T backend python - < deploy/casual_match_export.py > ~/casual_matches.csv

- DB를 읽기만 한다. 아무것도 바꾸지 않는다.
- 회원코드 = 관리자 화면의 회원코드(U로 시작하는 7글자)와 같다. 메일·닉네임은 내보내지 않는다.
- 대상: '찾는 관계'가 생긴 2026-10-24(한국 시간) 이후에 생긴 매칭 중에서
  한쪽은 캐주얼한 만남을 고른 적이 있고(변경 기록 또는 지금 값), 다른 쪽은 고른 적이 없는 매칭.
  한 줄 = 그런 매칭 하나. "회원코드" 칸이 캐주얼을 고르지 않은 쪽이다.
- 한계: 변경 기록은 2026-11-15부터 남았다. 그 전에 캐주얼을 골랐다가 바꾼 사람은 "고른 적 없음"으로 보일 수 있다.
  탈퇴해서 프로필이 지워진 사람은 지금 값을 알 수 없다 → 찾는관계 칸에 "모름(탈퇴)".
- 엑셀에서 한글이 깨지지 않게 UTF-8 BOM을 붙인다. 요약은 화면(stderr)에 따로 찍는다.
"""

import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.core.security import pseudonymous_code
from app.db.session import SessionLocal
from app.models.matching import Like, Match, Message
from app.models.profile import PublicProfile, RelationshipGoalChange
from app.models.user import User

KST = timezone(timedelta(hours=9))
START = datetime(2026, 10, 24, tzinfo=KST)
GOAL = {"SERIOUS": "진지한 연애", "FRIEND": "대학교 친구", "CASUAL": "캐주얼한 만남", None: "안 고름"}
STATUS = {"ACTIVE": "대화 중", "ENDED": "끝남"}


def kst(dt):
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")


db = SessionLocal()
goal_now = {uid: g for uid, g in db.query(PublicProfile.user_id, PublicProfile.relationship_goal)}
has_profile = set(goal_now)
ever_casual = {uid for (uid,) in db.query(RelationshipGoalChange.user_id).filter(RelationshipGoalChange.new_goal == "CASUAL")}
ever_casual |= {uid for uid, g in goal_now.items() if g == "CASUAL"}
deleted = {uid for (uid,) in db.query(User.id).filter(User.status == "DELETED")}

start_utc = START.astimezone(timezone.utc)
matches = [m for m in db.query(Match).all() if (m.created_at.replace(tzinfo=timezone.utc) if m.created_at.tzinfo is None else m.created_at) >= start_utc]

msg_count = defaultdict(int)  # (match_id, sender) -> 메시지 수
for mid, sender in db.query(Message.match_id, Message.sender_user_id).filter(Message.match_id.in_([m.id for m in matches])):
    msg_count[(mid, sender)] += 1


def goal_label(uid):
    if uid in has_profile:
        return GOAL.get(goal_now[uid], goal_now[uid])
    return "모름(탈퇴)"


def first_liker(a, b):
    """두 사람 중 좋아요를 먼저 보낸 쪽 (지금 남아 있는 좋아요 기록 기준)."""
    rows = (
        db.query(Like.from_user_id, Like.created_at)
        .filter(Like.action == "LIKE", ((Like.from_user_id == a) & (Like.to_user_id == b)) | ((Like.from_user_id == b) & (Like.to_user_id == a)))
        .order_by(Like.created_at)
        .all()
    )
    return rows[0][0] if rows else None


out = csv.writer(sys.stdout)
sys.stdout.write("﻿")
out.writerow(
    ["회원코드", "찾는관계(지금)", "탈퇴", "상대 회원코드(캐주얼)", "상대 찾는관계(지금)", "매칭일(한국시간)", "매칭 방법", "먼저 좋아요한 쪽", "이 사람이 보낸 메시지 수", "매칭 상태"]
)
codes = set()
rows = 0
for m in sorted(matches, key=lambda x: x.created_at):
    a, b = m.user_a_id, m.user_b_id
    if (a in ever_casual) == (b in ever_casual):
        continue  # 둘 다 캐주얼이거나 둘 다 아님
    casual, other = (a, b) if a in ever_casual else (b, a)
    how = "슈퍼 라이크" if m.super_like_by else ("좋아요 5번" if m.by_repeat_likes else "서로 좋아요")
    first = first_liker(a, b)
    first_label = "" if first is None else ("이 사람" if first == other else "상대(캐주얼)")
    out.writerow(
        [
            pseudonymous_code(other),
            goal_label(other),
            "탈퇴" if other in deleted else "",
            pseudonymous_code(casual),
            goal_label(casual),
            kst(m.created_at),
            how,
            first_label,
            msg_count[(m.id, other)],
            STATUS.get(m.status, m.status),
        ]
    )
    codes.add(other)
    rows += 1

print(f"[요약] {START:%Y-%m-%d} 이후 매칭 {len(matches)}개 중 해당 매칭 {rows}개, 캐주얼을 고르지 않은 사람 {len(codes)}명", file=sys.stderr)
