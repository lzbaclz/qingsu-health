import type { Alert } from '../api/types'
import { SEVERITY } from '../labels'

/**
 * 协议批准的紧急提示：固定在页面顶部、红色、不可关闭。
 * 只展示 notice_shown 为 true 的红旗（task_only 的红旗文案仅供医生复核，不能给患者看）。
 */
export function NoticeBanner({ notices }: { notices: Alert[] }) {
  const shown = notices.filter((n) => n.notice_shown)
  if (shown.length === 0) return null
  return (
    <div className="notice-banner" role="alert" aria-live="assertive">
      {shown.map((n) => (
        <div key={n.id} className={`notice-item sev-${n.severity}`}>
          <div className="notice-head">
            <span className="notice-badge">{SEVERITY[n.severity] ?? n.severity}提示</span>
            <span className="notice-label">{n.label}</span>
          </div>
          <p className="notice-text">{n.patient_message}</p>
          {n.patient_disputed && <p className="notice-note">你已说明这条整理不对。提示仍保留：如果确有上述情况，请立即就医；医生也会复核。</p>}
        </div>
      ))}
    </div>
  )
}
