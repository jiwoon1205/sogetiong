#!/usr/bin/env python3
"""통계 분석용 데이터 내보내기 (2026-11-11).

서버에서 실행:  cd ~/sogetiong && sudo python3 deploy/export_stats.py data/sogetiong.db ~
→ 홈 폴더(~)에 stats_users.csv, stats_daily.csv 두 파일이 생긴다.
   (DB 경로를 안 주면 ./data/sogetiong.db, 저장 폴더를 안 주면 DB와 같은 폴더)

- 서버의 DB(./data/sogetiong.db)를 **읽기 전용**으로 연다. DB를 고치지 않는다.
- 파이썬 기본 모듈만 쓴다 (서버에 따로 설치할 것 없음, 도커 밖에서 실행).
- **개인정보를 빼고** 내보낸다: 이메일·닉네임·실명·사용자 ID·자기소개 원문·대화 내용·탈퇴 사유 원문은 없다.
  사람은 순서 번호(row)로만 구분한다. 글은 글자 수만, 탈퇴 사유는 적었는지만.
- 시각은 모두 한국 시간.
- **빼는 계정** (2026-11-11): 운영자 테스트 계정(닉네임 SKIP_NICKNAMES, VIP_TEST_EMAILS)과 슈퍼 VIP 계정.
  그 사람의 줄뿐 아니라, 그 계정과 주고받은 좋아요·매칭·대화·결제·접속도 모든 숫자에서 뺀다.
  테스트 계정 메일은 환경 변수 VIP_TEST_EMAILS → deploy/backend.env의 VIP_TEST_EMAILS= 줄 → 기본값 순서로 찾는다.

stats_users.csv : 한 사람에 한 줄 (외모 점수·활동·좋아요·매칭·대화·결제)
stats_daily.csv : 하루에 한 줄 (성별 가입자 수·접속자 수·매칭 수·결제)
"""

import csv
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "sogetiong.db")
OUT = os.path.abspath(os.path.expanduser(sys.argv[2])) if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(DB))


SKIP_NICKNAMES = {"케로롱"}  # 관리자 테스트 계정 닉네임
DEFAULT_TEST_EMAILS = "wldns051205@hufs.ac.kr"  # backend/app/core/config.py 의 vip_test_emails 기본값과 같게


def test_emails():
    """운영자 테스트 계정 메일 (소문자). 서버가 쓰는 설정과 같은 곳에서 읽는다."""
    raw = os.environ.get("VIP_TEST_EMAILS")
    if raw is None:
        env_path = os.path.join(HERE, "backend.env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("VIP_TEST_EMAILS="):
                        raw = line.split("=", 1)[1].strip().strip('"').strip("'")
    if raw is None:
        raw = DEFAULT_TEST_EMAILS
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def ts(v):
    """DB 시각 문자열 → 한국 시간 datetime (DB에는 시간대 없이 UTC로 저장됨)."""
    if not v:
        return None
    s = str(v).replace("T", " ").split("+")[0]
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).astimezone(KST)
        except ValueError:
            pass
    return None


def d(v):
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def chars(text):
    return len("".join((text or "").split()))


def main():
    if not os.path.exists(DB):
        sys.exit(f"DB 파일이 없어요: {DB}")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    q = lambda sql, *a: con.execute(sql, a).fetchall()  # noqa: E731

    now = datetime.now(KST)
    today = now.date()

    schools = {r["id"]: r["email_domain"] for r in q("SELECT id, email_domain FROM universities")}
    all_users = q("SELECT * FROM users")
    pub = {r["user_id"]: r for r in q("SELECT * FROM public_profiles")}
    # 운영자 테스트 계정과 슈퍼 VIP 계정은 통계에서 뺀다 (2026-11-11)
    tests = test_emails()
    skip = {
        u["id"] for u in all_users
        if bool(u["super_vip"])
        or (u["email"] or "").strip().lower() in tests
        or (u["id"] in pub and (pub[u["id"]]["nickname"] or "").strip() in SKIP_NICKNAMES)
    }
    users = [u for u in all_users if u["id"] not in skip]
    priv = {r["user_id"]: r for r in q("SELECT user_id, birth_date FROM private_profiles")}
    interests = defaultdict(int)
    for r in q("SELECT user_id, COUNT(*) n FROM user_interests GROUP BY user_id"):
        interests[r["user_id"]] = r["n"]

    # 외모 점수: 승인된 사진 묶음에 대한 가장 최근 평가
    evals = {}
    for r in q(
        "SELECT e.* FROM appearance_evaluations e JOIN user_photos p ON p.id = e.photo_id "
        "WHERE p.review_status = 'APPROVED' ORDER BY e.created_at"
    ):
        evals[r["user_id"]] = r
    approved = {r["user_id"] for r in q("SELECT DISTINCT user_id FROM user_photos WHERE review_status = 'APPROVED'")}
    first_approved = {r["user_id"]: ts(r["t"]) for r in q(
        "SELECT user_id, MIN(reviewed_at) t FROM user_photos WHERE review_status = 'APPROVED' GROUP BY user_id"
    )}

    visits = defaultdict(list)
    for r in q("SELECT user_id, visit_date FROM user_daily_visits"):
        if r["user_id"] in skip:
            continue
        visits[r["user_id"]].append(d(r["visit_date"]))

    like_sent = defaultdict(lambda: [0, 0, 0, 0])  # 좋아요 횟수 합, 좋아요 보낸 사람 수, 넘기기 수, 슈퍼 라이크 수
    like_recv = defaultdict(lambda: [0, 0, 0])  # 받은 좋아요 횟수 합, 좋아요 보낸 사람 수, 받은 넘기기 수
    for r in q("SELECT from_user_id f, to_user_id t, action, like_count, is_super FROM likes"):
        if r["f"] in skip or r["t"] in skip:
            continue
        if r["action"] == "LIKE":
            n = max(r["like_count"] or 1, 1)
            like_sent[r["f"]][0] += n
            like_sent[r["f"]][1] += 1
            like_recv[r["t"]][0] += n
            like_recv[r["t"]][1] += 1
            if r["is_super"]:
                like_sent[r["f"]][3] += 1
        elif r["action"] == "PASS":
            like_sent[r["f"]][2] += 1
            like_recv[r["t"]][2] += 1

    match_rows = [
        r for r in q("SELECT id, user_a_id a, user_b_id b, created_at, super_like_by, by_repeat_likes FROM matches")
        if r["a"] not in skip and r["b"] not in skip
    ]
    senders = defaultdict(set)
    msg_count = defaultdict(int)
    for r in q("SELECT match_id, sender_user_id s FROM messages WHERE message_type = 'TEXT' OR message_type IS NULL"):
        senders[r["match_id"]].add(r["s"])
        msg_count[(r["match_id"], r["s"])] += 1
    m = defaultdict(lambda: {"n": 0, "n7": 0, "n30": 0, "talk": 0, "both": 0, "msgs": 0, "forced_recv": 0, "first": None})
    for r in match_rows:
        t = ts(r["created_at"])
        for me, other in ((r["a"], r["b"]), (r["b"], r["a"])):
            x = m[me]
            x["n"] += 1
            if t and (now - t).days < 7:
                x["n7"] += 1
            if t and (now - t).days < 30:
                x["n30"] += 1
            if me in senders[r["id"]]:
                x["talk"] += 1
            if len(senders[r["id"]]) >= 2:
                x["both"] += 1
            x["msgs"] += msg_count[(r["id"], me)]
            if (r["super_like_by"] and r["super_like_by"] == other) or (r["by_repeat_likes"] and r["super_like_by"] != me):
                x["forced_recv"] += 1
            if t and (x["first"] is None or t < x["first"]):
                x["first"] = t

    pays = defaultdict(lambda: {"n": 0, "amount": 0, "SIGNUP": 0, "VIP": 0, "SUPER_LIKE": 0, "first": None})
    pay_rows = [
        r for r in q("SELECT user_id, kind, amount, status, processed_at FROM payments WHERE status = 'CONFIRMED'")
        if r["user_id"] not in skip
    ]
    for r in pay_rows:
        x = pays[r["user_id"]]
        x["n"] += 1
        x["amount"] += r["amount"] or 0
        x[r["kind"]] = x.get(r["kind"], 0) + 1
        t = ts(r["processed_at"])
        if t and (x["first"] is None or t < x["first"]):
            x["first"] = t

    reports_recv = defaultdict(int)
    for r in q("SELECT reported_user_id u, COUNT(*) n FROM reports GROUP BY reported_user_id"):
        if r["u"] in skip:
            continue
        reports_recv[r["u"]] = r["n"]

    cols = [
        "row", "gender", "school", "status", "signup_at", "signup_days_ago", "deleted_at", "age", "beta_member",
        "photo_approved", "first_approved_days_after_signup",
        "overall", "style", "grooming", "photo_vibe", "score_avg", "tier",
        "relationship_goal", "mbti_set", "bio_chars", "ideal_chars", "interests", "face_type_set", "height_set",
        "visit_days_total", "visit_days_7d", "visit_days_30d", "last_active_days_ago",
        "likes_sent", "likes_sent_people", "passes_sent", "super_likes_sent",
        "likes_received", "likes_received_people", "passes_received",
        "matches", "matches_7d", "matches_30d", "matches_i_talked", "matches_both_talked", "messages_sent",
        "matches_forced_received", "first_match_days_after_signup",
        "paid", "paid_count", "paid_amount", "paid_basic", "paid_vip", "paid_superlike", "first_paid_days_after_signup",
        "trial_likes_used", "vip_active", "member_active", "super_vip", "referred", "reports_received", "withdraw_reason_given",
    ]
    out_users = os.path.join(OUT, "stats_users.csv")
    with open(out_users, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for i, u in enumerate(sorted(users, key=lambda r: r["created_at"] or ""), start=1):
            uid = u["id"]
            p = pub.get(uid)
            e = evals.get(uid)
            created = ts(u["created_at"])
            vs = [v for v in visits.get(uid, []) if v]
            birth = d(priv[uid]["birth_date"]) if uid in priv else None
            age = None
            if birth:
                age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
            mm = m[uid]
            pp = pays[uid]
            ls, lr = like_sent[uid], like_recv[uid]
            last = ts(u["last_active_at"])
            fa = first_approved.get(uid)

            def after(t):
                return round((t - created).total_seconds() / 86400, 2) if t and created else ""

            scores = [e["overall_impression"], e["style"], e["grooming"], e["photo_vibe"]] if e else []
            w.writerow([
                i,
                (p["gender"] if p else None) or u["deleted_gender"] or "",
                schools.get(u["university_id"], ""),
                u["status"],
                created.strftime("%Y-%m-%d %H:%M") if created else "",
                (now - created).days if created else "",
                ts(u["deleted_at"]).strftime("%Y-%m-%d") if u["deleted_at"] else "",
                age if age is not None else "",
                int(bool(u["is_beta_member"])),
                int(uid in approved),
                after(fa),
                *(scores if scores else ["", "", "", ""]),
                round(sum(scores) / 4, 2) if scores else "",
                (e["tier"] or "") if e else "",
                (p["relationship_goal"] or "") if p else "",
                int(bool(p and p["mbti"])),
                chars(p["bio"]) if p else "",
                chars(p["ideal_type"]) if p else "",
                interests[uid],
                int(bool(p and p["face_type"])),
                int(bool(p and p["height_cm"])),
                len(vs),
                sum(1 for v in vs if (today - v).days < 7),
                sum(1 for v in vs if (today - v).days < 30),
                (now - last).days if last else "",
                ls[0], ls[1], ls[2], ls[3],
                lr[0], lr[1], lr[2],
                mm["n"], mm["n7"], mm["n30"], mm["talk"], mm["both"], mm["msgs"], mm["forced_recv"], after(mm["first"]),
                int(pp["n"] > 0), pp["n"], pp["amount"], pp.get("SIGNUP", 0), pp.get("VIP", 0), pp.get("SUPER_LIKE", 0),
                after(pp["first"]),
                u["trial_likes_used"] or 0,
                int(bool(u["vip_until"] and ts(u["vip_until"]) and ts(u["vip_until"]) > now)),
                int(bool(u["member_until"] and ts(u["member_until"]) and ts(u["member_until"]) > now)),
                int(bool(u["super_vip"])),
                int(bool(u["referred_by_id"])),
                reports_recv[uid],
                int(bool(u["deleted_reason"])) if "deleted_reason" in u.keys() else "",
            ])

    # ---- 하루 단위 ----
    gender_of = {}
    for u in users:
        p = pub.get(u["id"])
        gender_of[u["id"]] = (p["gender"] if p else None) or u["deleted_gender"] or "UNKNOWN"
    day = defaultdict(lambda: defaultdict(int))
    for u in users:
        t = ts(u["created_at"])
        if t:
            day[t.date()][f"signup_{gender_of[u['id']]}"] += 1
        t = ts(u["deleted_at"])
        if t:
            day[t.date()][f"withdraw_{gender_of[u['id']]}"] += 1
    for uid, vs in visits.items():
        for v in vs:
            if v:
                day[v][f"visit_{gender_of.get(uid, 'UNKNOWN')}"] += 1
    for r in match_rows:
        t = ts(r["created_at"])
        if t:
            day[t.date()]["matches"] += 1
    for r in pay_rows:
        t = ts(r["processed_at"])
        if t:
            g = gender_of.get(r["user_id"], "UNKNOWN")
            day[t.date()][f"paid_{g}"] += 1
            day[t.date()][f"paid_amount_{g}"] += r["amount"] or 0
            day[t.date()][f"paid_{r['kind']}"] += 1
    keys = sorted({k for v in day.values() for k in v})
    out_daily = os.path.join(OUT, "stats_daily.csv")
    with open(out_daily, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["date", *keys])
        for dd in sorted(day):
            w.writerow([dd.isoformat(), *[day[dd].get(k, 0) for k in keys]])

    print(f"완료: {len(users)}명 (테스트·슈퍼 VIP 계정 {len(skip)}개 뺌)")
    print(f"  {out_users}")
    print(f"  {out_daily}")


if __name__ == "__main__":
    main()
