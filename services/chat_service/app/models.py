from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base, USE_SCHEMAS

_CHAT = "chat." if USE_SCHEMAS else ""


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        {"schema": "auth", "extend_existing": True} if USE_SCHEMAS else {"extend_existing": True}
    )

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(20), default="user", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_deleted = Column(Integer, default=0, nullable=False)


class Chat(Base):
    __tablename__ = "chats"
    __table_args__ = (
        UniqueConstraint("user_a_id", "user_b_id", name="uq_chat_user_pair"),
        {"schema": "chat"} if USE_SCHEMAS else {},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_a_id = Column(Integer, nullable=False, index=True)
    user_b_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_deleted = Column(Integer, default=0, nullable=False)
    is_global = Column(Integer, default=0, nullable=False)

    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_chat_deleted_created", "chat_id", "is_deleted", "created_at"),
        {"schema": "chat"} if USE_SCHEMAS else {},
    )

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    edited_at = Column(DateTime, nullable=True)
    is_deleted = Column(Integer, default=0, nullable=False)

    file_url = Column(String(500), nullable=True)
    file_name = Column(String(255), nullable=True)
    file_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)

    chat_id = Column(Integer, ForeignKey(f"{_CHAT}chats.id"), nullable=False, index=True)
    author_id = Column(Integer, nullable=False)
    recipient_id = Column(Integer, nullable=False)
    reply_to_message_id = Column(Integer, ForeignKey(f"{_CHAT}messages.id"), nullable=True)

    chat = relationship("Chat", back_populates="messages", foreign_keys=[chat_id])
    reply_to = relationship("Message", remote_side=[id], uselist=False)
