"""/api/v1/auth — 학교 이메일 인증, 가입, 로그인, 로그아웃, 비밀번호 재설정."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.core.security import hash_password, hash_token, verify_password
from app.core.time import age_on, utcnow
from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.models.profile import PrivateProfile, PublicProfile
from app.models.university import Campus
from app.models.user import User, UserSession
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    SendCodeRequest,
    VerifyCodeRequest,
    VerifyCodeResponse,
)
from app.services import auth_service
from app.services.email_service import EmailDeliveryError, EmailService
from app.services.session_service import (
    auth_response_body,
    clear_user_cookies,
    create_user_session,
    is_app_client,
    revoke_all_user_sessions,
    set_user_cookies,
)

logger = logging.getLogger(__name__)
router = APIRouter()

CODE_SENT_MESSAGE = "입력한 주소로 인증번호를 보냈습니다. 메일함을 확인해주세요."


@router.post("/email/send-code", status_code=status.HTTP_202_ACCEPTED)
def send_code(payload: SendCodeRequest, request: Request, db: Session = Depends(get_db)):
    email = auth_service.normalize_email(payload.email)
    enforce_rate_limit(f"send-code:ip:{client_ip(request)}", 10, 3600)
    enforce_rate_limit(f"send-code:email:{email}", 3, 3600)

    if auth_service.find_university_for_email(db, email) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="등록된 학교 이메일만 사용할 수 있습니다.")

    # 이미 가입된 주소여도 같은 응답을 준다 → 특정 학생의 가입 여부를 알아낼 수 없게 (계정 존재 노출 방지)
    already_registered = db.query(User.id).filter(User.email == email).first() is not None
    if not already_registered:
        code = auth_service.issue_verification_code(db, email)
        try:
            EmailService.send_verification_code(email, code)
        except EmailDeliveryError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="메일을 보내지 못했습니다. 잠시 후 다시 시도해주세요.") from exc
    return {"message": CODE_SENT_MESSAGE}


@router.post("/email/verify", response_model=VerifyCodeResponse)
def verify_code(payload: VerifyCodeRequest, request: Request, db: Session = Depends(get_db)):
    email = auth_service.normalize_email(payload.email)
    enforce_rate_limit(f"verify:ip:{client_ip(request)}", 20, 600)
    ticket = auth_service.verify_code_and_issue_ticket(db, email, payload.code)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="인증번호가 올바르지 않거나 만료되었습니다.")
    return VerifyCodeResponse(verification_ticket=ticket, expires_in_minutes=get_settings().verification_ticket_minutes)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    settings = get_settings()
    enforce_rate_limit(f"register:ip:{client_ip(request)}", 10, 3600)

    if not (payload.agree_terms and payload.agree_privacy and payload.agree_appearance_public):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="필수 약관에 모두 동의해야 합니다.")

    ticket = auth_service.find_valid_ticket(db, payload.verification_ticket)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이메일 인증을 다시 진행해주세요.")

    age = age_on(payload.birth_date)
    if age < settings.min_age:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"만 {settings.min_age}세 이상만 가입할 수 있습니다.")
    if age > settings.max_age:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="생년월일을 다시 확인해주세요.")

    university = auth_service.find_university_for_email(db, ticket.email)
    campus = db.get(Campus, payload.campus_id)
    if university is None or campus is None or campus.university_id != university.id or not campus.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="캠퍼스를 다시 선택해주세요.")

    if db.query(User.id).filter(User.email == ticket.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 가입된 계정입니다. 로그인해주세요.")

    now = utcnow()
    user = User(
        email=ticket.email,
        password_hash=hash_password(payload.password),
        university_id=university.id,
        status="ACTIVE",
        email_verified_at=ticket.verified_at,
    )
    db.add(user)
    db.flush()
    db.add(
        PrivateProfile(
            user_id=user.id,
            birth_date=payload.birth_date,
            real_name=payload.real_name,
            student_id=payload.student_id,
            verification_data_json={
                "method": "SCHOOL_EMAIL",
                "verified_at": ticket.verified_at.isoformat() if ticket.verified_at else None,
                "consents": {"terms": True, "privacy": True, "appearance_public": True, "agreed_at": now.isoformat()},
            },
        )
    )
    db.add(PublicProfile(user_id=user.id, nickname=payload.nickname, gender=payload.gender, campus_id=campus.id))
    ticket.consumed_at = now
    issued = create_user_session(db, user.id, request)
    db.commit()

    if not is_app_client(request):
        set_user_cookies(response, issued)
    return auth_response_body(request, issued, {"message": "가입이 완료되었습니다."})


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    email = auth_service.normalize_email(payload.email)
    enforce_rate_limit(f"login:ip:{client_ip(request)}", 30, 900)
    enforce_rate_limit(f"login:email:{email}", 10, 900)

    user = db.query(User).filter(User.email == email).first()
    if not verify_password(payload.password, user.password_hash if user else None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    if user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="이용이 제한된 계정입니다.")

    # Session Rotation: 로그인할 때마다 새 세션 발급, 이 브라우저의 이전 세션은 폐기
    old_token = request.cookies.get(get_settings().session_cookie_name)
    if old_token:
        db.query(UserSession).filter(UserSession.token_hash == hash_token(old_token)).delete(synchronize_session=False)
    issued = create_user_session(db, user.id, request)
    db.commit()

    if not is_app_client(request):
        set_user_cookies(response, issued)
    return auth_response_body(request, issued, {"message": "로그인되었습니다."})


@router.post("/logout")
def logout(response: Response, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(current.session)
    db.commit()
    clear_user_cookies(response)
    return {"message": "로그아웃되었습니다."}


# ---------- 비밀번호 재설정 ----------
# 1) reset-request: 이메일로 6자리 코드 발송
# 2) reset: 코드 + 새 비밀번호 → 변경, 모든 기기 로그아웃, 변경 안내 메일

RESET_SENT_MESSAGE = "가입된 주소라면 비밀번호 재설정 인증번호를 보냈습니다. 메일함을 확인해주세요."
RESET_INVALID_MESSAGE = "인증번호가 올바르지 않거나 만료되었습니다."


def _send_in_background(send, *args) -> None:
    """메일은 응답을 보낸 뒤에 발송한다.

    가입된 주소일 때만 발송 시간만큼 응답이 늦어지면, 응답 시간으로 가입 여부를 알아낼 수 있다.
    발송 실패도 사용자에게 알리지 않는다 (실패 여부도 가입 여부를 드러내므로). 서버 로그에만 남긴다.
    """
    try:
        send(*args)
    except EmailDeliveryError:
        logger.error("password reset email failed")


@router.post("/password/reset-request", status_code=status.HTTP_202_ACCEPTED)
def password_reset_request(
    payload: PasswordResetRequest,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    email = auth_service.normalize_email(payload.email)
    enforce_rate_limit(f"reset-request:ip:{client_ip(request)}", 10, 3600)
    enforce_rate_limit(f"reset-request:email:{email}", 3, 3600)

    if auth_service.find_university_for_email(db, email) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="등록된 학교 이메일만 사용할 수 있습니다.")

    # 가입 여부·계정 상태와 상관없이 항상 같은 응답 (계정 존재 노출 방지)
    user = db.query(User).filter(User.email == email).first()
    if user is not None and user.status == "ACTIVE":
        code = auth_service.issue_verification_code(db, email, auth_service.PURPOSE_PASSWORD_RESET)
        background.add_task(_send_in_background, EmailService.send_password_reset_code, email, code)
    return {"message": RESET_SENT_MESSAGE}


@router.post("/password/reset")
def password_reset(
    payload: PasswordResetConfirm,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    email = auth_service.normalize_email(payload.email)
    enforce_rate_limit(f"reset:ip:{client_ip(request)}", 20, 600)

    if not auth_service.use_password_reset_code(db, email, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=RESET_INVALID_MESSAGE)
    user = db.query(User).filter(User.email == email).first()
    if user is None or user.status != "ACTIVE":
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=RESET_INVALID_MESSAGE)

    user.password_hash = hash_password(payload.new_password)
    # 비밀번호가 바뀌면 모든 기기에서 로그아웃 (누군가 로그인해 있었다면 쫓아냄)
    revoke_all_user_sessions(db, user.id)
    db.commit()

    clear_user_cookies(response)
    background.add_task(_send_in_background, EmailService.send_password_changed_notice, email)
    return {"message": "비밀번호가 변경되었습니다. 새 비밀번호로 로그인해주세요."}
