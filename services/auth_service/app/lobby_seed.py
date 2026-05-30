import secrets

from sqlalchemy.orm import Session

from asyncgram_common.constants import LOBBY_DISPLAY_NAME, LOBBY_USERNAME
from asyncgram_common.passwords import get_password_hash

from . import models
from .repositories import UserRepository


def ensure_lobby_user(db: Session) -> None:
    users = UserRepository(db)
    if users.get_active_by_username(LOBBY_USERNAME):
        return
    user = models.User(
        username=LOBBY_USERNAME,
        name=LOBBY_DISPLAY_NAME,
        password_hash=get_password_hash(secrets.token_hex(32)),
        role="user",
        is_deleted=0,
    )
    db.add(user)
    db.commit()
