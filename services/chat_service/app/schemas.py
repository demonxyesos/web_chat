from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: str
    role: str
    created_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(default="", max_length=4_000)
    to: str = Field(min_length=3, max_length=50)
    reply_to_id: Optional[int] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None

    @field_validator("content")
    @classmethod
    def strip_content(cls, v: str) -> str:
        return v or ""


class MessageUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=4_000)


class MessageReplyRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    author: UserOut


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    created_at: datetime
    edited_at: Optional[datetime] = None
    chat_id: int
    reply_to: Optional[MessageReplyRef] = None
    author: UserOut
    recipient: UserOut
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None


class ChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    peer: UserOut
    updated_at: datetime
    last_message: Optional[MessageOut] = None
    is_global: bool = False
