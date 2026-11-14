"""대화방 ＋ 버튼: 사진 보내기 · 인스타 아이디 교환 (2026-11-14).

사진 보내기
- 보내는 사람이 방식을 고른다.
  · ONCE(1회 보기): 받은 사람이 "사진 보기"를 눌러야 열린다. 5초 동안 보이고, 한 번 보면 다시 볼 수 없다
    (대화창에는 "열어본 사진"으로만 남는다). 보내는 사람도 다시 볼 수 없다.
  · KEEP(대화에 보관): 일반 사진처럼 두 사람 모두 계속 볼 수 있다.
- 훕팅은 웹사이트라 캡처를 막거나, 캡처한 사실을 알아낼 수 없다 (휴대폰이 웹사이트에 알려주지 않음).
  대신 1회 보기 사진에는 보는 사람의 사용자 코드·시각을 사진 전체에 흐리게 새긴다 → 캡처가 퍼지면 누가 유출했는지 알 수 있다.
- 파일은 관리자 확인(신고 처리)용으로 보낸 뒤 90일 동안 서버에 보관한다 (1회 보기 사진도). 90일이 지나면 지운다.
  그 대화방에 처리 중인 신고(OPEN·IN_REVIEW)가 있으면 처리가 끝날 때까지 지우지 않는다.
- 슈퍼 라이크 "답장 전 메시지 1개" 제한, 대화가 끝난 방(해제·차단·탈퇴)에서는 보낼 수도, 볼 수도 없다.

인스타 아이디 교환
- 요청하는 사람이 자기 아이디를 적고 요청 → 상대가 자기 아이디를 적고 수락(또는 거절).
  수락하는 순간 두 아이디가 서로에게 동시에 보인다. 수락 전에는 요청한 사람의 아이디도 상대에게 안 보인다.
- 아이디를 적을 때 "가짜·오타 아이디는 영구정지"에 동의해야 한다 (agree=true).
  아이디가 진짜인지는 서버가 확인할 수 없으므로, 받은 사람이 "가짜 인스타 아이디"로 신고 → 관리자가 확인 → 영구정지.
- 한 대화방에 진행 중인 요청은 하나만. 이미 교환했으면 다시 요청할 수 없다.
  거절된 뒤에는 24시간이 지나야 다시 요청할 수 있다 (같은 요청을 계속 보내 괴롭히지 못하게).
- 요청한 사람은 상대가 답하기 전에 요청을 취소할 수 있다.
- 관리자는 대화 열람 화면에서 두 아이디(수락 전·거절된 것 포함)를 볼 수 있다.

메시지 종류 (messages.message_type)
- TEXT: 일반 글
- PHOTO: 사진 (chat_photos)
- INSTA_REQUEST: 인스타 교환 요청 카드 (insta_shares.request_message_id)
- INSTA_RESULT: "교환했어요/거절했어요/취소했어요" 안내 줄 (상대에게 알림이 가도록 메시지로 남긴다)
  body에는 대화 목록 미리보기용 문구가 들어 있다.
"""

import logging
import re
import uuid
from datetime import timedelta
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import pseudonymous_code
from app.core.time import KST, as_utc, utcnow
from app.models.chat_extra import ChatPhoto, InstaShare
from app.models.matching import Match, Message, Report
from app.services.storage_service import get_storage

logger = logging.getLogger(__name__)

PHOTO = "PHOTO"
INSTA_REQUEST = "INSTA_REQUEST"
INSTA_RESULT = "INSTA_RESULT"

# 대화 목록 미리보기·옛 화면에 보이는 문구
PHOTO_BODY = {"ONCE": "1회용 사진을 보냈어요", "KEEP": "사진을 보냈어요"}
INSTA_REQUEST_BODY = "인스타 아이디 교환을 요청했어요"
INSTA_RESULT_BODY = {
    "ACCEPTED": "인스타 아이디를 교환했어요",
    "DECLINED": "인스타 아이디 교환을 거절했어요",
    "CANCELLED": "인스타 아이디 교환 요청을 취소했어요",
}

# 인스타그램 아이디 규칙: 영문 소문자·숫자·마침표(.)·밑줄(_), 1~30자. 마침표로 끝나거나 마침표 두 개 연속은 안 됨
_HANDLE_RE = re.compile(r"^(?!.*\.\.)(?!.*\.$)[a-z0-9._]{1,30}$")


class ChatExtraError(ValueError):
    """사용자에게 그대로 보여줄 수 있는 문구를 담는다. code는 화면이 구분할 때 쓴다."""

    def __init__(self, message: str, code: str = "INVALID", status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


def normalize_handle(raw: str) -> str:
    """앞의 @와 공백을 떼고 소문자로. 형식이 틀리면 ChatExtraError."""
    handle = (raw or "").strip().lstrip("@").strip().lower()
    if not _HANDLE_RE.match(handle):
        raise ChatExtraError(
            "인스타 아이디는 영문·숫자·마침표(.)·밑줄(_)로 된 30자 이하만 적을 수 있어요.", code="BAD_HANDLE", status=422
        )
    return handle


# ---------- 사진 ----------

def create_photo(db: Session, match: Match, sender_id: uuid.UUID, mode: str, processed) -> tuple[Message, ChatPhoto]:
    """사진 메시지를 만든다. processed = storage_service.ProcessedPhoto. commit은 부르는 쪽에서."""
    from app.services.storage_service import new_chat_storage_key

    if mode not in PHOTO_BODY:
        raise ChatExtraError("사진 보내는 방식을 골라주세요.", status=422)
    key = new_chat_storage_key(match.id)
    get_storage().save(key, processed.data)
    message = Message(match_id=match.id, sender_user_id=sender_id, body=PHOTO_BODY[mode], message_type=PHOTO)
    db.add(message)
    db.flush()
    photo = ChatPhoto(
        message_id=message.id,
        match_id=match.id,
        sender_user_id=sender_id,
        mode=mode,
        storage_key=key,
        width=processed.width,
        height=processed.height,
        file_size=len(processed.data),
    )
    db.add(photo)
    return message, photo


def photo_state(photo: ChatPhoto, viewer_id: uuid.UUID) -> str:
    """화면에 보여줄 상태.
    - EXPIRED: 보관 기간이 지나 파일이 지워짐
    - ONCE 사진: 받은 사람 → UNOPENED(아직 안 봄) / OPENED(이미 봄)
                 보낸 사람 → SENT_UNOPENED(상대가 아직 안 봄) / SENT_OPENED(상대가 봄)
    - KEEP 사진: AVAILABLE
    """
    if not photo.storage_key:
        return "EXPIRED"
    if photo.mode == "ONCE":
        mine = photo.sender_user_id == viewer_id
        if photo.viewed_at is None:
            return "SENT_UNOPENED" if mine else "UNOPENED"
        return "SENT_OPENED" if mine else "OPENED"
    return "AVAILABLE"


def photo_view(photo: ChatPhoto, viewer_id: uuid.UUID, match_id: uuid.UUID) -> dict:
    state = photo_state(photo, viewer_id)
    view = {"photo_id": str(photo.id), "mode": photo.mode, "state": state, "width": photo.width, "height": photo.height}
    if state == "AVAILABLE":
        view["image_url"] = f"/api/v1/matches/{match_id}/photos/{photo.id}/image"
    return view


def get_photo(db: Session, match: Match, photo_id: uuid.UUID) -> ChatPhoto:
    photo = db.get(ChatPhoto, photo_id)
    if photo is None or photo.match_id != match.id:
        raise ChatExtraError("사진을 찾을 수 없어요.", code="NOT_FOUND", status=404)
    return photo


def read_keep_photo(photo: ChatPhoto) -> bytes:
    if photo.mode != "KEEP":
        raise ChatExtraError("이 사진은 '사진 보기'로만 볼 수 있어요.", code="ONCE_ONLY", status=409)
    if not photo.storage_key:
        raise ChatExtraError("보관 기간이 지난 사진이에요.", code="EXPIRED", status=410)
    return get_storage().read(photo.storage_key)


def open_once_photo(db: Session, photo: ChatPhoto, viewer_id: uuid.UUID) -> bytes:
    """1회 보기 사진을 연다. 받은 사람만, 딱 한 번. 연 순간 viewed_at을 기록한다 (commit도 여기서).

    두 번 눌러도 한 번만 열리도록, viewed_at이 비어 있을 때만 바꾸는 조건부 UPDATE로 기록한다.
    """
    if photo.mode != "ONCE":
        raise ChatExtraError("1회용 사진이 아니에요.", code="NOT_ONCE", status=409)
    if photo.sender_user_id == viewer_id:
        raise ChatExtraError("보낸 1회용 사진은 다시 볼 수 없어요.", code="SENDER", status=403)
    if not photo.storage_key:
        raise ChatExtraError("보관 기간이 지난 사진이에요.", code="EXPIRED", status=410)
    if photo.viewed_at is not None:
        raise ChatExtraError("이미 본 사진이에요.", code="ALREADY_OPENED", status=410)
    now = utcnow()
    # 파일을 먼저 읽고 워터마크까지 만든 뒤에 "봤음"으로 기록한다 (파일 문제로 못 봤는데 사라지는 일이 없게)
    stamped = watermark_for_viewer(
        get_storage().read(photo.storage_key), f"훕팅 {pseudonymous_code(viewer_id)} {now.astimezone(KST):%m-%d %H:%M}"
    )
    updated = (
        db.query(ChatPhoto)
        .filter(ChatPhoto.id == photo.id, ChatPhoto.viewed_at.is_(None))
        .update({"viewed_at": now}, synchronize_session=False)
    )
    if updated == 0:
        db.rollback()
        raise ChatExtraError("이미 본 사진이에요.", code="ALREADY_OPENED", status=410)
    db.commit()
    return stamped


def watermark_for_viewer(data: bytes, text: str) -> bytes:
    """보는 사람의 사용자 코드·시각을 사진 전체에 비스듬히 흐리게 반복해서 새긴다.
    캡처를 막을 수는 없지만, 캡처가 퍼졌을 때 누가 본 화면인지 알 수 있게 한다."""
    with Image.open(BytesIO(data)) as image:
        image = image.convert("RGBA")
        w, h = image.size
        font = ImageFont.load_default(size=max(14, w // 28))
        text_w, text_h = font.getbbox(text)[2:4]
        # 글씨를 넉넉한 투명 판에 바둑판처럼 찍고, 30도 돌려서 사진 위에 겹친다
        side = int((w**2 + h**2) ** 0.5) + text_w
        tile = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        draw = ImageDraw.Draw(tile)
        step_x, step_y = text_w + max(40, w // 6), text_h * 5
        for row, y in enumerate(range(0, side, step_y)):
            offset = (step_x // 2) if row % 2 else 0
            for x in range(-offset, side, step_x):
                draw.text((x + 1, y + 1), text, fill=(0, 0, 0, 55), font=font)
                draw.text((x, y), text, fill=(255, 255, 255, 80), font=font)
        tile = tile.rotate(30, resample=Image.BICUBIC)
        left, top = (side - w) // 2, (side - h) // 2
        image = Image.alpha_composite(image, tile.crop((left, top, left + w, top + h)))
        out = BytesIO()
        image.convert("RGB").save(out, format="JPEG", quality=88)
        return out.getvalue()


def purge_expired_photos(db: Session, now=None) -> int:
    """보관 기간(90일)이 지난 대화방 사진 파일을 지운다. 처리 중인 신고가 있는 대화방은 건너뛴다.
    지운 장 수를 돌려준다. 백엔드가 켜져 있는 동안 1시간마다 돈다 (app.main)."""
    now = now or utcnow()
    cutoff = now - timedelta(days=get_settings().chat_photo_retention_days)
    open_report_matches = db.query(Report.match_id).filter(
        Report.match_id.isnot(None), Report.status.in_(["OPEN", "IN_REVIEW"])
    )
    rows = (
        db.query(ChatPhoto)
        .filter(ChatPhoto.storage_key != "", ChatPhoto.created_at <= cutoff, ChatPhoto.match_id.notin_(open_report_matches))
        .all()
    )
    storage = get_storage()
    for photo in rows:
        try:
            storage.delete(photo.storage_key)
        except (FileNotFoundError, ValueError):
            pass
        photo.storage_key = ""
        photo.purged_at = now
    db.commit()
    if rows:
        logger.info("purged chat photos: %d", len(rows))
    return len(rows)


# ---------- 인스타 아이디 교환 ----------

def _shares(db: Session, match_id: uuid.UUID) -> list[InstaShare]:
    return db.query(InstaShare).filter(InstaShare.match_id == match_id).order_by(InstaShare.created_at.asc()).all()


def request_insta(db: Session, match: Match, requester_id: uuid.UUID, raw_handle: str) -> tuple[Message, InstaShare]:
    """commit은 부르는 쪽에서."""
    handle = normalize_handle(raw_handle)
    now = utcnow()
    for share in _shares(db, match.id):
        if share.status == "ACCEPTED":
            raise ChatExtraError("이미 인스타 아이디를 교환했어요.", code="ALREADY_SHARED")
        if share.status == "PENDING":
            raise ChatExtraError("아직 답을 기다리는 요청이 있어요.", code="PENDING_EXISTS")
        if (
            share.status == "DECLINED"
            and share.requester_user_id == requester_id
            and share.responded_at is not None
            and as_utc(share.responded_at) > now - timedelta(hours=get_settings().insta_rerequest_hours)
        ):
            raise ChatExtraError(
                f"상대가 거절했어요. 거절된 뒤 {get_settings().insta_rerequest_hours}시간이 지나야 다시 요청할 수 있어요.",
                code="DECLINED_RECENTLY",
            )
    message = Message(match_id=match.id, sender_user_id=requester_id, body=INSTA_REQUEST_BODY, message_type=INSTA_REQUEST)
    db.add(message)
    db.flush()
    share = InstaShare(
        match_id=match.id,
        request_message_id=message.id,
        requester_user_id=requester_id,
        requester_handle=handle,
        responder_user_id=match.partner_of(requester_id),
        status="PENDING",
    )
    db.add(share)
    return message, share


def get_share(db: Session, match: Match, share_id: uuid.UUID) -> InstaShare:
    share = db.get(InstaShare, share_id)
    if share is None or share.match_id != match.id:
        raise ChatExtraError("요청을 찾을 수 없어요.", code="NOT_FOUND", status=404)
    return share


def respond_insta(
    db: Session, match: Match, share: InstaShare, user_id: uuid.UUID, action: str, raw_handle: str | None = None
) -> Message:
    """action: ACCEPT(받은 사람, 아이디 필요) / DECLINE(받은 사람) / CANCEL(요청한 사람). commit은 부르는 쪽에서.

    두 번 눌러도 한 번만 처리되도록, 상태가 PENDING일 때만 바꾸는 조건부 UPDATE를 쓴다.
    """
    if action in ("ACCEPT", "DECLINE") and share.responder_user_id != user_id:
        raise ChatExtraError("받은 사람만 답할 수 있어요.", code="NOT_RESPONDER", status=403)
    if action == "CANCEL" and share.requester_user_id != user_id:
        raise ChatExtraError("요청한 사람만 취소할 수 있어요.", code="NOT_REQUESTER", status=403)
    values: dict = {"responded_at": utcnow()}
    if action == "ACCEPT":
        values.update(status="ACCEPTED", responder_handle=normalize_handle(raw_handle or ""))
    elif action == "DECLINE":
        values.update(status="DECLINED")
    elif action == "CANCEL":
        values.update(status="CANCELLED")
    else:
        raise ChatExtraError("알 수 없는 요청이에요.", status=422)
    updated = (
        db.query(InstaShare)
        .filter(InstaShare.id == share.id, InstaShare.status == "PENDING")
        .update(values, synchronize_session=False)
    )
    if updated == 0:
        db.rollback()
        raise ChatExtraError("이미 답한 요청이에요.", code="ALREADY_ANSWERED")
    db.refresh(share)
    message = Message(
        match_id=match.id, sender_user_id=user_id, body=INSTA_RESULT_BODY[share.status], message_type=INSTA_RESULT
    )
    db.add(message)
    return message


def share_view(share: InstaShare, viewer_id: uuid.UUID) -> dict:
    """사용자 화면용. 수락되기 전에는 상대 아이디를 절대 내보내지 않는다."""
    mine = share.requester_user_id == viewer_id
    my_handle = share.requester_handle if mine else share.responder_handle
    partner_handle = None
    if share.status == "ACCEPTED":
        partner_handle = share.responder_handle if mine else share.requester_handle
    return {
        "share_id": str(share.id),
        "status": share.status,
        "requested_by_me": mine,
        "my_handle": my_handle,
        "partner_handle": partner_handle,
    }


def last_handle(db: Session, user_id: uuid.UUID) -> str | None:
    """내가 마지막으로 적은 인스타 아이디 (다음에 적을 때 미리 채워 준다)."""
    rows = (
        db.query(InstaShare)
        .filter((InstaShare.requester_user_id == user_id) | (InstaShare.responder_user_id == user_id))
        .order_by(InstaShare.created_at.desc())
        .limit(10)
        .all()
    )
    for share in rows:
        if share.requester_user_id == user_id:
            return share.requester_handle
        if share.responder_handle:
            return share.responder_handle
    return None


def match_extras(db: Session, match_id: uuid.UUID, viewer_id: uuid.UUID) -> dict:
    """대화방의 사진·인스타 요청 최신 상태 (화면이 몇 초마다 새 메시지만 받아 가므로, 예전 카드의 상태 변화는 이걸로 맞춘다).
    대화방 하나에 사진·요청은 많지 않아 매번 통째로 보내도 가볍다."""
    photos = db.query(ChatPhoto).filter(ChatPhoto.match_id == match_id).all()
    shares = _shares(db, match_id)
    return {
        "photos": {str(p.message_id): photo_view(p, viewer_id, match_id) for p in photos},
        "insta": {str(s.request_message_id): share_view(s, viewer_id) for s in shares},
    }


def admin_extras(db: Session, message_ids: list[uuid.UUID]) -> tuple[dict, dict]:
    """관리자 대화 열람용: message_id → 사진 / 인스타 요청."""
    if not message_ids:
        return {}, {}
    photos = {p.message_id: p for p in db.query(ChatPhoto).filter(ChatPhoto.message_id.in_(message_ids))}
    shares = {s.request_message_id: s for s in db.query(InstaShare).filter(InstaShare.request_message_id.in_(message_ids))}
    return photos, shares
