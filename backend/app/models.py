"""数据模型。

设计原则（来自立项书）：
1. 原始记录（Entry）不可变，是所有事实的证据来源。
2. 事实（Fact）区分六种状态，绝不把"没问"压成"没有"。
3. 任何修改都产生新版本，旧版本保留（Fact.superseded_by / Summary.version）。
4. 任务与通知的状态由人推进，系统只能创建，不能宣布"已处理"。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from .util import new_id, now


# ---- 常量 -------------------------------------------------------------

class EncounterKind:
    PRE_VISIT = "pre_visit"      # 就诊前采集
    FOLLOW_UP = "follow_up"      # 诊后随访


class EncounterStatus:
    DRAFT = "draft"                                   # 患者填写身体图/描述
    QUESTIONING = "questioning"                       # 系统按协议补问
    AWAITING_PATIENT_CONFIRMATION = "awaiting_patient_confirmation"
    READY_FOR_DOCTOR = "ready_for_doctor"             # 患者已确认事实
    UNDER_REVIEW = "under_review"                     # 医生已打开
    DOCTOR_CONFIRMED = "doctor_confirmed"             # 医生已核对确认
    CLOSED = "closed"

    ORDER = [DRAFT, QUESTIONING, AWAITING_PATIENT_CONFIRMATION, READY_FOR_DOCTOR,
             UNDER_REVIEW, DOCTOR_CONFIRMED, CLOSED]


class FactStatus:
    PRESENT = "present"                    # 患者报告存在 / 给出了值
    DENIED = "denied"                      # 患者明确否认
    NOT_ASKED = "not_asked"                # 尚未询问
    ASKED_UNANSWERED = "asked_unanswered"  # 询问后未回答 / 跳过 / 不清楚
    UNCERTAIN = "uncertain"                # 模糊表达（"好像有一点"）
    CONFLICTING = "conflicting"            # 前后矛盾，待澄清

    RESOLVED = {PRESENT, DENIED}
    UNKNOWN = {NOT_ASKED, ASKED_UNANSWERED}
    ALL = {PRESENT, DENIED, NOT_ASKED, ASKED_UNANSWERED, UNCERTAIN, CONFLICTING}


class EntryKind:
    BODY_MAP = "body_map"
    FREE_TEXT = "free_text"
    ANSWER = "answer"
    CORRECTION = "correction"       # 患者在确认页修改
    DOCTOR_NOTE = "doctor_note"
    SYSTEM_NOTICE = "system_notice"  # 系统向患者展示的（协议批准的）提示


class FactSource:
    BODY_MAP = "body_map"
    EXTRACTION = "extraction"   # 从自由文本抽取
    ANSWER = "answer"           # 结构化问答
    CORRECTION = "correction"
    DOCTOR = "doctor"
    DERIVED = "derived"         # 由其他事实确定性推导（如由身体图推导左右侧）


class TaskStatus:
    UNVIEWED = "unviewed"
    VIEWED = "viewed"
    CONTACTED = "contacted"
    PENDING = "pending"        # 待进一步处理
    ESCALATED = "escalated"
    COMPLETED = "completed"

    TRANSITIONS = {
        UNVIEWED: {VIEWED},
        VIEWED: {CONTACTED, PENDING, ESCALATED, COMPLETED},
        CONTACTED: {PENDING, ESCALATED, COMPLETED},
        PENDING: {CONTACTED, ESCALATED, COMPLETED},
        ESCALATED: {CONTACTED, PENDING, COMPLETED},
        COMPLETED: set(),
    }


class NotificationStatus:
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    SEEN = "seen"
    ACKNOWLEDGED = "acknowledged"  # 患者点击阅读确认；不能证明理解或执行

    TRANSITIONS = {
        QUEUED: {SENT, FAILED},
        FAILED: {QUEUED},
        SENT: {SEEN},
        SEEN: {ACKNOWLEDGED},
        ACKNOWLEDGED: set(),
    }


# ---- 表 ---------------------------------------------------------------

class Patient(SQLModel, table=True):
    """只存假名编号，不存姓名/手机号。真实身份映射由机构在自己系统保存。"""
    __table_args__ = (UniqueConstraint("clinic_id", "display_code", name="uq_patient_clinic_code"),)
    id: str = Field(default_factory=lambda: new_id("pat"), primary_key=True)
    display_code: str = Field(index=True)          # 例：P-0007
    clinic_id: str = Field(default="clinic_demo", index=True)
    created_at: datetime = Field(default_factory=now)


class Encounter(SQLModel, table=True):
    id: str = Field(default_factory=lambda: new_id("enc"), primary_key=True)
    patient_id: str = Field(index=True)
    clinic_id: str = Field(default="clinic_demo", index=True)
    protocol_id: str
    protocol_version: str
    protocol_sha256: Optional[str] = None
    kind: str = Field(default=EncounterKind.PRE_VISIT)
    parent_encounter_id: Optional[str] = Field(default=None, index=True)
    parent_plan_version_id: Optional[str] = None
    status: str = Field(default=EncounterStatus.DRAFT, index=True)
    question_count: int = 0
    patient_confirmed_at: Optional[datetime] = None
    doctor_confirmed_at: Optional[datetime] = None
    doctor_confirmed_by: Optional[str] = None
    followup_plan: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    # 谁在填：self 本人 | family 家属代述（本人在场确认）| staff 前台代录
    respondent: str = Field(default="self")
    respondent_relation: Optional[str] = None
    proxy_consent: bool = False
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Entry(SQLModel, table=True):
    """不可变原始记录：身体图标记、患者原话、问答、医生备注。"""
    id: str = Field(default_factory=lambda: new_id("ent"), primary_key=True)
    encounter_id: str = Field(index=True)
    seq: int
    kind: str
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now)


class Fact(SQLModel, table=True):
    id: str = Field(default_factory=lambda: new_id("fct"), primary_key=True)
    encounter_id: str = Field(index=True)
    key: str = Field(index=True)
    status: str = Field(default=FactStatus.NOT_ASKED)
    value: Any = Field(default=None, sa_column=Column(JSON))
    # [{"entry_id": ..., "quote": ..., "field": ...}]
    evidence: list = Field(default_factory=list, sa_column=Column(JSON))
    source: str = Field(default=FactSource.DERIVED)
    version: int = 1
    superseded_by: Optional[str] = Field(default=None, index=True)
    patient_confirmed: bool = False
    created_at: datetime = Field(default_factory=now)


class AskedQuestion(SQLModel, table=True):
    id: str = Field(default_factory=lambda: new_id("ask"), primary_key=True)
    encounter_id: str = Field(index=True)
    question_id: str
    fact_keys: list = Field(default_factory=list, sa_column=Column(JSON))
    text: str
    kind: str = "protocol"   # protocol | clarification | followup
    options: list = Field(default_factory=list, sa_column=Column(JSON))
    payload: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    asked_at: datetime = Field(default_factory=now)
    answer_entry_id: Optional[str] = None
    answer_status: str = "pending"  # pending | answered | skipped | unknown


class Summary(SQLModel, table=True):
    id: str = Field(default_factory=lambda: new_id("sum"), primary_key=True)
    encounter_id: str = Field(index=True)
    version: int
    author: str          # system | doctor:<id>
    content: dict = Field(default_factory=dict, sa_column=Column(JSON))
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=now)


class Alert(SQLModel, table=True):
    provisional: bool = False
    """协议红旗规则触发记录。"""
    id: str = Field(default_factory=lambda: new_id("alr"), primary_key=True)
    encounter_id: str = Field(index=True)
    rule_id: str
    severity: str        # urgent | same_day | routine
    label: str
    patient_message: str
    evidence: list = Field(default_factory=list, sa_column=Column(JSON))
    notice_entry_id: Optional[str] = None   # 已向患者展示的提示记录
    # 患者在"一键核对"中表示触发这条红旗的整理不对：红旗与任务都保留给医生复核，但不再终止问询
    patient_disputed: bool = False
    dispute_entry_id: Optional[str] = None
    # 触发时的去向与是否在门诊服务时间内（患者端紧急页据此选主按钮）
    route: Optional[str] = None
    in_service_hours: Optional[bool] = None
    created_at: datetime = Field(default_factory=now)


class Task(SQLModel, table=True):
    dedupe_key: Optional[str] = Field(default=None, index=True, unique=True)
    id: str = Field(default_factory=lambda: new_id("tsk"), primary_key=True)
    encounter_id: str = Field(index=True)
    alert_id: Optional[str] = None
    kind: str            # red_flag_review | conflict_review | followup_check | doctor_review | after_hours_callback | recovery_review | no_response
    title: str
    status: str = Field(default=TaskStatus.UNVIEWED, index=True)
    assignee: Optional[str] = None
    # 疗程安全网：默认派给哪个角色、几点前处理；红旗任务结案时的处置记录
    assignee_role: Optional[str] = None
    severity: Optional[str] = None
    due_at: Optional[datetime] = None
    detail: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    closure: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    history: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Notification(SQLModel, table=True):
    id: str = Field(default_factory=lambda: new_id("ntf"), primary_key=True)
    encounter_id: str = Field(index=True)
    channel: str = "in_app"
    content: str
    plan_version_id: Optional[str] = Field(default=None, index=True)
    status: str = Field(default=NotificationStatus.QUEUED)
    history: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now)


class VerificationReport(SQLModel, table=True):
    id: str = Field(default_factory=lambda: new_id("ver"), primary_key=True)
    encounter_id: str = Field(index=True)
    passed: bool
    checks: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now)


class AuditLog(SQLModel, table=True):
    id: str = Field(default_factory=lambda: new_id("aud"), primary_key=True)
    actor: str
    action: str
    target_type: str
    target_id: str
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now)


class UsageEvent(SQLModel, table=True):
    """可用性测试埋点：只记录交互步骤与时间，不记录输入内容。"""
    id: str = Field(default_factory=lambda: new_id("evt"), primary_key=True)
    encounter_id: str = Field(index=True)
    type: str = Field(index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    client_ts: Optional[str] = None
    created_at: datetime = Field(default_factory=now)


class StaffAccount(SQLModel, table=True):
    id: str = Field(default_factory=lambda: new_id("usr"), primary_key=True)
    username: str = Field(index=True, unique=True)
    display_name: str
    clinic_id: str = Field(index=True)
    role: str
    password_hash: str
    disabled: bool = False
    created_at: datetime = Field(default_factory=now)


class ProtocolSnapshot(SQLModel, table=True):
    id: str = Field(primary_key=True)
    protocol_id: str = Field(index=True)
    version: str
    content: dict = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now)


class AccessSession(SQLModel, table=True):
    # 原始 bearer/cookie 只发给客户端；数据库只保存不可逆摘要。
    id: str = Field(primary_key=True)
    kind: str = Field(index=True)  # staff / patient
    subject_id: str = Field(index=True)
    clinic_id: str = Field(index=True)
    expires_at: datetime
    revoked: bool = False
    created_at: datetime = Field(default_factory=now)


class PatientInvite(SQLModel, table=True):
    id: str = Field(primary_key=True)  # token 的 SHA256
    patient_id: str = Field(index=True)
    clinic_id: str
    protocol_id: str
    parent_encounter_id: Optional[str] = None
    expires_at: datetime
    consumed_at: Optional[datetime] = None
    created_by: str
    created_at: datetime = Field(default_factory=now)


class LoginThrottle(SQLModel, table=True):
    id: str = Field(primary_key=True)
    failures: int = 0
    window_started: datetime = Field(default_factory=now)


class TaskDelivery(SQLModel, table=True):
    id: str = Field(primary_key=True)
    task_id: str = Field(index=True)
    clinic_id: str = Field(index=True)
    event: str
    state: str = "unconfigured"
    attempts: int = 0
    last_error: Optional[str] = None
    next_attempt_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now)


class SymptomEvent(SQLModel, table=True):
    """一次原话中的事件；报告时间不冒充起病时间，后续核实保留完整历史。"""
    id: str = Field(default_factory=lambda: new_id("sev"), primary_key=True)
    encounter_id: str = Field(index=True)
    entry_id: str = Field(index=True)
    fact_keys: list = Field(default_factory=list, sa_column=Column(JSON))
    candidates: dict = Field(default_factory=dict, sa_column=Column(JSON))
    quote: str
    subject: str = "unclear"  # patient / other / unclear
    assertion_type: str = "asserted"  # asserted / hypothetical，条件句不投影为当前症状
    time_relation: str = "unknown"  # new / ongoing / worsening / improving / past / unknown
    time_text: str = ""
    verification_state: str = "extracted"  # extracted / patient_confirmed / doctor_confirmed / review_required
    confirmed_entry_id: Optional[str] = None
    inference_source: str = ""
    inference_issues: list = Field(default_factory=list, sa_column=Column(JSON))
    history: list = Field(default_factory=list, sa_column=Column(JSON))
    reported_at: datetime = Field(default_factory=now)


class PlanVersion(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("encounter_id", "version", name="uq_plan_encounter_version"),)
    id: str = Field(default_factory=lambda: new_id("pln"), primary_key=True)
    encounter_id: str = Field(index=True)
    version: int
    content_sha256: str
    content: dict = Field(sa_column=Column(JSON))
    created_by: str
    created_at: datetime = Field(default_factory=now)


class TeachbackResponse(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("plan_version_id", "submission_key", name="uq_teachback_submission"),)
    id: str = Field(default_factory=lambda: new_id("tbr"), primary_key=True)
    encounter_id: str = Field(index=True)
    plan_version_id: str = Field(index=True)
    submission_key: str = Field(default_factory=lambda: new_id("sub"), index=True)
    response_text: str
    execution_status: str
    barrier_text: str = ""
    analysis: dict = Field(default_factory=dict, sa_column=Column(JSON))
    reviewed: bool = False
    review: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now)


class FunctionalGoal(SQLModel, table=True):
    id: str = Field(default_factory=lambda: new_id("fng"), primary_key=True)
    patient_id: str = Field(index=True)
    clinic_id: str = Field(index=True)
    root_encounter_id: str = Field(index=True)
    description: str
    unit: str
    conditions: str
    confirmed_at: datetime = Field(default_factory=now)


class FunctionalObservation(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("goal_id", "submission_key", name="uq_goal_submission"),)
    id: str = Field(default_factory=lambda: new_id("fno"), primary_key=True)
    goal_id: str = Field(index=True)
    encounter_id: str = Field(index=True)
    submission_key: str
    state: str
    value: Optional[float] = None
    observed_date: Optional[str] = None
    condition_match: str
    conditions: str
    note: str = ""
    created_at: datetime = Field(default_factory=now)
