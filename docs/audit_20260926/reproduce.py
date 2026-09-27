"""本轮评审复现：只用临时数据库与模拟数据，不访问运行中的服务或模型。"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="tiji_audit_20260926_"))
os.environ.update(
    TIJI_DATABASE_URL=f"sqlite:///{TMP / 'audit.db'}",
    TIJI_LLM_PROVIDER="mock",
    TIJI_PATIENT_REWRITE="glossary",
    TIJI_DEFAULT_PROTOCOL="lbp_adult_v0.2",
    TIJI_ENABLE_DEV="0",
    TIJI_USER_TEST_PLANT="0",
    TIJI_DEMO_NOW="",
)
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from sqlmodel import select
from app.db import session_scope
from app.main import app
from app.models import EncounterStatus, Notification, Task, TaskStatus
from app.protocol import get_protocol
from app.protocol.schema import Protocol
from app.services import encounter as svc
from app.tasks.service import create_notification, create_task, deliver_queued
from app.course.tasks import sweep_no_response, _due
from app.questioning.engine import next_question
from app.util import iso, now, set_clock


out: dict = {"date": "2026-09-26", "scope": "isolated synthetic data; mock only; dev API disabled"}
p = get_protocol("lbp_adult_v0.2")
out["protocol"] = {"id": p.protocol_id, "status": p.status, "max_questions": p.max_questions,
                   "screening": p.screening.model_dump(), "no_response": p.course.no_response.model_dump() if p.course.no_response else None}
out["protocol"]["course_configuration"] = {
    "service_windows": len(p.course.service_windows), "outcomes": len(p.course.outcomes),
    "recovery_rules": len(p.course.recovery_rules), "task_routing": list(p.course.task_routing)}

with TestClient(app) as client:
    # 1. 草案协议在关闭演示接口时仍可新建患者记录。
    r = client.post("/api/patient/encounters", json={
        "patient_code": "AUDIT-A", "eligibility": {x.id: True for x in p.scope.eligibility}})
    assert r.status_code == 200, r.text
    a_id = r.json()["encounter"]["id"] if "encounter" in r.json() else r.json()["id"]
    out["draft_protocol_creation"] = {"status_code": r.status_code, "protocol_status": p.status}
    with session_scope() as s:
        b = svc.create_encounter(s, patient_code="AUDIT-B", protocol_id=p.protocol_id)
        b_id = b.id
        n = create_notification(s, a_id, "仅用于评审的模拟说明", "doctor:synthetic")
        deliver_queued(s, a_id)
        n_id = n.id
        t = create_task(s, a_id, "red_flag_review", "评审模拟红旗任务")
        t_id = t.id
    # 2. 无任何身份凭据即可读取列表和明细。
    out["unauthenticated_doctor_reads"] = {
        "list_http": client.get("/api/doctor/encounters").status_code,
        "detail_http": client.get(f"/api/doctor/encounters/{a_id}").status_code,
    }
    # 3. 用 B 的记录地址推进 A 的通知状态。
    statuses = []
    for event in ("seen", "acknowledged"):
        rr = client.post(f"/api/patient/encounters/{b_id}/notifications/{n_id}/event", json={"event": event})
        statuses.append({"event": event, "http": rr.status_code})
    with session_scope() as s:
        nn = s.get(Notification, n_id)
        out["cross_encounter_notification"] = {
            "requests": statuses, "notification_belongs_to_A": nn.encounter_id == a_id,
            "final_status": nn.status, "history_actor_uses_B": nn.history[-1]["by"] == f"patient:{b_id}"}
    # 4. 未认证 actor 字符串可推进任务，联系未果只填次数也可结案。
    steps = []
    for to in (TaskStatus.VIEWED, TaskStatus.CONTACTED, TaskStatus.COMPLETED):
        body = {"actor": "随意填写的操作者", "to": to}
        if to == TaskStatus.COMPLETED:
            body["closure"] = {"reached": "unreached", "attempts": 2}
        rr = client.post(f"/api/doctor/tasks/{t_id}/transition", json=body)
        steps.append({"to": to, "http": rr.status_code})
    with session_scope() as s:
        tt = s.get(Task, t_id)
        out["unverified_task_closure"] = {"steps": steps, "status": tt.status, "closure": tt.closure}
    # 5. 对照：未到访 vs 创建了空随访后退出，二者都没有提交随访信息。
    set_clock(datetime(2026, 10, 1, 1, 0, tzinfo=timezone.utc))
    with session_scope() as s:
        ids = {}
        for tag in ("control", "abandoned"):
            enc = svc.create_encounter(s, patient_code="AUDIT-" + tag, protocol_id=p.protocol_id)
            enc.status = EncounterStatus.DOCTOR_CONFIRMED
            enc.followup_plan = {"interval_days": 1, "set_at": iso(now()), "patient_message": "模拟随访"}
            s.add(enc)
            s.commit()
            ids[tag] = enc.id
        set_clock(datetime(2026, 10, 1, 2, 0, tzinfo=timezone.utc))
        child = svc.create_encounter(s, patient_code="AUDIT-abandoned", protocol_id=p.protocol_id,
                                     kind="follow_up", parent_encounter_id=ids["abandoned"])
        child_status = child.status
        set_clock(datetime(2026, 10, 6, 1, 0, tzinfo=timezone.utc))
        sweep_no_response(s)
        out["default_no_response_check"] = {
            "rule_enabled": p.course.no_response is not None,
            "empty_child_status": child_status,
            "control_reminders": len(s.exec(select(Task).where(Task.encounter_id == ids["control"], Task.kind == "no_response")).all()),
            "abandoned_reminders": len(s.exec(select(Task).where(Task.encounter_id == ids["abandoned"], Task.kind == "no_response")).all()),
        }
    # 6. 工作日上午创建当天任务，比较文案里的两小时与计算出的截止时间。
    at = datetime(2026, 9, 28, 1, 0, tzinfo=timezone.utc)  # 周一，北京时间 09:00
    role, due, label = _due(p, "same_day", at)
    out["same_day_deadline"] = {"created_local": "2026-09-28 09:00 +08:00", "due": iso(due),
        "hours_until_due": (due-at).total_seconds()/3600 if due else None, "label": label,
        "protocol_service_hours": p.scope.service_hours,
        "routing": p.course.task_routing["same_day"].model_dump() if "same_day" in p.course.task_routing else None}
    # 条件性检查：仅在本进程临时装入审计目录的候选配置，绝不覆盖项目默认协议。
    candidate_path = Path(__file__).with_name("candidate_lbp_adult_v0.2.yaml")
    if candidate_path.exists():
        import yaml
        candidate = Protocol.model_validate(yaml.safe_load(candidate_path.read_text()))
        previous_course = p.course
        p.course = candidate.course
        with session_scope() as s:
            sweep_no_response(s)
            configured = {tag: len(s.exec(select(Task).where(Task.encounter_id == eid, Task.kind == "no_response")).all())
                          for tag, eid in ids.items()}
        role, due, label = _due(p, "same_day", at)
        out["candidate_configuration_ONLY_not_current_default"] = {
            "reminder_counts": configured, "empty_child_status": child_status,
            "same_day_due_hours": (due-at).total_seconds()/3600 if due else None,
            "same_day_label": label,
            "routing_due_minutes": p.course.task_routing["same_day"].due_minutes_in_hours,
            "note": "仅临时装载候选 course 配置的条件性复现；当前默认配置仍未启用这些规则。"}
        p.course = previous_course
    # 7. 普通模拟路径真实交互量；grid 每一行算一次判断，不把一屏当一题。
    set_clock(None)
    with session_scope() as s:
        enc = svc.create_encounter(s, patient_code="AUDIT-burden", protocol_id=p.protocol_id)
        svc.add_body_map(s, enc, [{"region_id": "lower_back_right", "kind": "primary"}])
        svc.add_text(s, enc, "右腰疼一周，坐久了更疼。")
        trace = []
        for _ in range(60):
            q = svc.get_next_question(s, enc)
            if q is None:
                break
            decisions = len(q["items"]) if q["kind"] in ("red_flag_grid", "verification") else 1
            trace.append({"kind": q["kind"], "id": q["question_id"], "decisions": decisions})
            if q["kind"] == "red_flag_grid":
                svc.answer_question(s, enc, q["question_id"], value={i["question_id"]: "no" for i in q["items"]})
            elif q["kind"] == "verification":
                svc.answer_question(s, enc, q["question_id"], value={i["fact_key"]: "confirm" for i in q["items"]})
            else:
                svc.answer_question(s, enc, q["question_id"], unknown=True)
        out["question_burden_one_synthetic_path"] = {"counter": enc.question_count, "screens": len(trace),
            "item_decisions": sum(x["decisions"] for x in trace), "trace": trace,
            "note": "不含适用范围、身体图、自由描述、最终确认；不是患者平均值，也不是计时试验。"}

files = ["backend/app/api/patient.py", "backend/app/api/doctor.py", "backend/app/course/tasks.py",
         "backend/app/services/encounter.py", "backend/app/questioning/engine.py", "backend/app/llm/provider.py",
         "protocols/lbp_adult_v0.2.yaml", "eval/runner.py"]
out["sha256"] = {f: hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
target = Path(__file__).with_name("reproduction_results.json")
target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=2))
