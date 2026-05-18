from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from typing import Optional

from .. import models


class MessageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        content: str,
        chat_id: int,
        author_id: int,
        recipient_id: int,
        reply_to_message_id: int | None = None,
        file_url: str | None = None,
        file_name: str | None = None,
        file_type: str | None = None,
        file_size: int | None = None,
    ):
        msg = models.Message(
            content=content,
            chat_id=chat_id,
            author_id=author_id,
            recipient_id=recipient_id,
            reply_to_message_id=reply_to_message_id,
            file_url=file_url,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_by_id(self, message_id: int):
        return self.db.query(models.Message).filter(models.Message.id == message_id).first()

    def get_active_by_id(self, message_id: int):
        return (
            self.db.query(models.Message)
            .filter(models.Message.id == message_id, models.Message.is_deleted == 0)
            .first()
        )

    def get_in_chat(self, message_id: int, chat_id: int):
        return (
            self.db.query(models.Message)
            .filter(models.Message.id == message_id, models.Message.chat_id == chat_id)
            .first()
        )

    def list_admin_feed(self, limit: int, before_id: Optional[int] = None):
        q = (
            self.db.query(models.Message)
            .options(
                joinedload(models.Message.author),
                joinedload(models.Message.recipient),
                joinedload(models.Message.reply_to).joinedload(models.Message.author),
            )
            .filter(models.Message.is_deleted == 0)
        )
        if before_id is not None:
            q = q.filter(models.Message.id < before_id)
        rows = q.order_by(models.Message.id.desc()).limit(limit).all()
        return list(reversed(rows))

    def list_active_in_chat(self, chat_id: int, limit: int):
        return (
            self.db.query(models.Message)
            .filter(models.Message.chat_id == chat_id, models.Message.is_deleted == 0)
            .order_by(models.Message.created_at.desc())
            .limit(limit)
            .all()
        )

    def latest_active_in_chat(self, chat_id: int):
        return (
            self.db.query(models.Message)
            .filter(models.Message.chat_id == chat_id, models.Message.is_deleted == 0)
            .order_by(models.Message.created_at.desc())
            .first()
        )

    def latest_active_by_chat_ids(self, chat_ids: list[int]) -> dict[int, models.Message]:
        if not chat_ids:
            return {}
        subq = (
            self.db.query(
                models.Message.chat_id.label("cid"),
                func.max(models.Message.id).label("max_id"),
            )
            .filter(
                models.Message.chat_id.in_(chat_ids),
                models.Message.is_deleted == 0,
            )
            .group_by(models.Message.chat_id)
            .subquery()
        )
        rows = (
            self.db.query(models.Message)
            .join(
                subq,
                (models.Message.chat_id == subq.c.cid) & (models.Message.id == subq.c.max_id),
            )
            .options(
                joinedload(models.Message.author),
                joinedload(models.Message.recipient),
                joinedload(models.Message.reply_to).joinedload(models.Message.author),
            )
            .all()
        )
        return {m.chat_id: m for m in rows}
