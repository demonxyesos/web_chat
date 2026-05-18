import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import database, models, schemas, security
from .api.routes import admin, auth, chats, ws
from .core.lobby_seed import ensure_lobby_and_global_chat, migrate_chats_is_global_column

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024


def init_db():
    models.Base.metadata.create_all(bind=database.engine)
    dialect = database.engine.dialect.name
    with database.engine.connect() as conn:
        migrate_chats_is_global_column(conn, dialect)
    with database.engine.connect() as conn:
        if dialect in ("postgresql", "sqlite"):
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_messages_chat_deleted_created "
                    "ON messages (chat_id, is_deleted, created_at)"
                )
            )
            conn.commit()
    if dialect != "sqlite":
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

        mcols2 = [r[1] for r in conn.execute(text("PRAGMA table_info(messages)")).fetchall()]
        if mcols2 and "file_url" not in mcols2:
            conn.execute(text("ALTER TABLE messages ADD COLUMN file_url VARCHAR(500)"))
            conn.execute(text("ALTER TABLE messages ADD COLUMN file_name VARCHAR(255)"))
            conn.execute(text("ALTER TABLE messages ADD COLUMN file_type VARCHAR(100)"))
            conn.execute(text("ALTER TABLE messages ADD COLUMN file_size INTEGER"))
            conn.commit()

    db = database.SessionLocal()
    try:
        ensure_lobby_and_global_chat(db)
    finally:
        db.close()


init_db()

app = FastAPI(title="Asyncgram")

_cors_origins = os.environ.get("CORS_ORIGINS", "").strip()
_allow_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()] if _cors_origins else [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_origin_regex=r"^http://192\.168\.\d{1,3}\.\d{1,3}:\d{2,5}$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg",
    ".mp4", ".webm", ".mov", ".avi", ".mkv",
    ".mp3", ".ogg", ".wav", ".flac",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".zip", ".rar", ".7z", ".tar", ".gz",
}


@app.post("/upload")
async def upload_file(
    current_user: security.CurrentUser,
    file: UploadFile = File(...),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not allowed")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / unique_name
    dest.write_bytes(contents)

    return {
        "file_url": f"/uploads/{unique_name}",
        "file_name": file.filename,
        "file_type": file.content_type or "",
        "file_size": len(contents),
    }


@app.get("/users/me", response_model=schemas.UserOut)
def read_users_me(current_user: security.CurrentUser):
    return current_user


@app.patch("/users/me", response_model=schemas.UserOut)
def update_users_me(
    body: schemas.UserUpdate,
    current_user: security.CurrentUser,
    db: Session = Depends(database.get_db),
):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    existing = (
        db.query(models.User)
        .filter(
            models.User.id != current_user.id,
            models.User.name == name,
            models.User.is_deleted == 0,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Name already taken")
    current_user.name = name
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@app.delete("/users/me", status_code=204)
def delete_users_me(
    current_user: security.CurrentUser,
    db: Session = Depends(database.get_db),
):
    user = (
        db.query(models.User)
        .filter(models.User.id == current_user.id, models.User.is_deleted == 0)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_deleted = 1
    db.add(user)
    db.commit()
    return None


app.include_router(auth.router)
app.include_router(chats.router)
app.include_router(admin.router)
app.include_router(ws.router)

