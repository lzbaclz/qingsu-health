import { Fragment, useState } from 'react'
import type { Entry, Fact } from '../../api/types'
import { FlagNotes } from '../../components/FlagNotes'
import { FactStatusTag, Tag } from '../../components/Tag'
import { EVIDENCE_KIND, SOURCE, lbl } from '../../labels'

export function FactsTable({ facts, entries, onQuote }: { facts: Fact[]; entries: Entry[]; onQuote: (entryId: string) => void }) {
  const [open, setOpen] = useState<Set<string>>(new Set())
  const [onlyKnown, setOnlyKnown] = useState(true)  // 默认隐藏"未询问"，医生第一眼看到的是有信息的行
  const seqOf = (entryId: string) => entries.find((e) => e.id === entryId)?.seq

  function toggle(key: string) {
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const shown = onlyKnown ? facts.filter((f) => f.status !== 'not_asked') : facts

  return (
    <section className="card">
      <div className="card-head">
        <h2 className="card-title">
          事实与证据 <span className="muted small">{shown.length} / {facts.length} 条 · 点击行展开证据</span>
        </h2>
        <label className="check-inline small">
          <input type="checkbox" checked={onlyKnown} onChange={(e) => setOnlyKnown(e.target.checked)} />
          隐藏未询问
        </label>
      </div>
      <div className="table-scroll">
        <table className="table facts-table">
          <thead>
            <tr>
              <th>事实</th>
              <th>状态</th>
              <th>值</th>
              <th>来源</th>
              <th>版本</th>
              <th className="num">证据</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((f) => {
              const isOpen = open.has(f.key)
              return (
                <Fragment key={f.key}>
                  <tr className={`row-click${isOpen ? ' open' : ''}${f.status === 'conflicting' ? ' row-conflict' : ''}`} onClick={() => toggle(f.key)}>
                    <td>
                      <div>{f.label}</div>
                      <div className="small muted mono">
                        {f.key}
                        {f.required ? ' · 必填' : ''}
                        {f.critical ? ' · 关键' : ''}
                      </div>
                    </td>
                    <td>
                      <FactStatusTag status={f.status} />
                    </td>
                    <td className={f.status === 'conflicting' ? 'text-red' : ''}>
                      {f.value_label}
                      <FlagNotes flags={f.flags} />
                    </td>
                    <td className="small">{lbl(SOURCE, f.source)}</td>
                    <td className="small">
                      v{f.version}
                      {f.patient_confirmed && (
                        <span className="text-ok" title="患者已确认">
                          {' '}
                          ✓
                        </span>
                      )}
                    </td>
                    <td className="num">{f.evidence.length}</td>
                  </tr>
                  {isOpen && (
                    <tr className="evidence-row">
                      <td colSpan={6}>
                        {f.evidence.length === 0 ? (
                          <span className="small muted">无证据（未询问 / 未回答的事实不带值）</span>
                        ) : (
                          <ul className="evidence-list">
                            {f.evidence.map((ev, i) => (
                              <li key={i}>
                                <Tag tone="gray">{lbl(EVIDENCE_KIND, ev.kind)}</Tag>
                                <button
                                  type="button"
                                  className="quote-btn"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    onQuote(ev.entry_id)
                                  }}
                                  title="在原始记录中定位"
                                >
                                  「{ev.quote}」
                                </button>
                                <span className="small muted">
                                  记录 #{seqOf(ev.entry_id) ?? '?'} · <span className="mono">{ev.entry_id}</span>
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
