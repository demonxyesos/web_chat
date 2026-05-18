import secrets

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from .. import models, security
from .constants import LOBBY_DISPLAY_NAME, LOBBY_USERNAME


def migrate_chats_is_global_column(conn: Connection, dialect: str) -> None:
    if dialect == "sqlite":
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(chats)")).fetchall()]
        if cols and "is_global" not in cols:
            conn.execute(text("ALTER TABLE chats ADD COLUMN is_global INTEGER NOT NULL DEFAULT 0"))
            conn.commit()
    elif dialect == "postgresql":
        conn.execute(
            text(
                "ALTER TABLE chats ADD COLUMN IF NOT EXISTS is_global INTEGER NOT NULL DEFAULT 0"
            )
        )
        conn.commit()


def ensure_lobby_and_global_chat(db: Session) -> None:
    lobby = (
        db.query(models.User)
        .filter(models.User.username == LOBBY_USERNAME)
        .first()
    )
    if not lobby:
        lobby = models.User(
            username=LOBBY_USERNAME,
            name=LOBBY_DISPLAY_NAME,
            password_hash=security.get_password_hash(secrets.token_hex(32)),
            role="user",
            is_deleted=0,
        )
        db.add(lobby)
        db.commit()
        db.refresh(lobby)

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
