from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from .database import Base, USE_SCHEMAS


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"} if USE_SCHEMAS else {}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_deleted = Column(Integer, default=0, nullable=False)
