"""캐주얼 매칭 파일(casual_matches.csv)의 사람을 감시 대상에 한꺼번에 올린다 (2026-11-17, 한 번만 쓰는 스크립트).

서버에서 실행 (마이그레이션 0043까지 적용된 뒤, 백엔드 컨테이너 안에서):
    cd ~/sogetiong
    docker compose exec -T backend python -c "$(cat deploy/watch_import.py)" < ~/casual_matches.csv

- 파일은 deploy/casual_match_export.py로 만든 것. "회원코드" 칸(캐주얼을 고르지 않은 쪽)만 쓴다.
- 회원코드 → 계정은 서버에서 다시 계산해서 찾는다 (회원코드는 서버 비밀키로 만들어서 서버에서만 풀 수 있다).
- 탈퇴한 계정이 같은 메일로 다시 가입했으면 새 계정에 올린다.
- 이미 감시 대상인 사람은 그대로 둔다 (상태·메모를 덮어쓰지 않는다). 새로 올리는 사람은 origin=MATCH_IMPORT, '지켜보는 중'.
- 여러 번 실행해도 같은 사람이 두 번 올라가지 않는다.
"""

import csv
import sys
from datetime import datetime, timedelta, timezone

from app.core.security import pseudonymous_code
from app.core.time import utcnow
from app.db.session import SessionLocal
from app.models.user import User
from app.models.watch import WatchTarget

KST = timezone(timedelta(hours=9))


def parse_kst(text):
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=KST).astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return None


rows = list(csv.DictReader(sys.stdin.read().lstrip("﻿").splitlines()))
if not rows or "회원코드" not in rows[0]:
    sys.exit("파일 형식이 다릅니다. casual_match_export.py로 만든 casual_matches.csv를 넣어 주세요.")

when: dict[str, list] = {}
for r in rows:
    code = (r.get("회원코드") or "").strip()
    if code:
        when.setdefault(code, []).append(parse_kst(r.get("매칭일(한국시간)", "")))

db = SessionLocal()
users = db.query(User).all()
by_code = {pseudonymous_code(u.id): u for u in users}
active_by_hash = {u.email_hash: u for u in users if u.status != "DELETED" and u.email_hash}

added = kept = moved = missing = 0
now = utcnow()
for code, dates in when.items():
    user = by_code.get(code)
    if user is None:
        missing += 1
        continue
    if user.status == "DELETED" and user.email_hash in active_by_hash:
        user = active_by_hash[user.email_hash]  # 다시 가입한 새 계정
        moved += 1
    if db.get(WatchTarget, user.id) is not None:
        kept += 1
        continue
    dates = [d for d in dates if d is not None] or [now]
    db.add(
        WatchTarget(
            user_id=user.id,
            status="WATCHING",
            origin="MATCH_IMPORT",
            note=None,
            event_count=0,
            first_at=min(dates),
            last_at=max(dates),
            updated_at=now,
        )
    )
    db.flush()
    added += 1
db.commit()
print(f"[감시 대상 올리기] 파일 속 {len(when)}명 → 새로 {added}명 · 이미 있음 {kept}명 · 재가입 계정으로 {moved}명 · 못 찾음 {missing}명")
