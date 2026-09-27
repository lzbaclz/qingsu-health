import type { FactFlag } from '../api/types'

/** 患者原话里的药名/剂量/诊断性表述或疑似指令：只提醒"这是原话，不是系统建议"，不改写、不隐藏。 */
export function FlagNotes({ flags, print = false }: { flags?: FactFlag[]; print?: boolean }) {
  if (!flags || flags.length === 0) return null
  if (print) {
    return (
      <>
        {flags.map((f) => (
          <div key={f.code} className="print-flag">
            〔{f.label}〕
          </div>
        ))}
      </>
    )
  }
  return (
    <span className="flag-notes">
      {flags.map((f) => (
        <span key={f.code} className="flag-note" title={f.label}>
          ⚑ {f.label}
        </span>
      ))}
    </span>
  )
}
