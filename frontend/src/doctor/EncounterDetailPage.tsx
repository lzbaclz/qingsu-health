import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { doctorApi, errorMessage } from '../api/client'
import type { DoctorView } from '../api/types'
import { ErrorBox, Loading, WarnBox } from '../components/Boxes'
import { Fold } from '../components/Fold'
import { QuoteTrace } from '../components/QuoteTrace'
import { EncounterStatusTag, KindTag, Tag } from '../components/Tag'
import { TaskCard } from '../components/TaskCard'
import { useBodyRegions } from '../hooks'
import { ANSWER_STATUS, PROTOCOL_STATUS, PROTOCOL_STATUS_TONE, QUESTION_KIND, fmtTime, lbl } from '../labels'
import { useActor } from './ActorContext'
import { ChangeCardPanel } from './detail/ChangeCardPanel'
import { DoctorActions } from './detail/DoctorActions'
import { EntriesPanel } from './detail/EntriesPanel'
import { FactsTable } from './detail/FactsTable'
import { RecordDraftPanel } from './detail/RecordDraftPanel'
import { SummaryPanel } from './detail/SummaryPanel'
import { TrajectoryCard } from './detail/TrajectoryCard'
import { VerificationPanel } from './detail/VerificationPanel'
import { VisitBriefCard } from './detail/VisitBriefCard'
import { SymptomEventsPanel } from './detail/SymptomEventsPanel'
import { FunctionalGoals } from '../components/FunctionalGoals'
import { TeachbackPanel } from './detail/TeachbackPanel'

export default function EncounterDetailPage() {
  const { id = '' } = useParams()
  const { actor } = useActor()
  const [view, setView] = useState<DoctorView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeEntry, setActiveEntry] = useState<string | null>(null)
  const { regions } = useBodyRegions()
  const protocol = view?.protocol_snapshot ?? null

  const load = useCallback(async () => {
    try {
      const v = await doctorApi.get(id, actor)
      setView(v)
      setError(null)
    } catch (e) {
      setError(errorMessage(e))
    }
  }, [id, actor])

  useEffect(() => {
    let active = true
    doctorApi.get(id, actor).then(v => {
      if (active) { setView(v); setError(null) }
    }).catch(e => { if (active) setError(errorMessage(e)) })
    return () => { active = false }
  }, [id, actor])

  const jump = useCallback((anchor: string) => {
    document.getElementById(anchor)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  const focusEntry = useCallback((entryId: string) => {
    setActiveEntry(entryId)
    requestAnimationFrame(() => {
      document.getElementById(`entry-${entryId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  }, [])

  if (!view) {
    return (
      <div className="stack">
        <Link to="/d" className="small">
          ← 返回列表
        </Link>
        {error ? <ErrorBox error={error} /> : <Loading />}
      </div>
    )
  }

  const enc = view.encounter
  // 出处连线：只放能连回原话的整理，加上患者核对时否认过的红旗（线不会断，画成红色虚线）
  const disputed = view.summary?.content?.disputed ?? []
  const disputedKeys = disputed.map((d) => d.key)
  const traceFacts = [
    ...view.facts.filter((f) => f.evidence.some((ev) => ev.kind === 'free_text') && f.status !== 'not_asked'),
    ...disputed.map((d) => ({ ...d, now: d.now })),
  ]

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <Link to="/d" className="small">
            ← 返回列表
          </Link>
          <h1 className="row wrap">
            患者 <span className="mono">{enc.patient_code ?? '—'}</span>
            <KindTag kind={enc.kind} />
            <EncounterStatusTag status={enc.status} />
          </h1>
        </div>
        <div className="row">
          <Link to={`/d/e/${enc.id}/slip`} target="_blank" className="btn btn-secondary btn-sm">
            打印接诊小票
          </Link>
          <Link to={`/d/e/${enc.id}/print`} target="_blank" className="btn btn-secondary btn-sm">
            打印 / 导出摘要
          </Link>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => void load()}>
            刷新
          </button>
        </div>
      </div>
      {view.stop?.stop_reason === 'urgent_red_flag' && (
        <div className="box box-error">
          <strong>问询已因紧急红旗终止。</strong> 患者端已显示"立即联系门诊 / 拨打急救电话"，不再继续答题：
          {view.stop.stop_alerts.map((a) => a.label).join('、')}。请按红旗任务尽快电话联系；未问到的事实会在缺口里列出。
        </div>
      )}
      <ErrorBox error={error} onClose={() => setError(null)} />
      {view.brief && <VisitBriefCard brief={view.brief} onJump={jump} />}
      {view.protocol_snapshot?.event_verification?.enabled && <SymptomEventsPanel events={view.symptom_events ?? []} encounterId={id} onChanged={load} onQuote={focusEntry} />}
      <FunctionalGoals goals={view.functional_goals ?? []} />
      <TeachbackPanel responses={view.teachback_responses ?? []} encounterId={id} onChanged={load} />
      {traceFacts.length > 0 && (
        <section className="card" aria-label="原话与整理的出处连线">
          <h2 className="card-title">
            原话 → 整理 <span className="small muted">每条整理都连回患者的原话；没连上的字医生照样看得到</span>
          </h2>
          <QuoteTrace entries={view.entries} facts={traceFacts} alerts={view.alerts} disputedKeys={disputedKeys} compact />
        </section>
      )}

      <section className="card">
        <dl className="kv">
          <div>
            <dt>就诊编号</dt>
            <dd className="mono">{enc.id}</dd>
          </div>
          <div>
            <dt>协议</dt>
            <dd>
              {view.protocol.title} · v{view.protocol.version}{' '}
              <Tag tone={PROTOCOL_STATUS_TONE[view.protocol.status] ?? 'gray'}>{lbl(PROTOCOL_STATUS, view.protocol.status)}</Tag>
            </dd>
          </div>
          <div>
            <dt>适用范围</dt>
            <dd>
              {view.eligibility?.attested
                ? `患者在开始页确认：${view.eligibility.items.map((it) => it.text).join('；')}`
                : view.eligibility
                  ? '未经开始页确认（测试或演示接口创建）'
                  : '本协议未设置'}
            </dd>
          </div>
          {view.respondent && view.respondent.value !== 'self' && (
            <div>
              <dt>谁在填</dt>
              <dd>
                <Tag tone="orange">{view.respondent.label}</Tag>
                {view.respondent.relation ? ` · ${view.respondent.relation}` : ''}
              </dd>
            </div>
          )}
          <div>
            <dt>患者确认时间</dt>
            <dd>{fmtTime(enc.patient_confirmed_at)}</dd>
          </div>
          <div>
            <dt>医生确认时间</dt>
            <dd>{fmtTime(enc.doctor_confirmed_at)}</dd>
          </div>
          <div>
            <dt>创建 / 更新</dt>
            <dd>
              {fmtTime(enc.created_at)} / {fmtTime(enc.updated_at)}
            </dd>
          </div>
          {enc.parent_encounter_id && (
            <div>
              <dt>上次就诊</dt>
              <dd>
                <Link to={`/d/e/${enc.parent_encounter_id}`} className="mono">
                  {enc.parent_encounter_id}
                </Link>
              </dd>
            </div>
          )}
        </dl>
        {view.protocol.status === 'draft' && (
          <WarnBox>
            <strong>协议尚未临床审核。</strong> 本协议（{view.protocol.id} v{view.protocol.version}）为草稿：问题、红旗规则与给患者的提示文字均待临床审核，仅用于原型演示。
          </WarnBox>
        )}
      </section>

      <div className="d-detail-grid">
        <div className="d-detail-main stack">
          {view.trajectory && <TrajectoryCard t={view.trajectory} regions={regions} />}
          {enc.kind === 'follow_up' && view.change_card && <ChangeCardPanel card={view.change_card} onQuote={focusEntry} />}
          <SummaryPanel view={view} regions={regions} onQuote={focusEntry} />
          {view.record_draft && <RecordDraftPanel draft={view.record_draft} />}
          <div id="doctor-actions">
            <DoctorActions view={view} protocol={protocol} regions={regions} actor={actor} onDone={() => void load()} />
          </div>

          <section className="card" id="tasks">
            <h2 className="card-title">
              任务 <span className="muted small">{view.tasks.length} 个</span>
            </h2>
            {view.tasks.length === 0 ? (
              <p className="small muted">暂无任务</p>
            ) : (
              <div className="task-grid">
                {view.tasks.map((t) => (
                  <TaskCard key={t.id} task={t} actor={actor} onChanged={() => void load()} />
                ))}
              </div>
            )}
          </section>

          <h2 className="fold-group-title">更多细节 <span className="small muted">默认收起；需要核对出处或给评审看时再展开</span></h2>
          <Fold title="事实与证据" hint={`${view.facts.length} 条，每条都能点回患者原话`}>
            <FactsTable facts={view.facts} entries={view.entries} onQuote={focusEntry} />
          </Fold>
          <Fold
            title="验收检查"
            hint={view.verification ? (view.verification.passed ? '九项约束全部满足' : '有未通过的检查，请展开查看') : '尚无报告'}
            defaultOpen={view.verification ? !view.verification.passed : false}
          >
            <VerificationPanel verification={view.verification} />
          </Fold>

          <Fold title="摘要版本" hint={`${view.summary_versions.length} 个`}>
          <section className="card">
            <h2 className="card-title">
              摘要版本 <span className="muted small">{view.summary_versions.length} 个</span>
            </h2>
            {view.summary_versions.length === 0 ? (
              <p className="small muted">暂无</p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>版本</th>
                    <th>作者</th>
                    <th>说明</th>
                    <th>时间</th>
                  </tr>
                </thead>
                <tbody>
                  {view.summary_versions.map((v) => (
                    <tr key={v.id} className={view.summary?.id === v.id ? 'selected' : ''}>
                      <td className="mono">v{v.version}</td>
                      <td>{v.author === 'system' ? <Tag tone="gray">系统</Tag> : <Tag tone="purple">{v.author}</Tag>}</td>
                      <td className="small">{v.note ?? '—'}</td>
                      <td className="small">{fmtTime(v.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
          </Fold>

          <Fold title="问答记录" hint={`${view.questions.length} 题`}>
          <section className="card">
            <h2 className="card-title">
              问答记录 <span className="muted small">{view.questions.length} 题</span>
            </h2>
            {view.questions.length === 0 ? (
              <p className="small muted">尚未提问</p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>问题</th>
                    <th>类型</th>
                    <th>回答状态</th>
                    <th>时间</th>
                  </tr>
                </thead>
                <tbody>
                  {view.questions.map((q, i) => (
                    <tr key={`${q.question_id}-${i}`}>
                      <td className="muted">{i + 1}</td>
                      <td>
                        <div>{q.text}</div>
                        <div className="small muted mono">{q.question_id}</div>
                      </td>
                      <td>
                        <Tag tone={q.kind === 'clarification' ? 'orange' : 'gray'}>{lbl(QUESTION_KIND, q.kind)}</Tag>
                      </td>
                      <td>
                        <Tag tone={q.answer_status === 'answered' ? 'green' : q.answer_status === 'pending' ? 'yellow' : 'gray'}>
                          {lbl(ANSWER_STATUS, q.answer_status)}
                        </Tag>
                      </td>
                      <td className="small">{fmtTime(q.asked_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
          </Fold>
        </div>

        <aside className="d-detail-side">
          <EntriesPanel entries={view.entries} activeId={activeEntry} regions={regions} protocol={protocol} extractions={view.extractions} encounterId={enc.id} />
        </aside>
      </div>
    </div>
  )
}
