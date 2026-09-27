from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class CreateEncounterIn(BaseModel):
    invite_token: Optional[str] = Field(default=None, max_length=200)
    patient_code: Optional[str] = None
    protocol_id: Optional[str] = None
    kind: str = Field(default="pre_visit", pattern="^(pre_visit|follow_up)$")
    parent_encounter_id: Optional[str] = None
    eligibility: Optional[dict[str, bool]] = None  # 开始页适用范围确认（协议 scope.eligibility 的 id → 是否符合）
    respondent: str = "self"                 # self 本人 | family 家属代述 | staff 前台代录
    respondent_relation: Optional[str] = None
    proxy_consent: bool = False              # 代填时患者本人在场并同意


class BodyMapMark(BaseModel):
    region_id: str
    kind: str = Field(default="primary", pattern="^(primary|radiation)$")
    intensity: Optional[int] = None


class BodyMapIn(BaseModel):
    marks: list[BodyMapMark]


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=6000)


class EventReviewIn(BaseModel):
    subject: str = Field(pattern="^(patient|other|unclear)$")
    time_relation: str = Field(pattern="^(new|ongoing|historical|worsening|improving|past|unknown)$")
    note: str = Field(min_length=1, max_length=2000)


class EventCorrectionIn(BaseModel):
    choice: str = Field(pattern="^(new|ongoing|worsening|improving|past|other|incorrect|unsure)$")


class AnswerIn(BaseModel):
    question_id: str
    value: Any = None
    unknown: bool = False
    skipped: bool = False


class Correction(BaseModel):
    fact_key: str
    status: str = "present"
    value: Any = None


class ConfirmIn(BaseModel):
    corrections: list[Correction] = Field(default_factory=list)


class NotificationEventIn(BaseModel):
    event: str = Field(pattern="^(seen|acknowledged)$")


class SummaryEditIn(BaseModel):
    actor: str
    edits: dict[str, str]
    note: Optional[str] = None


class FactCorrectionIn(BaseModel):
    actor: str
    key: str
    status: str
    value: Any = None
    note: str


class DoctorConfirmIn(BaseModel):
    actor: str
    override_reason: Optional[str] = None


class FollowupPlanIn(BaseModel):
    understanding_points: list[str] = Field(default_factory=list, max_length=6)
    expected_plan_version_id: Optional[str] = None
    actor: str
    interval_days: Optional[int] = Field(default=None, ge=1, le=365)
    watch_facts: Optional[list[str]] = None
    patient_message: str
    drafted_with: Optional[str] = None  # 说明由 AI 按医生要点改写过时，记下用的模型（审计用）
    draft_id: Optional[str] = None      # 由"改写"起草时的草稿编号：发送前据此复查要点以外的新内容
    override_reason: Optional[str] = None  # 确需保留要点以外的内容时，医生写的理由（记入审计）


class TeachbackIn(BaseModel):
    response_text: str = Field(min_length=1, max_length=3000)
    execution_status: str = Field(pattern="^(not_started|planned|attempted|reported_done|unable|unclear)$")
    barrier_text: str = Field(default="", max_length=2000)
    submission_key: str = Field(min_length=10, max_length=100)


class TeachbackReviewIn(BaseModel):
    result: str = Field(pattern="^(aligned|needs_explanation|unclear)$")
    note: str = Field(min_length=1, max_length=2000)


class FollowupDraftIn(BaseModel):
    actor: str
    notes: str                          # 医生要点，可以简写
    interval_days: Optional[int] = None


class TaskTransitionIn(BaseModel):
    actor: str
    to: str
    note: Optional[str] = None
    closure: Optional[dict] = None  # 红旗任务结案的处置记录：reached / attempts / advice / reason / note


class ContactAttemptIn(BaseModel):
    result: str = Field(pattern="^(reached|unreached|in_person)$")
    note: str = Field(min_length=1, max_length=2000)


class ProtocolValidateIn(BaseModel):
    yaml_text: str = Field(max_length=200000)


class FunctionalGoalIn(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    unit: str = Field(pattern="^(minutes|metres|count)$")
    conditions: str = Field(min_length=1, max_length=500)
    confirmed: bool


class FunctionalObservationIn(BaseModel):
    submission_key: str = Field(min_length=10, max_length=100)
    state: str = Field(pattern="^(measured|not_attempted|unknown)$")
    value: Optional[float] = Field(default=None, ge=0, le=100000)
    observed_date: Optional[str] = Field(default=None, max_length=10)
    condition_match: str = Field(pattern="^(same|changed|unknown)$")
    conditions: str = Field(min_length=1, max_length=500)
    note: str = Field(default="", max_length=1000)


class UsageEventIn(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    client_ts: Optional[str] = None
