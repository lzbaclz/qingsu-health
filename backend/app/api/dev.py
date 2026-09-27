from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..db import get_session
from ..security import require_doctor
from pydantic import BaseModel

from ..seed import make_followup_parent, seed_demo

router = APIRouter(prefix="/api/dev", tags=["dev"], dependencies=[Depends(require_doctor)])


@router.post("/seed")
def seed(session: Session = Depends(get_session)):
    return seed_demo(session)



class FollowupParentIn(BaseModel):
    patient_code: str


@router.post("/followup-parent")
def followup_parent(body: FollowupParentIn, session: Session = Depends(get_session)):
    """可用性测试卡 D：为测试编号（如 UT-P01-D）准备一次已确认的"上次就诊"，返回可直接打开的随访链接。"""
    eid = make_followup_parent(session, body.patient_code)
    return {"parent_encounter_id": eid, "start_url": f"/p?code={body.patient_code}&parent={eid}&mode=follow_up"}



class ClockIn(BaseModel):
    at: str | None = None   # ISO 时间（带时区），例如 2026-10-15T22:47:00+08:00；为空则恢复真实时间


@router.post("/clock")
def set_demo_clock(body: ClockIn):
    """演示时钟：把"现在"拨到指定时刻（例如晚上 22:47 演示停诊后的红旗分流，再拨到次日 08:30 看早班交接）。"""
    from datetime import datetime

    from ..util import set_clock
    set_clock(datetime.fromisoformat(body.at) if body.at else None)
    return clock_info()


def clock_info() -> dict:
    from ..config import settings
    from ..course.hours import describe_windows, in_service_hours, local_now
    from ..protocol import get_protocol
    from ..util import clock_offset
    p = get_protocol(settings.default_protocol_id)
    return {"now_local": local_now().strftime("%Y-%m-%d %H:%M"), "demo_clock": clock_offset().total_seconds() != 0,
            "in_service_hours": in_service_hours(p), "service_hours": describe_windows(p)}


@router.get("/clock")
def get_demo_clock():
    return clock_info()
