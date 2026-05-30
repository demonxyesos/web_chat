from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.password_confirm:
            raise ValueError("Passwords do not match")
        return self


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
