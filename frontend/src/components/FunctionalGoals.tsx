import { useState } from 'react'
import { errorMessage, patientApi } from '../api/client'
import type { FunctionalGoal } from '../api/types'
import { ErrorBox } from './Boxes'
import { fmtTime } from '../labels'

const UNITS: Record<string, string> = { minutes: '分钟', metres: '米', count: '次' }
const STATES: Record<string, string> = { measured: '已观察', not_attempted: '没有尝试', unknown: '不清楚' }
const CONDITIONS: Record<string, string> = { same: '与目标条件一致', changed: '条件有变化', unknown: '条件不清楚' }

function recentDate(daysAgo: number) {
  const d = new Date()
  d.setDate(d.getDate() - daysAgo)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function ObservationForm({ goal, encounterId, onChanged }: { goal: FunctionalGoal; encounterId: string; onChanged: () => Promise<unknown> }) {
  const [state, setState] = useState('unknown')
  const [value, setValue] = useState('')
  const [date, setDate] = useState('')
  const [match, setMatch] = useState('unknown')
  const [conditions, setConditions] = useState('')
  const [note, setNote] = useState('')
  const [key, setKey] = useState(() => crypto.randomUUID())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function save() {
    setBusy(true); setError(null)
    try {
      await patientApi.observeGoal(encounterId, goal.id, { submission_key: key, state, value: state === 'measured' && value !== '' ? Number(value) : null,
        observed_date: date || null, condition_match: match, conditions: match === 'same' ? goal.conditions : conditions || '不清楚', note })
      await onChanged(); setKey(crypto.randomUUID()); setValue(''); setNote('')
    } catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }
  return <details><summary>追加一次日常观察</summary><fieldset disabled={busy} className="stack">
    <label>这次的情况<select value={state} onChange={e => setState(e.target.value)}>{Object.entries(STATES).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select></label>
    {state === 'measured' && <label>观察值（{UNITS[goal.unit]}）<input type="number" min="0" max="100000" step="any" value={value} onChange={e => setValue(e.target.value)} /></label>}
    <label>实际观察日期（记不清可留空）<input type="date" value={date} onChange={e => setDate(e.target.value)} /></label>
    <div className="row wrap" aria-label="选择最近的观察日期">
      <button className="btn btn-sm btn-secondary" type="button" onClick={() => setDate(recentDate(0))}>观察发生在今天</button>
      <button className="btn btn-sm btn-secondary" type="button" onClick={() => setDate(recentDate(1))}>观察发生在昨天</button>
      <button className="btn btn-sm btn-ghost" type="button" onClick={() => setDate('')}>日期记不清</button>
    </div>
    <p className="small muted">{date ? `将记录观察日期：${date}` : '观察日期尚未确定，不会用提交时间代替。'}</p>
    <label>与目标条件的关系<select value={match} onChange={e => setMatch(e.target.value)}>{Object.entries(CONDITIONS).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select></label>
    {match !== 'same' && <label>实际条件<input value={conditions} onChange={e => setConditions(e.target.value)} placeholder="例如换成平路、扶着走；不知道可留空" /></label>}
    <label>补充原话<textarea value={note} onChange={e => setNote(e.target.value)} maxLength={1000} /></label>
    <ErrorBox error={error} /><button type="button" className="btn btn-secondary" onClick={() => void save()}>{busy ? '保存中…' : '确认并保存这次观察'}</button>
  </fieldset></details>
}

export function FunctionalGoals({ goals, encounterId, onChanged }: { goals: FunctionalGoal[]; encounterId?: string; onChanged?: () => Promise<unknown> }) {
  const [description, setDescription] = useState('')
  const [unit, setUnit] = useState('minutes')
  const [conditions, setConditions] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function create() {
    if (!encounterId || !onChanged) return
    setBusy(true); setError(null)
    try { await patientApi.createGoal(encounterId, { description, unit, conditions, confirmed }); await onChanged(); setDescription(''); setConditions(''); setConfirmed(false) }
    catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }
  if (!encounterId && goals.length === 0) return null
  return <section className="card stack" aria-label="生活功能目标"><h2 className="card-title">想恢复的日常活动</h2>
    <p className="small muted">记录已经发生的日常活动，不需要为了填写而额外测试身体。这里是自报观察，不是康复处方或标准量表；有新症状请通过症状采集单独报告。</p>
    {goals.map(g => <article key={g.id} className="card stack"><h3>{g.description}</h3><p>固定条件：{g.conditions} · 单位：{UNITS[g.unit]}</p>
      <p className="small">{g.comparison.comparable && <>最近两次相差 {g.comparison.delta} {UNITS[g.unit]}。 </>}{g.comparison.reason}</p>
      <div className="table-card"><table className="table"><thead><tr><th>观察日期／记录时间</th><th>自报情况</th><th>条件与原话</th></tr></thead><tbody>{g.observations.map(o => <tr key={o.id}><td>{o.observed_date ?? '日期不清楚'}<br /><span className="small muted">记录于 {fmtTime(o.created_at)}</span></td><td>{STATES[o.state]}{o.value !== null && `：${o.value} ${UNITS[g.unit]}`}</td><td>{CONDITIONS[o.condition_match]}：{o.conditions}<br />{o.note}</td></tr>)}</tbody></table></div>
      {encounterId && onChanged && <ObservationForm goal={g} encounterId={encounterId} onChanged={onChanged} />}
    </article>)}
    {encounterId && <details><summary>确认一个自己的生活目标</summary><fieldset disabled={busy} className="stack">
      <label>想恢复什么活动<input value={description} onChange={e => setDescription(e.target.value)} maxLength={300} placeholder="例如自己走到附近商店" /></label>
      <label>用什么记录<select value={unit} onChange={e => setUnit(e.target.value)}>{Object.entries(UNITS).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      <label>固定观察条件<input value={conditions} onChange={e => setConditions(e.target.value)} maxLength={500} placeholder="例如平地、不提重物、是否使用辅助工具" /></label>
      <label><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />我确认这是自己的目标和观察条件</label>
      <ErrorBox error={error} /><button className="btn btn-secondary" type="button" disabled={!confirmed || !description.trim() || !conditions.trim()} onClick={() => void create()}>保存目标</button>
    </fieldset></details>}
  </section>
}
