from typing import Any

from pydantic import BaseModel, Field


class ChatEvent(BaseModel):
    type: str
    broadcast: bool = False
    target_user_ids: list[int] = Field(default_factory=list)
    payload: dict[str, Any]
