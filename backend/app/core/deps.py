import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..models import User
from .database import get_db
from .security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
# auto_error=False: doesn't raise 401 on a missing header, just resolves to
# None - see get_current_user_optional below. FastAPI's OAuth2PasswordBearer
# raises for a malformed/missing Authorization header before the endpoint
# ever runs unless this is set.
_oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    subject = decode_access_token(token)
    if subject is None:
        raise credentials_error

    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise credentials_error

    user = db.get(User, user_id)
    if user is None:
        raise credentials_error
    return user


def get_current_user_optional(
    token: str | None = Depends(_oauth2_scheme_optional), db: Session = Depends(get_db)
) -> User | None:
    """Same validation as get_current_user, but returns None instead of
    401ing on a missing/invalid token - for endpoints like POST /chat
    that work for both logged-out and logged-in callers, and use login
    only to unlock extra behavior (Chat AI's personalized tier) rather
    than gate the whole endpoint. A malformed/expired token is treated
    the same as no token at all (silently anonymous), not an error -
    this endpoint's baseline (stateless) behavior must never break just
    because a client sent a stale token.
    """
    if token is None:
        return None

    subject = decode_access_token(token)
    if subject is None:
        return None

    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        return None

    return db.get(User, user_id)
