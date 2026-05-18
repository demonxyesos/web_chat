from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..repositories.user_repository import UserRepository


class UserService:
    def __init__(self, users: UserRepository, db: Session) -> None:
        self.users = users
        self.db = db

    def update_me_name(self, user_id: int, name: str):
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
