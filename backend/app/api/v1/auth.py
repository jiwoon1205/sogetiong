from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, VerificationRequest, VerifyCodeRequest

router = APIRouter()


@router.post("/send-verification")
def send_verification(payload: VerificationRequest, db: Session = Depends(get_db)):
    # Placeholder implementation for email verification request.
    return {"message": "verification email sent"}


@router.post("/verify")
def verify_code(payload: VerifyCodeRequest, db: Session = Depends(get_db)):
    # Placeholder verification logic.
    return {"verified": True}


@router.post("/register", response_model=TokenResponse)
def register_user(payload: RegisterRequest, db: Session = Depends(get_db)):
    # Placeholder user creation logic.
    hashed_password = hash_password(payload.password)
    _ = hashed_password
    access_token = create_access_token(subject="placeholder-user-id")
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
def login_user(payload: LoginRequest, db: Session = Depends(get_db)):
    # Placeholder user validation logic.
    stored_hash = hash_password(payload.password)
    if not verify_password(payload.password, stored_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    access_token = create_access_token(subject="placeholder-user-id")
    return TokenResponse(access_token=access_token)


@router.post("/logout")
def logout_user():
    return {"message": "logged out"}
