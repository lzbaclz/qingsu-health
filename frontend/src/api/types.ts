// 与后端 app/services/encounter.py、app/tasks/service.py、app/questioning/engine.py 对应的类型。
// 类型刻意保持宽松：后端 JSON 是权威，前端只做展示。

export type EncounterKind = 'pre_visit' | 'follow_up'
export type EncounterStatus =
  | 'draft'
  | 'questioning'
  | 'awaiting_patient_confirmation'
  | 'ready_for_doctor'
  | 'under_review'
  | 'doctor_confirmed'
  | 'closed'
export type FactStatus = 'present' | 'denied' | 'not_asked' | 'asked_unanswered' | 'uncertain' | 'conflicting'
export type Severity = 'urgent' | 'same_day' | 'routine'
export type TaskStatus = 'unviewed' | 'viewed' | 'contacted' | 'pending' | 'escalated' | 'completed'
export type NotificationStatus = 'queued' | 'sent' | 'failed' | 'seen' | 'acknowledged'
export type MarkKind = 'primary' | 'radiation'
export type BodyView = 'front' | 'back'

export interface Region {
  id: string
  label: string
  view: BodyView
  side: 'left' | 'right' | 'center'
  group: string
}

export interface Mark {
  region_id: string
  kind: MarkKind
  intensity?: number | null
}

export interface Option {
  value: string
  label: string
  resolve?: string
}

export interface Evidence {
  entry_id: string
  quote: string
  kind: string
}

export interface Fact {
  id: string
  key: string
  status: FactStatus
  value: unknown
  evidence: Evidence[]
  source: string
  version: number
  patient_confirmed: boolean
  label: string
  type: string
  category: string
  required: boolean
  critical: boolean
  value_label: string
  /** 值是患者原话且含药名/剂量/诊断性表述或疑似指令时的标记（不阻断，只提醒医生这是原话、不是系统建议） */
  flags?: FactFlag[]
}

export interface FactFlag {
  code: string
  label: string
}

/** 每段患者原话的抽取记录：用了哪个模型、写入/丢弃几条、协议外提到了什么 */
export interface ExtractionLog {
  entry_id: string
  at: string
  provider: string
  applied: string[]
  rejected: { key: string | null; reason: string }[]
  unmapped: { text: string; flags?: FactFlag[] }[]
}

export interface ConfirmFact extends Fact {
  options: Option[]
  /** 给患者看的取值（"没有 / 好像有，但不确定"），医生端仍用 value_label */
  patient_value_label?: string
}

export interface AlertEvidence {
  fact_key: string
  status: FactStatus
  value: unknown
  evidence: Evidence[]
}

export interface Alert {
  id: string
  rule_id: string
  severity: Severity
  label: string
  patient_message: string
  evidence: AlertEvidence[]
  notice_shown: boolean
  /** 患者在一键核对中表示触发这条红旗的整理不对（红旗与任务保留给医生复核，但不再终止问询） */
  patient_disputed?: boolean
  created_at: string
}

export interface HistoryItem {
  to: string
  by: string
  at: string
  note?: string | null
}

export interface Notification {
  plan_version_id?: string | null
  plan_version?: number | null
  understanding_points?: { id: string; text: string }[]
  teachback_enabled?: boolean
  is_current_plan?: boolean
  id: string
  encounter_id: string
  channel: string
  content: string
  status: NotificationStatus
  history: HistoryItem[]
  created_at: string
}

export interface EncounterBrief {
  id: string
  patient_code: string | null
  kind: EncounterKind
  status: EncounterStatus
  protocol_id: string
  parent_encounter_id: string | null
  created_at: string
  updated_at: string
  patient_confirmed_at: string | null
  doctor_confirmed_at: string | null
  alert_max_severity: Severity | null
  /** 紧急程度（患者核对时否认的红旗仍按原级别计，并提示电话核实）；列表按它排序 */
  triage?: Severity | null
  triage_rank?: number
  triage_label?: string
  /** 最高级别的红旗全部是"患者核对时否认"的：要尽快电话核实 */
  triage_disputed?: boolean
  open_tasks: number
  conflicts: number
  respondent?: Respondent
  respondent_label?: string
  /** 恢复提醒（医生设定的阈值命中）：例如"比首诊加重 ≥2 分 → 治疗前请医生复评" */
  recovery_flags?: { rule_id: string; label: string; slip_line: string | null; severity: Severity | null }[]
  overdue_tasks?: number
}

export interface Task {
  deliveries?: { state: string; attempts: number; event: string; delivered_at: string | null }[]
  id: string
  encounter_id: string
  alert_id: string | null
  kind: string
  title: string
  status: TaskStatus
  assignee: string | null
  history: HistoryItem[]
  allowed_transitions: TaskStatus[]
  created_at: string
  updated_at: string
  encounter?: EncounterBrief | null
  // 疗程安全网：派给哪个角色、几点前、是否超时；红旗任务结案必须填处置记录
  assignee_role?: string | null
  assignee_role_label?: string | null
  severity?: Severity | null
  due_at?: string | null
  due_local?: string | null
  overdue?: boolean
  detail?: Record<string, unknown> | null
  closure?: TaskClosure | null
  needs_closure?: boolean
}

export interface TaskClosure {
  reached: string
  reached_label?: string
  attempts: number
  advice?: string | null
  advice_label?: string | null
  reason?: string | null
  note?: string | null
  by?: string
  at?: string
}

export interface ClosureOption {
  value: string
  label: string
  requires_reason?: boolean
  unreached?: boolean
}

export interface ClosureSpec {
  reached: { options: ClosureOption[]; min_attempts_if_unreached?: number }
  advice: { options: ClosureOption[] }
  outcome_followup?: { label: string; options: ClosureOption[] } | null
}

export interface HandoverSheet {
  generated_at_local: string
  tasks: Task[]
}

/** 恢复轨迹卡：以首诊为基线，按医生设定的最小临床重要差异判读（不做预测） */
export type TrajectoryVerdict = 'improved_meaningful' | 'no_meaningful_change' | 'worse_meaningful' | 'insufficient' | 'improved' | 'same' | 'worse'

export interface TrajectoryPoint {
  day: number
  value: number | string | null
  encounter_id: string
  is_current: boolean
  category?: string | null
}

export interface TrajectoryOutcome {
  key: string
  label: string
  categorical?: boolean
  direction?: 'lower_better' | 'higher_better'
  mcid_abs?: number | null
  mcid_pct?: number | null
  rule?: 'both' | 'either'
  source?: string | null
  baseline?: number | null
  current?: number | null
  baseline_substitute?: string | null
  series: TrajectoryPoint[]
  verdict: TrajectoryVerdict
  label_verdict?: string
  delta?: number | null
  pct?: number | null
}

export interface Trajectory {
  baseline_encounter_id: string
  day: number
  visit_index: number
  visits: number
  outcomes: TrajectoryOutcome[]
  regions: { baseline: string[]; current: string[]; added: string[]; removed: string[]; delta: number } | null
  reference_curves: Record<string, unknown> | null
  simulated: boolean
  note: string
}

// ---------------- 患者端 ----------------

export interface PatientProtocolInfo {
  id: string
  title: string
  service_hours: string
  service_notice: string
  emergency_notice: string
  contact_label?: string
  contact_phone?: string | null
  emergency_phone?: string
  body_map_view?: BodyView
}

export type StopReason = 'urgent_red_flag' | null

/** 紧急页文案：由"红旗去向（急诊 / 门诊）× 现在是否开诊"决定（协议 course，内容来自模拟临床负责人，待医生审定） */
export interface UrgentView {
  route: 'ed' | 'clinic'
  in_service_hours: boolean | null
  copy_key: string
  headline: string
  body: string
  primary: string
  secondary: string | null
  reassurance: string | null
  next_open: string | null
  service_hours: string | null
  simulated: boolean
}

export interface StopInfo {
  stop_reason: StopReason
  stop_alerts: Alert[]
  urgent_view?: UrgentView | null
}

export interface PatientState {
  functional_goals_enabled?: boolean
  functional_goals?: FunctionalGoal[]
  question_metrics?: QuestionMetrics
  id: string
  patient_code: string | null
  kind: EncounterKind
  status: EncounterStatus
  protocol: PatientProtocolInfo
  question_count: number
  max_questions: number
  body_map: { primary: string[]; radiation: string[] }
  notices: Alert[]
  notifications: Notification[]
  parent_encounter_id: string | null
  stop_reason?: StopReason
  stop_alerts?: Alert[]
  urgent_view?: UrgentView | null
  respondent?: Respondent
  course?: PatientCourseInfo
}

export type Respondent = 'self' | 'family' | 'staff'

export interface PatientCourseInfo {
  time_budget: string | null
  safety_card: { collapsed: string; items: string[]; save_hint: string | null } | null
  respondent_options: { value: Respondent; label: string }[]
  service_hours: string | null
  in_service_hours: boolean | null
  simulated: boolean
}

export type QuestionType = 'yes_no' | 'single_choice' | 'multi_choice' | 'scale' | 'number' | 'text' | 'body_regions' | 'verify' | 'grid'

export type VerifyDecision = 'confirm' | 'reject' | 'unsure'

export interface VerifyItem {
  fact_key: string
  label: string
  status: FactStatus
  value: unknown
  value_label: string
  quote: string
}

/** 红旗一屏的一行（逐行 有 / 没有 / 不确定，必答，不计题数） */
export interface GridItem {
  question_id: string
  fact_key: string
  text: string
}

export type GridAnswer = 'yes' | 'no' | 'unsure'

export interface Question {
  question_id: string
  fact_key: string
  fact_keys?: string[]
  text: string
  type: QuestionType
  kind: 'protocol' | 'clarification' | 'verification' | 'red_flag_grid' | 'event_context'
  event_id?: string
  quote?: string
  reason?: string
  decision_trace?: EventDecisionTrace
  scope?: 'urgent' | 'normal'
  items?: VerifyItem[]
  preface?: string | null
  options: Option[]
  allow_unknown: boolean
  allow_skip: boolean
  tier?: number
  min?: number
  max?: number
  anchors?: Record<string, string>
}

export interface NextQuestionResp extends StopInfo {
  question_metrics?: QuestionMetrics
  question: Question | null
  status: EncounterStatus
  question_count: number
  notices: Alert[]
}

export interface QuestionMetrics {
  screens_shown: number
  items_shown: number
  items_answered: number
  note: string
}

export interface AnswerResp extends StopInfo {
  question_metrics?: QuestionMetrics
  entry_id: string
  new_alerts: Alert[]
  next: Question | null
  status: EncounterStatus
  question_count: number
}

export interface BodyMapResp {
  entry_id: string
  new_alerts: Alert[]
}

export interface ExtractionResult {
  provider: string
  applied: { key: string; status: FactStatus; value: unknown }[]
  rejected: unknown[]
  unmapped_mentions: string[]
}

export interface TextResp {
  entry_id: string
  extraction: ExtractionResult
  new_alerts: Alert[]
}

export interface ConfirmationView {
  requires_more_questions?: boolean
  symptom_events?: Pick<SymptomEvent, 'id' | 'entry_id' | 'fact_keys' | 'quote' | 'subject' | 'subject_label' | 'assertion_type' | 'time_relation' | 'time_label' | 'time_text' | 'reported_at' | 'verification_label'>[]
  context_options?: Option[]
  encounter_id: string
  status: EncounterStatus
  groups: {
    confirmed: ConfirmFact[]
    uncertain: ConfirmFact[]
    unanswered: ConfirmFact[]
    conflicting: ConfirmFact[]
  }
  notices: Alert[]
  can_confirm: boolean
  stop_reason?: StopReason
  stop_alerts?: Alert[]
}

export interface Correction {
  fact_key: string
  status: 'present' | 'denied'
  value: unknown
}

export interface ConfirmResp {
  status: EncounterStatus
  verification_passed: boolean
  next_step: string
}

// ---------------- 医生端 ----------------

export interface Entry {
  id: string
  seq: number
  kind: string
  payload: Record<string, unknown>
  created_at: string
}

export interface Check {
  id: string
  label: string
  severity: 'critical' | 'major' | 'minor'
  passed: boolean
  details: string[]
}

export interface Verification {
  id: string
  passed: boolean
  checks: Check[]
  created_at: string
}

export interface RegionRef {
  id: string
  label: string
}

export interface SummaryAlert {
  id: string
  rule_id: string
  severity: Severity
  label: string
  evidence: AlertEvidence[]
}

export interface EditLogItem {
  by: string
  at: string
  fields: string[]
  note?: string | null
}

export interface SummaryContent {
  headline: string
  body_map: { primary: RegionRef[]; radiation: RegionRef[]; side: string }
  key_facts: Fact[]
  denied: Fact[]
  uncertain: Fact[]
  unknown: Fact[]
  gaps: Fact[]
  conflicts: Fact[]
  /** 患者否认过的红旗：原话提到，核对时说不对（第三轮评审 T3）。不进"明确否认" */
  disputed?: DisputedFact[]
  alerts: SummaryAlert[]
  quotes: { entry_id: string; text: string; at: string; flags?: FactFlag[] }[]
  narrative: string
  narrative_provider: string
  based_on_fact_ids: string[]
  doctor_edits: Record<string, string>
  edit_log?: EditLogItem[]
}

export interface DisputedFact extends Fact {
  quotes: string[]
  now: string
  rule_label: string
  severity: Severity
}

export interface Summary {
  id: string | null
  /** 患者尚未确认时给医护的临时整理（不落库、不算版本） */
  provisional?: boolean
  version: number
  author: string
  note: string | null
  content: SummaryContent
  created_at: string
}

export interface SummaryVersion {
  id: string
  version: number
  author: string
  note: string | null
  created_at: string
}

export interface ChangeItem {
  key: string
  label: string
  before: string
  after: string
  before_status: FactStatus | null
  after_status: FactStatus
  evidence: Evidence[]
}

export interface FollowupPlan {
  version_id?: string
  version?: number
  content_sha256?: string
  understanding_points?: { id: string; text: string }[]
  teachback_enabled?: boolean
  interval_days: number
  watch_facts: string[]
  patient_message: string
  set_by: string
  set_at: string
  drafted_with?: string
  draft_id?: string
  rewrite_mode?: string
  ai_assisted?: boolean
  override_terms?: string[]
  override_reason?: string
}

export interface ChangeCard {
  parent_encounter_id: string
  parent_confirmed_at: string | null
  changed: ChangeItem[]
  new: ChangeItem[]
  unconfirmed: ChangeItem[]
  unchanged: ChangeItem[]
  triggered: Alert[]
  plan_delivery: Notification[]
  followup_plan: FollowupPlan | null
}

export interface AskedQuestion {
  question_id: string
  text: string
  kind: string
  answer_status: string
  asked_at: string
}

export interface DoctorView {
  functional_goals?: FunctionalGoal[]
  teachback_responses?: TeachbackResponse[]
  symptom_events?: SymptomEvent[]
  protocol_snapshot?: ProtocolDetail & { content_sha256: string | null; snapshot_verified: boolean }
  encounter: EncounterBrief
  protocol: { id: string; version: string; status: string; title: string }
  summary: Summary | null
  summary_versions: SummaryVersion[]
  facts: Fact[]
  entries: Entry[]
  alerts: Alert[]
  tasks: Task[]
  notifications: Notification[]
  verification: Verification | null
  change_card: ChangeCard | null
  followup_plan: FollowupPlan | null
  questions: AskedQuestion[]
  stop?: StopInfo
  extractions?: ExtractionLog[]
  eligibility?: EligibilityRecord | null
  brief?: VisitBrief
  record_draft?: RecordDraft
  trajectory?: Trajectory | null
  respondent?: { value: Respondent; label: string; relation: string | null; proxy_consent: boolean }
}

export interface EventDecisionTrace {
  variants: { subject: string; time_relation: string; actions: { id: string; label: string; severity: string; role: string; stop: boolean }[] }[]
  distinct_action_sets: number
  priority: number
  should_ask: boolean
  reason: string
  strategy: string
  protocol_sha256: string
}

export interface SymptomEvent {
  id: string
  entry_id: string
  fact_keys: string[]
  labels: string[]
  quote: string
  subject: string
  assertion_type?: string
  subject_label: string
  time_relation: string
  time_label: string
  time_text: string
  reported_at: string
  verification_state: string
  verification_label: string
  inference_source: string
  inference_issues: string[]
  history: { at: string; by: string; note?: string; label?: string; entry_id?: string }[]
  decision_trace: EventDecisionTrace
}

export interface TeachbackResponse {
  id: string
  plan_version_id: string
  plan_version: number
  is_current_plan: boolean
  response_text: string
  execution_status: string
  execution_label: string
  barrier_text: string
  analysis: { source?: string; provider?: string; note?: string; items?: { point_id: string; point_text: string; plan_quote: string; response_quote: string; verdict: string; label: string; issue: string }[] }
  reviewed: boolean
  review: { by: string; at: string; result: string; note: string } | null
  created_at: string
}

/** 接诊速览：紧急程度、一句话主诉、面诊要当面确认的几件事（确定性整理，不做诊断） */
export interface VisitBrief {
  triage: Severity | null
  triage_rank: number
  triage_label: string
  headline: string
  note: string
  red_flags: { label: string; severity: Severity; severity_label: string; disputed: boolean; notice_shown: boolean }[]
  triage_disputed?: boolean
  confirm_items: { key: string; label: string; kind: 'disputed' | 'conflict' | 'uncertain' | 'gap'; detail: string }[]
  confirm_more: number
  open_tasks: number
}

/** 门诊病历初稿：只用患者确认过的事实拼成，医生核对后复制使用 */
export interface RecordDraft {
  sections: { title: string; text: string }[]
  footer: string
  text: string
  provisional: boolean
}

export interface NewTerm {
  term: string
  category: string
  category_label: string
}

export interface FollowupDraft {
  draft: string
  provider: string
  /** glossary = 医生审定的术语对照表（不调用模型）；llm = 模型改写措辞 */
  mode: 'glossary' | 'llm'
  ai_assisted: boolean
  warnings: string[]
  /** 改写里有、医生要点里没有的医学内容：发送前必须删掉或写理由 */
  new_terms: NewTerm[]
  draft_id: string
  interval_days: number
}

export interface EligibilityItem {
  id: string
  text: string
  no_label: string
  if_not: string
}

export interface EligibilityRecord {
  attested: boolean
  answers: Record<string, boolean>
  items: { id: string; text: string }[]
  at: string
}

export interface ProbeResult {
  ok: boolean
  provider: string
  name?: string
  mode?: string
  detail: string
  seconds?: number
  facts?: number
  checked_at: string
  credentials?: string | null
  cached?: boolean
}

export interface ClockInfo {
  now_local: string
  demo_clock: boolean
  in_service_hours: boolean | null
  service_hours: string | null
}

export interface HealthInfo {
  worker?: { running: boolean; last_tick: string | null; last_error: string | null; consecutive_failures: number }
  external_delivery_configured?: boolean
  version: string
  mode: 'demo' | 'production'
  ok: boolean
  llm_provider: string
  clock?: ClockInfo
  llm?: {
    provider: string
    name: string
    fallback: string | null
    last_used: string
    ready?: boolean
    not_ready_reason?: string | null
    last_error?: string | null
    last_error_at?: string | null
    credentials?: string | null
    usage?: { calls: number; errors: number; fallbacks: number }
    last_probe?: ProbeResult | null
  }
  default_protocol: string
  dev_endpoints?: boolean
}

// ---------------- 协议 ----------------

export interface ProtocolListItem {
  protocol_id: string
  version?: string
  status?: string
  title?: string
  specialty?: string
  facts?: number
  questions?: number
  red_flags?: number
  review_gaps?: number
  error?: string
}

export interface ProtocolFactDef {
  key: string
  label: string
  type: string
  category: string
  options: { value: string; label: string }[]
  required: boolean
  critical: boolean
  min?: number | null
  max?: number | null
  notes?: string | null
}

export interface ProtocolRedFlag {
  id: string
  label: string
  when: string
  severity: Severity
  action: string
  patient_message: string
}

export interface ProtocolDetail {
  event_verification?: { enabled: boolean; strategy: 'all' | 'action_sensitive' }
  protocol_id: string
  version: string
  status: string
  title: string
  specialty: string
  language: string
  owners: Record<string, string>
  review: Record<string, unknown>
  scope: {
    inclusion: string[]
    exclusion: string[]
    setting: string
    service_hours: string
    service_notice: string
    emergency_notice: string
    out_of_scope_message: string
    contact_label?: string
    contact_phone?: string | null
    emergency_phone?: string
    /** 开始页逐条确认的适用范围；选"不对"不进入采集 */
    eligibility?: EligibilityItem[]
  }
  max_questions: number
  facts: ProtocolFactDef[]
  questions: unknown[]
  red_flags: ProtocolRedFlag[]
  followup: { default_interval_days: number; change_facts: string[]; questions: unknown[]; teachback_enabled?: boolean; teachback_point_limit?: number }
  review_gaps: string[]
  course?: {
    simulated?: boolean
    time_budget?: Record<string, string>
    respondent?: { options: { value: Respondent; label: string }[]; proxy_note?: string | null } | null
  }
}

/** "用词表重放这句"：同一句原话的离线词表结果（只读）与当时模型写入的结果 */
export interface LexiconReplay {
  entry_id: string
  text: string
  provider: string | null
  model: { key: string; label: string; status: FactStatus; pass?: string | null; red_flag: boolean }[]
  lexicon: { key: string; label: string; status: FactStatus; value_label: string; quote: string | null; red_flag: boolean }[]
  only_model: string[]
  only_lexicon: string[]
  red_flag_pass?: { ran: boolean; added: string[]; raised: string[] } | null
  note: string
}

export interface FunctionalGoal {
  id: string; description: string; unit: string; conditions: string; confirmed_at: string
  comparison: { comparable: boolean; delta: number | null; reason: string }
  observations: { id: string; state: string; value: number | null; observed_date: string | null; condition_match: string; conditions: string; note: string; created_at: string }[]
}
