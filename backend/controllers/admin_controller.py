"""Controller HTTP của trang quản trị. Mọi endpoint đều yêu cầu vai trò admin.

  /api/admin/overview, /devices-by-room, /login-history            số liệu (chỉ đọc)
  /api/admin/users            GET (?q=&role=&status=), POST     tài khoản
  /api/admin/users/{id}       PUT, DELETE (xóa mềm)
  /api/admin/users/{id}/active    PUT             khóa / mở khóa nhanh
  /api/admin/roles            GET                 2 vai trò cố định (admin, user) + quyền + số tài khoản
  /api/admin/roles/{code}     PUT                 đổi tên hiển thị
  /api/admin/devices          GET, POST           thiết bị đã đăng ký
  /api/admin/devices/{id}     PUT, DELETE
  /api/admin/device-options   GET                 danh sách phòng + loại thiết bị cho form
  /api/admin/rules            GET, POST           luật tự động (rules.json)
  /api/admin/rules/{id}       PUT, DELETE
  /api/admin/rules/{id}/enabled   PUT             bật/tắt nhanh
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query

from backend.controllers.auth_controller import require_admin
from backend.repositories import admin_repository
from backend.services import device_service, rule_service, user_service
from backend.services.rule_validation import RuleError

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _call(fn, *args):
    """Đổi lỗi nghiệp vụ thành mã HTTP: dữ liệu sai → 400, không tìm thấy → 404."""
    try:
        return fn(*args)
    except (device_service.DeviceError, RuleError, user_service.UserError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (device_service.DeviceNotFound, rule_service.RuleNotFound, user_service.UserNotFound) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------- số liệu ----------
@router.get("/overview")
def overview():
    return admin_repository.overview()


@router.get("/devices-by-room")
def devices_by_room():
    return admin_repository.devices_by_room()


@router.get("/login-history")
def login_history(limit: int = Query(20, ge=1, le=200)):
    return admin_repository.login_history(limit)


# ---------- tài khoản & vai trò ----------
@router.get("/users")
def list_users(q: str = "", role: str = "", status: str = ""):
    return user_service.list_users(q, role, status)


@router.post("/users", status_code=201)
def create_user(body: dict = Body(...)):
    return _call(user_service.create, body)


@router.put("/users/{user_id}")
def update_user(user_id: int, body: dict = Body(...), admin: dict = Depends(require_admin)):
    return _call(user_service.update, user_id, body, admin)


@router.put("/users/{user_id}/active")
def set_user_active(user_id: int, body: dict = Body(...), admin: dict = Depends(require_admin)):
    return _call(user_service.set_active, user_id, bool(body.get("is_active")), admin)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    _call(user_service.delete, user_id, admin)


@router.get("/roles")
def list_roles():
    return user_service.list_roles()


@router.put("/roles/{code}")
def rename_role(code: str, body: dict = Body(...)):
    return _call(user_service.rename_role, code, body.get("name"))


# ---------- thiết bị ----------
@router.get("/devices")
def list_devices():
    return device_service.list_devices()


@router.get("/device-options")
def device_options():
    return device_service.options()


@router.post("/devices", status_code=201)
def create_device(body: dict = Body(...)):
    return _call(device_service.create, body)


@router.put("/devices/{device_id}")
def update_device(device_id: int, body: dict = Body(...)):
    return _call(device_service.update, device_id, body)


@router.delete("/devices/{device_id}", status_code=204)
def delete_device(device_id: int):
    _call(device_service.delete, device_id)


# ---------- luật tự động ----------
@router.get("/rules")
def list_rules():
    return rule_service.list_rules()


@router.post("/rules", status_code=201)
def create_rule(body: dict = Body(...)):
    return _call(rule_service.create, body)


@router.put("/rules/{rule_id}")
def update_rule(rule_id: str, body: dict = Body(...)):
    return _call(rule_service.update, rule_id, body)


@router.put("/rules/{rule_id}/enabled")
def set_rule_enabled(rule_id: str, body: dict = Body(...)):
    return _call(rule_service.set_enabled, rule_id, bool(body.get("enabled", True)))


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: str):
    _call(rule_service.delete, rule_id)
