import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { doctorApi, errorMessage } from '../api/client'
import type { Task } from '../api/types'
import { ErrorBox, Loading } from '../components/Boxes'
import { TaskCard } from '../components/TaskCard'
import { TASK_STATUS, TASK_STATUS_ORDER } from '../labels'
import { useActor } from './ActorContext'

export default function TasksPage() {
  const { actor } = useActor()
  const [tasks, setTasks] = useState<Task[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    doctorApi
      .tasks()
      .then((t) => {
        setTasks(t)
        setError(null)
      })
      .catch((e) => setError(errorMessage(e)))
  }, [])

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
          <h1>任务看板</h1>
          <p className="small muted">任务由系统创建、由人推进；系统不会自行标记"已处理"。</p>
        </div>
        <div className="row">
          <Link to="/d/handover" target="_blank" className="btn btn-secondary btn-sm">
            打印早班交接单
          </Link>
          <button type="button" className="btn btn-secondary btn-sm" onClick={load}>
            刷新
          </button>
        </div>
      </div>
      <ErrorBox error={error} />
      {!tasks && !error && <Loading />}
      {tasks && tasks.some((t) => t.status !== 'completed' && (t.due_at || t.overdue)) && (
        <section className="card">
          <h2 className="card-title">
            今日待办 <span className="small muted">按截止时间排序；超时的标红。每件事都写明谁来做、几点前。</span>
          </h2>
          <div className="task-grid">
            {tasks
              .filter((t) => t.status !== 'completed' && (t.due_at || t.overdue))
              .sort((a, b) => Number(!!b.overdue) - Number(!!a.overdue) || String(a.due_at ?? '9').localeCompare(String(b.due_at ?? '9')))
              .map((t) => (
                <TaskCard key={`due-${t.id}`} task={t} actor={actor} onChanged={load} showEncounter />
              ))}
          </div>
        </section>
      )}
      {tasks && (
        <div className="kanban">
          {TASK_STATUS_ORDER.map((s) => {
            const col = tasks.filter((t) => t.status === s)
            return (
              <div key={s} className={`kanban-col status-${s}`}>
                <div className="kanban-head">
                  <span>{TASK_STATUS[s]}</span>
                  <span className="kanban-count">{col.length}</span>
                </div>
                <div className="kanban-body">
                  {col.length === 0 && <div className="small muted center">无</div>}
                  {col.map((t) => (
                    <TaskCard key={t.id} task={t} actor={actor} onChanged={load} showEncounter />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
