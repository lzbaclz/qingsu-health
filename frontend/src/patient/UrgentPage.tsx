import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { track } from '../api/client'
import type { Alert } from '../api/types'
import { usePatient } from './PatientContext'

type Action = 'clinic' | 'emergency' | null

/** 文案里写的是哪种动作：提到 120 / 急诊 → 拨打急救；提到门诊 / 电话 → 打给门诊；否则只显示文字（如"明早门诊会联系你"） */
function actionOf(label: string | null | undefined, hasClinicPhone: boolean): Action {
  if (!label) return null
  if (/120|急诊|急救/.test(label)) return 'emergency'
  if (/门诊|电话/.test(label) && hasClinicPhone) return 'clinic'
  return null
}

/** 紧急红旗终止问询后的页面：不再让患者答题。主按钮由"红旗去向 × 现在是否开诊"决定：
 *  门诊停诊时不把"打电话给门诊"放第一（第 1 轮团队评审 · 医学）。 */
export function UrgentActions({ alerts, compact = false }: { alerts: Alert[]; compact?: boolean }) {
  const { id, state } = usePatient()
  const phone = state?.protocol.contact_phone
  const label = state?.protocol.contact_label ?? '门诊电话'
  const emergency = state?.protocol.emergency_phone ?? '120'
  const view = state?.urgent_view ?? null

  function button(text: string, act: Action, primary: boolean) {
    const cls = `btn ${primary ? 'btn-danger' : 'btn-danger-outline'} btn-lg btn-block`
    if (act === 'emergency')
      return (
        <a key={text} className={cls} href={`tel:${emergency}`} onClick={() => track(id, 'urgent_action', { action: 'call_emergency' })}>
          {text}
        </a>
      )
    if (act === 'clinic' && phone)
      return (
        <a key={text} className={cls} href={`tel:${phone}`} onClick={() => track(id, 'urgent_action', { action: 'call_clinic' })}>
          {text}（{label} {phone}）
        </a>
      )
    return (
      <p key={text} className="urgent-next">
        {text}
      </p>
    )
  }

  if (view) {
    return (
      <div className={`urgent-card${compact ? ' compact' : ''}`} role="alert">
        <h1 className="urgent-title">{view.headline}</h1>
        <p className="urgent-lead">
          {view.body} <strong>你不需要再回答其他问题。</strong>
        </p>
        {!compact &&
          alerts.map((a) => (
            <div key={a.id} className="urgent-msg">
              <strong>{a.label}</strong>
              <p>{a.patient_message}</p>
            </div>
          ))}
        <div className="urgent-actions">
          {button(view.primary, actionOf(view.primary, !!phone), true)}
          {view.secondary ? button(view.secondary, actionOf(view.secondary, !!phone), false) : null}
        </div>
        {view.in_service_hours === false && view.next_open && (
          <p className="small urgent-note">门诊现在不在服务时间（{view.service_hours}）。{view.next_open} 开门后，门诊会先联系你确认情况。</p>
        )}
        {view.reassurance && <p className="urgent-reassure">{view.reassurance}</p>}
      </div>
    )
  }

  return (
    <div className={`urgent-card${compact ? ' compact' : ''}`} role="alert">
      <h1 className="urgent-title">{compact ? '你的情况需要尽快联系医生' : '请现在就联系医生'}</h1>
      <p className="urgent-lead">
        根据你刚才的回答，你的情况需要尽快由医生当面评估。<strong>你不需要再回答其他问题。</strong>
      </p>
      {!compact &&
        alerts.map((a) => (
          <div key={a.id} className="urgent-msg">
            <strong>{a.label}</strong>
            <p>{a.patient_message}</p>
          </div>
        ))}
      <div className="urgent-actions">
        {phone ? button(`打电话给门诊`, 'clinic', true) : null}
        {button(`拨打 ${emergency} 急救电话 / 前往就近急诊`, 'emergency', !phone)}
      </div>
      {!phone && <p className="small urgent-note">原型提示：门诊电话尚未配置（协议 scope.contact_phone），上线前由门诊填写。</p>}
    </div>
  )
}

export default function UrgentPage() {
  const { id, state } = usePatient()
  const nav = useNavigate()
  const alerts = state?.stop_alerts ?? []

  useEffect(() => {
    track(id, 'urgent_screen', { alerts: alerts.length })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  if (state && state.stop_reason !== 'urgent_red_flag') {
    return (
      <div className="stack">
        <p className="muted">当前没有需要立即处理的提示。</p>
        <button type="button" className="btn btn-primary btn-block" onClick={() => nav(`/p/e/${id}/questions`, { replace: true })}>
          继续填写
        </button>
      </div>
    )
  }

  return (
    <div className="stack">
      <UrgentActions alerts={alerts} />
      <button
        type="button"
        className="btn btn-secondary btn-block"
        onClick={() => {
          track(id, 'urgent_action', { action: 'submit' })
          nav(`/p/e/${id}/confirm`)
        }}
      >
        把已经填写的内容交给医生
      </button>
      <p className="small muted center">提交只是让医生提前看到你说过的内容，不能代替就医。</p>
    </div>
  )
}
