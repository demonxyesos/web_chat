from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from .. import models


class ChatRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_pair_chat(self, user_a_id: int, user_b_id: int):
        a, b = sorted([user_a_id, user_b_id])
        return (
            self.db.query(models.Chat)
            .filter(models.Chat.user_a_id == a, models.Chat.user_b_id == b)
            .first()
        )

    def create_pair_chat(self, user_a_id: int, user_b_id: int):
        a, b = sorted([user_a_id, user_b_id])
        chat = models.Chat(user_a_id=a, user_b_id=b)
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(chat)
        return chat

    def list_active_for_user(self, user_id: int):
        return (
            self.db.query(models.Chat)
            .filter(
                models.Chat.is_deleted == 0,
                or_(
                    models.Chat.user_a_id == user_id,
                    models.Chat.user_b_id == user_id,
                    models.Chat.is_global == 1,
                ),
            )
            .options(joinedload(models.Chat.user_a), joinedload(models.Chat.user_b))
            .order_by(models.Chat.updated_at.desc())
            .all()
        )

    def get_global_chat(self):
        return (
            self.db.query(models.Chat)
            .filter(models.Chat.is_global == 1, models.Chat.is_deleted == 0)
            .options(joinedload(models.Chat.user_a), joinedload(models.Chat.user_b))
            .first()
        )

    def get_active_by_id(self, chat_id: int):
        return (
            self.db.query(models.Chat)
            .filter(models.Chat.id == chat_id, models.Chat.is_deleted == 0)
            .first()
        )
