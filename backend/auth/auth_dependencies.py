import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from auth.auth_service import AuthService
from db.session import get_db
from user.user import User

auth_service = AuthService()
_bearer = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Authorization: Bearer <jwt>를 검증하고 현재 사용자를 반환한다."""
    if credentials is None:
        raise _UNAUTHENTICATED
    try:
        payload = auth_service.decode_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _UNAUTHENTICATED

    user = db.get(User, user_id)
    if user is None:
        raise _UNAUTHENTICATED
    return user
