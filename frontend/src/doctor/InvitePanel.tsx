import { useState } from 'react'
import { authApi, errorMessage } from '../api/client'
import { ErrorBox } from '../components/Boxes'
import { fmtTime } from '../labels'

export function InvitePanel({ parentId }: { parentId?: string }) {
  const [code, setCode] = useState('')
  const [link, setLink] = useState('')
  const [expires, setExpires] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  return <section className="card stack-sm">
    <h2 className="card-title">{parentId ? '随访访问邀请' : '患者采集邀请'}</h2>
    {!parentId && <label>患者编号（留空自动分配）<input className="input" value={code} onChange={e => setCode(e.target.value)} maxLength={80} /></label>}
    <button type="button" className="btn btn-secondary" disabled={busy} onClick={async () => {
      setBusy(true); setError(null)
      try {
        const r = await authApi.invite({ patient_code: code.trim() || undefined, parent_encounter_id: parentId })
        setLink(window.location.origin + r.path); setExpires(fmtTime(r.expires_at))
      } catch (e) { setError(errorMessage(e)) }
      finally { setBusy(false) }
    }}>{busy ? '生成中…' : '生成一次性邀请'}</button>
    <ErrorBox error={error} />
    {link && <div className="stack-sm">
      <label>仅发给这位患者<input className="input" readOnly value={link} onFocus={e => e.target.select()} /></label>
      <div className="row wrap"><button className="btn btn-secondary" onClick={() => navigator.clipboard.writeText(link).catch(() => setError('请选中上方链接后复制'))}>复制邀请</button><a className="btn btn-secondary" href={link} target="_blank" rel="noreferrer">打开邀请</a></div>
      <p className="small muted">有效至 {expires}。首次开始后失效；已有访问会话可继续填写。不要公开转发。</p>
      {parentId && <img width={160} height={160} src={`/api/qr.svg?data=${encodeURIComponent(link)}`} alt="患者一次性随访邀请二维码" />}
    </div>}
  </section>
}
