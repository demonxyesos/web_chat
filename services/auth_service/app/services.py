from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from asyncgram_common.constants import LOBBY_USERNAME
from asyncgram_common.jwt import create_access_token
from asyncgram_common.passwords import get_password_hash, verify_password

from . import models, schemas
from .repositories import UserRepository


class AuthService:
    def __init__(self, users: UserRepository, db: Session) -> None:
        self.users = users
        self.db = db

    def register(self, user_in: schemas.UserCreate) -> schemas.UserOut:
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
            password_hash=get_password_hash(user_in.password),
            role="admin" if is_first_user else "user",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return schemas.UserOut.model_validate(user)

    def issue_token(self, username: str, password: str) -> schemas.Token:
        user = self.users.get_active_by_username(username)
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )
        access_token = create_access_token(subject=user.id, role=user.role)
        user_out = schemas.UserOut.model_validate(user)
        return schemas.Token(access_token=access_token, user=user_out)


class UserService:
    def __init__(self, users: UserRepository, db: Session) -> None:
        self.users = users
        self.db = db

    def update_me_name(self, user_id: int, name: str) -> models.User:
        user = self.users.get_active_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        new_name = (name or "").strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="Name is required")
        existing = self.users.get_active_by_name(new_name)
        if existing and existing.id != user_id:
            raise HTTPException(status_code=400, detail="Name already taken")
        user.name = new_name
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_me(self, user_id: int) -> None:
        user = self.users.get_active_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_deleted = 1
        self.db.add(user)
        self.db.commit()

    def admin_delete_user(self, actor_id: int, user_id: int) -> None:
        if user_id == actor_id:
            raise HTTPException(status_code=403, detail="Cannot delete yourself")
        user = self.users.get_active_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.username == LOBBY_USERNAME:
            raise HTTPException(status_code=403, detail="Cannot delete system user")
        user.is_deleted = 1
        self.db.add(user)
        self.db.commit()
