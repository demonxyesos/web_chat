from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, validator

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str = Field(min_length=8, max_length=128)

    @validator('password_confirm')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: str
    role: str
    created_at: datetime


class UserUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class TokenData(BaseModel):
    user_id: Optional[int] = None


class MessageCreate(BaseModel):
    content: str = Field(default="", max_length=4_000)
    to: str = Field(min_length=3, max_length=50)
    reply_to_id: Optional[int] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None

    @validator("content", always=True)
    def content_or_file_required(cls, v, values):
        if not (v or "").strip() and not values.get("file_url"):
            raise ValueError("Message must have content or a file")
        return v


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

