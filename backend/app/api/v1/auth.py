import smtplib

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.core.rate_limit import enforce_rate_limit
from app.db.session import get_db
from app.models.matching import VerificationToken
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, VerificationRequest, VerifyCodeRequest
from app.services.auth_service import AuthService
from app.services.email_service import EmailService

router = APIRouter()


@router.post("/send-verification")
def send_verification(payload: VerificationRequest, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(f"verify-send:{request.client.host if request.client else 'unknown'}:{payload.email}", 3, 3600)
    if not AuthService.is_valid_school_email(str(payload.email)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="only @hufs.ac.kr email addresses are allowed")

    existing_user = db.query(User).filter(User.email == str(payload.email).lower()).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user already exists")

    code = AuthService.create_verification_code()
    AuthService.store_verification_code(db, str(payload.email), code)
    try:
        EmailService.send_verification_code(str(payload.email), code)
    except (OSError, RuntimeError, smtplib.SMTPException) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="email delivery is unavailable") from exc
    return {"message": "verification email sent", "email": str(payload.email)}


@router.post("/verify")
def verify_code(payload: VerifyCodeRequest, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(f"verify-check:{request.client.host if request.client else 'unknown'}:{payload.email}", 10, 600)
    if not AuthService.is_valid_school_email(str(payload.email)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="only @hufs.ac.kr email addresses are allowed")
    if not payload.code or len(payload.code) < 4:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid verification code")

    verified = AuthService.verify_verification_code(db, str(payload.email), payload.code)
    if not verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired verification code")

    return {"verified": True, "email": str(payload.email)}


@router.post("/register", response_model=TokenResponse)
def register_user(payload: RegisterRequest, db: Session = Depends(get_db)):
    if not AuthService.is_valid_school_email(str(payload.email)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="only @hufs.ac.kr email addresses are allowed")

    existing_user = db.query(User).filter(User.email == str(payload.email).lower()).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user already exists")

    verification = (
        db.query(VerificationToken)
        .filter(VerificationToken.email == str(payload.email).lower())
        .order_by(VerificationToken.created_at.desc())
        .first()
    )
    if verification is None or verification.used_at is None or verification.expires_at < __import__("datetime").datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email verification required")

    user = User(
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        status="ACTIVE",
        email_verified_at=verification.used_at,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    verification.user_id = user.id
    db.commit()

    access_token = create_access_token(str(user.id), role="USER")
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
def login_user(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(f"login:{request.client.host if request.client else 'unknown'}:{payload.email}", 10, 900)
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    if user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account is not active")

    access_token = create_access_token(str(user.id), role="USER")
    return TokenResponse(access_token=access_token)


@router.post("/logout")
def logout_user():
    return {"message": "logged out"}
