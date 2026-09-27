import type { DoctorView, Fact, Mark, Region } from '../../api/types'
import { BodyMap } from '../../components/BodyMap'
import { FlagNotes } from '../../components/FlagNotes'
import { SeverityTag, Tag } from '../../components/Tag'
import { EVIDENCE_KIND, fmtTime, lbl, providerLabel, type Tone } from '../../labels'

function ListBlock({
  title,
  tone,
  items,
  hint,
  onQuote,
}: {
  title: string
  tone: Tone
  items: Fact[]
  hint?: string
  onQuote: (entryId: string) => void
}) {
  return (
    <div className={`list-block tone-${tone}`}>
      <h3 className="list-block-title">
        <Tag tone={tone}>{title}</Tag>
        <span className="muted small">{items.length} 项</span>
      </h3>
      {hint && <p className="small muted">{hint}</p>}
      {items.length === 0 ? (
        <p className="small muted">无</p>
      ) : (
        <ul className="plain-list">
          {items.map((f) => (
            <li key={f.key}>
              <span className="strong">{f.label}</span>：{f.value_label}
              <FlagNotes flags={f.flags} />
              {f.evidence.length > 0 && (
                <span className="inline-quotes">
                  {f.evidence.slice(0, 3).map((ev, i) => (
                    <button key={i} type="button" className="quote-btn" onClick={() => onQuote(ev.entry_id)}>
                      「{ev.quote}」
                    </button>
                  ))}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function SummaryPanel({ view, regions, onQuote }: { view: DoctorView; regions: Region[]; onQuote: (entryId: string) => void }) {
  const s = view.summary
  if (!s) {
    return (
      <section className="card">
        <h2 className="card-title">摘要</h2>
        <p className="muted">患者尚未确认自己的表达，暂无摘要。摘要在患者确认后由系统仅根据事实库生成，每条都能点回原始记录。</p>
      </section>
    )
  }
  const c = s.content
  const marks: Mark[] = [
    ...c.body_map.primary.map((r) => ({ region_id: r.id, kind: 'primary' as const })),
    ...c.body_map.radiation.map((r) => ({ region_id: r.id, kind: 'radiation' as const })),
  ]
  const doctorNotes = c.doctor_edits?.doctor_notes

  return (
    <section className="card">
      <div className="card-head">
        <h2 className="card-title">摘要</h2>
        <span className="small muted">
          {s.provisional ? '临时整理（未落库）' : `版本 v${s.version}`} · {s.author} · {fmtTime(s.created_at)}
          {s.note ? ` · ${s.note}` : ''}
        </span>
      </div>
      {s.provisional && (
        <div className="box box-warn small">
          <strong>患者尚未确认自己的表达。</strong> 因为已触发红旗，这里先给出一份临时整理，便于护士/医生立即电话联系；患者确认后会生成正式的 v1。
        </div>
      )}
      <p className="headline">{c.headline}</p>

      <div className="summary-grid">
        <div className="summary-map">
          <BodyMap regions={regions} marks={marks} size="compact" initialView="back" />
          <p className="small muted">
            主要：{c.body_map.primary.map((r) => r.label).join('、') || '无'}；放射：{c.body_map.radiation.map((r) => r.label).join('、') || '无'}；侧别：{c.body_map.side}
          </p>
        </div>
        <div className="stack-sm">
          <div className="sub-card">
            <h3 className="sub-title">
              叙述 <Tag tone={c.narrative_provider.startsWith('mock') ? 'gray' : 'blue'}>{providerLabel(c.narrative_provider)}</Tag>
            </h3>
            <p className="narrative">{c.narrative || '（无叙述）'}</p>
            <p className="small muted">叙述仅根据已整理的事实行生成，并经过越界检查（不含诊断/处方/剂量）。以事实表为准。</p>
          </div>
          {doctorNotes && (
            <div className="sub-card">
              <h3 className="sub-title">医生备注</h3>
              <p>{doctorNotes}</p>
            </div>
          )}
          {c.quotes.length > 0 && (
            <div className="sub-card">
              <h3 className="sub-title">患者原话</h3>
              {c.quotes.map((q) => (
                <div key={q.entry_id}>
                  <button type="button" className="quote-btn block" onClick={() => onQuote(q.entry_id)}>
                    「{q.text}」
                  </button>
                  <FlagNotes flags={q.flags} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {(c.disputed ?? []).length > 0 && (
        <div className="list-block tone-red">
          <h3 className="list-block-title">
            <Tag tone="red">待核实</Tag>
            <span className="muted small">{(c.disputed ?? []).length} 项</span>
          </h3>
          <p className="small muted">原话提到、患者在核对时说不对的红旗。系统不替患者取其一，请电话核实，不要当作"否认"。</p>
          <ul className="plain-list">
            {(c.disputed ?? []).map((x) => (
              <li key={x.key}>
                <SeverityTag severity={x.severity} /> <span className="strong">{x.label}</span>：{x.now}
                <span className="inline-quotes">
                  {x.evidence.slice(0, 3).map((ev, i) => (
                    <button key={i} type="button" className="quote-btn" onClick={() => onQuote(ev.entry_id)}>
                      「{ev.quote}」
                    </button>
                  ))}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="summary-lists">
        <ListBlock title="缺口" tone="yellow" items={c.gaps} hint="关键事实未明确（未问/未答），就诊时需要补问" onQuote={onQuote} />
        <ListBlock title="矛盾" tone="red" items={c.conflicts} hint="患者前后说法不一致且未澄清，系统不自动取其一" onQuote={onQuote} />
        <ListBlock title="表达不确定" tone="orange" items={c.uncertain} onQuote={onQuote} />
        <ListBlock title="明确否认" tone="blue" items={c.denied} hint="只有患者明确说「没有」才会列在这里" onQuote={onQuote} />
      </div>

      <div className="sub-card">
        <h3 className="sub-title">红旗</h3>
        {c.alerts.length === 0 ? (
          <p className="small muted">未触发红旗规则。</p>
        ) : (
          <ul className="plain-list">
            {c.alerts.map((a) => {
              const full = view.alerts.find((x) => x.id === a.id)
              return (
                <li key={a.id} className="alert-row">
                  <div className="row wrap">
                    <SeverityTag severity={a.severity} />
                    <strong>{a.label}</strong>
                    <span className="mono small muted">{a.rule_id}</span>
                    {full && <span className="small muted">{full.notice_shown ? '已向患者展示提示' : '仅供医生复核，未向患者展示'}</span>}
                    {full?.patient_disputed && <Tag tone="orange">患者核对时否认，待电话确认</Tag>}
                  </div>
                  <ul className="plain-list small">
                    {a.evidence.map((ev, i) => (
                      <li key={i}>
                        <span className="mono">{ev.fact_key}</span> = {String(ev.value ?? ev.status)}
                        {ev.evidence.map((e2, j) => (
                          <button key={j} type="button" className="quote-btn" onClick={() => onQuote(e2.entry_id)}>
                            <span className="muted">[{lbl(EVIDENCE_KIND, e2.kind)}]</span> 「{e2.quote}」
                          </button>
                        ))}
                      </li>
                    ))}
                  </ul>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </section>
  )
}
