from sqlalchemy import text

from .. import database, models
from .lobby_seed import ensure_lobby_and_global_chat, migrate_chats_is_global_column


def init_db() -> None:
    models.Base.metadata.create_all(bind=database.engine)
    dialect = database.engine.dialect.name
    with database.engine.connect() as conn:
        migrate_chats_is_global_column(conn, dialect)
    if database.engine.dialect.name != "sqlite":
        db = database.SessionLocal()
        try:
            ensure_lobby_and_global_chat(db)
        finally:
            db.close()
        return
    with database.engine.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(messages)")).fetchall()]
        if cols and "edited_at" not in cols:
            conn.execute(text("ALTER TABLE messages ADD COLUMN edited_at DATETIME"))
            conn.commit()
        if cols and "reply_to_message_id" not in cols:
            conn.execute(text("ALTER TABLE messages ADD COLUMN reply_to_message_id INTEGER"))
            conn.commit()
        if cols and "is_deleted" not in cols:
            conn.execute(text("ALTER TABLE messages ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0"))
            conn.commit()

        ucols = [r[1] for r in conn.execute(text("PRAGMA table_info(users)")).fetchall()]
        if ucols and "is_deleted" not in ucols:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0"))
            conn.commit()

        ccols = [r[1] for r in conn.execute(text("PRAGMA table_info(chats)")).fetchall()]
        if ccols and "is_deleted" not in ccols:
            conn.execute(text("ALTER TABLE chats ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0"))
            conn.commit()

    db = database.SessionLocal()
    try:
        ensure_lobby_and_global_chat(db)
    finally:
        db.close()
