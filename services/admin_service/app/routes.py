from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from asyncgram_common.auth_deps import AdminTokenUser
from asyncgram_common.config import AUTH_SERVICE_URL, CHAT_SERVICE_URL

router = APIRouter(tags=["admin"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def bearer_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@router.get("/admin/users")
async def admin_list_users(
    _admin: AdminTokenUser,
    token: str = Depends(oauth2_scheme),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{AUTH_SERVICE_URL}/internal/users",
            headers=bearer_headers(token),
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


@router.delete("/admin/users/{user_id}", status_code=204)
async def admin_delete_user(
    user_id: int,
    _admin: AdminTokenUser,
    token: str = Depends(oauth2_scheme),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{AUTH_SERVICE_URL}/internal/users/{user_id}",
            headers=bearer_headers(token),
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return None


@router.get("/admin/messages")
async def admin_list_messages(
    _admin: AdminTokenUser,
    limit: int = 50,
    before_id: Optional[int] = None,
    token: str = Depends(oauth2_scheme),
):
    params: dict = {"limit": max(1, min(limit, 200))}
    if before_id is not None:
        params["before_id"] = before_id
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{CHAT_SERVICE_URL}/internal/messages",
            headers=bearer_headers(token),
            params=params,
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


@router.delete("/admin/messages/{message_id}", status_code=204)
async def admin_delete_message(
    message_id: int,
    _admin: AdminTokenUser,
    token: str = Depends(oauth2_scheme),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{CHAT_SERVICE_URL}/internal/messages/{message_id}",
            headers=bearer_headers(token),
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return None
