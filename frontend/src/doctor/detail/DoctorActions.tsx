import { useStaff } from '../../auth/AuthContext'
import { useState } from 'react'
import { InvitePanel } from '../InvitePanel'
import { doctorApi, errorMessage } from '../../api/client'
import type { DoctorView, FollowupDraft, ProtocolDetail, Region } from '../../api/types'
import { ErrorBox, SuccessBox, WarnBox } from '../../components/Boxes'
import { NotificationFlow } from '../../components/NotificationFlow'
import { FactStatusTag } from '../../components/Tag'
import { ENCOUNTER_STATUS, FACT_STATUS, FACT_TYPE, fmtTime, lbl } from '../../labels'

interface FormProps {
  view: DoctorView
  actor: string
  onSuccess: (msg: string) => void
}

// ---------------------------------------------------------------- a) 修改摘要
function SummaryEditForm({ view, actor, onSuccess }: FormProps) {
  const s = view.summary && !view.summary.provisional ? view.summary : null
  const [form, setForm] = useState(() => ({ headline: s?.content.headline ?? '', narrative: s?.content.narrative ?? '', doctor_notes: s?.content.doctor_edits?.doctor_notes ?? '' }))
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    if (!s) return
    const orig = {
      headline: s.content.headline ?? '',
      narrative: s.content.narrative ?? '',
      doctor_notes: s.content.doctor_edits?.doctor_notes ?? '',
    }
    const edits: Record<string, string> = {}
    for (const k of ['headline', 'narrative', 'doctor_notes'] as const) {
      if (form[k] !== orig[k]) edits[k] = form[k]
    }
    if (Object.keys(edits).length === 0) {
      setError('没有修改任何字段。')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const r = await doctorApi.editSummary(view.encounter.id, { actor, edits, note: note.trim() || undefined })
      setNote('')
      onSuccess(`摘要已保存为新版本 v${r.version}（系统版本保留）`)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="sub-card action-form">
      <h3 className="sub-title">a) 修改摘要</h3>
      {!s ? (
        <p className="small muted">尚无摘要可修改（患者确认后生成）。</p>
      ) : (
        <>
          <p className="small muted">只能修改标题、叙述与医生备注；每次修改产生新版本，原始系统版本保留。事实本身请用"修正事实"。</p>
          <div className="field">
            <label className="field-label" htmlFor="se-headline">
              标题 headline
            </label>
            <input id="se-headline" value={form.headline} onChange={(e) => setForm({ ...form, headline: e.target.value })} />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="se-narrative">
              叙述 narrative
            </label>
            <textarea id="se-narrative" rows={4} value={form.narrative} onChange={(e) => setForm({ ...form, narrative: e.target.value })} />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="se-notes">
              医生备注 doctor_notes
            </label>
            <textarea id="se-notes" rows={2} value={form.doctor_notes} onChange={(e) => setForm({ ...form, doctor_notes: e.target.value })} />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="se-note">
              修改说明 note（可选）
            </label>
            <input id="se-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="为什么修改" />
          </div>
          <ErrorBox error={error} onClose={() => setError(null)} />
          <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={submit}>
            {busy ? '保存中…' : '保存为新版本'}
          </button>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- b) 修正事实
function FactCorrectionForm({ view, actor, onSuccess, protocol, regions }: FormProps & { protocol: ProtocolDetail | null; regions: Region[] }) {
  const [key, setKey] = useState(view.facts[0]?.key ?? '')
  const [status, setStatus] = useState<'present' | 'denied' | 'uncertain'>('present')
  const [value, setValue] = useState('')
  const [multi, setMulti] = useState<string[]>([])
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const cur = view.facts.find((f) => f.key === key)
  const def = protocol?.facts.find((f) => f.key === key)
  const type = def?.type ?? cur?.type ?? 'text'
  const options = def?.options ?? []

  function buildValue(): unknown {
    if (status === 'denied') return null
    switch (type) {
      case 'bool':
        return status === 'present' ? true : null
      case 'enum':
        return value || null
      case 'multi_enum':
      case 'body_regions':
        return multi
      case 'scale':
      case 'number':
        return value === '' ? null : Number(value)
      default:
        return value || null
    }
  }

  async function submit() {
    if (!key) return
    if (!note.trim()) {
      setError('医生修正必须写明依据（note）。')
      return
    }
    if (status !== 'denied' && (type === 'multi_enum' || type === 'body_regions') && multi.length === 0 && status === 'present') {
      setError('请至少选择一项。')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const r = await doctorApi.correctFact(view.encounter.id, { actor, key, status, value: buildValue(), note: note.trim() })
      setNote('')
      setValue('')
      setMulti([])
      onSuccess(`事实「${cur?.label ?? key}」已修正为 v${r.version}，并生成新摘要版本`)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  function renderValue() {
    if (status === 'denied') return <p className="small muted">明确否认不需要值。</p>
    switch (type) {
      case 'bool':
        return <p className="small muted">是/否事实：状态「已明确」表示"有"，「明确否认」表示"没有"，「表达不确定」表示不确定。</p>
      case 'enum':
        return (
          <select value={value} onChange={(e) => setValue(e.target.value)}>
            <option value="">（请选择）</option>
            {options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        )
      case 'multi_enum':
        return (
          <div className="check-grid">
            {options.map((o) => (
              <label key={o.value} className="check-inline small">
                <input
                  type="checkbox"
                  checked={multi.includes(o.value)}
                  onChange={(e) => setMulti(e.target.checked ? [...multi, o.value] : multi.filter((x) => x !== o.value))}
                />
                {o.label}
              </label>
            ))}
          </div>
        )
      case 'body_regions':
        return (
          <select multiple size={8} value={multi} onChange={(e) => setMulti(Array.from(e.target.selectedOptions).map((o) => o.value))}>
            {(['back', 'front'] as const).map((v) => (
              <optgroup key={v} label={v === 'back' ? '背面' : '正面'}>
                {regions
                  .filter((r) => r.view === v)
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.label}
                    </option>
                  ))}
              </optgroup>
            ))}
          </select>
        )
      case 'scale':
      case 'number':
        return (
          <input
            type="number"
            value={value}
            min={def?.min ?? undefined}
            max={def?.max ?? undefined}
            onChange={(e) => setValue(e.target.value)}
            placeholder={def?.min != null && def?.max != null ? `${def.min} – ${def.max}` : '数值'}
          />
        )
      default:
        return <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="文本" />
    }
  }

  return (
    <div className="sub-card action-form">
      <h3 className="sub-title">b) 修正事实</h3>
      <p className="small muted">医生修正会作为新版本写入事实库（旧版本保留），必须写明依据；修正后系统重新生成摘要版本。</p>
      <div className="field">
        <label className="field-label" htmlFor="fc-key">
          事实
        </label>
        <select
          id="fc-key"
          value={key}
          onChange={(e) => {
            setKey(e.target.value)
            setValue('')
            setMulti([])
          }}
        >
          {view.facts.map((f) => (
            <option key={f.key} value={f.key}>
              {f.label}（{f.key}）
            </option>
          ))}
        </select>
        {cur && (
          <p className="small muted">
            当前：<FactStatusTag status={cur.status} /> {cur.value_label} · 类型 {lbl(FACT_TYPE, type)} · v{cur.version}
          </p>
        )}
      </div>
      <div className="field">
        <label className="field-label">状态</label>
        <div className="row wrap">
          {(['present', 'denied', 'uncertain'] as const).map((s) => (
            <label key={s} className="check-inline small">
              <input type="radio" name={`corr-status-${view.encounter.id}`} checked={status === s} onChange={() => setStatus(s)} />
              {FACT_STATUS[s]}
            </label>
          ))}
        </div>
      </div>
      <div className="field">
        <label className="field-label">值</label>
        {renderValue()}
      </div>
      <div className="field">
        <label className="field-label" htmlFor="fc-note">
          依据 note（必填）
        </label>
        <input id="fc-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="例如：门诊当面询问，患者确认……" />
      </div>
      <ErrorBox error={error} onClose={() => setError(null)} />
      <button type="button" className="btn btn-primary btn-sm" disabled={busy || !key} onClick={submit}>
        {busy ? '提交中…' : '提交修正'}
      </button>
    </div>
  )
}

// ---------------------------------------------------------------- c) 确认核对完成
function ConfirmForm({ view, actor, onSuccess }: FormProps) {
  const enc = view.encounter
  const can = enc.status === 'ready_for_doctor' || enc.status === 'under_review'
  const failed = view.verification ? !view.verification.passed : false
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    if (failed && !reason.trim()) {
      setError('验收检查未通过：如需继续确认，必须填写 override_reason（越过验收的理由），系统会记录审计。')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const r = await doctorApi.confirm(enc.id, { actor, override_reason: failed ? reason.trim() : undefined })
      onSuccess(`已确认核对完成（验收${r.verification_passed ? '通过' : '未通过，已记录 override'}）`)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="sub-card action-form">
      <h3 className="sub-title">c) 确认核对完成</h3>
      {enc.status === 'doctor_confirmed' || enc.status === 'closed' ? (
        <p className="small">
          已于 {fmtTime(enc.doctor_confirmed_at)} 确认。
        </p>
      ) : !can ? (
        <p className="small muted">当前状态「{ENCOUNTER_STATUS[enc.status]}」不能确认：需要患者先确认自己的表达。</p>
      ) : (
        <>
          <p className="small muted">确认表示你已核对摘要与事实；确认后患者输入不再可改，随后可设置随访计划。</p>
          {!enc.patient_confirmed_at && <WarnBox>患者尚未确认自己的表达，后端将拒绝确认。</WarnBox>}
          {failed && (
            <>
              <WarnBox>
                <strong>验收检查未通过。</strong> 如仍要确认，必须填写理由（override_reason），该理由会与验收结果一起写入审计日志。
              </WarnBox>
              <div className="field">
                <label className="field-label" htmlFor="cf-reason">
                  override_reason（必填）
                </label>
                <textarea id="cf-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="说明为何在验收未通过的情况下仍确认" />
              </div>
            </>
          )}
          <ErrorBox error={error} onClose={() => setError(null)} />
          <button type="button" className={`btn btn-sm ${failed ? 'btn-danger' : 'btn-primary'}`} disabled={busy} onClick={submit}>
            {busy ? '提交中…' : failed ? '越过验收，确认核对完成' : '确认核对完成'}
          </button>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- d) 随访计划
function FollowupPlanForm({ view, actor, onSuccess, protocol }: FormProps & { protocol: ProtocolDetail | null }) {
  const enc = view.encounter
  const can = enc.status === 'doctor_confirmed'
  const defaultDays = protocol?.followup.default_interval_days ?? 7
  const [days, setDays] = useState('')
  const [msg, setMsg] = useState('')
  const [pointsText, setPointsText] = useState('')
  const [notes, setNotes] = useState('')
  const [draftedWith, setDraftedWith] = useState<string | null>(null)
  const [draftId, setDraftId] = useState<string | null>(null)
  const [draftMode, setDraftMode] = useState<FollowupDraft['mode'] | null>(null)
  const [aiAssisted, setAiAssisted] = useState(false)
  const [newTerms, setNewTerms] = useState<FollowupDraft['new_terms']>([])
  const [overrideReason, setOverrideReason] = useState('')
  const [warnings, setWarnings] = useState<string[]>([])
  const [drafting, setDrafting] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function draft() {
    if (!notes.trim()) {
      setError('先写下你要告诉患者的要点（可以简写），系统只负责改写成患者看得懂的话。')
      return
    }
    setDrafting(true)
    setError(null)
    try {
      const r = await doctorApi.followupDraft(enc.id, { actor, notes: notes.trim(), interval_days: days ? Number(days) : undefined })
      setMsg(r.draft)
      setDraftedWith(r.provider)
      setDraftId(r.draft_id)
      setDraftMode(r.mode)
      setAiAssisted(r.ai_assisted)
      setNewTerms(r.new_terms)
      setOverrideReason('')
      setWarnings(r.warnings)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setDrafting(false)
    }
  }

  function clearDraft() {
    setDraftedWith(null)
    setDraftId(null)
    setDraftMode(null)
    setAiAssisted(false)
    setNewTerms([])
    setOverrideReason('')
    setWarnings([])
  }

  async function submit() {
    if (!msg.trim()) {
      setError('随访计划必须包含医生确认后发给患者的说明。')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await doctorApi.followupPlan(enc.id, {
        expected_plan_version_id: view.followup_plan?.version_id,
        understanding_points: pointsText.split('\n').map(s => s.trim()).filter(Boolean),
        actor,
        interval_days: days ? Number(days) : undefined,
        patient_message: msg.trim(),
        drafted_with: draftedWith ?? undefined,
        draft_id: draftId ?? undefined,
        override_reason: overrideReason.trim() || undefined,
      })
      setMsg('')
      setPointsText('')
      setNotes('')
      clearDraft()
      onSuccess('计划新版本已保存，说明等待患者取回；复述与执行情况会单独记录。')
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="sub-card action-form">
      <h3 className="sub-title">d) 设置随访计划</h3>
      {can && <InvitePanel parentId={enc.id} />}
      {view.followup_plan && (
        <div className="stack-sm">
          <dl className="kv kv-compact">
            <div>
              <dt>当前计划</dt>
              <dd>
                计划第 {view.followup_plan.version ?? 1} 版 · 间隔 {view.followup_plan.interval_days} 天 · {view.followup_plan.set_by} · {fmtTime(view.followup_plan.set_at)}
              </dd>
            </div>
            <div>
              <dt>给患者的说明</dt>
              <dd>{view.followup_plan.patient_message}</dd>
            </div>
          </dl>
          {view.notifications.map((n) => (
            <NotificationFlow key={n.id} n={n} showContent={false} />
          ))}
        </div>
      )}
      {!can ? (
        <p className="small muted">只有「医生已确认」状态的就诊才能设置随访计划（当前：{ENCOUNTER_STATUS[enc.status]}）。</p>
      ) : (
        <>
          <div className="field">
            <label className="field-label" htmlFor="fp-days">
              随访间隔（天）
            </label>
            <input id="fp-days" type="number" min={1} value={days} onChange={(e) => setDays(e.target.value)} placeholder={`默认 ${defaultDays}`} />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="fp-notes">
              你的要点（可以简写）
            </label>
            <textarea id="fp-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="例如：继续正常活动，避免久坐；两周后复查" />
            <button type="button" className="btn btn-secondary btn-sm" disabled={drafting} onClick={() => void draft()}>
              {drafting ? '整理中…' : '整理成患者看得懂的话'}
            </button>
            <p className="small muted">
              默认按医生审定的术语对照表整理：分条、在术语后加一句大白话，你的字一个不改，不调用模型。复诊时间和紧急提示由系统按协议附上。
            </p>
          </div>
          {draftMode && (
            <p className="small muted">
              {draftMode === 'glossary'
                ? '本次：术语对照表整理（不调用模型）。'
                : `本次：模型改写（${draftedWith ?? ''}）。要点以外的新内容发送前必须删掉或写理由${aiAssisted ? '；发送时会自动加一行 AI 协助改写的标注' : ''}。`}{' '}
              <button type="button" className="link-btn small" onClick={clearDraft}>
                不用这份草稿，自己写
              </button>
            </p>
          )}
          {warnings.map((w) => (
            <WarnBox key={w}>{w}</WarnBox>
          ))}
          {newTerms.length > 0 && (
            <div className="field">
              <label className="field-label" htmlFor="fp-override">
                确需保留上面这些内容时，写一句理由（会记入审计）；否则请在下面的说明里删掉它们
              </label>
              <input id="fp-override" value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)} placeholder="例如：药名是我当面交代过的，这里再写一次" />
            </div>
          )}
          <div className="field">
            <label className="field-label" htmlFor="fp-message">
              发给患者的说明（必填，发送前请核对）
            </label>
            <textarea id="fp-message" rows={6} value={msg} onChange={(e) => setMsg(e.target.value)} placeholder="可以直接写，也可以先写要点再点上面的按钮改写。" />
            <p className="small muted">内容由医生决定。患者可记录阅读确认、复述与执行情况；这些状态不会互相替代。</p>
          </div>
          {protocol?.followup.teachback_enabled && <div className="form-field">
            <label htmlFor="fp-points">需要患者复述的原文要点（每行一条）</label>
            <textarea id="fp-points" rows={3} value={pointsText} onChange={e => setPointsText(e.target.value)} placeholder="从上面的患者说明复制 1–3 条完整要点，不另加或改写。" disabled={busy} />
            <p className="small muted">每个要点绑定这版说明；患者回复由医护核实，不能据此自动认定已经执行。</p>
          </div>}
          <ErrorBox error={error} onClose={() => setError(null)} />
          <button type="button" className="btn btn-primary btn-sm" disabled={busy || (protocol?.followup.teachback_enabled && !pointsText.trim())} onClick={submit}>
            {busy ? '提交中…' : view.followup_plan ? '更新随访计划并重新发送说明' : '设置随访计划'}
          </button>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- 汇总
export function DoctorActions({
  view,
  protocol,
  regions,
  actor,
  onDone,
}: {
  view: DoctorView
  protocol: ProtocolDetail | null
  regions: Region[]
  actor: string
  onDone: () => void
}) {
  const { user } = useStaff()
  const [flash, setFlash] = useState<string | null>(null)
  function onSuccess(msg: string) {
    setFlash(msg)
    onDone()
  }
  if (user.role !== 'doctor') return <section className="card"><p>摘要修正、确认和随访计划由医生账号操作；你可以在下方处理已授权任务。</p></section>
  return (
    <section className="card">
      <div className="card-head">
        <h2 className="card-title">医生操作</h2>
        <span className="small muted">
          操作者 <span className="mono strong">{actor}</span> · 所有操作记入审计日志
        </span>
      </div>
      <SuccessBox message={flash} onClose={() => setFlash(null)} />
      <div className="actions-grid">
        <SummaryEditForm key={`${view.encounter.id}:${view.summary?.id}:${view.summary?.version}`} view={view} actor={actor} onSuccess={onSuccess} />
        <FactCorrectionForm view={view} actor={actor} onSuccess={onSuccess} protocol={protocol} regions={regions} />
        <ConfirmForm view={view} actor={actor} onSuccess={onSuccess} />
        <FollowupPlanForm view={view} actor={actor} onSuccess={onSuccess} protocol={protocol} />
      </div>
    </section>
  )
}
