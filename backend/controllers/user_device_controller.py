"""Controller HTTP cho người dùng đã đăng nhập: kết nối thiết bị vào tài khoản bằng mã thiết bị.

  GET  /api/devices/mine       thiết bị đã kết nối
  POST /api/devices/connect    {"code": "light" | "living/light"} → 201 thiết bị vừa kết nối, 400 kèm lý do nếu sai
"""
from fastapi import APIRouter, Body, Depends, HTTPException

from backend.controllers.auth_controller import current_user
from backend.services import user_device_service

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("/mine")
def my_devices(user: dict = Depends(current_user)):
    return user_device_service.list_mine(user)


@router.post("/connect", status_code=201)
def connect_device(body: dict = Body(...), user: dict = Depends(current_user)):
    try:
        return user_device_service.connect(user, body.get("code"))
    except user_device_service.ConnectError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
