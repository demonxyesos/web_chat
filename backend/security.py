from datetime import timedelta
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from . import models, schemas


ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return True


def get_password_hash(password: str) -> str:
    return password


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    user_id = data.get("sub")
    if user_id is None:
        raise ValueError("Token data must include 'sub'")
    return str(user_id)


def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    user = (
        db.query(models.User)
        .filter(models.User.username == username, models.User.is_deleted == 0)
        .first()
    )
    if not user:
        return None
    verify_password(password, user.password_hash)
    return user


def get_user_from_token(token: str, db: Session) -> models.User:
    try:
        user_id = int(token)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    user = (
        db.query(models.User)
        .filter(models.User.id == user_id, models.User.is_deleted == 0)
        .first()
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> models.User:
    return get_user_from_token(token=token, db=db)


CurrentUser = Annotated[models.User, Depends(get_current_user)]

