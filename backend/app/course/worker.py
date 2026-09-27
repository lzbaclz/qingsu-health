"""独立于页面读取的失访检查和持久通知队列。没有配置通道时明确保持 unconfigured。"""
from __future__ import annotations

import asyncio
from datetime import timedelta
import hashlib
import hmac
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from sqlalchemy import and_, or_, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from ..config import settings
from ..db import session_scope
from ..models import Encounter, Task, TaskDelivery, TaskStatus
from ..security import aware, real_now
from ..util import iso, now
from .tasks import is_overdue, sweep_no_response

STATE = {"running": False, "last_tick": None, "last_error": None, "consecutive_failures": 0}


def _config() -> dict:
    if not settings.delivery_config:
        return {}
    obj = json.loads(Path(settings.delivery_config).read_text())
    if not isinstance(obj, dict):
        raise ValueError("通知配置必须按机构标识映射")
    return obj


def _post(url: str, payload: bytes, headers: dict) -> None:
    parsed = urlsplit(url)
    if parsed.username or parsed.password or not parsed.hostname:
        raise ValueError("通知地址格式不正确")
    local_demo = settings.app_mode == "demo" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (local_demo and parsed.scheme == "http"):
        raise ValueError("通知地址必须使用 HTTPS")
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        response = client.post(url, content=payload, headers=headers)
        response.raise_for_status()


def tick(deliver=None) -> dict:
    configs = _config()
    send = deliver or _post
    made = delivered = failed = 0
    with session_scope() as session:
        made = len(sweep_no_response(session))
        tasks = session.exec(select(Task).where(Task.status != TaskStatus.COMPLETED)).all()
        for task in tasks:
            if task.severity not in {"urgent", "same_day"} and not is_overdue(task) and task.kind != "no_response":
                continue
            enc = session.get(Encounter, task.encounter_id)
            if not enc:
                continue
            event = "overdue" if is_overdue(task) else "pending"
            key = f"{task.id}:{event}:{task.assignee_role or 'unassigned'}"
            row = session.get(TaskDelivery, key)
            if not row:
                row = TaskDelivery(id=key, task_id=task.id, clinic_id=enc.clinic_id, event=event)
                session.add(row)
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    row = session.get(TaskDelivery, key)
            if row.state in {"delivered", "failed"}:
                continue
            if row.state == "sending" and row.attempts >= 3 and row.next_attempt_at and aware(row.next_attempt_at) <= real_now():
                row.state, row.last_error = "failed", "DeliveryOutcomeUnknown"
                session.add(row)
                session.commit()
                continue
            spec = configs.get(enc.clinic_id) or {}
            if not spec.get("url") or not spec.get("secret"):
                continue  # 保持未配置，绝不假装已通知医护
            if row.next_attempt_at and aware(row.next_attempt_at) > real_now():
                continue
            claim = session.exec(update(TaskDelivery).where(
                TaskDelivery.id == key, TaskDelivery.attempts < 3,
                or_(TaskDelivery.state.in_(["unconfigured", "retry_pending"]),
                    and_(TaskDelivery.state == "sending", TaskDelivery.next_attempt_at < real_now())),
                or_(TaskDelivery.next_attempt_at.is_(None), TaskDelivery.next_attempt_at <= real_now()))
                .values(state="sending", attempts=TaskDelivery.attempts + 1,
                        next_attempt_at=real_now() + timedelta(seconds=60)))
            session.commit()
            if claim.rowcount != 1:
                continue
            session.refresh(row)
            # 通知只带内部任务标识和责任角色，不传患者姓名、原话或症状。
            payload = json.dumps({"event_id": key, "task_id": task.id, "clinic_id": enc.clinic_id,
                                  "event": event, "role": task.assignee_role, "due_at": iso(task.due_at)},
                                 ensure_ascii=False, sort_keys=True).encode()
            signature = hmac.new(str(spec["secret"]).encode(), payload, hashlib.sha256).hexdigest()
            try:
                send(spec["url"], payload, {"Content-Type": "application/json", "Idempotency-Key": key,
                                           "X-Tiji-Signature": signature})
                row.state, row.delivered_at, row.last_error = "delivered", real_now(), None
                delivered += 1
            except Exception as exc:
                row.last_error = type(exc).__name__  # 不记录配置密钥、URL 参数或外部响应正文
                row.state = "failed" if row.attempts >= 3 else "retry_pending"
                row.next_attempt_at = real_now() + timedelta(seconds=60 * row.attempts)
                failed += 1
            session.add(row)
            session.commit()
    STATE.update(last_tick=iso(now()), last_error=None, consecutive_failures=0)
    return {"created_tasks": made, "delivered": delivered, "failed": failed}


async def run(stop: asyncio.Event):
    STATE["running"] = True
    try:
        while not stop.is_set():
            try:
                await asyncio.to_thread(tick)
            except Exception as exc:
                STATE["last_error"] = type(exc).__name__
                STATE["consecutive_failures"] += 1
                if STATE["consecutive_failures"] >= 3:
                    return  # 三次同一调度阻塞后停止，须操作人员处理并重启
            try:
                await asyncio.wait_for(stop.wait(), timeout=max(1, settings.worker_interval_seconds))
            except TimeoutError:
                pass
    finally:
        STATE["running"] = False
