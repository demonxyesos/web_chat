from typing import List, Optional

from fastapi import APIRouter, Depends

from ... import schemas, security
from ...core.dependencies import get_admin_service
from ...services.admin_service import AdminService
from ...services.ws_chat_service import manager

router = APIRouter(tags=["admin"])


@router.get("/admin/users", response_model=list[schemas.UserOut])
def admin_list_users(
    current_user: security.CurrentUser,
    service: AdminService = Depends(get_admin_service),
):
    return service.list_users(current_user.role)


@router.delete("/admin/users/{user_id}", status_code=204)
def admin_delete_user(
    user_id: int,
    current_user: security.CurrentUser,
    service: AdminService = Depends(get_admin_service),
):
    service.delete_user(current_user.role, current_user.id, user_id)
    return None


@router.get("/admin/messages", response_model=List[schemas.MessageOut])
def admin_list_messages(
    current_user: security.CurrentUser,
    limit: int = 50,
    before_id: Optional[int] = None,
    service: AdminService = Depends(get_admin_service),
):
    safe = max(1, min(limit, 200))
    return service.list_messages(current_user.role, safe, before_id)


@router.delete("/admin/messages/{message_id}", status_code=204)
async def admin_delete_message(
    message_id: int,
    current_user: security.CurrentUser,
    service: AdminService = Depends(get_admin_service),
):
    _mid, cid, chat = service.delete_message(current_user.role, message_id)
    ws_payload = {"type": "message_deleted", "id": message_id, "chat_id": cid}
    if chat and getattr(chat, "is_global", 0) == 1:
        await manager.broadcast_json(ws_payload)
    elif chat:
        await manager.send_to(chat.user_a_id, ws_payload)
        await manager.send_to(chat.user_b_id, ws_payload)
    return None
