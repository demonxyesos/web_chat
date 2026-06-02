from sqlalchemy.orm import Session

from asyncgram_common.constants import LOBBY_USERNAME

from . import models


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def count_all(self) -> int:
        return self.db.query(models.User).count()

    def count_real_users(self) -> int:
        return (
            self.db.query(models.User)
            .filter(models.User.username != LOBBY_USERNAME, models.User.is_deleted == 0)
            .count()
        )

    def get_active_by_username(self, username: str):
        return (
            self.db.query(models.User)
            .filter(models.User.username == username, models.User.is_deleted == 0)
            .first()
        )

    def get_active_by_name(self, name: str):
        return (
            self.db.query(models.User)
            .filter(models.User.name == name, models.User.is_deleted == 0)
            .first()
        )

    def get_active_by_id(self, user_id: int):
        return (
            self.db.query(models.User)
            .filter(models.User.id == user_id, models.User.is_deleted == 0)
            .first()
        )

    def list_active(self):
        return (
            self.db.query(models.User)
            .filter(models.User.is_deleted == 0)
            .order_by(models.User.created_at.asc())
            .all()
        )
