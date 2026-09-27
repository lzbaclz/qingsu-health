"""临床协议（由医生填写、工程校验）的结构定义。

协议是医生与工程团队之间的正式接口：
- 医生决定：适用范围、问什么、什么时候问、什么算需要人工处理、给患者看什么话。
- 工程保证：每一条都能被机器执行、被验证、被版本管理。
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from . import expr as expr_mod

FactType = Literal["bool", "enum", "multi_enum", "number", "scale", "text", "body_regions", "duration"]
QuestionType = Literal["yes_no", "single_choice", "multi_choice", "scale", "number", "text", "body_regions"]
Severity = Literal["urgent", "same_day", "routine"]


class Option(BaseModel):
    value: str
    label: str
    synonyms: list[str] = Field(default_factory=list, description="口语同义词，供抽取使用")


class Lexicon(BaseModel):
    """供离线（mock）抽取器与证据校验使用的词表。真实部署可由 LLM 抽取，但词表仍用于兜底与测试。"""
    present_terms: list[str] = Field(default_factory=list)
    denied_terms: list[str] = Field(default_factory=list)
    context_terms: list[str] = Field(default_factory=list, description="非空时，只在包含这些词的句子里抽取该事实（如：起病时间只在提到疼痛的句子里抽）")


class FactDef(BaseModel):
    key: str
    label: str
    record_label: Optional[str] = Field(default=None, description="写进病历初稿时用的短标签，如'病程''诱因'；不填则用 label")
    type: FactType
    category: str = "general"
    options: list[Option] = Field(default_factory=list)
    required: bool = Field(default=False, description="关键事实：摘要必须明确其状态（含‘未知’）")
    critical: bool = Field(default=False, description="评测关键事实：遗漏/编造算严重错误")
    lexicon: Optional[Lexicon] = None
    min: Optional[float] = None
    max: Optional[float] = None
    patient_prompt: Optional[str] = Field(default=None, description="默认问法（可被 questions 覆盖）")
    notes: Optional[str] = None
    clinical_review_required: bool = True

    @field_validator("key")
    @classmethod
    def _key_ok(cls, v: str) -> str:
        if not v.replace("_", "").isalnum() or v.startswith("_"):
            raise ValueError(f"fact key 只能包含字母数字下划线: {v}")
        return v

    @model_validator(mode="after")
    def _options_ok(self) -> "FactDef":
        if self.type in ("enum", "multi_enum") and not self.options:
            raise ValueError(f"{self.key}: enum/multi_enum 必须给 options")
        vals = [o.value for o in self.options]
        if len(vals) != len(set(vals)):
            raise ValueError(f"{self.key}: options.value 重复")
        return self


class QuestionDef(BaseModel):
    extract_answer: bool = False
    id: str
    fact_key: str
    text: str
    type: QuestionType
    options: Optional[list[Option]] = None
    when: Optional[str] = Field(default=None, description="触发条件表达式，空=总是")
    priority: int = 100
    allow_unknown: bool = True
    allow_skip: bool = True
    purpose: Optional[str] = Field(default=None, description="医生填写：这个问题为了明确什么")
    stage: Literal["pre_visit", "follow_up", "both"] = "pre_visit"
    tier: Literal[1, 2, 3] = Field(default=2, description="1 = 必问（范围核查/红旗），不计入 max_questions；2/3 受上限约束")
    anchors: Optional[dict[int, str]] = Field(default=None, description="0–10 分题的文字锚点，给患者看")

    @field_validator("when")
    @classmethod
    def _when_ok(cls, v: Optional[str]) -> Optional[str]:
        if v:
            expr_mod.parse(v)
        return v

    @model_validator(mode="after")
    def _extraction_input(self) -> "QuestionDef":
        if self.extract_answer and self.type != "text":
            raise ValueError("只有明确用于新症状采集的文本题可开启 extract_answer")
        return self


class ClarificationOption(BaseModel):
    label: str
    resolve: Literal["keep_first", "keep_second", "both", "changed_to_second", "unknown"] | dict


class ClarificationTemplate(BaseModel):
    fact_key: str
    text: str = Field(description="可用 {label} {first} {second} {first_source} {second_source} 占位")
    options: list[ClarificationOption]


class RedFlagRule(BaseModel):
    id: str
    label: str
    when: str
    severity: Severity
    patient_message: str = Field(description="经临床审核、可直接展示给患者的文字")
    action: Literal["immediate_notice_and_task", "task_only"] = "immediate_notice_and_task"
    on_trigger: Literal["continue", "stop_questioning"] = "continue"
    task_kind: str = "red_flag_review"
    clinical_review_required: bool = True
    escalate_on_conflict: bool = False
    conflict_patient_message: Optional[str] = None

    @field_validator("when")
    @classmethod
    def _when_ok(cls, v: str) -> str:
        expr_mod.parse(v)
        return v

    @property
    def fact_keys(self) -> list[str]:
        return expr_mod.referenced_facts(self.when)


class ScopeGuard(BaseModel):
    """对系统生成的、面向患者的文字做越界检查。"""
    forbidden_patterns: list[str] = Field(default_factory=list, description="正则；命中即视为越界（诊断断言、药名剂量等）")
    allowed_content_ids: list[str] = Field(default_factory=list, description="协议中经审核、可豁免的内容 id")


class EducationItem(BaseModel):
    id: str
    when: Optional[str] = None
    text: str
    source: Optional[str] = None
    clinical_review_required: bool = True

    @field_validator("when")
    @classmethod
    def _when_ok(cls, v: Optional[str]) -> Optional[str]:
        if v:
            expr_mod.parse(v)
        return v


class VerificationSpec(BaseModel):
    """一键核对：只从自由文本抽取、尚未经患者直接回答的关键事实，在继续问询前请患者逐条确认。
    目的：堵住"错抽后引擎不再问"的洞——漏抽会被问卷兜住，错抽只能靠核对兜住。"""
    enabled: bool = True
    include_critical: bool = True
    include_categories: list[str] = Field(default_factory=lambda: ["red_flag"])
    max_items: int = 8


class ScreeningSpec(BaseModel):
    pre_visit_grid_title: Optional[str] = None
    """红旗一屏：本阶段 tier 1、是否型的红旗筛查题合成一屏，逐行必答，不计题数。文字由临床负责人定。"""
    grid_enabled: bool = True
    grid_title: str = "下面几种情况，这次腰背痛以来有没有出现？每一行都请选一下。"
    grid_followup_title: str = "再确认几件事："
    grid_preface: Optional[str] = Field(default=None, description="红旗一屏上方的一句话（例如私密题提示）")
    pre_visit_grid: list[str] = Field(default_factory=list, description="首诊红旗一屏的题 id；为空时取 tier 1 是否型红旗题")
    checkin_grid: list[str] = Field(default_factory=list, description="签到红旗一屏的题 id；为空时取 tier 1 是否型红旗题")


# ---------------------------------------------------------------- 疗程安全网（第 1 轮团队评审）
class ServiceWindow(BaseModel):
    days: list[int] = Field(description="1=周一 … 7=周日")
    start: str = Field(description="HH:MM，门诊本地时间")
    end: str


class UrgentCopy(BaseModel):
    headline: str
    body: str
    primary: str
    secondary: Optional[str] = None


class OutcomeDef(BaseModel):
    key: str
    label: str
    direction: Literal["lower_better", "higher_better"] = "lower_better"
    mcid_abs: Optional[float] = None
    mcid_pct: Optional[float] = None
    rule: Literal["both", "either"] = Field(default="both", description="有意义改善：both = 绝对值与百分比都要达到；either = 任一达到")
    baseline_keys: list[str] = Field(default_factory=list, description="首诊没问到本结局时可替代的基线事实（显示时注明）")
    categories: Optional[dict[str, str]] = Field(default=None, description="单选型结局：选项值 → improved / same / worse")
    source: Optional[str] = None


class RecoveryRule(BaseModel):
    """只生成任务、不做预测；阈值由医生设定。"""
    id: str
    label: str
    outcome: Optional[str] = None
    worse_abs: Optional[float] = None
    min_day: Optional[int] = None
    max_improvement_pct: Optional[float] = None
    region_count_increase_gte: Optional[int] = None
    severity: Literal["urgent", "same_day", "routine"] = "routine"
    slip_line: Optional[str] = None
    assignee_role: Optional[str] = None
    task_title: Optional[str] = None


class CallbackTaskSpec(BaseModel):
    title: str = "次日开门第一件：回访是否已就诊"
    due_minutes_after_open: int = 30
    assignee_role: str = "nurse"


class NoResponseSpec(BaseModel):
    hours_after_due: int = 48
    title: str = "电话回访（到期未签到）"
    assignee_role: str = "frontdesk"


class TaskRoute(BaseModel):
    model_config = {"extra": "allow"}
    assignee_role: str
    due_minutes_in_hours: Optional[int] = None
    after_hours: Optional[str] = None
    due: Optional[str] = None
    due_days: Optional[int] = None


class SafetyCard(BaseModel):
    collapsed: str = "出现这些情况，立刻就医 ›"
    items: list[str] = Field(default_factory=list)
    save_hint: Optional[str] = None


class RespondentOption(BaseModel):
    value: Literal["self", "family", "staff"]
    label: str


class RespondentSpec(BaseModel):
    options: list[RespondentOption] = Field(default_factory=list)
    proxy_note: Optional[str] = None


class CourseSpec(BaseModel):
    """疗程安全网：服务时段分流、红旗去向、恢复轨迹、提醒规则、任务派发、结案。内容由临床负责人决定。"""
    model_config = {"extra": "allow"}
    functional_goals_enabled: bool = False
    simulated: bool = Field(default=True, description="内容来自模拟临床负责人（AI 医学视角），待真实医生复核")
    time_budget: dict[str, str] = Field(default_factory=dict)
    service_windows: list[ServiceWindow] = Field(default_factory=list)
    red_flag_routes: dict[str, Literal["ed", "clinic"]] = Field(default_factory=dict)
    urgent_page: dict[str, UrgentCopy] = Field(default_factory=dict)
    reassurance: Optional[str] = None
    callback_task: CallbackTaskSpec = Field(default_factory=CallbackTaskSpec)
    outcomes: list[OutcomeDef] = Field(default_factory=list)
    reference_curves: Optional[dict[str, Any]] = None
    recovery_rules: list[RecoveryRule] = Field(default_factory=list)
    schedule_days: list[int] = Field(default_factory=list)
    no_response: Optional[NoResponseSpec] = None
    task_routing: dict[str, TaskRoute] = Field(default_factory=dict)
    closure: Optional[dict[str, Any]] = None
    safety_card: Optional[SafetyCard] = None
    respondent: Optional[RespondentSpec] = None


class PlainTerm(BaseModel):
    """术语对照：医生说明里出现这个词时，在后面加一句大白话。只解释医生已经写下的词，不增加任何医学内容。"""
    term: str
    plain: str
    clinical_review_required: bool = True


class FollowupSpec(BaseModel):
    teachback_enabled: bool = False
    teachback_point_limit: int = Field(default=3, ge=1, le=6)
    teachback_clinical_review_required: bool = True
    default_interval_days: int = 7
    change_facts: list[str] = Field(default_factory=list, description="随访时重点对比的事实")
    questions: list[QuestionDef] = Field(default_factory=list)
    plain_language: list[PlainTerm] = Field(default_factory=list, description="给患者说明的术语对照表（医生审定）")


class SummarySpec(BaseModel):
    key_facts_order: list[str] = Field(default_factory=list)
    narrative_enabled: bool = True
    chief_complaint_label: str = Field(default="不适", description="摘要标题里的主诉名称，如\"腰背部不适\"\"膝部不适\"")


class ErrorType(BaseModel):
    code: str
    label: str
    severity: Literal["critical", "major", "minor"]


class EvaluationSpec(BaseModel):
    critical_facts: list[str] = Field(default_factory=list)
    error_taxonomy: list[ErrorType] = Field(default_factory=list)


class BodyMapSpec(BaseModel):
    regions_fact_key: str
    side_fact_key: str
    radiation_fact_key: Optional[str] = None
    regions_of_interest: list[str] = Field(default_factory=list, description="本协议重点关注的区域 id")
    initial_view: Literal["front", "back"] = Field(default="back", description="患者端身体图默认显示正面还是背面")


class EligibilityItem(BaseModel):
    """开始页请患者逐条确认的适用范围（例如年龄、孕期）。任何一条选"不对"都不进入采集，显示 if_not。"""
    id: str
    text: str = Field(description="请患者确认的陈述，如'我已年满 18 岁'")
    no_label: str = Field(default="不对", description="否定选项的文字")
    if_not: str = Field(description="选否定选项时显示的话")


class ScopeSpec(BaseModel):
    inclusion: list[str]
    exclusion: list[str]
    setting: str
    service_hours: str
    service_notice: str = Field(description="进入产品前向患者展示的用途/边界说明")
    emergency_notice: str = Field(description="全程可见的紧急情况提示")
    out_of_scope_message: str
    contact_label: str = Field(default="门诊电话", description="紧急终止页主按钮的名称")
    contact_phone: Optional[str] = Field(default=None, description="门诊联系电话；为空时紧急终止页只显示急救电话")
    emergency_phone: str = Field(default="120", description="急救电话")
    eligibility: list[EligibilityItem] = Field(default_factory=list, description="开始页逐条确认的适用范围；选'不对'则不进入采集")


class EventReviewRule(BaseModel):
    id: str
    label: str
    fact_keys: list[str]
    changes: list[Literal["new", "ongoing", "historical", "worsening", "improving", "past", "unknown"]]
    severity: Severity = "routine"
    assignee_role: str = "doctor"
    clinical_review_required: bool = True


class EventVerificationSpec(BaseModel):
    # 旧快照默认关闭，不能因代码更新改变已保存疗程。
    enabled: bool = False
    strategy: Literal["all", "action_sensitive"] = "all"
    fact_keys: list[str] = Field(default_factory=list)
    lifetime_fact_keys: list[str] = Field(default_factory=list)
    new_change_fact_keys: list[str] = Field(default_factory=list)
    review_rules: list[EventReviewRule] = Field(default_factory=list)
    question: str = "关于你说的「{quote}」，哪一项更准确？"
    clinical_review_required: bool = True
    skip_redundant_negative_verification: bool = False


class Protocol(BaseModel):
    content_sha256: str = Field(default="", exclude=True)
    protocol_id: str
    version: str
    status: Literal["draft", "clinically_reviewed", "approved"] = "draft"
    title: str
    specialty: str
    language: str = "zh-CN"
    owners: dict[str, str] = Field(default_factory=dict)
    review: dict[str, Any] = Field(default_factory=dict)
    scope: ScopeSpec
    max_questions: int = 12
    body_map: BodyMapSpec
    facts: list[FactDef]
    questions: list[QuestionDef]
    clarifications: list[ClarificationTemplate] = Field(default_factory=list)
    red_flags: list[RedFlagRule] = Field(default_factory=list)
    scope_guard: ScopeGuard = Field(default_factory=ScopeGuard)
    education: list[EducationItem] = Field(default_factory=list)
    followup: FollowupSpec = Field(default_factory=FollowupSpec)
    verification: VerificationSpec = Field(default_factory=VerificationSpec)
    screening: ScreeningSpec = Field(default_factory=ScreeningSpec)
    course: CourseSpec = Field(default_factory=CourseSpec)
    summary: SummarySpec = Field(default_factory=SummarySpec)
    evaluation: EvaluationSpec = Field(default_factory=EvaluationSpec)
    event_verification: EventVerificationSpec = Field(default_factory=EventVerificationSpec)

    # ---- 派生索引 ----
    def fact(self, key: str) -> FactDef:
        return self.fact_index[key]

    @property
    def fact_index(self) -> dict[str, FactDef]:
        return {f.key: f for f in self.facts}

    @property
    def red_flag_screen_keys(self) -> set[str]:
        """红旗筛查类的是否型事实：属于 red_flag 类别，或被紧急 / 当天级红旗规则引用。
        这些事实上点"不清楚"记为"不确定"（而不是"未回答"），红旗"没有"只认患者的直接回答。"""
        refs: set[str] = set()
        for r in self.red_flags:
            if r.severity in ("urgent", "same_day"):
                refs.update(r.fact_keys)
        return {f.key for f in self.facts if f.type == "bool" and (f.category == "red_flag" or f.key in refs)}

    @property
    def question_index(self) -> dict[str, QuestionDef]:
        idx = {q.id: q for q in self.questions}
        idx.update({q.id: q for q in self.followup.questions})
        return idx

    @model_validator(mode="after")
    def _cross_check(self) -> "Protocol":
        keys = {f.key for f in self.facts}
        if len(keys) != len(self.facts):
            raise ValueError("facts.key 重复")
        qids = [q.id for q in self.questions] + [q.id for q in self.followup.questions]
        if len(qids) != len(set(qids)):
            raise ValueError("questions.id 重复")
        for q in self.questions + self.followup.questions:
            if q.fact_key not in keys:
                raise ValueError(f"question {q.id} 引用了不存在的 fact_key: {q.fact_key}")
        for c in self.clarifications:
            if c.fact_key not in keys:
                raise ValueError(f"clarification 引用了不存在的 fact_key: {c.fact_key}")
        for k in (self.body_map.regions_fact_key, self.body_map.side_fact_key, self.body_map.radiation_fact_key):
            if k and k not in keys:
                raise ValueError(f"body_map 引用了不存在的 fact_key: {k}")
        for k in self.evaluation.critical_facts + self.followup.change_facts + self.summary.key_facts_order:
            if k not in keys:
                raise ValueError(f"引用了不存在的 fact_key: {k}")
        event_keys = self.event_verification.fact_keys + self.event_verification.lifetime_fact_keys + self.event_verification.new_change_fact_keys
        for rule in self.event_verification.review_rules:
            event_keys += rule.fact_keys
        if set(event_keys) - keys:
            raise ValueError(f"事件核实引用未知事实：{sorted(set(event_keys) - keys)}")
        return self

    def review_gaps(self) -> list[str]:
        """列出仍需临床审核的条目——用于医生任务清单与 BP 诚实披露。"""
        gaps = []
        if self.status != "approved":
            gaps.append(f"协议整体状态为 {self.status}，尚未 approved")
        gaps += [f"fact:{f.key}" for f in self.facts if f.clinical_review_required]
        gaps += [f"red_flag:{r.id}" for r in self.red_flags if r.clinical_review_required]
        gaps += [f"education:{e.id}" for e in self.education if e.clinical_review_required]
        gaps += [f"plain_language:{g.term}" for g in self.followup.plain_language if g.clinical_review_required]
        if self.followup.teachback_enabled and self.followup.teachback_clinical_review_required:
            gaps.append("followup:teachback_workflow")
        if self.event_verification.enabled:
            if self.event_verification.clinical_review_required:
                gaps.append("event_verification:question_and_interpretation")
            gaps += [f"event_rule:{r.id}" for r in self.event_verification.review_rules if r.clinical_review_required]
        return gaps
