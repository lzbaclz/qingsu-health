import { InvitePanel } from './InvitePanel'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { doctorApi, errorMessage } from '../api/client'
import type { EncounterBrief } from '../api/types'
import { Empty, ErrorBox, Loading } from '../components/Boxes'
import { EncounterStatusTag, KindTag, SeverityTag, Tag } from '../components/Tag'
import { ENCOUNTER_STATUS, ENCOUNTER_STATUS_ORDER, fmtTime } from '../labels'

export default function EncounterListPage() {
  const nav = useNavigate()
  const [status, setStatus] = useState('')
  const [rows, setRows] = useState<EncounterBrief[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    doctorApi
      .list(status || undefined)
      .then((r) => {
        setRows(r)
        setError(null)
      })
      .catch((e) => setError(errorMessage(e)))
  }, [status])

  useEffect(() => {
    load()
    const timer = window.setInterval(() => { if (!document.hidden) load() }, 15000)
    const onVisible = () => { if (!document.hidden) load() }
    document.addEventListener('visibilitychange', onVisible)
    return () => { window.clearInterval(timer); document.removeEventListener('visibilitychange', onVisible) }
  }, [load])

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>就诊列表</h1>
          <p className="small muted">按医生写好的规则排序：紧急 → 当天联系 → 常规 → 未触发红旗；同一级里等医生核对的在前。点击一行进入详情。</p>
        </div>
        <div className="filter-bar">
          <label>
            状态
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">全部</option>
              {ENCOUNTER_STATUS_ORDER.map((s) => (
                <option key={s} value={s}>
                  {ENCOUNTER_STATUS[s]}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="btn btn-secondary btn-sm" onClick={load}>
            刷新
          </button>
        </div>
      </div>

      <InvitePanel />
      <ErrorBox error={error} />
      {!rows && !error && <Loading />}
      {rows && rows.length === 0 && <Empty text="没有符合条件的就诊记录" />}
      {rows && rows.length > 0 && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>患者编号</th>
                <th>类型</th>
                <th>状态</th>
                <th>紧急程度</th>
                <th>治疗前提醒</th>
                <th className="num">未完成任务</th>
                <th className="num">矛盾</th>
                <th>更新时间</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.id}
                  className={`row-click${r.triage === 'urgent' ? ' row-urgent' : ''}`}
                  tabIndex={0}
                  onClick={() => nav(`/d/e/${r.id}`)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') nav(`/d/e/${r.id}`)
                  }}
                >
                  <td className="mono strong">
                    {r.patient_code ?? '—'}
                    {r.respondent && r.respondent !== 'self' && <div className="small muted">{r.respondent_label}</div>}
                  </td>
                  <td>
                    <KindTag kind={r.kind} />
                  </td>
                  <td>
                    <EncounterStatusTag status={r.status} />
                  </td>
                  <td>
                    <SeverityTag severity={r.triage ?? r.alert_max_severity} />
                    {r.triage_disputed && <span className="small muted"> 患者否认，待电话核实</span>}
                  </td>
                  <td>
                    {(r.recovery_flags ?? []).length === 0 ? (
                      <span className="muted small">—</span>
                    ) : (
                      (r.recovery_flags ?? []).map((f) => (
                        <Tag key={f.rule_id} tone={f.severity === 'same_day' ? 'red' : 'orange'}>
                          {f.slip_line ?? f.label}
                        </Tag>
                      ))
                    )}
                  </td>
                  <td className="num">
                    {r.open_tasks > 0 ? <Tag tone="orange">{r.open_tasks}</Tag> : <span className="muted">0</span>}
                    {(r.overdue_tasks ?? 0) > 0 && <div className="small danger-text">{r.overdue_tasks} 个超时</div>}
                  </td>
                  <td className="num">{r.conflicts > 0 ? <Tag tone="red">{r.conflicts}</Tag> : <span className="muted">0</span>}</td>
                  <td className="small">{fmtTime(r.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
