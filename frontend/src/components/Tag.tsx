import type { ReactNode } from 'react'
import type { EncounterKind, EncounterStatus, FactStatus, NotificationStatus, Severity, TaskStatus } from '../api/types'
import {
  ENCOUNTER_KIND,
  ENCOUNTER_STATUS,
  ENCOUNTER_STATUS_TONE,
  FACT_STATUS,
  FACT_STATUS_TONE,
  NOTIFICATION_STATUS,
  NOTIFICATION_STATUS_TONE,
  SEVERITY,
  SEVERITY_TONE,
  TASK_STATUS,
  TASK_STATUS_TONE,
  type Tone,
} from '../labels'

export function Tag({
  tone = 'gray',
  children,
  title,
  className,
}: {
  tone?: Tone
  children: ReactNode
  title?: string
  className?: string
}) {
  return (
    <span className={`tag tag-${tone}${className ? ` ${className}` : ''}`} title={title}>
      {children}
    </span>
  )
}

export function EncounterStatusTag({ status }: { status: EncounterStatus }) {
  return <Tag tone={ENCOUNTER_STATUS_TONE[status] ?? 'gray'}>{ENCOUNTER_STATUS[status] ?? status}</Tag>
}

export function KindTag({ kind }: { kind: EncounterKind }) {
  return <Tag tone={kind === 'follow_up' ? 'purple' : 'blue'}>{ENCOUNTER_KIND[kind] ?? kind}</Tag>
}

export function FactStatusTag({ status }: { status: FactStatus }) {
  return <Tag tone={FACT_STATUS_TONE[status] ?? 'gray'}>{FACT_STATUS[status] ?? status}</Tag>
}

export function SeverityTag({ severity }: { severity: Severity | null | undefined }) {
  if (!severity) return <span className="muted">—</span>
  return <Tag tone={SEVERITY_TONE[severity] ?? 'gray'}>{SEVERITY[severity] ?? severity}</Tag>
}

export function TaskStatusTag({ status }: { status: TaskStatus }) {
  return <Tag tone={TASK_STATUS_TONE[status] ?? 'gray'}>{TASK_STATUS[status] ?? status}</Tag>
}

export function NotificationStatusTag({ status }: { status: NotificationStatus }) {
  return <Tag tone={NOTIFICATION_STATUS_TONE[status] ?? 'gray'}>{NOTIFICATION_STATUS[status] ?? status}</Tag>
}
