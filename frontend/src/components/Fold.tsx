import { useState, type ReactNode } from 'react'

/** 可折叠区块：默认收起的细节（事实表、验收检查、版本、问答记录），医生需要时再点开。 */
export function Fold({
  title,
  hint,
  defaultOpen = false,
  children,
}: {
  title: string
  hint?: string
  defaultOpen?: boolean
  children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className={`fold${open ? ' open' : ''}`}>
      <button type="button" className="fold-head" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <span className="fold-caret" aria-hidden="true">
          {open ? '▾' : '▸'}
        </span>
        <span className="fold-title">{title}</span>
        {hint && <span className="small muted">{hint}</span>}
      </button>
      {open && <div className="fold-body">{children}</div>}
    </div>
  )
}
