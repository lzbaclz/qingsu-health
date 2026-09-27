import { useState } from 'react'
import type { RecordDraft } from '../../api/types'

/** 门诊病历初稿：只用患者确认过的事实拼成主诉 / 现病史 / 阴性 / 未明确；医生核对后复制到自己的病历系统。 */
export function RecordDraftPanel({ draft }: { draft: RecordDraft }) {
  const [copied, setCopied] = useState(false)
  const [open, setOpen] = useState(false)
  const first = draft.sections[0]

  async function copy() {
    try {
      await navigator.clipboard.writeText(draft.text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setOpen(true)
    }
  }

  return (
    <section className="card" id="record-draft">
      <div className="card-head">
        <h2 className="card-title">
          病历初稿 <span className="muted small">{draft.provisional ? '患者尚未确认，临时整理' : '根据患者确认的信息整理'}</span>
        </h2>
        <div className="row">
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setOpen((v) => !v)}>
            {open ? '收起' : '展开全文'}
          </button>
          <button type="button" className="btn btn-primary btn-sm" onClick={() => void copy()}>
            {copied ? '已复制' : '复制全文'}
          </button>
        </div>
      </div>
      {!open && first && (
        <p className="record-preview">
          【{first.title}】{first.text}
        </p>
      )}
      {open && (
        <div className="record-draft">
          {draft.sections.map((s) => (
            <p key={s.title}>
              <strong>【{s.title}】</strong>
              {s.text}
            </p>
          ))}
          <p className="small muted">{draft.footer}</p>
        </div>
      )}
    </section>
  )
}
