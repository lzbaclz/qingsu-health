import { useState } from 'react'
import { Link } from 'react-router-dom'
import { errorMessage, patientApi } from '../api/client'
import type { Notification } from '../api/types'
import { ErrorBox } from '../components/Boxes'

export function TeachbackForm({ notification: n, patientCode, onSubmitted }: { notification: Notification; patientCode: string | null; onSubmitted: () => Promise<unknown> }) {
  const [text, setText] = useState('')
  const [execution, setExecution] = useState('not_started')
  const [barrier, setBarrier] = useState('')
  const [key, setKey] = useState(() => crypto.randomUUID())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState('')
  if (!n.teachback_enabled || !n.plan_version_id) return null
  if (n.is_current_plan === false) return <p className="small muted">这是历史计划第 {n.plan_version} 版。请核对最新说明；历史记录不代表理解了新版。</p>
  return <form className="sub-card stack-sm" onSubmit={async e => {
    e.preventDefault(); setBusy(true); setError(null)
    try {
      const r = await patientApi.teachback(n.encounter_id, n.plan_version_id!, { response_text: text, execution_status: execution, barrier_text: barrier, submission_key: key })
      setSaved(r.message)
      await onSubmitted()
    } catch (err) { setError(errorMessage(err)) }
    finally { setBusy(false) }
  }}>
    <h3>用自己的话说一说 · 计划第 {n.plan_version} 版</h3>
    <p className="small">我们想确认说明是否解释清楚了，不是在考你。请说说你对下面要点的理解。</p>
    <ul>{n.understanding_points?.map(p => <li key={p.id}>{p.text}</li>)}</ul>
    <label>我的理解<textarea disabled={busy} value={text} onChange={e => { setText(e.target.value); setSaved(''); setKey(crypto.randomUUID()) }} maxLength={3000} required placeholder="可以打字，也可以用手机输入法语音。" /></label>
    <label>目前执行情况<select disabled={busy} value={execution} onChange={e => { setExecution(e.target.value); setSaved(''); setKey(crypto.randomUUID()) }}>
      <option value="not_started">尚未开始</option><option value="planned">计划执行</option><option value="attempted">已经尝试</option><option value="reported_done">我已经做了</option><option value="unable">有困难暂时做不到</option><option value="unclear">不清楚</option>
    </select></label>
    <label>安排或操作上的困难（如有）<textarea disabled={busy} value={barrier} onChange={e => { setBarrier(e.target.value); setSaved(''); setKey(crypto.randomUUID()) }} maxLength={2000} required={execution === 'unable'} placeholder="例如需要家人协助、时间安排不方便。" /></label>
    <p className="small muted">这里只核实说明和执行安排，不提供实时问诊。身体出现新变化请另行报告；情况紧急请按页面提示就医，不要等线上回复。</p>
    <Link className="btn btn-secondary" to={`/p?mode=follow_up&parent=${encodeURIComponent(n.encounter_id)}&code=${encodeURIComponent(patientCode ?? '')}`}>报告新的身体变化</Link>
    <ErrorBox error={error} />
    {saved ? <p role="status">{saved}</p> : <button className="btn btn-primary" disabled={busy || !text.trim() || (execution === 'unable' && !barrier.trim())}>{busy ? '提交并整理中…' : '提交复述和执行情况'}</button>}
  </form>
}
