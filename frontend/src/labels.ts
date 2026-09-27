import type { EncounterKind, EncounterStatus, FactStatus, NotificationStatus, Severity, TaskStatus } from './api/types'

export type Tone = 'red' | 'orange' | 'yellow' | 'green' | 'blue' | 'purple' | 'gray'

export const ENCOUNTER_STATUS: Record<EncounterStatus, string> = {
  draft: '填写中',
  questioning: '补问中',
  awaiting_patient_confirmation: '待患者确认',
  ready_for_doctor: '待医生核对',
  under_review: '医生核对中',
  doctor_confirmed: '医生已确认',
  closed: '已结束',
}

export const ENCOUNTER_STATUS_TONE: Record<EncounterStatus, Tone> = {
  draft: 'gray',
  questioning: 'blue',
  awaiting_patient_confirmation: 'yellow',
  ready_for_doctor: 'orange',
  under_review: 'purple',
  doctor_confirmed: 'green',
  closed: 'gray',
}

export const ENCOUNTER_STATUS_ORDER: EncounterStatus[] = [
  'draft',
  'questioning',
  'awaiting_patient_confirmation',
  'ready_for_doctor',
  'under_review',
  'doctor_confirmed',
  'closed',
]

export const ENCOUNTER_KIND: Record<EncounterKind, string> = {
  pre_visit: '就诊前',
  follow_up: '随访',
}

export const FACT_STATUS: Record<FactStatus, string> = {
  present: '已明确',
  denied: '明确否认',
  not_asked: '未询问',
  asked_unanswered: '已问未答',
  uncertain: '表达不确定',
  conflicting: '存在矛盾',
}

export const FACT_STATUS_TONE: Record<FactStatus, Tone> = {
  present: 'green',
  denied: 'blue',
  not_asked: 'gray',
  asked_unanswered: 'gray',
  uncertain: 'yellow',
  conflicting: 'red',
}

export const SEVERITY: Record<Severity, string> = {
  urgent: '紧急',
  same_day: '当日处理',
  routine: '常规',
}

export const SEVERITY_TONE: Record<Severity, Tone> = {
  urgent: 'red',
  same_day: 'orange',
  routine: 'gray',
}

export const TASK_STATUS: Record<TaskStatus, string> = {
  unviewed: '未查看',
  viewed: '已查看',
  contacted: '已联系患者',
  pending: '待进一步处理',
  escalated: '已升级',
  completed: '已完成',
}

export const TASK_STATUS_TONE: Record<TaskStatus, Tone> = {
  unviewed: 'red',
  viewed: 'blue',
  contacted: 'purple',
  pending: 'yellow',
  escalated: 'orange',
  completed: 'green',
}

export const TASK_STATUS_ORDER: TaskStatus[] = ['unviewed', 'viewed', 'contacted', 'pending', 'escalated', 'completed']

export const TASK_KIND: Record<string, string> = {
  teachback_review: '复述与执行困难核实',
  event_review: '病程事件复核',
  red_flag_review: '红旗复核',
  conflict_review: '矛盾复核',
  followup_check: '随访检查',
  doctor_review: '医生核对',
  after_hours_callback: '停诊后回访',
  recovery_review: '恢复提醒',
  no_response: '到期未签到',
}

export const NOTIFICATION_STATUS: Record<NotificationStatus, string> = {
  queued: '排队中',
  sent: '已提供到患者页面',
  failed: '发送失败',
  seen: '已看到',
  acknowledged: '患者点击确认',
}

export const NOTIFICATION_STATUS_TONE: Record<NotificationStatus, Tone> = {
  queued: 'gray',
  sent: 'blue',
  failed: 'red',
  seen: 'purple',
  acknowledged: 'green',
}

export const NOTIFICATION_FLOW: NotificationStatus[] = ['queued', 'sent', 'seen', 'acknowledged']

export const ENTRY_KIND: Record<string, string> = {
  body_map: '身体图标记',
  free_text: '患者描述',
  answer: '问题回答',
  correction: '修改',
  doctor_note: '医生备注',
  system_notice: '系统提示',
}

export const ENTRY_KIND_TONE: Record<string, Tone> = {
  body_map: 'purple',
  free_text: 'blue',
  answer: 'green',
  correction: 'yellow',
  doctor_note: 'orange',
  system_notice: 'red',
}

export const SOURCE: Record<string, string> = {
  body_map: '身体图',
  extraction: '文字描述',
  answer: '问题回答',
  correction: '修改',
  doctor: '医生修正',
  derived: '系统推导',
}

export const EVIDENCE_KIND: Record<string, string> = {
  body_map: '身体图',
  free_text: '原话',
  answer: '回答',
  correction: '修改',
  doctor_note: '医生备注',
}

export const CHECK_SEVERITY: Record<string, string> = {
  critical: '关键',
  major: '重要',
  minor: '次要',
}

export const PROTOCOL_STATUS: Record<string, string> = {
  draft: '草稿（尚未临床审核）',
  clinically_reviewed: '已临床审核',
  approved: '已批准',
}

export const PROTOCOL_STATUS_TONE: Record<string, Tone> = {
  draft: 'orange',
  clinically_reviewed: 'blue',
  approved: 'green',
}

export const ANSWER_STATUS: Record<string, string> = {
  pending: '待回答',
  answered: '已回答',
  skipped: '已跳过',
  unknown: '不清楚',
}

export const QUESTION_KIND: Record<string, string> = {
  event_context: '主体与时间核实',
  red_flag_grid: '逐项安全检查',
  protocol: '协议问题',
  clarification: '澄清问题',
  verification: '一键核对',
  followup: '随访问题',
}

export const VERIFY_DECISION: Record<string, string> = {
  confirm: '对',
  reject: '不对',
  unsure: '不确定',
}

/** 界面上展示"抽取用的是哪个模型"：评委与医生都应该一眼看到是真实模型还是离线词表 */
export function providerLabel(name: string | null | undefined): string {
  if (!name) return '—'
  if (name === 'mock') return '离线词表（mock）'
  if (name === 'mock(fallback)') return '离线词表（真实模型失败后的兜底）'
  if (name.startsWith('anthropic:')) return `Claude · ${name.slice('anthropic:'.length)}`
  if (name.startsWith('compat:')) return `兼容接口 · ${name.slice('compat:'.length)}`
  if (name.startsWith('ollama:')) return `本机模型 · ${name.slice('ollama:'.length)}`
  return name
}

export const FACT_TYPE: Record<string, string> = {
  bool: '是/否',
  enum: '单选',
  multi_enum: '多选',
  number: '数值',
  scale: '量表',
  text: '文本',
  body_regions: '身体区域',
  duration: '时长',
}

export function lbl(map: Record<string, string>, key: string | null | undefined): string {
  if (!key) return '—'
  return map[key] ?? key
}

let clinicTimeZone = 'Asia/Shanghai'
export function setClinicTimeZone(zone: string): void {
  try { new Intl.DateTimeFormat('zh-CN', { timeZone: zone }).format(); clinicTimeZone = zone } catch { /* 保留当前合法时区 */ }
}

export function fmtTime(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', {
    timeZone: clinicTimeZone,
    timeZoneName: 'short',
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
