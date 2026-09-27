import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { errorMessage, patientApi } from '../api/client'
import type { EncounterStatus, Notification } from '../api/types'
import { ErrorBox } from '../components/Boxes'
import { Tag } from '../components/Tag'
import { fmtTime } from '../labels'
import { LOCKED_STATUSES, usePatient } from './PatientContext'
import { Steps } from './PatientShell'
import { FunctionalGoals } from '../components/FunctionalGoals'
import { TeachbackForm } from './TeachbackForm'

const PATIENT_STATUS_TEXT: Partial<Record<EncounterStatus, string>> = {
  ready_for_doctor: '已提交，等待医生核对',
  under_review: '医护正在核对',
  doctor_confirmed: '医生已核对确认',
  closed: '本次记录已结束',
}

const NOTIF_TEXT: Record<string, string> = {
  queued: '待患者取回',
  sent: '已提供到本页面',
  failed: '发送失败',
  seen: '你已看到',
  acknowledged: '你已点击确认，尚非理解核验',
}

export default function DonePage() {
  const { id, state, refresh } = usePatient()
  const loc = useLocation()
  const nextStep = (loc.state as { next_step?: string } | null)?.next_step
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  async function event(n: Notification, ev: 'seen' | 'acknowledged') {
    setBusy(n.id)
    setError(null)
    try {
      await patientApi.notificationEvent(n.encounter_id, n.id, ev)
      await refresh()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }

  async function copyId() {
    try {
      await navigator.clipboard.writeText(id)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  if (!state) return null
  const locked = LOCKED_STATUSES.includes(state.status)
  const text =
    nextStep ??
    `你的描述已经交给门诊医生核对。服务时间：${state.protocol.service_hours}。如果出现页面上方提示的紧急情况，请不要等待线上回复。`

  return (
    <div className="stack">
      <Steps current="done" />
      {locked ? (
        <>
          <h1 className="p-title">已提交</h1>
          <section className="card">
            <p className="p-text">{text}</p>
            <p className="small muted">服务时间：{state.protocol.service_hours}</p>
            <p className="small">
              当前状态：<Tag tone="blue">{PATIENT_STATUS_TEXT[state.status] ?? state.status}</Tag>
            </p>
          </section>
        </>
      ) : (
        <>
          <h1 className="p-title">本次填写尚未完成</h1>
          <section className="card">
            <p className="p-text">你还没有确认自己的表达。</p>
            <Link to={`/p/e/${id}/questions`} className="btn btn-primary btn-block">
              继续填写
            </Link>
          </section>
        </>
      )}

      <section className="card">
        <h2 className="card-title">你的记录编号</h2>
        <p className="small muted">记录编号仅用于核对。随访请使用门诊发给你的一次性邀请，编号本身不能授权访问。</p>
        <div className="row">
          <code className="mono id-chip">{id}</code>
          <button type="button" className="btn btn-sm btn-secondary" onClick={copyId}>
            {copied ? '已复制' : '复制'}
          </button>
        </div>
      </section>

      {state.notifications.length > 0 && (
        <section className="card">
          <h2 className="card-title">医生给你的说明</h2>
          <p className="small muted">这段话由医生确认后发给你。阅读确认、复述核实和执行情况分开记录。</p>
          <ErrorBox error={error} onClose={() => setError(null)} />
          <ul className="notif-list">
            {state.notifications.map((n) => (
              <li key={n.id} className="notif-item">
                <p className="notif-content">{n.content}</p>
                <div className="row wrap">
                  <Tag tone={n.status === 'acknowledged' ? 'green' : n.status === 'seen' ? 'purple' : 'blue'}>
                    {NOTIF_TEXT[n.status] ?? n.status}
                  </Tag>
                  <span className="small muted">{fmtTime(n.created_at)}</span>
                </div>
                <div className="row">
                  {n.status === 'sent' && (
                    <button type="button" className="btn btn-secondary" disabled={busy === n.id} onClick={() => event(n, 'seen')}>
                      我已看到
                    </button>
                  )}
                  {n.status === 'seen' && (
                    <button type="button" className="btn btn-primary" disabled={busy === n.id} onClick={() => event(n, 'acknowledged')}>
                      确认已收到说明
                    </button>
                  )}
                  {n.status === 'acknowledged' && <span className="small muted">已记录你的阅读确认。</span>}
                  {n.status === 'queued' && <span className="small muted">等待取回。</span>}
                </div>
                <TeachbackForm notification={n} patientCode={state.patient_code} onSubmitted={refresh} />
              </li>
            ))}
          </ul>
        </section>
      )}

      <FunctionalGoals goals={state.functional_goals ?? []} encounterId={state.functional_goals_enabled ? id : undefined} onChanged={refresh} />
      <Link to="/p" className="btn btn-ghost btn-block">
        返回开始页
      </Link>
    </div>
  )
}
