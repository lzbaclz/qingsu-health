import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { Alert } from '../api/types'
import { NoticeBanner } from '../components/NoticeBanner'
import { EMERGENCY_OPEN_KEY, storageGet, storageSet } from '../storage'

/** 全程可见的紧急提示：可收起为一行，但不能关闭；收起状态跨页面记住。 */
export function EmergencyBar({ text }: { text: string }) {
  const [open, setOpen] = useState(() => storageGet(EMERGENCY_OPEN_KEY) !== '0')
  function toggle() {
    setOpen((o) => {
      storageSet(EMERGENCY_OPEN_KEY, o ? '0' : '1')
      return !o
    })
  }
  return (
    <div className={`emergency-bar${open ? ' open' : ''}`} role="note" aria-label="紧急情况提示">
      <button type="button" className="emergency-toggle" onClick={toggle} aria-expanded={open}>
        <strong>紧急情况提示</strong>
        <span>{open ? '收起' : '展开查看'}</span>
      </button>
      {open && <p className="emergency-text">{text}</p>}
    </div>
  )
}

export function PatientShell({
  children,
  notices = [],
  emergency,
  patientCode,
  subtitle,
}: {
  children: ReactNode
  notices?: Alert[]
  emergency?: string | null
  patientCode?: string | null
  subtitle?: string
}) {
  return (
    <div className={`p-shell${emergency ? ' has-emergency' : ''}`}>
      <NoticeBanner notices={notices} />
      <header className="p-header">
        <Link to="/" className="brand">
          体迹 AI
        </Link>
        <span className="p-header-sub">{subtitle ?? '就诊前症状表达'}</span>
        {patientCode && <span className="p-header-code mono">{patientCode}</span>}
      </header>
      <main className="p-page">{children}</main>
      {emergency && <EmergencyBar text={emergency} />}
    </div>
  )
}

const STEPS = [
  { key: 'body', label: '身体图' },
  { key: 'describe', label: '描述' },
  { key: 'questions', label: '补问' },
  { key: 'confirm', label: '确认' },
] as const

export type StepKey = (typeof STEPS)[number]['key'] | 'done'

export function Steps({ current }: { current: StepKey }) {
  const idx = current === 'done' ? STEPS.length : STEPS.findIndex((s) => s.key === current)
  return (
    <ol className="steps" aria-label="填写进度">
      {STEPS.map((s, i) => (
        <li key={s.key} className={`step${i < idx ? ' done' : ''}${i === idx ? ' active' : ''}`}>
          <span className="step-num">{i + 1}</span>
          <span className="step-label">{s.label}</span>
        </li>
      ))}
    </ol>
  )
}
