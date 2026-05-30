from typing import Annotated, Protocol

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .jwt import decode_token_payload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


class AuthUser(Protocol):
    id: int
    username: str
    name: str
    role: str


class TokenUser:
    def __init__(self, user_id: int, role: str) -> None:
        self.id = user_id
        self.role = role
        self.username = ""
        self.name = ""


def get_token_user(token: Annotated[str, Depends(oauth2_scheme)]) -> TokenUser:
    try:
        payload = decode_token_payload(token)
        user_id = int(payload["sub"])
        role = str(payload.get("role") or "user")
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return TokenUser(user_id=user_id, role=role)


def require_admin(user: Annotated[TokenUser, Depends(get_token_user)]) -> TokenUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return user


CurrentTokenUser = Annotated[TokenUser, Depends(get_token_user)]
AdminTokenUser = Annotated[TokenUser, Depends(require_admin)]
