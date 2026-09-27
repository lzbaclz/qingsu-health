import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { doctorApi, errorMessage } from '../api/client'
import type { DoctorView, Fact } from '../api/types'
import { ErrorBox, Loading } from '../components/Boxes'
import { FlagNotes } from '../components/FlagNotes'
import { ENCOUNTER_KIND, ENCOUNTER_STATUS, FACT_STATUS, SEVERITY, fmtTime, lbl, providerLabel } from '../labels'

function Rows({ title, facts, withQuotes = true }: { title: string; facts: Fact[]; withQuotes?: boolean }) {
  if (facts.length === 0) return null
  return (
    <section className="print-section">
      <h2>{title}</h2>
      <table className="print-table">
        <tbody>
          {facts.map((f) => (
            <tr key={f.key}>
              <th>{f.label}</th>
              <td>
                {f.value_label}
                <FlagNotes flags={f.flags} print />
                {withQuotes && f.evidence.length > 0 && (
                  <div className="print-quote">依据：{f.evidence.slice(0, 2).map((e) => `「${e.quote}」`).join(' ')}</div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

/** 打印 / 导出 PDF：给门诊存档或纸质交接用的一页摘要（浏览器"打印 → 存储为 PDF"）。 */
export default function PrintPage() {
  const { id = '' } = useParams()
  const [view, setView] = useState<DoctorView | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    doctorApi
      .get(id)
      .then((v) => {
        setView(v)
        document.title = `就诊摘要 ${v.encounter.patient_code ?? ''}`
      })
      .catch((e) => setError(errorMessage(e)))
  }, [id])

  if (error) return <ErrorBox error={error} />
  if (!view) return <Loading />
  const enc = view.encounter
  const s = view.summary
  const c = s?.content

  return (
    <div className="print-page">
      <div className="print-toolbar no-print">
        <button type="button" className="btn btn-primary" onClick={() => window.print()}>
          打印 / 存储为 PDF
        </button>
        <span className="small muted">打印对话框里选择"存储为 PDF"即可导出。</span>
      </div>
      <header className="print-header">
        <div>
          <h1>就诊前症状摘要</h1>
          <div className="small">
            患者编号 <strong>{enc.patient_code ?? '—'}</strong> · {lbl(ENCOUNTER_KIND, enc.kind)} · {lbl(ENCOUNTER_STATUS, enc.status)}
          </div>
        </div>
        <div className="small right">
          <div>记录编号 {enc.id}</div>
          <div>
            协议 {view.protocol.id} v{view.protocol.version}（{view.protocol.status === 'draft' ? '尚未临床审核' : view.protocol.status}）
          </div>
          <div>患者确认 {fmtTime(enc.patient_confirmed_at)} · 医生确认 {fmtTime(enc.doctor_confirmed_at)}</div>
        </div>
      </header>

      {!c ? (
        <p>患者尚未确认，暂无摘要。</p>
      ) : (
        <>
          {s?.provisional && <p className="print-warn">患者尚未确认，以下为临时整理。</p>}
          <section className="print-section">
            <h2>主诉与时间线</h2>
            <p className="print-headline">{c.headline}</p>
            <p className="small">
              身体图 · 主要：{c.body_map.primary.map((r) => r.label).join('、') || '无'}；放射：
              {c.body_map.radiation.map((r) => r.label).join('、') || '无'}；侧别：{c.body_map.side}
            </p>
          </section>
          {c.alerts.length > 0 && (
            <section className="print-section print-alerts">
              <h2>红旗</h2>
              <ul>
                {c.alerts.map((a) => (
                  <li key={a.id}>
                    [{lbl(SEVERITY, a.severity)}] {a.label}
                  </li>
                ))}
              </ul>
            </section>
          )}
          <Rows title="已明确" facts={c.key_facts} />
          {(c.disputed ?? []).length > 0 && (
            <section className="print-section">
              <h2>待核实（原话提到、患者核对时否认的红旗）</h2>
              <ul>
                {(c.disputed ?? []).map((x) => (
                  <li key={x.key}>
                    {x.label}：原话「{x.quotes.join('」「')}」；{x.now}。面诊请当面复核。
                  </li>
                ))}
              </ul>
            </section>
          )}
          <Rows title="矛盾（未澄清）" facts={c.conflicts} />
          <Rows title="表达不确定" facts={c.uncertain} />
          <Rows title="明确否认" facts={c.denied} withQuotes={false} />
          {c.gaps.length > 0 && (
            <section className="print-section">
              <h2>缺口（关键事实未明确，就诊时补问）</h2>
              <p>{c.gaps.map((g) => `${g.label}（${lbl(FACT_STATUS, g.status)}）`).join('；')}</p>
            </section>
          )}
          <section className="print-section">
            <h2>叙述</h2>
            <p>{c.narrative}</p>
            <p className="small muted">叙述：{providerLabel(c.narrative_provider)}；仅整理患者表达，未做医学判断。</p>
          </section>
          {c.doctor_edits?.doctor_notes && (
            <section className="print-section">
              <h2>医生备注</h2>
              <p>{c.doctor_edits.doctor_notes}</p>
            </section>
          )}
          {c.quotes.length > 0 && (
            <section className="print-section">
              <h2>患者原话</h2>
              {c.quotes.map((q) => (
                <div key={q.entry_id}>
                  <p>「{q.text}」</p>
                  <FlagNotes flags={q.flags} print />
                </div>
              ))}
            </section>
          )}
        </>
      )}
      <footer className="print-footer small">
        体迹 AI 原型生成 · 本摘要只整理患者表达，不含诊断、处方或治疗建议 · 打印时间 {fmtTime(new Date().toISOString())}
      </footer>
    </div>
  )
}
