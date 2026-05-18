from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..core.constants import LOBBY_USERNAME
from ..repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, users: UserRepository, db: Session) -> None:
        self.users = users
        self.db = db

    def register(self, user_in: schemas.UserCreate):
        if user_in.username == LOBBY_USERNAME:
            raise HTTPException(status_code=400, detail="Username is reserved")
        if self.users.get_active_by_username(user_in.username):
            raise HTTPException(status_code=400, detail="Username already taken")
        if self.users.get_active_by_name(user_in.name):
            raise HTTPException(status_code=400, detail="Name already taken")

        is_first_user = self.users.count_all() == 0
        user = models.User(
            username=user_in.username,
            name=user_in.name,
            password_hash=security.get_password_hash(user_in.password),
            role="admin" if is_first_user else "user",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return schemas.UserOut.model_validate(user)

    def issue_token(self, username: str, password: str):
        user = security.authenticate_user(self.db, username, password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )
        access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = security.create_access_token(
            data={"sub": user.id},
            expires_delta=access_token_expires,
        )
        user_out = schemas.UserOut.model_validate(user)
        return schemas.Token(access_token=access_token, user=user_out)
