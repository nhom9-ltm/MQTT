"""
Controller HTTP của API lịch sử — nhận request, gọi history_service, trả JSON cho frontend/history.html.

    pip install -r backend/requirements-extra.txt
    uvicorn backend.controllers.api_controller:app --port 8011        # chạy từ thư mục gốc repo
    python backend/run_api.py                                         # tương đương
    HISTORY_DB=backend/data/demo_history.db python backend/run_api.py      # dùng dữ liệu mẫu
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.controllers.admin_controller import router as admin_router
from backend.controllers.auth_controller import router as auth_router
from backend.controllers.user_device_controller import router as user_device_router
from backend.repositories.history_repository import DatabaseUnavailable
from backend.services import history_service

app = FastAPI(title="Smart Home History API")
# Dashboard chạy ở cổng khác (8080) nên phải cho phép CORS. Phiên gửi qua header Authorization, không dùng cookie.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST", "PUT", "DELETE"],
                   allow_headers=["Authorization", "Content-Type"])
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(user_device_router)


@app.exception_handler(DatabaseUnavailable)
async def db_unavailable(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/api/summary")
def summary(hours: int = Query(24, ge=1, le=24 * 30)):
    return history_service.summary(hours)


@app.get("/api/climate")
def climate(room: str, hours: int = Query(24, ge=1, le=24 * 30)):
    return history_service.climate(room, hours)


@app.get("/api/energy")
def energy(days: int = Query(7, ge=1, le=90)):
    return history_service.energy(days)


@app.get("/api/commands")
def commands(hours: int = Query(24, ge=1, le=24 * 30)):
    return history_service.commands(hours)


@app.get("/api/alerts")
def alerts(limit: int = Query(20, ge=1, le=200)):
    return history_service.alerts(limit)
