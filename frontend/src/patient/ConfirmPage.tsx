import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { errorMessage, patientApi, track } from '../api/client'
import type { ConfirmFact, ConfirmationView, Correction } from '../api/types'
import { ErrorBox, Loading } from '../components/Boxes'
import { CURRENT_ENCOUNTER_KEY, LAST_ENCOUNTER_KEY, storageRemove, storageSet } from '../storage'
import { usePatient } from './PatientContext'
import { Steps } from './PatientShell'
import { UrgentActions } from './UrgentPage'

const BOOL_OPTIONS = [
  { value: 'yes', label: '有 / 是' },
  { value: 'no', label: '没有 / 否' },
]

export default function ConfirmPage() {
  const { id, addAlerts, refresh } = usePatient()
  const nav = useNavigate()
  const [view, setView] = useState<ConfirmationView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [eventChoices, setEventChoices] = useState<Record<string, string>>({})
  const [corrections, setCorrections] = useState<Record<string, Correction>>({})
  const [editing, setEditing] = useState<string | null>(null)
  const [mountedAt] = useState(Date.now)

  useEffect(() => {
    let alive = true
    patientApi
      .confirmation(id)
      .then((v) => {
        if (!alive) return
        setView(v)
        if (v.notices.length) addAlerts(v.notices)
      })
      .catch((e) => {
        if (alive) setError(errorMessage(e))
      })
    return () => {
      alive = false
    }
  }, [id, addAlerts])

  function editable(f: ConfirmFact): boolean {
    return f.type === 'bool' || (f.type === 'enum' && f.options.length > 0)
  }

  function correctedLabel(f: ConfirmFact): string | null {
    const c = corrections[f.key]
    if (!c) return null
    if (f.type === 'bool') return c.status === 'denied' ? '没有 / 否' : '有 / 是'
    return f.options.find((o) => o.value === c.value)?.label ?? String(c.value)
  }

  function choose(f: ConfirmFact, optionValue: string) {
    let c: Correction
    if (f.type === 'bool') {
      c = optionValue === 'no' ? { fact_key: f.key, status: 'denied', value: null } : { fact_key: f.key, status: 'present', value: true }
    } else {
      c = { fact_key: f.key, status: 'present', value: optionValue }
    }
    setCorrections((prev) => ({ ...prev, [f.key]: c }))
    setEditing(null)
    track(id, 'confirm_edit', { fact_key: f.key })
  }

  function undo(key: string) {
    setCorrections((prev) => {
      const next = { ...prev }
      delete next[key]
      return next
    })
  }

  async function submit() {
    if (!view?.can_confirm) return
    setBusy(true)
    setError(null)
    try {
      const r = await patientApi.confirm(id, Object.values(corrections))
      track(id, 'confirm_submit', { corrections: Object.keys(corrections).length, ms: Date.now() - mountedAt,
        urgent: view.stop_reason === 'urgent_red_flag' })
      await refresh()
      storageSet(LAST_ENCOUNTER_KEY, id)
      storageRemove(CURRENT_ENCOUNTER_KEY)
      nav(`/p/e/${id}/done`, { replace: true, state: { next_step: r.next_step } })
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  if (!view) {
    return (
      <div className="stack">
        <Steps current="confirm" />
        {error ? <ErrorBox error={error} /> : <Loading text="正在整理你的记录…" />}
      </div>
    )
  }

  const g = view.groups
  const urgent = view.stop_reason === 'urgent_red_flag'
  const hasConflict = g.conflicting.length > 0
  const nCorr = Object.keys(corrections).length

  return (
    <div className="stack">
      <Steps current="confirm" />
      {urgent && <UrgentActions alerts={view.stop_alerts ?? []} compact />}
      <h1 className="p-title">请核对：这些是不是你想表达的？</h1>
      <p className="p-text muted">
        你确认的是<strong>记录是否准确</strong>，不是同意任何医学判断。医生会在就诊时再和你核对。
      </p>

      {(view.symptom_events?.length ?? 0) > 0 && <section className="card stack-sm">
        <h2 className="card-title">病程信息：谁的情况，什么时候发生</h2>
        {view.symptom_events?.map(event => <div className="sub-card stack-sm" key={event.id}>
          <p>原话：「{event.quote}」</p><strong>{event.assertion_type === 'hypothetical' && '条件句中的假设 · '}{event.subject_label} · {event.time_label}</strong>
          <span className="small muted">{event.verification_label} · 原文时间线索：{event.time_text || '未明确'}</span>
          <details><summary>这段话整理得不准确？修改含义</summary>
            <label>更准确的说法<select value={eventChoices[event.id] ?? ''} onChange={e => setEventChoices(v => ({ ...v, [event.id]: e.target.value }))}>
              <option value="">请选择</option>{view.context_options?.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select></label>
            <button className="btn btn-secondary" disabled={busy || !eventChoices[event.id]} onClick={async () => {
              setBusy(true); setError(null)
              try {
                const updated = await patientApi.correctEvent(id, event.id, eventChoices[event.id])
                setView(updated); addAlerts(updated.notices)
                setCorrections(previous => Object.fromEntries(Object.entries(previous).filter(([key]) => !event.fact_keys.includes(key))))
              } catch (e) { setError(errorMessage(e)) }
              finally { setBusy(false) }
            }}>保存这段话的含义</button>
          </details>
        </div>)}
        <button className="btn btn-secondary" onClick={() => nav(`/p/e/${id}/questions`)}>返回补问或核实</button>
      </section>}

      {hasConflict && urgent && (
        <section className="box box-warn">
          <strong>有 {g.conflicting.length} 项前后说法不一致</strong>
          <p className="small">现在不需要再回答问题，这些不一致的地方会原样交给医生核对。</p>
          <ul className="plain-list">
            {g.conflicting.map((f) => (
              <li key={f.key}>
                {f.label}：{f.value_label}
              </li>
            ))}
          </ul>
        </section>
      )}

      {hasConflict && !urgent && (
        <section className="box box-error">
          <strong>还有 {g.conflicting.length} 项前后说法不一致，需要先澄清</strong>
          <ul className="plain-list">
            {g.conflicting.map((f) => (
              <li key={f.key}>
                {f.label}：{f.value_label}
              </li>
            ))}
          </ul>
          <button type="button" className="btn btn-danger btn-block" onClick={() => nav(`/p/e/${id}/questions`)}>
            回到问题页澄清
          </button>
        </section>
      )}

      <section className="card confirm-group">
        <h2 className="card-title">
          已明确 <span className="muted small">{g.confirmed.length} 项</span>
        </h2>
        {g.confirmed.length === 0 && <p className="muted small">暂无</p>}
        <ul className="fact-list">
          {g.confirmed.map((f) => {
            const corrected = correctedLabel(f)
            const isEditing = editing === f.key
            return (
              <li key={f.key} className={`fact-item${corrected ? ' corrected' : ''}`}>
                <div className="fact-row">
                  <span className="fact-label">{f.label}</span>
                  <span className="fact-value">
                    {corrected ? (
                      <>
                        <s className="muted">{f.patient_value_label ?? f.value_label}</s> → <strong>{corrected}</strong>
                      </>
                    ) : (
                      f.patient_value_label ?? f.value_label
                    )}
                  </span>
                </div>
                {editable(f) && (
                  <div className="fact-actions">
                    {corrected ? (
                      <button type="button" className="btn btn-sm btn-ghost" onClick={() => undo(f.key)}>
                        撤销修改
                      </button>
                    ) : (
                      <button type="button" className="btn btn-sm btn-secondary" onClick={() => setEditing(isEditing ? null : f.key)}>
                        {isEditing ? '取消' : '修改'}
                      </button>
                    )}
                  </div>
                )}
                {isEditing && (
                  <div className="opt-list opt-list-sm" role="radiogroup" aria-label={`修改 ${f.label}`}>
                    {(f.type === 'bool' ? BOOL_OPTIONS : f.options).map((o) => (
                      <button key={o.value} type="button" role="radio" aria-checked={false} className="opt-btn opt-sm" onClick={() => choose(f, o.value)}>
                        {o.label}
                      </button>
                    ))}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      </section>

      {g.uncertain.length > 0 && (
        <section className="card confirm-group">
          <h2 className="card-title">
            表达不确定 <span className="muted small">{g.uncertain.length} 项</span>
          </h2>
          <p className="small muted">这些会按"不太确定"记录，医生会在就诊时进一步询问。</p>
          <ul className="fact-list">
            {g.uncertain.map((f) => (
              <li key={f.key} className="fact-item">
                <div className="fact-row">
                  <span className="fact-label">{f.label}</span>
                  <span className="fact-value">{f.patient_value_label ?? f.value_label}</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {g.unanswered.length > 0 && (
        <section className="card confirm-group">
          <h2 className="card-title">
            未回答 <span className="muted small">{g.unanswered.length} 项</span>
          </h2>
          <p className="small muted">这些会如实记录为"未回答"，医生会在就诊时询问。</p>
          <ul className="fact-list">
            {g.unanswered.map((f) => (
              <li key={f.key} className="fact-item">
                <div className="fact-row">
                  <span className="fact-label">{f.label}</span>
                  <span className="fact-value muted">医生会在就诊时询问</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <ErrorBox error={error} onClose={() => setError(null)} />

      {!view.can_confirm && !hasConflict && <div className="box box-warn">{view.requires_more_questions ? '还有需要回答或核实的信息，请返回补问。拿不准可以如实选择不清楚。' : `当前状态（${view.status}）不能确认。`}
        {view.requires_more_questions && <button className="btn btn-secondary" onClick={() => nav(`/p/e/${id}/questions`)}>返回补问</button>}
      </div>}

      <button type="button" className="btn btn-primary btn-lg btn-block" disabled={busy || !view.can_confirm} onClick={submit}>
        {busy ? '正在提交…' : nCorr > 0 ? `确认这是我的表达（含 ${nCorr} 处修改）` : '确认这是我的表达'}
      </button>
      <p className="small muted center">确认后会交给门诊医生核对；确认后将不能再修改本次填写。</p>
    </div>
  )
}
