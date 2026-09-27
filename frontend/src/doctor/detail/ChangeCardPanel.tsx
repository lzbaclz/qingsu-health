import type { ChangeCard, ChangeItem } from '../../api/types'
import { NotificationFlow } from '../../components/NotificationFlow'
import { FactStatusTag, SeverityTag, Tag } from '../../components/Tag'
import { fmtTime, type Tone } from '../../labels'

const GROUPS: { key: keyof Pick<ChangeCard, 'changed' | 'new' | 'unconfirmed' | 'unchanged'>; title: string; tone: Tone; hint: string }[] = [
  { key: 'changed', title: '有变化', tone: 'orange', hint: '与上次已明确的值不同' },
  { key: 'new', title: '新增记录', tone: 'blue', hint: '上次未记录不代表以前没有；起病与变化见病程事件核实' },
  { key: 'unconfirmed', title: '未确认', tone: 'gray', hint: '本次未问或未答，不等于没有' },
  { key: 'unchanged', title: '未变化', tone: 'green', hint: '与上次一致' },
]

function ChangeRow({ item, onQuote }: { item: ChangeItem; onQuote: (entryId: string) => void }) {
  return (
    <li className="change-row">
      <div className="change-label">{item.label}</div>
      <div className="change-vals">
        <span className="change-before">
          {item.before}
          {item.before_status && <FactStatusTag status={item.before_status} />}
        </span>
        <span className="change-arrow">→</span>
        <span className="change-after">
          <strong>{item.after}</strong>
          <FactStatusTag status={item.after_status} />
        </span>
      </div>
      {item.evidence.length > 0 && (
        <div className="change-ev">
          {item.evidence.map((ev, i) => (
            <button key={i} type="button" className="quote-btn" onClick={() => onQuote(ev.entry_id)} title="在原始记录中定位">
              「{ev.quote}」
            </button>
          ))}
        </div>
      )}
    </li>
  )
}

export function ChangeCardPanel({ card, onQuote }: { card: ChangeCard; onQuote: (entryId: string) => void }) {
  return (
    <section className="card change-card">
      <div className="card-head">
        <h2 className="card-title">变化卡：相比上次变了什么</h2>
        <span className="small muted">上次就诊 {card.parent_encounter_id} · 医生确认于 {fmtTime(card.parent_confirmed_at)}</span>
      </div>
      <div className="change-groups">
        {GROUPS.map((g) => {
          const items = card[g.key]
          return (
            <div key={g.key} className={`change-group tone-${g.tone}`}>
              <h3 className="change-group-title">
                <Tag tone={g.tone}>{g.title}</Tag>
                <span className="muted small">{items.length} 项 · {g.hint}</span>
              </h3>
              {items.length === 0 ? (
                <p className="muted small">无</p>
              ) : (
                <ul className="change-list">
                  {items.map((it) => (
                    <ChangeRow key={it.key} item={it} onQuote={onQuote} />
                  ))}
                </ul>
              )}
            </div>
          )
        })}
      </div>

      {card.triggered.length > 0 && (
        <div className="sub-card">
          <h3 className="sub-title">本次随访触发的红旗</h3>
          <ul className="plain-list">
            {card.triggered.map((a) => (
              <li key={a.id} className="row wrap">
                <SeverityTag severity={a.severity} />
                <strong>{a.label}</strong>
                <span className="small muted">{a.notice_shown ? '已向患者展示提示' : '仅供医生复核'}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid-2">
        <div className="sub-card">
          <h3 className="sub-title">上次医嘱通知的状态</h3>
          {card.plan_delivery.length === 0 ? (
            <p className="muted small">上次没有发送医嘱通知。</p>
          ) : (
            card.plan_delivery.map((n) => <NotificationFlow key={n.id} n={n} />)
          )}
        </div>
        <div className="sub-card">
          <h3 className="sub-title">上次随访计划</h3>
          {card.followup_plan ? (
            <dl className="kv kv-compact">
              <div>
                <dt>间隔</dt>
                <dd>{card.followup_plan.interval_days} 天</dd>
              </div>
              <div>
                <dt>设置人 / 时间</dt>
                <dd>
                  {card.followup_plan.set_by} · {fmtTime(card.followup_plan.set_at)}
                </dd>
              </div>
              <div>
                <dt>医生写给患者的说明</dt>
                <dd>{card.followup_plan.patient_message}</dd>
              </div>
              <div>
                <dt>重点对比事实</dt>
                <dd className="small muted mono">{card.followup_plan.watch_facts.join(', ')}</dd>
              </div>
            </dl>
          ) : (
            <p className="muted small">上次未设置随访计划。</p>
          )}
        </div>
      </div>
    </section>
  )
}
