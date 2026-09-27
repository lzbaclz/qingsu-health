import type { Verification } from '../../api/types'
import { Tag } from '../../components/Tag'
import { CHECK_SEVERITY, fmtTime, lbl } from '../../labels'

export function VerificationPanel({ verification }: { verification: Verification | null }) {
  if (!verification) {
    return (
      <section className="card">
        <h2 className="card-title">验收检查</h2>
        <p className="muted">尚无验收报告：患者确认后系统会生成摘要并运行验收检查。</p>
      </section>
    )
  }
  const failed = verification.checks.filter((c) => !c.passed)
  return (
    <section className="card">
      <div className="card-head">
        <h2 className="card-title">验收检查</h2>
        <span className={`verdict ${verification.passed ? 'pass' : 'fail'}`}>{verification.passed ? '通过' : '未通过'}</span>
      </div>
      <p className="small muted">
        验收证明的是"指定约束得到满足"，不是"医学判断正确"。总体通过 = 没有关键项失败。
        {failed.length > 0 ? ` 当前 ${failed.length} 项未通过。` : ''} 生成于 {fmtTime(verification.created_at)}。
      </p>
      <ul className="check-list">
        {verification.checks.map((c) => (
          <li key={c.id} className={`check ${c.passed ? 'pass' : 'fail'}`}>
            <div className="check-head">
              <span className="check-mark" aria-label={c.passed ? '通过' : '未通过'}>
                {c.passed ? '✓' : '✗'}
              </span>
              <span className="mono small check-id">{c.id}</span>
              <span className="check-label">{c.label}</span>
              <Tag tone={c.severity === 'critical' ? 'red' : c.severity === 'major' ? 'orange' : 'gray'}>{lbl(CHECK_SEVERITY, c.severity)}</Tag>
            </div>
            {!c.passed && (
              <ul className="check-details">
                {c.details.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
