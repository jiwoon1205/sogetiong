"""휴대폰 알림 (웹 푸시) + 알림을 못 켠 사람에게 메일 (2026-10-05, `휴대폰 알림 설계`).

규칙
- 알림을 보내는 일: 새 메시지(MESSAGE), 새 매칭(MATCH) 두 가지뿐.
- 잠금화면에 보이는 글에는 상대 닉네임·대화 내용을 넣지 않는다 ("훕팅 · 새 메시지가 왔어요").
- 휴대폰 알림은 메시지마다 보낸다 (카톡·DM처럼, 2026-10-05 변경. 처음엔 같은 방 10분에 한 번이었음).
  잠금화면에는 대화방마다 한 줄만 남고(같은 tag), 새 메시지가 올 때마다 다시 울린다(renotify).
- 새 메시지 알림은 그 사람이 "지금 그 대화방 화면을 보고 있을 때"만 생략한다 (2026-10-06 변경).
  예전에는 "45초 안에 사이트를 쓴 사람"이면 아무 화면이든 생략했는데, 그러면
  ① 앱을 막 닫은 직후 온 답장, ② PC에 사이트를 켜 둔 동안 휴대폰으로 와야 할 알림이 사라졌다.
  대화방 화면은 4초마다 새 메시지를 확인하므로, 그 확인이 12초(PUSH_SKIP_IF_VIEWING_SECONDS) 안에 있었으면 "보는 중".
  화면을 닫거나 다른 앱으로 가면 화면이 /me/alerts/away로 바로 알려서 그때부터는 알림이 온다.
- 새 매칭 알림은 항상 보낸다 (자주 생기지 않고 중요해서).
- 휴대폰 알림이 켜진 기기가 하나도 없거나 모두 배달에 실패하면 → 학교 메일로 보낸다 (본인이 메일 알림을 끄지 않았다면).
  메일만은 같은 대화방·같은 종류에 10분(EMAIL_ALERT_THROTTLE_MINUTES)에 한 번 (메일함이 넘치지 않게).

흐름
1) API가 DB에 메시지·매칭을 쓰면서 queue()로 "보낼 알림"을 세션에 적어 둔다.
2) DB commit이 성공한 뒤에만 실제로 보낸다 (commit이 실패·취소되면 버린다).
3) 보내는 일은 응답을 늦추지 않도록 별도 작업 스레드에서 한다 (테스트에서는 바로 실행).
"""

import json
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import utcnow
from app.db.session import SessionLocal
from app.models.push import PushSubscription
from app.models.user import User
from app.services.email_service import EmailDeliveryError, EmailService

logger = logging.getLogger(__name__)

MESSAGE = "MESSAGE"
MATCH = "MATCH"

# 잠금화면에 보이는 글. 상대 닉네임·대화 내용은 절대 넣지 않는다.
PUSH_TITLE = "훕팅"
PUSH_BODY = {MESSAGE: "새 메시지가 왔어요", MATCH: "새로운 매칭이 생겼어요"}

# 알림 배달 회사 주소만 받는다. 아무 주소나 받으면 우리 서버가 엉뚱한 곳으로 요청을 보내게 만들 수 있다.
# (크롬·삼성 인터넷·엣지 = 구글, 사파리 = 애플, 파이어폭스 = 모질라, 윈도우 엣지 = 마이크로소프트)
ALLOWED_PUSH_HOST_SUFFIXES = (
    "fcm.googleapis.com",
    "push.apple.com",
    "push.services.mozilla.com",
    "notify.windows.com",
)

_PENDING_KEY = "pending_alerts"


@dataclass(frozen=True)
class Alert:
    user_id: uuid.UUID
    kind: str  # MESSAGE / MATCH
    match_id: uuid.UUID


# ---------- 기억해 두는 값 (서버 프로세스가 1개라 메모리에 둔다. 재시작하면 비워지는데 그래도 괜찮다) ----------

_lock = threading.Lock()
_viewing: dict[tuple[uuid.UUID, uuid.UUID], float] = {}  # (사용자, 대화방) → 그 대화방 화면이 마지막으로 새 메시지를 확인한 시각
_last_sent: dict[tuple[uuid.UUID, uuid.UUID, str], float] = {}  # (사용자, 대화방, 종류) → 마지막 메일 알림 시각
_executor: ThreadPoolExecutor | None = None


def reset() -> None:
    """테스트용: 기억해 둔 값을 모두 지운다."""
    with _lock:
        _viewing.clear()
        _last_sent.clear()


def mark_viewing(user_id: uuid.UUID, match_id: uuid.UUID) -> None:
    """대화방 화면이 새 메시지를 확인할 때마다 (GET /matches/{id}/messages). DB에 쓰지 않는다."""
    with _lock:
        _viewing[(user_id, match_id)] = time.monotonic()


def mark_away(user_id: uuid.UUID) -> None:
    """화면을 닫거나 다른 앱·대화방으로 갔을 때 (POST /me/alerts/away). 이때부터 바로 알림이 간다."""
    with _lock:
        for key in [k for k in _viewing if k[0] == user_id]:
            del _viewing[key]


def is_allowed_endpoint(endpoint: str) -> bool:
    try:
        url = urlparse(endpoint)
    except ValueError:
        return False
    host = (url.hostname or "").lower()
    if url.scheme != "https" or not host or url.port not in (None, 443):
        return False
    return any(host == s or host.endswith("." + s) for s in ALLOWED_PUSH_HOST_SUFFIXES)


# ---------- 1) 보낼 알림 적어 두기 → 2) commit 뒤에 보내기 ----------

def queue(db: Session, user_id: uuid.UUID, kind: str, match_id: uuid.UUID) -> None:
    """commit이 성공하면 보낸다. commit은 부르는 쪽에서 한다."""
    db.info.setdefault(_PENDING_KEY, []).append(Alert(user_id=user_id, kind=kind, match_id=match_id))


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    alerts = session.info.pop(_PENDING_KEY, None)
    for alert in alerts or ():
        _submit(alert)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    session.info.pop(_PENDING_KEY, None)


def _submit(alert: Alert) -> None:
    global _executor
    if get_settings().environment == "test":
        deliver(alert)  # 테스트에서는 결과를 바로 확인할 수 있게
        return
    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="push")
    _executor.submit(_deliver_safely, alert)


def _deliver_safely(alert: Alert) -> None:
    try:
        deliver(alert)
    except Exception:  # 알림 실패가 서버를 멈추게 하지 않는다
        logger.exception("alert delivery failed")


# ---------- 3) 실제로 보내기 ----------

def _viewing_room(alert: Alert) -> bool:
    """지금 그 대화방 화면을 보고 있나 (새 메시지 알림만 해당)."""
    if alert.kind != MESSAGE:
        return False
    seen = _viewing.get((alert.user_id, alert.match_id))
    return seen is not None and time.monotonic() - seen < get_settings().push_skip_if_viewing_seconds


def _email_allowed(alert: Alert) -> bool:
    """같은 방 메일 알림을 10분 안에 보냈으면 False. 보내기로 하면 시각을 기록한다."""
    now = time.monotonic()
    key = (alert.user_id, alert.match_id, alert.kind)
    with _lock:
        sent = _last_sent.get(key)
        if sent is not None and now - sent < get_settings().email_alert_throttle_minutes * 60:
            return False
        _last_sent[key] = now
        return True


def deliver(alert: Alert) -> str:
    """결과: "push" / "email" / "skipped" (테스트에서 확인용)."""
    with _lock:
        if _viewing_room(alert):
            return "skipped"
    db = SessionLocal()
    try:
        user = db.get(User, alert.user_id)
        if user is None or user.status != "ACTIVE":
            return "skipped"
        if get_settings().push_enabled:
            subs = db.query(PushSubscription).filter(PushSubscription.user_id == user.id).all()
            if subs and send_to_devices(db, subs, payload_for(alert)) > 0:
                return "push"
        if not user.email_notify or not _email_allowed(alert):
            return "skipped"
        email = user.email
    finally:
        db.close()
    try:
        if alert.kind == MESSAGE:
            EmailService.send_new_message_notice(email, alert.match_id)
        else:
            EmailService.send_new_match_notice(email, alert.match_id)
    except EmailDeliveryError:
        return "skipped"  # 이유는 email_service가 로그에 남긴다
    return "email"


def payload_for(alert: Alert) -> dict:
    return {
        "title": PUSH_TITLE,
        "body": PUSH_BODY[alert.kind],
        "url": f"/chat/{alert.match_id}",
        # 같은 방 알림은 잠금화면에 하나만 남게 (새 알림이 예전 것을 덮어씀)
        "tag": f"{alert.kind.lower()}-{alert.match_id}",
    }


def send_to_devices(db: Session, subs: list[PushSubscription], payload: dict) -> int:
    """기기들에 알림을 보낸다. 배달된 기기 수를 돌려준다.
    배달 회사가 "이 주소는 이제 없다"(404·410)고 하면 그 기기를 지운다 (알림을 끄거나 앱을 지운 경우)."""
    delivered = 0
    for sub in subs:
        status = _webpush(sub, payload)
        if status in (404, 410):
            db.delete(sub)
        elif status is not None and 200 <= status < 300:
            sub.last_success_at = utcnow()
            delivered += 1
        else:
            logger.warning("push delivery failed: status=%s host=%s", status, urlparse(sub.endpoint).hostname)
    db.commit()
    return delivered


def _webpush(sub: PushSubscription, payload: dict) -> int | None:
    """배달 회사에 보내고 HTTP 상태 번호를 돌려준다. 연결 자체가 안 되면 None."""
    from pywebpush import WebPushException, webpush  # 서버가 켜질 때 느려지지 않게 쓸 때 불러온다

    settings = get_settings()
    try:
        response = webpush(
            subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=settings.vapid_private_key.strip(),
            vapid_claims={"sub": settings.vapid_subject},
            ttl=24 * 60 * 60,  # 휴대폰이 꺼져 있으면 하루까지 기다렸다 배달
            headers={"Urgency": "high"},
            timeout=10,
        )
        return response.status_code
    except WebPushException as exc:
        return exc.response.status_code if exc.response is not None else None
    except Exception as exc:  # 네트워크 오류 등
        logger.warning("push request error: %s", type(exc).__name__)
        return None
