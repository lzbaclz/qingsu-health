from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import auth, doctor, patient, protocols
from .config import settings
from .db import init_db
from .security import Principal, require_clinical

@asynccontextmanager
async def _lifespan(_: FastAPI):
    if settings.app_mode not in {"demo", "production"}:
        raise RuntimeError("TIJI_MODE 必须是 demo 或 production")
    init_db()
    if settings.demo_now:  # 演示时钟：TIJI_DEMO_NOW=2026-10-15T22:47:00+08:00
        from datetime import datetime

        from .util import set_clock
        set_clock(datetime.fromisoformat(settings.demo_now))
    from .course import worker
    stop = asyncio.Event()
    runner = asyncio.create_task(worker.run(stop)) if settings.worker_interval_seconds > 0 else None
    try:
        yield
    finally:
        stop.set()
        if runner:
            await runner


app = FastAPI(title="体迹 AI API", version="0.3.1", lifespan=_lifespan,
              docs_url="/docs" if settings.app_mode == "demo" else None,
              redoc_url=None, openapi_url="/openapi.json" if settings.app_mode == "demo" else None,
              description="面向专科门诊的 AI 症状表达与病程协作工具。模型只做抽取与叙述；问什么、何时升级、给患者看什么，由临床协议决定。")
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
@app.middleware("http")
async def access_headers(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if (origin and origin not in settings.cors_origins) or request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "请求来源不被允许"}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
    return response

app.include_router(auth.router)
app.include_router(patient.router)
app.include_router(doctor.router)
app.include_router(protocols.router)
if settings.enable_dev_endpoints:
    from .api import dev
    app.include_router(dev.router)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/status")
def status(user: Principal = Depends(require_clinical)):
    """只报配置与最近一次调用/错误/自检结果，不在这里调用真实模型（不花钱）。"""
    from .llm.provider import provider_info
    from .course.hours import describe_windows, in_service_hours, local_now
    from .protocol import get_protocol
    from .util import clock_offset
    from .course.worker import STATE
    p = get_protocol(settings.default_protocol_id)
    return {"ok": True, "version": "0.3.1", "mode": settings.app_mode, "clinic_timezone": settings.clinic_tz,
            "llm_provider": settings.llm_provider, "llm": provider_info(),
            "worker": dict(STATE), "external_delivery_configured": bool(settings.delivery_config),
            "default_protocol": settings.default_protocol_id, "dev_endpoints": settings.enable_dev_endpoints,
            "clock": {"now_local": local_now().strftime("%Y-%m-%d %H:%M"), "demo_clock": clock_offset().total_seconds() != 0,
                      "in_service_hours": in_service_hours(p), "service_hours": describe_windows(p)}}


@app.get("/api/qr.svg")
def qr_code(data: str, scale: int = 6):
    """二维码（SVG，自研编码器，无第三方依赖）：随访卡、签到立牌用。只编码链接，不含任何患者信息。"""
    from fastapi import HTTPException, Response

    from .qr import qr_svg
    if not data or len(data) > 300:
        raise HTTPException(400, "内容为空或过长（最多 300 个字符）")
    try:
        svg = qr_svg(data, scale=max(2, min(scale, 12)))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "no-store"})


_probe_at = 0.0


@app.post("/api/llm/probe")
def llm_probe(user: Principal = Depends(require_clinical)):
    """真实模型连通性自检：跑一次固定测试原话的真实抽取。30 秒内重复调用直接返回上次结果，避免空耗费用。"""
    import time

    from .llm.provider import _LAST_PROBE, probe
    global _probe_at
    if _LAST_PROBE and time.monotonic() - _probe_at < 30:
        return {**_LAST_PROBE, "cached": True}
    _probe_at = time.monotonic()
    return probe()
