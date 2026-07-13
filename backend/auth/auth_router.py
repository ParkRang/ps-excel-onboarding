import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.auth_dependencies import get_current_user
from auth.auth_schema import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from auth.auth_service import AuthService, EmailAlreadyRegistered
from db.session import get_db
from user.user import User

router = APIRouter(prefix="/auth", tags=["auth"])
auth_service = AuthService()
logger = logging.getLogger(__name__)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = auth_service.register(db, req.email, req.password)
    except EmailAlreadyRegistered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    logger.info("회원가입 완료. user_id=%s", user.id)
    return user


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, req.email, req.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=auth_service.create_access_token(user))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
