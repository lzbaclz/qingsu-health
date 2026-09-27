import type { Region, Trajectory } from '../../api/types'
import { regionLabel } from '../../components/bodyRegionLabels'
import { Tag } from '../../components/Tag'
import type { Tone } from '../../labels'

/** 恢复轨迹卡（第 1 轮团队评审 · 生物学 / 数学）：以首诊为基线，按医生设定的最小临床重要差异判读。
 *  只比较患者自报的数值与阈值，不做预测；两端任一未知记"数据不足"，不当 0 分。 */

const VERDICT: Record<string, { label: string; tone: Tone }> = {
  improved_meaningful: { label: '有意义改善', tone: 'green' },
  no_meaningful_change: { label: '变化不大', tone: 'gray' },
  worse_meaningful: { label: '明显变差', tone: 'red' },
  insufficient: { label: '数据不足', tone: 'gray' },
  improved: { label: '患者自评：变好', tone: 'green' },
  same: { label: '患者自评：差不多', tone: 'gray' },
  worse: { label: '患者自评：变差', tone: 'red' },
}

const W = 320
const H = 120
const PAD = { l: 26, r: 10, t: 10, b: 22 }

function Spark({ points, maxDay, base, band, direction }: {
  points: { day: number; value: number | null; current: boolean }[]
  maxDay: number
  base: number | null
  band: number | null
  direction: 'lower_better' | 'higher_better'
}) {
  const sameDay = points.length > 1 && points.every(p => p.day === points[0].day)
  const x = (d: number, index: number) => PAD.l + (sameDay ? index / (points.length - 1) : maxDay > 0 ? d / maxDay : 0) * (W - PAD.l - PAD.r)
  const y = (v: number) => PAD.t + (1 - v / 10) * (H - PAD.t - PAD.b)
  const indexed = points.map((p, index) => ({ ...p, index }))
  const known = indexed.filter((p) => p.value !== null) as { day: number; value: number; current: boolean; index: number }[]
  const path = known.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.day, p.index).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="traj-svg" role="img" aria-label="恢复轨迹折线">
      {[0, 2, 4, 6, 8, 10].map((v) => (
        <g key={v}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} className="traj-grid" />
          <text x={PAD.l - 6} y={y(v) + 3} className="traj-axis" textAnchor="end">
            {v}
          </text>
        </g>
      ))}
      {base !== null && band !== null && (
        <rect
          x={PAD.l}
          width={W - PAD.l - PAD.r}
          y={y(Math.min(10, base + band))}
          height={Math.max(0, y(Math.max(0, base - band)) - y(Math.min(10, base + band)))}
          className="traj-band"
        >
          <title>绝对变化参考范围 ±{band} 分；最终判读还需结合百分比与协议规则</title>
        </rect>
      )}
      {base !== null && <line x1={PAD.l} x2={W - PAD.r} y1={y(base)} y2={y(base)} className="traj-base" />}
      <path d={path} className="traj-line" />
      {known.map((p, i) => (
        <circle key={i} cx={x(p.day, p.index)} cy={y(p.value)} r={p.current ? 5 : 3.5} className={p.current ? 'traj-dot current' : 'traj-dot'}>
          <title>
            第 {p.day} 天，第 {p.index + 1} 次记录：{p.value}
          </title>
        </circle>
      ))}
      {indexed
        .filter((p) => p.value === null)
        .map((p, i) => (
          <text key={`u${i}`} x={x(p.day, p.index)} y={H - PAD.b - 4} className="traj-unknown" textAnchor="middle">
            ?
          </text>
        ))}
      {points.map((p, i) => (
        <text key={`d${i}`} x={x(p.day, i)} y={H - 6} className="traj-axis" textAnchor={i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'}>
          {i === 0 ? '首诊' : sameDay ? `同日第${i+1}次` : `${p.day}天`}
        </text>
      ))}
      <text x={W - PAD.r} y={PAD.t + 2} className="traj-axis" textAnchor="end">
        {direction === 'lower_better' ? '越低越好' : '越高越好'}
      </text>
    </svg>
  )
}

export function TrajectoryCard({ t, regions }: { t: Trajectory; regions: Region[] }) {
  if (t.visits < 2) return null
  const maxDay = Math.max(1, ...t.outcomes.flatMap((o) => o.series.map((p) => p.day)))
  return (
    <section className="card traj-card" id="trajectory">
      <h2 className="card-title">
        恢复轨迹 <span className="small muted">第 {t.day} 天 · 第 {t.visit_index + 1} 次记录（共 {t.visits} 次）</span>
        {t.simulated && <Tag tone="gray">阈值为模拟临床稿，待医生审定</Tag>}
      </h2>
      <div className="traj-grid-list">
        {t.outcomes.map((o) => {
          const v = VERDICT[o.verdict] ?? VERDICT.insufficient
          if (o.categorical) {
            return (
              <div key={o.key} className="traj-row">
                <div className="traj-head">
                  <strong>{o.label}</strong>
                  <Tag tone={v.tone}>{v.label}</Tag>
                </div>
                <div className="traj-cats">
                  {o.series.map((p, i) => (
                    <span key={i} className={`traj-cat cat-${p.category ?? 'none'}${p.is_current ? ' current' : ''}`}>
                      {i === 0 ? '首诊' : p.day === 0 ? `同日第${i+1}次` : `${p.day}天`}：{p.value === null ? '未答' : String(p.value)}
                    </span>
                  ))}
                </div>
              </div>
            )
          }
          const pts = o.series.map((p) => ({ day: p.day, value: typeof p.value === 'number' ? p.value : null, current: p.is_current }))
          const delta = o.delta ?? null
          const rule =
            o.mcid_abs != null && o.mcid_pct != null
              ? `有意义改善：${o.direction === 'higher_better' ? '升' : '降'} ≥${o.mcid_abs} 分${o.rule === 'either' ? '或' : '且'} ≥${o.mcid_pct}%`
              : o.mcid_abs != null
                ? `有意义改善：${o.direction === 'higher_better' ? '升' : '降'} ≥${o.mcid_abs} 分`
                : ''
          return (
            <div key={o.key} className="traj-row">
              <div className="traj-head">
                <strong>{o.label}</strong>
                <Tag tone={v.tone}>{v.label}</Tag>
              </div>
              <p className="small traj-numbers">
                首诊 {o.baseline ?? '未知'}
                {o.baseline_substitute ? '（首诊未问此题，基线用"现在痛几分"代替）' : ''} → 本次 {o.current ?? '未知'}
                {delta !== null && `（${delta > 0 ? '+' : ''}${delta} 分${o.pct != null ? `，${o.pct > 0 ? '改善' : '变化'} ${Math.abs(o.pct)}%` : ''}）`}
              </p>
              <Spark points={pts} maxDay={maxDay} base={o.baseline ?? null} band={o.mcid_abs ?? null} direction={o.direction ?? 'lower_better'} />
              {rule && (
                <p className="small muted">
                  {rule}
                  {o.source ? ` · 出处：${o.source}` : ''}
                </p>
              )}
            </div>
          )
        })}
        {t.regions && (
          <div className="traj-row">
            <div className="traj-head">
              <strong>疼痛范围</strong>
              <Tag tone={t.regions.delta >= 2 ? 'orange' : 'gray'}>
                {t.regions.baseline.length} → {t.regions.current.length} 个区域
              </Tag>
            </div>
            <p className="small">
              {t.regions.added.length > 0 && <>新增：{t.regions.added.map((r) => regionLabel(regions, r)).join('、')}。</>}
              {t.regions.removed.length > 0 && <>不再标记：{t.regions.removed.map((r) => regionLabel(regions, r)).join('、')}。</>}
              {t.regions.added.length === 0 && t.regions.removed.length === 0 && '与首诊相同。'}
            </p>
          </div>
        )}
      </div>
      <p className="small muted">{t.note}</p>
    </section>
  )
}
