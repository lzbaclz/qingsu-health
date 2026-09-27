import { useState } from 'react'
import { errorMessage, protocolApi } from '../api/client'
import type { ProtocolDetail } from '../api/types'
import { ErrorBox } from '../components/Boxes'

interface PreviewReport {
  base: { version: string; sha256: string }; candidate: { version: string; sha256: string }
  case_count: number; changed_count: number; scope: string
  configuration_changes: { path: string; before: unknown; after: unknown }[]
  cases: { id: string; changed: boolean; before: unknown; after: unknown }[]
}

export function ProtocolPreview({ protocol }: { protocol: ProtocolDetail }) {
  const [candidate, setCandidate] = useState(() => JSON.stringify(protocol, null, 2))
  const [cases, setCases] = useState(JSON.stringify([
    { id: '尚未询问', facts: {} },
    { id: '排尿控制改变', facts: { bladder_change: { status: 'present', value: true } } },
    { id: '明确否认', facts: { bladder_change: { status: 'denied', value: false } } },
  ], null, 2))
  const [result, setResult] = useState<PreviewReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function run() {
    setBusy(true); setError(null); setResult(null)
    try { setResult(await protocolApi.preview(protocol.protocol_id, candidate, JSON.parse(cases)) as PreviewReport) }
    catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }
  return <section className="card stack"><h2 className="card-title">协议变更影响预演</h2>
    <p className="small muted">在独立模拟环境比较下一问、红旗提醒和处理角色。输入候选 YAML 或 JSON 及模拟事实；本操作不会发布协议。示例事实名称需与所选协议一致。</p>
    <details><summary>编辑候选与模拟情境</summary><div className="grid-2">
      <label>候选协议<textarea aria-label="候选协议" rows={18} value={candidate} onChange={e => setCandidate(e.target.value)} /></label>
      <label>模拟情境（JSON）<textarea aria-label="模拟情境" rows={18} value={cases} onChange={e => setCases(e.target.value)} /></label>
    </div></details><button className="btn btn-secondary" type="button" disabled={busy} onClick={() => void run()}>{busy ? '比较中…' : '运行只读预演'}</button>
    <ErrorBox error={error} />{result && <div className="stack"><p>{result.case_count} 个情境，{result.changed_count} 个当前状态结果有变化。{result.scope}</p>
      <p className="small mono">基线 v{result.base.version}：{result.base.sha256}<br />候选 v{result.candidate.version}：{result.candidate.sha256}</p>
      {result.configuration_changes.map(c => <details key={c.path}><summary>配置变更：{c.path}</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(c, null, 2)}</pre></details>)}
      {result.cases.map(c => <details key={c.id}><summary>{c.id} · {c.changed ? '有变化' : '无变化'}</summary><div className="grid-2"><div><h3>基线</h3><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(c.before, null, 2)}</pre></div><div><h3>候选</h3><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(c.after, null, 2)}</pre></div></div></details>)}
    </div>}
  </section>
}
