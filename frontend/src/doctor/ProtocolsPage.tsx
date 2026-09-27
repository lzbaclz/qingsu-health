import { ProtocolPreview } from './ProtocolPreview'
import { useEffect, useState } from 'react'
import { errorMessage, protocolApi } from '../api/client'
import type { ProtocolListItem } from '../api/types'
import { ErrorBox, Loading, WarnBox } from '../components/Boxes'
import { SeverityTag, Tag } from '../components/Tag'
import { useProtocol } from '../hooks'
import { PROTOCOL_STATUS, PROTOCOL_STATUS_TONE, lbl } from '../labels'

const GAP_GROUP: Record<string, string> = {
  fact: '事实定义',
  red_flag: '红旗规则',
  education: '宣教内容',
  other: '整体',
}

export default function ProtocolsPage() {
  const [list, setList] = useState<ProtocolListItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const { protocol, error: pError } = useProtocol(selected)

  useEffect(() => {
    protocolApi
      .list()
      .then((l) => {
        setList(l)
        setSelected((prev) => prev ?? l.find((x) => !x.error)?.protocol_id ?? null)
      })
      .catch((e) => setError(errorMessage(e)))
  }, [])

  const gapsGrouped = (() => {
    const g: Record<string, string[]> = {}
    for (const gap of protocol?.review_gaps ?? []) {
      const m = gap.match(/^(fact|red_flag|education):(.+)$/)
      const key = m ? m[1] : 'other'
      ;(g[key] ??= []).push(m ? m[2] : gap)
    }
    return g
  })()

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>临床协议</h1>
          <p className="small muted">协议是医生与工程之间的正式接口：问什么、何时升级、给患者看什么，都由协议决定。</p>
        </div>
      </div>
      <ErrorBox error={error} />
      {!list && !error && <Loading />}
      {list && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>协议</th>
                <th>版本</th>
                <th>状态</th>
                <th>专科</th>
                <th className="num">事实</th>
                <th className="num">问题</th>
                <th className="num">红旗</th>
                <th className="num">待审核条目</th>
              </tr>
            </thead>
            <tbody>
              {list.map((p) => (
                <tr
                  key={p.protocol_id}
                  className={`row-click${selected === p.protocol_id ? ' selected' : ''}`}
                  onClick={() => !p.error && setSelected(p.protocol_id)}
                >
                  <td>
                    <div className="strong">{p.title ?? p.protocol_id}</div>
                    <div className="small muted mono">{p.protocol_id}</div>
                    {p.error && <div className="small text-red">加载失败：{p.error}</div>}
                  </td>
                  <td className="mono">{p.version ?? '—'}</td>
                  <td>{p.status ? <Tag tone={PROTOCOL_STATUS_TONE[p.status] ?? 'gray'}>{lbl(PROTOCOL_STATUS, p.status)}</Tag> : '—'}</td>
                  <td className="small">{p.specialty ?? '—'}</td>
                  <td className="num">{p.facts ?? '—'}</td>
                  <td className="num">{p.questions ?? '—'}</td>
                  <td className="num">{p.red_flags ?? '—'}</td>
                  <td className="num">{p.review_gaps !== undefined ? <Tag tone="orange">{p.review_gaps}</Tag> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ErrorBox error={pError} />
      {selected && !protocol && !pError && <Loading text="正在加载协议详情…" />}
      {protocol && (
        <>
          <section className="card">
            <div className="card-head">
              <h2 className="card-title">{protocol.title}</h2>
              <span className="row">
                <span className="mono small">v{protocol.version}</span>
                <Tag tone={PROTOCOL_STATUS_TONE[protocol.status] ?? 'gray'}>{lbl(PROTOCOL_STATUS, protocol.status)}</Tag>
              </span>
            </div>
            {protocol.status !== 'approved' && (
              <WarnBox>
                协议尚未临床审核：本协议由工程团队按公开的常见问诊结构起草，作为占位示例；所有标记为待审核的条目须由临床负责人审核、修改或删除后，才能用于真实用户。
              </WarnBox>
            )}
            <dl className="kv">
              <div>
                <dt>专科</dt>
                <dd>{protocol.specialty}</dd>
              </div>
              <div>
                <dt>最多问题数</dt>
                <dd>{protocol.max_questions}</dd>
              </div>
              <div>
                <dt>随访默认间隔</dt>
                <dd>{protocol.followup.default_interval_days} 天</dd>
              </div>
              {Object.entries(protocol.owners).map(([k, v]) => (
                <div key={k}>
                  <dt>{k === 'clinical_lead' ? '临床负责人' : k === 'clinical_reviewer' ? '临床复核' : k === 'engineering' ? '工程' : k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          </section>

          <ProtocolPreview key={protocol.protocol_id} protocol={protocol} />
          <div className="grid-2">
            <section className="card">
              <h2 className="card-title">适用范围</h2>
              <p className="small muted">场景：{protocol.scope.setting}</p>
              <p className="small muted">服务时间：{protocol.scope.service_hours}</p>
              <h3 className="sub-title">纳入</h3>
              <ul className="plain-list">
                {protocol.scope.inclusion.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
              <h3 className="sub-title">排除</h3>
              <ul className="plain-list">
                {protocol.scope.exclusion.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </section>
            <section className="card">
              <h2 className="card-title">给患者看的文字</h2>
              <h3 className="sub-title">用途与边界</h3>
              <p className="small">{protocol.scope.service_notice}</p>
              <h3 className="sub-title">紧急情况提示</h3>
              <p className="small text-red">{protocol.scope.emergency_notice}</p>
              <h3 className="sub-title">不适用时</h3>
              <p className="small">{protocol.scope.out_of_scope_message}</p>
            </section>
          </div>

          <section className="card">
            <h2 className="card-title">
              规模 <span className="muted small">事实 {protocol.facts.length} · 问题 {protocol.questions.length}（随访 {protocol.followup.questions.length}）· 红旗 {protocol.red_flags.length}</span>
            </h2>
            <table className="table">
              <thead>
                <tr>
                  <th>红旗规则</th>
                  <th>等级</th>
                  <th>触发条件</th>
                  <th>动作</th>
                </tr>
              </thead>
              <tbody>
                {protocol.red_flags.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <div>{r.label}</div>
                      <div className="mono small muted">{r.id}</div>
                    </td>
                    <td>
                      <SeverityTag severity={r.severity} />
                    </td>
                    <td className="mono small">{r.when}</td>
                    <td className="small">{r.action === 'immediate_notice_and_task' ? '立即提示患者 + 建任务' : '仅建任务（不向患者展示）'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="card">
            <h2 className="card-title">
              以下条目仍需临床审核 <Tag tone="orange">{protocol.review_gaps.length}</Tag>
            </h2>
            <div className="gap-groups">
              {Object.entries(gapsGrouped).map(([k, items]) => (
                <div key={k} className="gap-group">
                  <h3 className="sub-title">
                    {GAP_GROUP[k] ?? k} <span className="muted small">{items.length}</span>
                  </h3>
                  <div className="chips">
                    {items.map((it) => (
                      <span key={it} className={`chip ${k === 'other' ? 'chip-warn' : ''}`}>
                        {it}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  )
}
