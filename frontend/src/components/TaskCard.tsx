import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { doctorApi, errorMessage } from '../api/client'
import type { ClosureSpec, Task, TaskStatus } from '../api/types'
import { TASK_KIND, TASK_STATUS, fmtTime, lbl } from '../labels'
import { ErrorBox } from './Boxes'
import { Tag, TaskStatusTag } from './Tag'

const TRANSITION_VERB: Record<TaskStatus, string> = {
  unviewed: '标记未查看',
  viewed: '标记已查看',
  contacted: '已联系患者',
  pending: '待进一步处理',
  escalated: '升级',
  completed: '完成',
}

export function TaskCard({
  task,
  actor,
  onChanged,
  showEncounter = false,
}: {
  task: Task
  actor: string
  onChanged: () => void
  showEncounter?: boolean
}) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  // 红旗任务结案：必须填处置记录（联系上没有、给了什么建议）；联系不上要至少两次尝试
  const [closing, setClosing] = useState(false)
  const [spec, setSpec] = useState<ClosureSpec | null>(null)
  const [reached, setReached] = useState('')
  const attempts = Array.isArray(task.detail?.contact_attempts) ? task.detail.contact_attempts.length : 0
  const [contactResult, setContactResult] = useState<'reached' | 'unreached' | 'in_person'>('unreached')
  const [advice, setAdvice] = useState('')
  const [reason, setReason] = useState('')

  useEffect(() => {
    if (closing && !spec) {
      doctorApi
        .taskClosureSpec(task.id)
        .then(setSpec)
        .catch((e) => setError(errorMessage(e)))
    }
  }, [closing, spec, task.id])

  async function go(to: TaskStatus) {
    if (to === 'completed' && task.needs_closure && !closing) {
      setClosing(true)
      return
    }
    setBusy(true)
    setError(null)
    try {
      await doctorApi.transition(task.id, {
        actor,
        to,
        note: note.trim() || undefined,
        closure: to === 'completed' && task.needs_closure ? { reached, advice: advice || undefined, reason: reason.trim() || undefined, note: note.trim() } : undefined,
      })
      setNote('')
      setClosing(false)
      onChanged()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const reachedOpt = spec?.reached.options.find((o) => o.value === reached)
  const adviceOpt = spec?.advice.options.find((o) => o.value === advice)

  return (
    <div className={`task-card status-${task.status}${task.overdue ? ' overdue' : ''}`}>
      <div className="row wrap">
        <TaskStatusTag status={task.status} />
        <Tag tone="gray">{lbl(TASK_KIND, task.kind)}</Tag>
        {task.overdue && <Tag tone="red">已超时</Tag>}
      </div>
      <div className="task-title">{task.title}</div>
      {Boolean(task.assignee_role_label || task.due_local || task.detail?.due_label) && (
        <div className="task-due">
          {task.assignee_role_label ?? '未派'} · {task.due_local ? `${task.due_local} 前` : String(task.detail?.due_label ?? '')}
          {task.due_local && task.detail?.due_label ? `（${String(task.detail.due_label)}）` : ''}
        </div>
      )}
      {typeof task.detail?.slip_line === 'string' && <div className="task-slip">{task.detail.slip_line}</div>}
      {task.closure && (
        <div className="small task-closure">
          结案记录：{task.closure.reached_label}
          {task.closure.attempts > 1 ? `（尝试 ${task.closure.attempts} 次）` : ''}
          {task.closure.advice_label ? ` · ${task.closure.advice_label}` : ''}
          {task.closure.reason ? ` · 理由：${task.closure.reason}` : ''} · {task.closure.by}
        </div>
      )}
      {showEncounter && (
        <div className="small">
          患者 <span className="mono strong">{task.encounter?.patient_code ?? '—'}</span> ·{' '}
          <Link to={`/d/e/${task.encounter_id}`}>查看就诊</Link>
        </div>
      )}
      <div className="small muted">
        负责人：{task.assignee ?? '未分配'} · 创建 {fmtTime(task.created_at)}
      </div>
      <div className="small muted">
        站外通知：{task.deliveries?.some(d => d.state === 'failed') ? '失败，需手动联系负责人' : task.deliveries?.some(d => d.state === 'delivered') ? '门诊通道已接收，仍需医护接手' : '尚无送达记录，请在看板处理'}
      </div>
      <button type="button" className="link-btn small" onClick={() => setShowHistory((s) => !s)}>
        {showHistory ? '收起历史' : `历史（${task.history.length}）`}
      </button>
      {showHistory && (
        <ul className="history small">
          {task.history.map((h, i) => (
            <li key={i}>
              {fmtTime(h.at)} · {h.by} → {lbl(TASK_STATUS, h.to)}
              {h.note ? `（${h.note}）` : ''}
            </li>
          ))}
        </ul>
      )}
      {task.allowed_transitions.length > 0 && (
        <div className="task-actions">
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="备注（可选）" className="input-sm" />
          {task.needs_closure && <div className="stack-sm">
            <label>联系结果<select value={contactResult} onChange={e => setContactResult(e.target.value as typeof contactResult)}>
              <option value="unreached">未接通</option><option value="reached">已接通</option><option value="in_person">当面处理</option>
            </select></label>
            <button className="btn btn-secondary btn-sm" disabled={busy || !note.trim()} onClick={async () => {
              setBusy(true); setError(null)
              try { await doctorApi.contactAttempt(task.id, contactResult, note.trim()); onChanged() }
              catch (e) { setError(errorMessage(e)) }
              finally { setBusy(false) }
            }}>记录联系尝试（需备注）</button>
            <span className="small muted">已记录 {attempts} 次；时间和登录身份自动保存。此记录是医护自报，不是通话平台回执。</span>
          </div>}
          <div className="row wrap">
            {task.allowed_transitions.map((t) => (
              <button
                key={t}
                type="button"
                className={`btn btn-sm ${t === 'completed' ? 'btn-primary' : t === 'escalated' ? 'btn-danger' : 'btn-secondary'}`}
                disabled={busy}
                onClick={() => go(t)}
              >
                {TRANSITION_VERB[t]}
              </button>
            ))}
          </div>
        </div>
      )}
      {closing && (
        <div className="closure-form">
          <strong>结案前填写处置记录</strong>
          {!spec ? (
            <p className="small muted">正在加载…</p>
          ) : (
            <>
              <div className="stack-sm">
                <span className="small muted">联系上没有？</span>
                <div className="row wrap">
                  {spec.reached.options.map((o) => (
                    <button key={o.value} type="button" className={`btn btn-sm ${reached === o.value ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setReached(o.value)}>
                      {o.label}
                    </button>
                  ))}
                </div>
                {reachedOpt?.unreached && (
                  <p className="small">未联系上不能记为完成。请记录结果，在备注里说明原因，再选择“升级”交医生接手。</p>
                )}
              </div>
              {reached && !reachedOpt?.unreached && (
                <div className="stack-sm">
                  <span className="small muted">给了什么建议？</span>
                  <div className="row wrap">
                    {spec.advice.options.map((o) => (
                      <button key={o.value} type="button" className={`btn btn-sm ${advice === o.value ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setAdvice(o.value)}>
                        {o.label}
                      </button>
                    ))}
                  </div>
                  {adviceOpt?.requires_reason && (
                    <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="写明理由（必填）" className="input-sm" />
                  )}
                </div>
              )}
              <div className="row">
                <button type="button" className="btn btn-sm btn-primary" disabled={busy || !reached || reachedOpt?.unreached || !note.trim()} onClick={() => go('completed')}>
                  确认结案
                </button>
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => setClosing(false)}>
                  取消
                </button>
              </div>
            </>
          )}
        </div>
      )}
      {task.status === 'completed' && <div className="small muted">已完成，无后续流转。</div>}
      <ErrorBox error={error} onClose={() => setError(null)} />
    </div>
  )
}
