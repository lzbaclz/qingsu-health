import type { StaffUser } from '../auth/AuthContext'
import { setClinicTimeZone } from '../labels'
import type {
  AnswerResp,
  ClosureSpec,
  ClockInfo,
  HandoverSheet,
  LexiconReplay,
  BodyMapResp,
  ConfirmResp,
  ConfirmationView,
  HealthInfo,
  FollowupDraft,
  ProbeResult,
  Correction,
  DoctorView,
  EncounterBrief,
  EncounterKind,
  Mark,
  NextQuestionResp,
  Notification,
  PatientState,
  ProtocolDetail,
  ProtocolListItem,
  Region,
  Respondent,
  Task,
  SymptomEvent,
  TextResp,
} from './types'

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.detail
  if (e instanceof Error) return e.message
  return String(e)
}

async function request<T>(method: 'GET' | 'POST', url: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, {
      method,
      credentials: 'same-origin',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, '网络错误：无法连接服务器，请稍后重试')
  }
  const text = await res.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }
  if (!res.ok) {
    let detail = `请求失败（HTTP ${res.status}）`
    if (data && typeof data === 'object' && 'detail' in data) {
      const d = (data as { detail: unknown }).detail
      detail = typeof d === 'string' ? d : JSON.stringify(d)
    } else if (typeof data === 'string' && data) {
      detail = data
    }
    throw new ApiError(res.status, detail)
  }
  if (data && typeof data === 'object' && 'clinic_timezone' in data && typeof data.clinic_timezone === 'string') setClinicTimeZone(data.clinic_timezone)
  return data as T
}

const get = <T,>(url: string) => request<T>('GET', url)
const post = <T,>(url: string, body?: unknown) => request<T>('POST', url, body ?? {})

export const authApi = {
  me: () => get<StaffUser>('/api/auth/me'),
  login: (username: string, password: string) => post<StaffUser>('/api/auth/login', { username, password }),
  logout: () => post<{ ok: boolean }>('/api/auth/logout'),
  logoutPatient: () => post<{ ok: boolean }>('/api/auth/patient/logout'),
  invite: (body: { patient_code?: string; parent_encounter_id?: string; protocol_id?: string }) =>
    post<{ token: string; path: string; expires_at: string }>('/api/auth/invites', body),
  inspect: (token: string) => post<{ protocol_id: string; patient_code: string; parent_encounter_id: string | null; kind: EncounterKind }>('/api/auth/invites/inspect', { token }),
}

// ---------------- 患者端 ----------------

export const patientApi = {
  createGoal: (id: string, body: { description: string; unit: string; conditions: string; confirmed: boolean }) => post(`/api/patient/encounters/${id}/functional-goals`, body),
  observeGoal: (id: string, goalId: string, body: { submission_key: string; state: string; value: number | null; observed_date: string | null; condition_match: string; conditions: string; note: string }) => post(`/api/patient/encounters/${id}/functional-goals/${goalId}/observations`, body),
  teachback: (encounterId: string, planId: string, body: { response_text: string; execution_status: string; barrier_text: string; submission_key: string }) =>
    post<{ id: string; status: string; plan_version: number; message: string }>(`/api/patient/encounters/${encounterId}/plans/${planId}/teachback`, body),
  create: (body: {
    invite_token?: string
    patient_code?: string
    kind: EncounterKind
    parent_encounter_id?: string
    protocol_id?: string
    eligibility?: Record<string, boolean>
    respondent?: Respondent
    respondent_relation?: string
    proxy_consent?: boolean
  }) =>
    post<PatientState>('/api/patient/encounters', body),
  state: (id: string) => get<PatientState>(`/api/patient/encounters/${id}`),
  bodyMap: (id: string, marks: Mark[]) => post<BodyMapResp>(`/api/patient/encounters/${id}/body-map`, { marks }),
  text: (id: string, text: string) => post<TextResp>(`/api/patient/encounters/${id}/text`, { text }),
  nextQuestion: (id: string) => get<NextQuestionResp>(`/api/patient/encounters/${id}/next-question`),
  answer: (id: string, body: { question_id: string; value?: unknown; unknown?: boolean; skipped?: boolean }) =>
    post<AnswerResp>(`/api/patient/encounters/${id}/answer`, body),
  confirmation: (id: string) => get<ConfirmationView>(`/api/patient/encounters/${id}/confirmation`),
  correctEvent: (id: string, eventId: string, choice: string) =>
    post<ConfirmationView>(`/api/patient/encounters/${id}/symptom-events/${eventId}/correct`, { choice }),
  confirm: (id: string, corrections: Correction[]) =>
    post<ConfirmResp>(`/api/patient/encounters/${id}/confirm`, { corrections }),
  notificationEvent: (id: string, notificationId: string, event: 'seen' | 'acknowledged') =>
    post<Notification>(`/api/patient/encounters/${id}/notifications/${notificationId}/event`, { event }),
}

/**
 * 可用性测试埋点：只记录交互步骤与耗时，不记录输入内容；失败静默（不能影响患者流程）。
 * 后端只接受白名单事件类型，payload 只保留标量。
 */
export function track(encounterId: string, type: string, payload: Record<string, string | number | boolean | null> = {}): void {
  if (!encounterId) return
  try {
    void fetch(`/api/patient/encounters/${encounterId}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, payload, client_ts: new Date().toISOString() }),
      keepalive: true,
    }).catch(() => undefined)
  } catch {
    // ignore
  }
}

// ---------------- 医生端 ----------------

export const doctorApi = {
  reviewTeachback: (encounterId: string, responseId: string, body: { result: string; note: string }) =>
    post<{ reviewed: boolean }>(`/api/doctor/encounters/${encounterId}/teachbacks/${responseId}/review`, body),
  reviewEvent: (encounterId: string, eventId: string, body: { subject: string; time_relation: string; note: string }) =>
    post<SymptomEvent>(`/api/doctor/encounters/${encounterId}/events/${eventId}/review`, body),
  list: (status?: string) =>
    get<EncounterBrief[]>(`/api/doctor/encounters${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  get: (id: string, actor?: string) =>
    get<DoctorView>(`/api/doctor/encounters/${id}${actor ? `?actor=${encodeURIComponent(actor)}` : ''}`),
  editSummary: (id: string, body: { actor: string; edits: Record<string, string>; note?: string }) =>
    post<{ summary_id: string; version: number }>(`/api/doctor/encounters/${id}/summary/edit`, body),
  correctFact: (id: string, body: { actor: string; key: string; status: string; value: unknown; note: string }) =>
    post<{ fact_id: string; version: number }>(`/api/doctor/encounters/${id}/facts/correct`, body),
  confirm: (id: string, body: { actor: string; override_reason?: string }) =>
    post<{ status: string; verification_passed: boolean }>(`/api/doctor/encounters/${id}/confirm`, body),
  followupPlan: (
    id: string,
    body: {
      actor: string
      understanding_points?: string[]
      expected_plan_version_id?: string
      interval_days?: number
      watch_facts?: string[]
      patient_message: string
      drafted_with?: string
      draft_id?: string
      override_reason?: string
    },
  ) => post<{ followup_plan: unknown; notification_id: string }>(`/api/doctor/encounters/${id}/followup-plan`, body),
  /** 把医生要点改写成患者看得懂的说明（不发送；医生核对后再用 followupPlan 发送） */
  followupDraft: (id: string, body: { actor: string; notes: string; interval_days?: number }) =>
    post<FollowupDraft>(`/api/doctor/encounters/${id}/followup-draft`, body),
  tasks: (status?: string) => get<Task[]>(`/api/doctor/tasks${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  transition: (taskId: string, body: { actor: string; to: string; note?: string; closure?: Record<string, unknown> }) =>
    post<Task>(`/api/doctor/tasks/${taskId}/transition`, body),
  contactAttempt: (taskId: string, result: 'reached' | 'unreached' | 'in_person', note: string) =>
    post<Task>(`/api/doctor/tasks/${taskId}/contact-attempt`, { result, note }),
  closureSpec: (protocolId?: string) =>
    get<ClosureSpec>(`/api/doctor/tasks/closure-spec${protocolId ? `?protocol_id=${encodeURIComponent(protocolId)}` : ''}`),
  taskClosureSpec: (taskId: string) => get<ClosureSpec>(`/api/doctor/tasks/${taskId}/closure-spec`),
  handover: () => get<HandoverSheet>('/api/doctor/handover'),
  lexiconReplay: (encId: string, entryId: string) =>
    get<LexiconReplay>(`/api/doctor/encounters/${encId}/entries/${entryId}/lexicon-replay`),
}

// ---------------- 协议 / 身体区域 ----------------

let regionsCache: Promise<Region[]> | null = null
const protocolCache = new Map<string, Promise<ProtocolDetail>>()

export const protocolApi = {
  preview: (base_protocol_id: string, candidate_yaml: string, cases: unknown) => post<unknown>('/api/protocols/preview-impact', { base_protocol_id, candidate_yaml, cases }),
  list: () => get<ProtocolListItem[]>('/api/protocols'),
  get: (id: string) => {
    let p = protocolCache.get(id)
    if (!p) {
      p = get<ProtocolDetail>(`/api/protocols/${encodeURIComponent(id)}`)
      protocolCache.set(id, p)
      p.catch(() => protocolCache.delete(id))
    }
    return p
  },
  regions: () => {
    if (!regionsCache) {
      regionsCache = get<Region[]>('/api/body-regions')
      regionsCache.catch(() => {
        regionsCache = null
      })
    }
    return regionsCache
  },
  health: () => get<HealthInfo>('/api/status'),
  setClock: (at: string | null) => post<ClockInfo>('/api/dev/clock', { at }),
  /** 真实模型连通性自检（跑一次固定测试原话的真实抽取；30 秒内重复调用返回上次结果） */
  probe: () => post<ProbeResult>('/api/llm/probe'),
}

export const DEFAULT_PROTOCOL_ID = 'lbp_adult_v0.2'
