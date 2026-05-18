from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_deleted = Column(Integer, default=0, nullable=False)

    messages = relationship(
        "Message", back_populates="author", foreign_keys="Message.author_id"
    )
    received_messages = relationship(
        "Message", back_populates="recipient", foreign_keys="Message.recipient_id"
    )

    chats_a = relationship("Chat", foreign_keys="Chat.user_a_id", back_populates="user_a")
    chats_b = relationship("Chat", foreign_keys="Chat.user_b_id", back_populates="user_b")


class Chat(Base):
    __tablename__ = "chats"
    __table_args__ = (
        UniqueConstraint("user_a_id", "user_b_id", name="uq_chat_user_pair"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_a_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user_b_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_deleted = Column(Integer, default=0, nullable=False)
    is_global = Column(Integer, default=0, nullable=False)

    user_a = relationship("User", foreign_keys=[user_a_id], back_populates="chats_a")
    user_b = relationship("User", foreign_keys=[user_b_id], back_populates="chats_b")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_chat_deleted_created", "chat_id", "is_deleted", "created_at"),
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

    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reply_to_message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)

    chat = relationship("Chat", back_populates="messages", foreign_keys=[chat_id])
    author = relationship("User", back_populates="messages", foreign_keys=[author_id])
    recipient = relationship("User", back_populates="received_messages", foreign_keys=[recipient_id])
    reply_to = relationship("Message", remote_side=[id], uselist=False)

