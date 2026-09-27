import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { errorMessage, patientApi, track } from '../api/client'
import type { GridAnswer, GridItem, Question, QuestionMetrics, StopReason, VerifyDecision } from '../api/types'
import { BodyMap } from '../components/BodyMap'
import { regionLabel } from '../components/bodyRegionLabels'
import { ErrorBox, Loading } from '../components/Boxes'
import { useBodyRegions } from '../hooks'
import { VERIFY_DECISION } from '../labels'
import { usePatient } from './PatientContext'
import { Steps } from './PatientShell'

const DECISIONS: VerifyDecision[] = ['confirm', 'reject', 'unsure']

export default function QuestionsPage() {
  const { id, addAlerts } = usePatient()
  const nav = useNavigate()
  const { regions } = useBodyRegions()
  const [q, setQ] = useState<Question | null>(null)
  const [metrics, setMetrics] = useState<QuestionMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [value, setValue] = useState<unknown>(null)
  const shownAt = useRef<number>(0)

  const goConfirm = useCallback(() => nav(`/p/e/${id}/confirm`, { replace: true }), [nav, id])
  const goAfter = useCallback(
    (stop: StopReason | undefined) => nav(stop === 'urgent_red_flag' ? `/p/e/${id}/urgent` : `/p/e/${id}/confirm`, { replace: true }),
    [nav, id],
  )

  function show(next: Question) {
    setQ(next)
    setValue(next.kind === 'verification' || next.kind === 'red_flag_grid' ? {} : null)
    shownAt.current = Date.now()
  }

  useEffect(() => {
    let alive = true
    setLoading(true)
    patientApi
      .nextQuestion(id)
      .then((r) => {
        if (!alive) return
        setMetrics(r.question_metrics ?? null)
        if (r.notices.length) addAlerts(r.notices)
        if (!r.question) {
          goAfter(r.stop_reason)
          return
        }
        show(r.question)
        setLoading(false)
      })
      .catch((e) => {
        if (!alive) return
        setError(errorMessage(e))
        setLoading(false)
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, addAlerts, goAfter])

  async function submit(payload: { value?: unknown; unknown?: boolean; skipped?: boolean }) {
    if (!q) return
    setBusy(true)
    setError(null)
    const ms = Date.now() - shownAt.current
    try {
      const r = await patientApi.answer(id, { question_id: q.question_id, ...payload })
      if (q.kind === 'verification') {
        const d = (payload.value ?? {}) as Record<string, VerifyDecision>
        const vals = Object.values(d)
        track(id, 'verification', {
          question_id: q.question_id, scope: q.scope ?? 'normal', items: q.items?.length ?? 0, ms,
          reject: vals.filter((v) => v === 'reject').length, unsure: payload.unknown ? q.items?.length ?? 0 : vals.filter((v) => v === 'unsure').length,
        })
      } else if (q.kind === 'red_flag_grid') {
        const d = (payload.value ?? {}) as Record<string, GridAnswer>
        const vals = Object.values(d)
        track(id, 'red_flag_grid', {
          question_id: q.question_id, rows: q.items?.length ?? 0, ms,
          yes: vals.filter((v) => v === 'yes').length, unsure: vals.filter((v) => v === 'unsure').length,
        })
      } else {
        track(id, 'answer', { question_id: q.question_id, kind: q.kind, type: q.type, ms, unknown: !!payload.unknown, skipped: !!payload.skipped })
      }
      if (r.new_alerts.length) addAlerts(r.new_alerts)
      setMetrics(r.question_metrics ?? null)
      if (!r.next) {
        goAfter(r.stop_reason)
        return
      }
      show(r.next)
      window.scrollTo({ top: 0 })
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }


  if (loading) {
    return (
      <div className="stack">
        <Steps current="questions" />
        <Loading text="正在准备问题…" />
        <ErrorBox error={error} />
      </div>
    )
  }
  if (!q) {
    return (
      <div className="stack">
        <Steps current="questions" />
        <ErrorBox error={error ?? '暂时没有问题可回答。'} />
        <button type="button" className="btn btn-secondary btn-block" onClick={goConfirm}>
          去确认页
        </button>
      </div>
    )
  }

  const arr = Array.isArray(value) ? (value as string[]) : []
  const decisions = (q.kind === 'verification' && value && typeof value === 'object' && !Array.isArray(value) ? value : {}) as Record<
    string,
    VerifyDecision
  >
  const grid = (q.kind === 'red_flag_grid' && value && typeof value === 'object' && !Array.isArray(value) ? value : {}) as Record<
    string,
    GridAnswer
  >
  const rows = (q.kind === 'red_flag_grid' ? (q.items ?? []) : []) as unknown as GridItem[]
  const canSubmit = (() => {
    switch (q.type) {
      case 'verify':
        return (q.items ?? []).every((it) => !!decisions[it.fact_key])
      case 'grid':
        return rows.every((it) => !!grid[it.question_id])
      case 'yes_no':
      case 'single_choice':
        return value !== null && value !== undefined && value !== ''
      case 'multi_choice':
      case 'body_regions':
        return arr.length > 0
      case 'scale':
      case 'number':
        return typeof value === 'number' && !Number.isNaN(value)
      case 'text':
        return typeof value === 'string' && value.trim().length > 0
      default:
        return value !== null
    }
  })()

  function toggleArr(v: string) {
    setValue(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v])
  }

  function decide(key: string, d: VerifyDecision) {
    setValue({ ...decisions, [key]: d })
  }

  function renderInput() {
    switch (q!.type) {
      case 'grid':
        return (
          <ul className="verify-list grid-list">
            {rows.map((it) => (
              <li key={it.question_id} className={`verify-item grid-item${grid[it.question_id] ? ` answered-${grid[it.question_id]}` : ''}`}>
                <div className="grid-text">{it.text}</div>
                <div className="verify-choices" role="radiogroup" aria-label={it.text}>
                  {q!.options.map((o) => (
                    <button
                      key={o.value}
                      type="button"
                      role="radio"
                      aria-checked={grid[it.question_id] === o.value}
                      className={`verify-btn grid-${o.value}${grid[it.question_id] === o.value ? ' selected' : ''}`}
                      onClick={() => setValue({ ...grid, [it.question_id]: o.value as GridAnswer })}
                    >
                      {o.label}
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )
      case 'verify':
        return (
          <ul className="verify-list">
            {(q!.items ?? []).map((it) => (
              <li key={it.fact_key} className={`verify-item${decisions[it.fact_key] ? ` decided-${decisions[it.fact_key]}` : ''}`}>
                <div className="verify-head">
                  <span className="verify-label">{it.label}</span>
                  <strong className="verify-value">{it.value_label}</strong>
                </div>
                {it.quote && <div className="verify-quote small">你的原话：「{it.quote}」</div>}
                <div className="verify-choices" role="radiogroup" aria-label={`核对：${it.label}`}>
                  {DECISIONS.map((d) => (
                    <button
                      key={d}
                      type="button"
                      role="radio"
                      aria-checked={decisions[it.fact_key] === d}
                      className={`verify-btn ${d}${decisions[it.fact_key] === d ? ' selected' : ''}`}
                      onClick={() => decide(it.fact_key, d)}
                    >
                      {VERIFY_DECISION[d]}
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )
      case 'yes_no':
      case 'single_choice':
        return (
          <div className="opt-list" role="radiogroup">
            {q!.options.map((o) => (
              <button
                key={o.value}
                type="button"
                role="radio"
                aria-checked={value === o.value}
                className={`opt-btn${value === o.value ? ' selected' : ''}`}
                onClick={() => setValue(o.value)}
              >
                {o.label}
              </button>
            ))}
          </div>
        )
      case 'multi_choice':
        return (
          <div className="opt-list" role="group">
            {q!.options.map((o) => (
              <button
                key={o.value}
                type="button"
                aria-pressed={arr.includes(o.value)}
                className={`opt-btn opt-multi${arr.includes(o.value) ? ' selected' : ''}`}
                onClick={() => toggleArr(o.value)}
              >
                <span className="opt-check">{arr.includes(o.value) ? '✓' : ''}</span>
                {o.label}
              </button>
            ))}
            <p className="small muted">可以多选。</p>
          </div>
        )
      case 'scale': {
        const min = q!.min ?? 0
        const max = q!.max ?? 10
        const nums: number[] = []
        for (let i = min; i <= max; i++) nums.push(i)
        return (
          <div className="stack-sm">
            <div className="scale-grid" role="radiogroup">
              {nums.map((n) => (
                <button
                  key={n}
                  type="button"
                  role="radio"
                  aria-checked={value === n}
                  className={`scale-btn${value === n ? ' selected' : ''}`}
                  onClick={() => setValue(n)}
                >
                  {n}
                </button>
              ))}
            </div>
            <input
              type="range"
              min={min}
              max={max}
              step={1}
              value={typeof value === 'number' ? value : min}
              onChange={(e) => setValue(Number(e.target.value))}
              aria-label="拖动选择程度"
            />
            <div className="scale-hint">
              <span>{min} {q!.anchors?.[String(min)] ?? '完全不痛'}</span>
              <strong>{typeof value === 'number' ? `已选 ${value}${q!.anchors?.[String(value)] ? ` · ${q!.anchors[String(value)]}` : ''}` : '请选择'}</strong>
              <span>{max} {q!.anchors?.[String(max)] ?? '无法忍受'}</span>
            </div>
          </div>
        )
      }
      case 'number':
        return (
          <input
            type="number"
            inputMode="decimal"
            className="p-input"
            min={q!.min}
            max={q!.max}
            value={typeof value === 'number' ? value : ''}
            onChange={(e) => setValue(e.target.value === '' ? null : Number(e.target.value))}
            placeholder="请输入数字"
          />
        )
      case 'text':
        return (
          <textarea
            className="p-textarea"
            rows={4}
            value={typeof value === 'string' ? value : ''}
            onChange={(e) => setValue(e.target.value)}
            placeholder="用自己的话写就可以"
          />
        )
      case 'body_regions':
        return (
          <div className="stack-sm">
            <BodyMap
              regions={regions}
              marks={arr.map((r) => ({ region_id: r, kind: 'radiation' as const }))}
              mode="radiation"
              onToggle={toggleArr}
              initialView="back"
            />
            <div>
              <span className="small muted">已选：</span>
              {arr.length === 0 ? (
                <span className="small muted">未选择</span>
              ) : (
                <span className="chips">
                  {arr.map((r) => (
                    <button key={r} type="button" className="chip chip-radiation" onClick={() => toggleArr(r)}>
                      {regionLabel(regions, r)} ×
                    </button>
                  ))}
                </span>
              )}
            </div>
            <p className="small muted">左右以你自己的身体为准。</p>
          </div>
        )
      default:
        return <p className="muted">暂不支持的问题类型：{q!.type}</p>
    }
  }

  const isClarify = q.kind === 'clarification'
  const isVerify = q.kind === 'verification'
  const isGrid = q.kind === 'red_flag_grid'
  const nItems = q.items?.length ?? 0
  const nDecided = isGrid ? Object.keys(grid).length : Object.keys(decisions).length
  const isContext = q.kind === 'event_context'

  return (
    <div className="stack">
      <Steps current="questions" />
      <div className="q-progress" aria-label="问询进度">
        <span className="small muted">已回应 {metrics?.items_answered ?? 0} 项 · {isContext ? '核实主体和时间' : isGrid ? `本页安全检查 ${rows.length} 项` : isVerify ? `本页核对 ${nItems} 项` : '按实际情况继续回答'}</span>
      </div>
      {isContext && <div className="box box-info"><strong>新记录不一定是新发生</strong><p className="small">{q.reason}</p></div>}

      {isVerify && (
        <div className={`box ${q.scope === 'urgent' ? 'box-error' : 'box-info'}`}>
          <strong>{q.scope === 'urgent' ? '先确认一件重要的事' : '请核对我们的理解'}</strong>
          <p className="small">
            这些是从你刚才的原话里整理出来的。说错的地方请选「不对」，我们会再直接问你一次；拿不准就选「不确定」。
          </p>
        </div>
      )}

      {isGrid && (
        <div className="box box-info">
          <strong>先做一个安全检查</strong>
          <p className="small">每一行都选一下。选「有」或「不确定」都没关系，医生会优先看；这一屏不算在题数里。</p>
          {q.preface && <p className="small">{q.preface}</p>}
        </div>
      )}

      {isClarify && (
        <div className="box box-warn">
          <strong>你的表达前后不一致，请澄清</strong>
          <p className="small">同一件事我们收到了两种不同的说法。请告诉我们现在以哪个为准；这不是在评价对错，只是为了记录准确。</p>
        </div>
      )}

      <h1 className={`q-title${isClarify ? ' q-clarify' : ''}`}>{q.text}</h1>

      {renderInput()}

      <ErrorBox error={error} onClose={() => setError(null)} />

      <button type="button" className="btn btn-primary btn-lg btn-block" disabled={busy || !canSubmit} onClick={() => submit({ value })}>
        {busy ? '正在提交…' : isVerify || isGrid ? (canSubmit ? '确认，继续' : `还有 ${nItems - nDecided} 行没选`) : '下一题'}
      </button>
      {(q.allow_unknown || q.allow_skip) && (
        <div className="row">
          {q.allow_unknown && (
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => submit({ unknown: true })}>
              {isVerify ? '都拿不准' : '不清楚'}
            </button>
          )}
          {q.allow_skip && (
            <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => submit({ skipped: true })}>
              跳过
            </button>
          )}
        </div>
      )}
      <p className="small muted">选「不清楚」或「跳过」会如实记录，不会被当成"没有"。</p>
    </div>
  )
}
