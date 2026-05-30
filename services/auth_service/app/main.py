from fastapi import FastAPI

from asyncgram_common.app_factory import add_cors, add_health

from .database import Base, SessionLocal, engine, ensure_schema
from .lobby_seed import ensure_lobby_user
from .routes import router

ensure_schema()
Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    ensure_lobby_user(db)
finally:
    db.close()

app = FastAPI(title="Asyncgram Auth Service")
add_cors(app)
add_health(app)
app.include_router(router)
