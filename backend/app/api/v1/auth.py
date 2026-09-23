from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, VerificationRequest, VerifyCodeRequest

router = APIRouter()


@router.post("/send-verification")
def send_verification(payload: VerificationRequest, db: Session = Depends(get_db)):
    return {"message": "verification email sent", "email": str(payload.email)}


@router.post("/verify")
def verify_code(payload: VerifyCodeRequest, db: Session = Depends(get_db)):
    if not payload.code or len(payload.code) < 4:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid verification code")
    return {"verified": True, "email": str(payload.email)}


@router.post("/register", response_model=TokenResponse)
def register_user(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user already exists")

    user = User(
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        status="ACTIVE",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(str(user.id), role="USER")
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
def login_user(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    access_token = create_access_token(str(user.id), role="USER")
    return TokenResponse(access_token=access_token)


@router.post("/logout")
def logout_user():
    return {"message": "logged out"}
