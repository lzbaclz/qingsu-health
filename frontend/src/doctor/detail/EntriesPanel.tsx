import { useState, type ReactNode } from 'react'
import { doctorApi, errorMessage } from '../../api/client'
import type { Entry, ExtractionLog, LexiconReplay, Mark, ProtocolDetail, Region } from '../../api/types'
import { regionLabel } from '../../components/bodyRegionLabels'
import { FlagNotes } from '../../components/FlagNotes'
import { Tag } from '../../components/Tag'
import { ENTRY_KIND, ENTRY_KIND_TONE, FACT_STATUS, VERIFY_DECISION, fmtTime, lbl, providerLabel } from '../../labels'

/** "用词表重放这句"（第 1 轮团队评审 · 计算机）：同一句原话交给离线词表再读一遍（只读），和当时模型的结果对照 */
function ReplayButton({ encounterId, entryId }: { encounterId: string; entryId: string }) {
  const [r, setR] = useState<LexiconReplay | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  async function run() {
    setBusy(true)
    setErr(null)
    try {
      setR(await doctorApi.lexiconReplay(encounterId, entryId))
    } catch (e) {
      setErr(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }
  if (!r)
    return (
      <div className="replay">
        <button type="button" className="btn btn-sm btn-secondary" disabled={busy} onClick={run}>
          {busy ? '重放中…' : '用词表重放这句'}
        </button>
        {err && <span className="small text-red"> {err}</span>}
      </div>
    )
  const only = new Set(r.only_model)
  const onlyLex = new Set(r.only_lexicon)
  return (
    <div className="replay replay-open">
      <div className="replay-cols">
        <div>
          <div className="small strong">当时的整理（{providerLabel(r.provider ?? '')}）</div>
          <ul className="plain-list small">
            {r.model.length === 0 && <li className="muted">没有整理出条目</li>}
            {r.model.map((m, i) => (
              <li key={i} className={only.has(m.key) ? 'replay-diff' : ''}>
                {m.red_flag && <Tag tone="red">红旗</Tag>} {m.label}：{lbl(FACT_STATUS, m.status)}
                {m.pass === 'red_flag_pass' ? <span className="muted">（红旗专查）</span> : null}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <div className="small strong">离线词表重放（只读）</div>
          <ul className="plain-list small">
            {r.lexicon.length === 0 && <li className="muted">词表一条也没认出</li>}
            {r.lexicon.map((m, i) => (
              <li key={i} className={onlyLex.has(m.key) ? 'replay-diff' : ''}>
                {m.red_flag && <Tag tone="red">红旗</Tag>} {m.label}：{m.value_label}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <p className="small muted">{r.note} 高亮的是只有一边认出来的。</p>
      <button type="button" className="link-btn small" onClick={() => setR(null)}>
        收起
      </button>
    </div>
  )
}

export function EntriesPanel({
  entries,
  activeId,
  regions,
  protocol,
  extractions = [],
  encounterId,
}: {
  entries: Entry[]
  activeId: string | null
  regions: Region[]
  protocol: ProtocolDetail | null
  extractions?: ExtractionLog[]
  encounterId?: string
}) {
  const factLabel = (key: unknown) => protocol?.facts.find((f) => f.key === key)?.label ?? String(key ?? '')

  function valueLabel(factKey: unknown, value: unknown): string {
    if (value === null || value === undefined) return '（无）'
    const def = protocol?.facts.find((f) => f.key === factKey)
    if (typeof value === 'boolean') return value ? '是' : '否'
    const one = (v: string) => {
      if (def?.type === 'bool') return v === 'yes' ? '有 / 是' : v === 'no' ? '没有 / 否' : v
      return def?.options.find((o) => o.value === v)?.label ?? regionLabel(regions, v)
    }
    if (Array.isArray(value)) return value.map((v) => one(String(v))).join('、')
    if (typeof value === 'object') return JSON.stringify(value)
    return one(String(value))
  }

  function describe(e: Entry): ReactNode {
    const p = e.payload
    switch (e.kind) {
      case 'body_map': {
        const marks = (p.marks as Mark[] | undefined) ?? []
        const prim = marks.filter((m) => m.kind !== 'radiation')
        const rad = marks.filter((m) => m.kind === 'radiation')
        return (
          <>
            <div>
              <span className="muted">主要：</span>
              {prim.map((m) => regionLabel(regions, m.region_id)).join('、') || '无'}
            </div>
            <div>
              <span className="muted">放射：</span>
              {rad.map((m) => regionLabel(regions, m.region_id)).join('、') || '无'}
            </div>
          </>
        )
      }
      case 'free_text': {
        const log = extractions.find((x) => x.entry_id === e.id)
        return (
          <>
            <blockquote className="entry-quote">{String(p.text ?? '')}</blockquote>
            {log && (
              <div className="small muted extraction-log">
                抽取：{providerLabel(log.provider)} · 写入 {log.applied.length} 条
                {log.rejected.length > 0 ? ` · 校验未通过丢弃 ${log.rejected.length} 条` : ''}
                {log.unmapped.length > 0 && (
                  <div>
                    协议外提到（模型整理，仅供参考）：
                    {log.unmapped.map((m, i) => (
                      <span key={i} className="unmapped-item">
                        「{m.text}」
                        <FlagNotes flags={m.flags} />
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
            {encounterId && <ReplayButton encounterId={encounterId} entryId={e.id} />}
          </>
        )
      }
      case 'answer': {
        const qid = String(p.question_id ?? '')
        if (p.kind === 'verification') {
          const decisions = (p.decisions ?? {}) as Record<string, string>
          const items = (p.items ?? []) as { fact_key: string; label: string; value_label: string; quote: string }[]
          return (
            <>
              <div className="small muted">一键核对（从原话整理出的关键事实，请患者确认）</div>
              <ul className="plain-list small">
                {items.map((it) => (
                  <li key={it.fact_key}>
                    {it.label}：{it.value_label} → <strong className={decisions[it.fact_key] === 'reject' ? 'text-red' : ''}>{lbl(VERIFY_DECISION, decisions[it.fact_key])}</strong>
                    {it.quote ? <span className="muted">（原话「{it.quote}」）</span> : null}
                  </li>
                ))}
              </ul>
            </>
          )
        }
        if (p.kind === 'red_flag_grid') {
          const answers = (p.answers ?? {}) as Record<string, string>
          const items = (p.items ?? []) as { question_id: string; fact_key: string; text: string }[]
          const word: Record<string, string> = { yes: '有', no: '没有', unsure: '不确定' }
          return (
            <>
              <div className="small muted">红旗一屏（逐行直接回答，不计题数）</div>
              <ul className="plain-list small">
                {items.map((it) => (
                  <li key={it.question_id}>
                    {it.text} → <strong className={answers[it.question_id] === 'yes' ? 'text-red' : ''}>{word[answers[it.question_id]] ?? '—'}</strong>
                  </li>
                ))}
              </ul>
            </>
          )
        }
        const isClarify = qid.startsWith('clarify:')
        const answer = p.unknown ? '不清楚' : p.skipped ? '跳过' : isClarify ? `澄清选项 #${String(p.value)}（见事实证据中的"澄清回答"）` : valueLabel(p.fact_key, p.value)
        return (
          <>
            <div className="small muted">问：{String(p.question_text ?? qid)}</div>
            <div>
              <span className="muted">答：</span>
              {answer}
            </div>
          </>
        )
      }
      case 'correction':
        return (
          <div>
            患者在确认页将「{factLabel(p.fact_key)}」修改为：{lbl(FACT_STATUS, String(p.status ?? 'present'))}
            {p.value !== null && p.value !== undefined ? ` / ${valueLabel(p.fact_key, p.value)}` : ''}
          </div>
        )
      case 'doctor_note':
        return (
          <>
            <div>
              医生 <span className="mono">{String(p.by ?? '')}</span> 修正「{factLabel(p.fact_key)}」→ {lbl(FACT_STATUS, String(p.status ?? ''))}
              {p.value !== null && p.value !== undefined ? ` / ${valueLabel(p.fact_key, p.value)}` : ''}
            </div>
            <div className="small">依据：{String(p.note ?? '')}</div>
          </>
        )
      case 'system_notice':
        return (
          <>
            <div className="text-red">{String(p.text ?? '')}</div>
            <div className="small muted mono">
              {String(p.rule_id ?? '')} {String(p.severity ?? '')}
              {p.approved_content ? ' · 协议预设文案，审核状态见上' : ''}
            </div>
          </>
        )
      default:
        return <pre className="small">{JSON.stringify(p, null, 2)}</pre>
    }
  }

  return (
    <section className="card entries-panel">
      <div className="card-head">
        <h2 className="card-title">原始记录</h2>
        <span className="small muted">{entries.length} 条 · 不可修改</span>
      </div>
      {entries.length === 0 && <p className="small muted">暂无记录。</p>}
      <ol className="entries">
        {entries.map((e) => (
          <li key={e.id} id={`entry-${e.id}`} className={`entry kind-${e.kind}${activeId === e.id ? ' active' : ''}`}>
            <div className="entry-head">
              <span className="entry-seq">#{e.seq}</span>
              <Tag tone={ENTRY_KIND_TONE[e.kind] ?? 'gray'}>{lbl(ENTRY_KIND, e.kind)}</Tag>
              <span className="small muted">{fmtTime(e.created_at)}</span>
            </div>
            <div className="entry-body">{describe(e)}</div>
            <div className="small muted mono">{e.id}</div>
          </li>
        ))}
      </ol>
    </section>
  )
}
