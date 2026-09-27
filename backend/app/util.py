from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


_CLOCK_OFFSET = timedelta(0)  # 演示时钟：相对真实时间的偏移（默认 0；TIJI_DEMO_NOW 或 /api/dev/clock 设置）


def now() -> datetime:
    """统一使用带时区的 UTC 时间（含演示时钟偏移）。"""
    return datetime.now(timezone.utc) + _CLOCK_OFFSET


def set_clock(target: datetime | None) -> None:
    """把"现在"拨到 target（带时区）；None 恢复真实时间。只给演示与测试用。"""
    global _CLOCK_OFFSET
    _CLOCK_OFFSET = timedelta(0) if target is None else target - datetime.now(timezone.utc)


def clock_offset() -> timedelta:
    return _CLOCK_OFFSET


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
