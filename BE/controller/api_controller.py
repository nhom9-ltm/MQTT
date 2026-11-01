"""
Controller HTTP của API lịch sử — nhận request, gọi history_service, trả JSON cho FE/history.html.

    pip install -r BE/requirements-extra.txt
    uvicorn BE.controller.api_controller:app --port 8000        # chạy từ thư mục gốc repo
    python BE/run_api.py                                         # tương đương
    HISTORY_DB=BE/data/demo_history.db python BE/run_api.py      # dùng dữ liệu mẫu
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from BE.repository.history_repository import DatabaseUnavailable
from BE.service import history_service

app = FastAPI(title="Smart Home History API")
# Dashboard chạy ở cổng khác (8080) nên phải cho phép CORS; API chỉ có GET, không ghi gì.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])


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
