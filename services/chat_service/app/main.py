from sqlalchemy import text

from fastapi import FastAPI

from asyncgram_common.app_factory import add_cors, add_health

from .database import Base, SessionLocal, engine, ensure_schemas
from .models import Chat, Message
from .repositories import ensure_lobby_and_global_chat, migrate_is_global
from .routes import router

ensure_schemas()
dialect = engine.dialect.name
Base.metadata.create_all(bind=engine, tables=[Chat.__table__, Message.__table__])

with engine.connect() as conn:
    migrate_is_global(conn, dialect)
    if dialect == "postgresql":
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_messages_chat_deleted_created "
                "ON chat.messages (chat_id, is_deleted, created_at)"
            )
        )
        conn.commit()
    elif dialect == "sqlite":
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_messages_chat_deleted_created "
                "ON messages (chat_id, is_deleted, created_at)"
            )
        )
        conn.commit()

db = SessionLocal()
try:
    ensure_lobby_and_global_chat(db)
finally:
    db.close()

app = FastAPI(title="Asyncgram Chat Service")
add_cors(app)
add_health(app)
app.include_router(router)
