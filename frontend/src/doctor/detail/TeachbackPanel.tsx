import { useState } from 'react'
import { doctorApi, errorMessage } from '../../api/client'
import type { TeachbackResponse } from '../../api/types'
import { useStaff } from '../../auth/AuthContext'
import { ErrorBox } from '../../components/Boxes'
import { fmtTime } from '../../labels'

function ResponseCard({ response: r, encounterId, onChanged }: { response: TeachbackResponse; encounterId: string; onChanged: () => void }) {
  const { user } = useStaff()
  const [result, setResult] = useState('unclear')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return <article className="sub-card stack-sm">
    <strong>计划第 {r.plan_version} 版 · {r.is_current_plan ? '当前计划' : '历史计划，不代表理解新版'}</strong>
    <blockquote>患者复述：{r.response_text}</blockquote>
    <div>{r.execution_label} · 困难：{r.barrier_text || '未填写'}</div>
    <p className="small muted">{r.analysis.source === 'model' ? `模型初筛（${r.analysis.provider}），待人工判断` : r.analysis.source === 'literal_only' ? '离线模式仅做逐字对照，语义由医护核实' : '模型结果不可用或尚未完成，请人工核实'} · {fmtTime(r.created_at)}</p>
    {r.analysis.items?.map(item => <div className="stack-sm" key={item.point_id}>
      <div>批准要点：{item.point_text}</div><div>对应原话：{item.response_quote || '未找到可引用的对应表达'}</div><span className="small">{item.label}</span>
    </div>)}
    {r.review && <p className="small">人工记录：{r.review.result === 'aligned' ? '本次表达已核实' : '仍需解释或核实'} · {r.review.note} · {fmtTime(r.review.at)}</p>}
    {(user.role === 'doctor' || user.role === 'nurse') && <form className="stack-sm" onSubmit={async e => {
      e.preventDefault(); setBusy(true); setError(null)
      try { await doctorApi.reviewTeachback(encounterId, r.id, { result, note }); onChanged() }
      catch (err) { setError(errorMessage(err)) }
      finally { setBusy(false) }
    }}>
      <label>人工核实结果<select disabled={busy} value={result} onChange={e => setResult(e.target.value)}><option value="unclear">尚不明确，继续核实</option><option value="needs_explanation">需要再次解释</option><option value="aligned">本次复述与要点一致</option></select></label>
      <label>依据与后续安排<textarea disabled={busy} value={note} onChange={e => setNote(e.target.value)} required maxLength={2000} /></label>
      <button className="btn btn-secondary" disabled={busy || !note.trim()}>{busy ? '保存中…' : '保存人工核实'}</button>
    </form>}
    <p className="small muted">表达核实不等于已经执行；患者自报执行也不等于治疗效果。</p>
    <ErrorBox error={error} />
  </article>
}

export function TeachbackPanel({ responses, encounterId, onChanged }: { responses: TeachbackResponse[]; encounterId: string; onChanged: () => void }) {
  if (!responses.length) return null
  return <section className="card stack"><h2 className="card-title">计划复述与执行困难</h2>{responses.map(r => <ResponseCard key={`${r.id}:${r.review?.at}`} response={r} encounterId={encounterId} onChanged={onChanged} />)}</section>
}
