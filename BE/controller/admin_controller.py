"""Controller HTTP của trang quản trị. Mọi endpoint đều yêu cầu vai trò admin."""
from fastapi import APIRouter, Depends, Query

from BE.controller.auth_controller import require_admin
from BE.repository import admin_repository

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/overview")
def overview():
    return admin_repository.overview()


@router.get("/users")
def users():
    return admin_repository.users()


@router.get("/devices-by-room")
def devices_by_room():
    return admin_repository.devices_by_room()


@router.get("/login-history")
def login_history(limit: int = Query(20, ge=1, le=200)):
    return admin_repository.login_history(limit)
