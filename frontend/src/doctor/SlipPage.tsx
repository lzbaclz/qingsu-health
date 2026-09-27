import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { doctorApi, errorMessage } from '../api/client'
import type { DoctorView } from '../api/types'
import { ErrorBox, Loading } from '../components/Boxes'
import { fmtTime } from '../labels'

/** 接诊小票（80mm 热敏纸，第 1 轮团队评审 · 工业设计）：跟着患者走到治疗床边。
 *  治疗师不用登录任何系统，看一眼就知道今天先别上手、面诊要确认什么。只放确定性整理的内容，不含诊断。 */
export default function SlipPage() {
  const { id = '' } = useParams()
  const [view, setView] = useState<DoctorView | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    doctorApi
      .get(id)
      .then((v) => {
        setView(v)
        document.title = `接诊小票 ${v.encounter.patient_code ?? ''}`
      })
      .catch((e) => setError(errorMessage(e)))
  }, [id])

  if (error) return <ErrorBox error={error} />
  if (!view) return <Loading />
  const enc = view.encounter
  const b = view.brief
  const t = view.trajectory
  const flags = enc.recovery_flags ?? []
  const main = t?.outcomes.find((o) => !o.categorical && o.baseline != null)
  const quotes = view.entries.filter((e) => e.kind === 'free_text').map((e) => String((e.payload as { text?: string }).text ?? ''))
  const firstQuote = quotes[0] ?? ''

  return (
    <div className="slip-wrap">
      <div className="no-print slip-toolbar">
        <button type="button" className="btn btn-primary" onClick={() => window.print()}>
          打印小票（80mm）
        </button>
        <span className="small muted">浏览器打印时纸张选 80mm 或"适合宽度"；也可存成 PDF。</span>
      </div>
      <article className="slip">
        <header className="slip-head">
          <strong>体迹 · 接诊小票</strong>
          <span>{fmtTime(enc.patient_confirmed_at ?? enc.created_at)}</span>
        </header>
        <div className={`slip-triage triage-${b?.triage ?? 'none'}`}>{b?.triage_label ?? '未触发红旗'}</div>
        <div className="slip-line">
          患者 <strong>{enc.patient_code ?? '—'}</strong> · {enc.kind === 'follow_up' ? `签到（第 ${(t?.visit_index ?? 0) + 1} 次记录）` : '首诊'}
          {enc.respondent && enc.respondent !== 'self' ? ` · ${enc.respondent_label}` : ''}
        </div>
        {b?.headline && <p className="slip-headline">{b.headline}</p>}
        {enc.kind === 'follow_up' && main && (
          <p className="slip-traj">
            {main.label}：首诊 {main.baseline} → 本次 {main.current ?? '?'}
            {main.delta != null ? `（${main.delta > 0 ? '↑' : main.delta < 0 ? '↓' : ''}${Math.abs(main.delta)}）` : ''}
          </p>
        )}
        {flags.map((f) => (
          <p key={f.rule_id} className="slip-stop">
            ▲ {f.slip_line ?? f.label}
          </p>
        ))}
        {b && b.red_flags.length > 0 && (
          <section className="slip-sec">
            <h3>红旗</h3>
            <ul>
              {b.red_flags.map((r, i) => (
                <li key={i}>
                  {r.label}
                  {r.disputed ? '（患者核对时否认，待电话核实）' : ''}
                </li>
              ))}
            </ul>
          </section>
        )}
        {b && b.confirm_items.length > 0 && (
          <section className="slip-sec">
            <h3>面诊当面确认</h3>
            <ul className="slip-checks">
              {b.confirm_items.map((c) => (
                <li key={c.key}>
                  □ {c.label}：{c.detail}
                </li>
              ))}
            </ul>
          </section>
        )}
        {firstQuote && (
          <section className="slip-sec">
            <h3>原话</h3>
            <p className="slip-quote">「{firstQuote.length > 60 ? `${firstQuote.slice(0, 60)}…` : firstQuote}」</p>
          </section>
        )}
        <footer className="slip-foot">
          不含诊断 · 每条信息可在系统里点回原话 · 原型演示（模拟数据）
          <br />
          记录号 {enc.id.slice(-6)}
        </footer>
      </article>
    </div>
  )
}
