import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from asyncgram_common.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


_connect_args: dict = {}
_engine_kwargs: dict = {"pool_pre_ping": True, "connect_args": _connect_args}

if DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False
    _connect_args["timeout"] = 30
elif DATABASE_URL.startswith("postgresql"):
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_schema() -> None:
    if engine.dialect.name == "postgresql":
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
            conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
