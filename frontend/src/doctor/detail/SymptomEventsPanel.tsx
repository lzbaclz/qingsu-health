import { useState } from 'react'
import { doctorApi, errorMessage } from '../../api/client'
import type { SymptomEvent } from '../../api/types'
import { useStaff } from '../../auth/AuthContext'
import { ErrorBox } from '../../components/Boxes'
import { fmtTime } from '../../labels'

const SUBJECTS = { patient: '患者本人', other: '他人情况', unclear: '主体待核实' }
const TIMES = { new: '本次新发', ongoing: '既有症状仍存在', historical: '历史提及，当前待核实', worsening: '本次加重', improving: '本次减轻', past: '过去已结束', unknown: '时间待核实' }

function EventCard({ event, encounterId, onChanged, onQuote }: { event: SymptomEvent; encounterId: string; onChanged: () => void; onQuote: (id: string) => void }) {
  const { user } = useStaff()
  const [editing, setEditing] = useState(false)
  const [subject, setSubject] = useState(event.subject)
  const [relation, setRelation] = useState(event.time_relation)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return <article className="sub-card stack-sm">
    <div className="row wrap"><strong>{event.assertion_type === 'hypothetical' && '假设提及 · '}{event.subject_label} · {event.time_label}</strong><span className="small muted">{event.verification_label}</span></div>
    <button type="button" className="quote-btn" onClick={() => onQuote(event.entry_id)}>患者原话：「{event.quote}」</button>
    <div className="small">报告时间：{fmtTime(event.reported_at)} · 原文时间线索：{event.time_text || '原话未明确'}；报告时间不代表起病时间。</div>
    {event.inference_issues.length > 0 && <p className="small">需核对：{event.inference_issues.join('；')}</p>}
    <details><summary>查看核实依据与流程差异</summary><div className="stack-sm">
      <p className="small">{event.decision_trace.reason} · {event.decision_trace.distinct_action_sets} 种处理组合。这里展示规则推演，不能替代临床判断。</p>
      <ul className="small">{event.decision_trace.variants.map((v, i) => <li key={i}>{SUBJECTS[v.subject as keyof typeof SUBJECTS] ?? v.subject}／{TIMES[v.time_relation as keyof typeof TIMES] ?? v.time_relation}：{v.actions.map(a => a.label).join('；') || '未触发这些规则，仍需常规核对'}</li>)}</ul>
      {event.history.map((h, i) => <div className="small" key={i}>{fmtTime(h.at)} · {h.by} · {h.label ?? h.note}</div>)}
    </div></details>
    {user.role === 'doctor' && <button className="btn btn-secondary btn-sm" onClick={() => setEditing(v => !v)}>{editing ? '收起复核' : '医生复核主体与时间'}</button>}
    {editing && <form className="stack-sm" onSubmit={async e => {
      e.preventDefault(); setBusy(true); setError(null)
      try { await doctorApi.reviewEvent(encounterId, event.id, { subject, time_relation: relation, note }); setEditing(false); onChanged() }
      catch (err) { setError(errorMessage(err)) }
      finally { setBusy(false) }
    }}>
      <label>事件主体<select value={subject} onChange={e => setSubject(e.target.value)}>{Object.entries(SUBJECTS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      <label>时间关系<select value={relation} onChange={e => setRelation(e.target.value)}>{Object.entries(TIMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      <label>核实依据与后续安排<textarea value={note} onChange={e => setNote(e.target.value)} required maxLength={2000} /></label>
      <p className="small muted">明确主体和时间后完成对应语义待办；选“待核实”会继续保持未完成。这里不自动取消红旗，事实修正与临床处置仍需单独记录。</p>
      <button className="btn btn-primary" disabled={busy || !note.trim()}>{busy ? '保存中…' : '保存语义复核'}</button>
    </form>}
    <ErrorBox error={error} />
  </article>
}

export function SymptomEventsPanel({ events, encounterId, onChanged, onQuote }: { events: SymptomEvent[]; encounterId: string; onChanged: () => void; onQuote: (id: string) => void }) {
  return <section className="card stack" aria-label="病程事件核实">
    <h2 className="card-title">病程事件：新记录不等于新发生</h2>
    <p className="small muted">逐条保留说的是谁、发生时间与报告时间。模型整理和患者核实都不是临床诊断。</p>
    {events.length ? events.map(e => <EventCard key={`${e.id}:${e.history.length}`} event={e} encounterId={encounterId} onChanged={onChanged} onQuote={onQuote} />) : <p className="small muted">尚无此版本支持的症状事件，不能从“上次未记录”推断新发。</p>}
  </section>
}
