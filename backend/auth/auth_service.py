from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import Settings
from user.user import User

settings = Settings()

# bcrypt는 최대 72바이트만 사용한다. 초과분은 잘라 일관되게 처리한다.
_BCRYPT_MAX_BYTES = 72


def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(password), hashed.encode("utf-8"))
    except ValueError:
        return False


class EmailAlreadyRegistered(Exception):
    pass


class AuthService:
    def register(self, db: Session, email: str, password: str) -> User:
        email = email.strip().lower()
        if db.scalar(select(User).where(User.email == email)) is not None:
            raise EmailAlreadyRegistered(email)
        user = User(email=email, hashed_password=hash_password(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def authenticate(self, db: Session, email: str, password: str) -> User | None:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None or not verify_password(password, user.hashed_password):
            return None
        return user

    def create_access_token(self, user: User) -> str:
        # exp는 반드시 UTC 기준(now()는 naive KST라 사용하지 않는다).
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        payload = {"sub": str(user.id), "email": user.email, "exp": expire}
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    def decode_token(self, token: str) -> dict:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
