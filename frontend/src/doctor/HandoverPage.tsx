import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { doctorApi, errorMessage } from '../api/client'
import type { HandoverSheet, Task } from '../api/types'
import { ErrorBox, Loading } from '../components/Boxes'
import { TASK_KIND, TASK_STATUS, fmtTime, lbl } from '../labels'

const GROUPS: { title: string; pick: (t: Task) => boolean }[] = [
  { title: '已超时', pick: (t) => !!t.overdue },
  { title: '停诊时段的红旗：开门第一件事回访', pick: (t) => !t.overdue && (t.kind === 'after_hours_callback' || (t.kind === 'red_flag_review' && t.severity === 'urgent')) },
  { title: '当天要联系的红旗', pick: (t) => !t.overdue && t.kind === 'red_flag_review' && t.severity !== 'urgent' },
  { title: '治疗前请医生复评 / 恢复提醒', pick: (t) => !t.overdue && t.kind === 'recovery_review' },
  { title: '到期未签到：电话回访', pick: (t) => !t.overdue && t.kind === 'no_response' },
]

/** 早班交接单（第 1 轮团队评审 · 工业设计 / 医学）：前一晚与超时的事项，谁来做、几点前，打印后逐条打勾。 */
export default function HandoverPage() {
  const [sheet, setSheet] = useState<HandoverSheet | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    doctorApi
      .handover()
      .then((s) => {
        setSheet(s)
        document.title = `早班交接单 ${s.generated_at_local}`
      })
      .catch((e) => setError(errorMessage(e)))
  }, [])

  if (error) return <ErrorBox error={error} />
  if (!sheet) return <Loading />
  const used = new Set<string>()

  return (
    <div className="print-page">
      <div className="print-toolbar no-print">
        <button type="button" className="btn btn-primary" onClick={() => window.print()}>
          打印 / 存储为 PDF
        </button>
        <Link to="/d/tasks" className="btn btn-secondary">
          回到任务看板
        </Link>
      </div>
      <header className="print-header">
        <h1>早班交接单</h1>
        <div className="right small">生成于 {sheet.generated_at_local}（门诊本地时间）</div>
      </header>
      <p className="small">每条都写明谁来做、几点前。处理完请在系统里结案：红旗任务要填联系结果和给出的建议。</p>
      {sheet.tasks.length === 0 && <p>没有待交接的事项。</p>}
      {GROUPS.map((g) => {
        const rows = sheet.tasks.filter((t) => !used.has(t.id) && g.pick(t))
        rows.forEach((t) => used.add(t.id))
        if (rows.length === 0) return null
        return (
          <section key={g.title} className="print-section">
            <h2>
              {g.title}（{rows.length}）
            </h2>
            <table className="print-table handover-table">
              <tbody>
                {rows.map((t) => (
                  <tr key={t.id} className={t.overdue ? 'overdue' : ''}>
                    <td className="handover-box">□</td>
                    <th>
                      {t.encounter?.patient_code ?? '—'}
                      <div className="small muted">{lbl(TASK_KIND, t.kind)}</div>
                    </th>
                    <td>
                      <strong>{t.title}</strong>
                      {typeof t.detail?.slip_line === 'string' && <div>{t.detail.slip_line}</div>}
                      <div className="small">
                        {t.assignee_role_label ?? '未派'} · {t.due_local ? `${t.due_local} 前` : String(t.detail?.due_label ?? '无时限')} · 当前：
                        {lbl(TASK_STATUS, t.status)} · 创建 {fmtTime(t.created_at)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )
      })}
      <footer className="print-footer small">体迹 AI · 原型演示 · 派单角色与时限来自协议（模拟临床稿，待医生审定）</footer>
    </div>
  )
}
