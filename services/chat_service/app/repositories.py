from sqlalchemy import or_, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from asyncgram_common.constants import LOBBY_USERNAME

from . import models
from .database import USE_SCHEMAS


def migrate_is_global(conn: Connection, dialect: str) -> None:
    if dialect == "sqlite":
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(chats)")).fetchall()]
        if cols and "is_global" not in cols:
            conn.execute(text("ALTER TABLE chats ADD COLUMN is_global INTEGER NOT NULL DEFAULT 0"))
            conn.commit()
    elif dialect == "postgresql":
        conn.execute(
            text("ALTER TABLE chat.chats ADD COLUMN IF NOT EXISTS is_global INTEGER NOT NULL DEFAULT 0")
        )
        conn.commit()


def ensure_lobby_and_global_chat(db: Session) -> None:
    lobby = db.query(models.User).filter(models.User.username == LOBBY_USERNAME).first()
    if not lobby:
        return

    gchat = db.query(models.Chat).filter(models.Chat.is_global == 1).first()
    if not gchat:
        gchat = models.Chat(
            user_a_id=lobby.id,
            user_b_id=lobby.id,
            is_global=1,
            is_deleted=0,
        )
        db.add(gchat)
        db.commit()


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active_by_username(self, username: str):
        return (
            self.db.query(models.User)
            .filter(models.User.username == username, models.User.is_deleted == 0)
            .first()
        )

    def get_active_by_id(self, user_id: int):
        return (
            self.db.query(models.User)
            .filter(models.User.id == user_id, models.User.is_deleted == 0)
            .first()
        )

    def get_by_id(self, user_id: int):
        return self.db.query(models.User).filter(models.User.id == user_id).first()

    def search_active(self, query: str, exclude_user_id: int):
        return (
            self.db.query(models.User)
            .filter(models.User.is_deleted == 0)
            .filter(models.User.username != LOBBY_USERNAME)
            .filter(models.User.username.ilike(f"%{query}%"))
            .filter(models.User.id != exclude_user_id)
            .order_by(models.User.username.asc())
            .limit(20)
            .all()
        )


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
            .order_by(models.Chat.updated_at.desc())
            .all()
        )

    def get_global_chat(self):
        return (
            self.db.query(models.Chat)
            .filter(models.Chat.is_global == 1, models.Chat.is_deleted == 0)
            .first()
        )

    def get_active_by_id(self, chat_id: int):
        return (
            self.db.query(models.Chat)
            .filter(models.Chat.id == chat_id, models.Chat.is_deleted == 0)
            .first()
        )


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

    def list_admin_feed(self, limit: int, before_id: int | None = None):
        q = (
            self.db.query(models.Message)
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

    def latest_active_by_chat_ids(self, chat_ids: list[int]) -> dict[int, models.Message]:
        from sqlalchemy import func

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
            .all()
        )
        return {m.chat_id: m for m in rows}
