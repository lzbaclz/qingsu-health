import type { VisitBrief } from '../../api/types'
import { SeverityTag, Tag } from '../../components/Tag'

const KIND_LABEL: Record<string, string> = { disputed: '待核实', conflict: '矛盾', uncertain: '不确定', gap: '未明确' }
const KIND_TONE = { disputed: 'red', conflict: 'red', uncertain: 'orange', gap: 'yellow' } as const

/** 接诊速览：一屏看完——紧急程度、一句话主诉、红旗、面诊要当面确认的几件事。全部是确定性整理，不做诊断。 */
export function VisitBriefCard({ brief, onJump }: { brief: VisitBrief; onJump: (anchor: string) => void }) {
  const tone = brief.triage === 'urgent' ? 'urgent' : brief.triage === 'same_day' ? 'sameday' : 'calm'
  return (
    <section className={`card brief-card brief-${tone}`} aria-label="接诊速览">
      <div className="brief-top">
        <div className="brief-triage">
          {brief.triage ? <SeverityTag severity={brief.triage} /> : <Tag tone="green">未触发红旗</Tag>}
          <span className="brief-triage-label">{brief.triage_label}</span>
        </div>
        <span className="small muted">接诊速览 · 由系统按协议整理，不含诊断</span>
      </div>
      <p className="brief-headline">{brief.headline}</p>
      {brief.note && <p className="small muted">{brief.note}</p>}

      {brief.red_flags.length > 0 && (
        <ul className="plain-list brief-flags">
          {brief.red_flags.map((f, i) => (
            <li key={i}>
              <SeverityTag severity={f.severity} /> <strong>{f.label}</strong>
              {f.disputed ? (
                <Tag tone="red">原话提到、核对时否认：请电话核实</Tag>
              ) : f.notice_shown ? (
                <span className="small muted brief-flag-note">已向患者展示提示</span>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      <div className="brief-confirm">
        <h3 className="sub-title">面诊时要当面确认</h3>
        {brief.confirm_items.length === 0 ? (
          <p className="small muted">关键事实都已明确，没有矛盾或不确定的地方。</p>
        ) : (
          <ol className="brief-list">
            {brief.confirm_items.map((it) => (
              <li key={it.key}>
                <Tag tone={KIND_TONE[it.kind]}>{KIND_LABEL[it.kind]}</Tag> <strong>{it.label}</strong>
                <span className="small muted">　{it.detail}</span>
              </li>
            ))}
          </ol>
        )}
        {brief.confirm_more > 0 && <p className="small muted">另有 {brief.confirm_more} 项，见下方摘要的缺口列表。</p>}
      </div>

      <div className="row wrap brief-actions">
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => onJump('record-draft')}>
          病历初稿
        </button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => onJump('doctor-actions')}>
          核对并确认
        </button>
        {brief.open_tasks > 0 && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => onJump('tasks')}>
            待办任务 {brief.open_tasks}
          </button>
        )}
      </div>
    </section>
  )
}
