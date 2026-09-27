import type { Notification } from '../api/types'
import { NOTIFICATION_FLOW, NOTIFICATION_STATUS, fmtTime } from '../labels'
import { Tag } from './Tag'

/** 通知状态流：已发送 ≠ 已看到 ≠ 已理解，三者分开记录。 */
export function NotificationFlow({ n, showContent = true }: { n: Notification; showContent?: boolean }) {
  const idx = NOTIFICATION_FLOW.indexOf(n.status)
  return (
    <div className="delivery">
      {showContent && <p className="delivery-content">{n.content}</p>}
      <ol className="delivery-flow" aria-label="通知状态">
        {NOTIFICATION_FLOW.map((s, i) => {
          const h = n.history.find((x) => x.to === s)
          return (
            <li key={s} className={`delivery-step${i <= idx ? ' reached' : ''}${s === n.status ? ' current' : ''}`}>
              <span className="delivery-name">{NOTIFICATION_STATUS[s]}</span>
              <span className="delivery-meta small muted">{h ? `${fmtTime(h.at)} · ${h.by}` : '—'}</span>
            </li>
          )
        })}
      </ol>
      {n.status === 'failed' && <Tag tone="red">发送失败</Tag>}
      <p className="small muted">站内提供 ≠ 患者看到 ≠ 实际理解；点击确认属于患者自报，不代表已经执行。</p>
    </div>
  )
}
