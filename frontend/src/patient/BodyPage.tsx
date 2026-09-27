import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { errorMessage, patientApi, track } from '../api/client'
import type { Mark, MarkKind } from '../api/types'
import { BodyMap } from '../components/BodyMap'
import { MARK_KIND_LABEL, regionLabel } from '../components/bodyRegionLabels'
import { ErrorBox, Loading } from '../components/Boxes'
import { useBodyRegions } from '../hooks'
import { usePatient } from './PatientContext'
import { Steps } from './PatientShell'

export default function BodyPage() {
  const { id, state, addAlerts } = usePatient()
  const nav = useNavigate()
  const { regions, error: regionsError } = useBodyRegions()
  const [marks, setMarks] = useState<Mark[]>(() => [
    ...(state?.body_map.primary ?? []).map(region_id => ({ region_id, kind: 'primary' as const })),
    ...(state?.body_map.radiation ?? []).map(region_id => ({ region_id, kind: 'radiation' as const })),
  ])
  const [mode, setMode] = useState<MarkKind>('primary')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mountedAt] = useState(Date.now)

  function toggle(regionId: string) {
    setMarks((prev) => {
      const existing = prev.find((m) => m.region_id === regionId)
      if (existing && existing.kind === mode) return prev.filter((m) => m.region_id !== regionId)
      return [...prev.filter((m) => m.region_id !== regionId), { region_id: regionId, kind: mode }]
    })
  }

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const r = await patientApi.bodyMap(id, marks)
      track(id, 'step_submit', { step: 'body', primary: marks.filter((m) => m.kind === 'primary').length,
        radiation: marks.filter((m) => m.kind === 'radiation').length, ms: Date.now() - mountedAt })
      if (r.new_alerts.length) addAlerts(r.new_alerts)
      nav(`/p/e/${id}/describe`)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const primary = marks.filter((m) => m.kind === 'primary')
  const radiation = marks.filter((m) => m.kind === 'radiation')

  return (
    <div className="stack">
      <Steps current="body" />
      <h1 className="p-title">哪里不舒服？请在身体图上点选</h1>
      <p className="p-text muted">先选择标记类型，再点身体图上的区域；再点一次可取消。可以切换正面/背面。</p>

      <div className="mode-toggle" role="radiogroup" aria-label="标记类型">
        {(['primary', 'radiation'] as MarkKind[]).map((k) => (
          <button
            key={k}
            type="button"
            role="radio"
            aria-checked={mode === k}
            className={`mode-btn ${k}${mode === k ? ' active' : ''}`}
            onClick={() => setMode(k)}
          >
            <i className={`bm-swatch ${k}`} />
            {MARK_KIND_LABEL[k]}
          </button>
        ))}
      </div>

      {regionsError && <ErrorBox error={regionsError} />}
      {regions.length === 0 && !regionsError ? (
        <Loading text="正在加载身体图…" />
      ) : (
        <BodyMap regions={regions} marks={marks} mode={mode} onToggle={toggle} initialView={state?.protocol.body_map_view ?? 'back'} />
      )}
      <p className="small muted">左右以你自己的身体为准（正面视图中，你的左侧显示在画面右侧）。</p>

      <section className="card">
        <h2 className="card-title">已选区域</h2>
        <div className="stack-sm">
          <div>
            <span className="small muted">主要疼痛位置：</span>
            {primary.length === 0 ? (
              <span className="small muted">未选择</span>
            ) : (
              <span className="chips">
                {primary.map((m) => (
                  <button key={m.region_id} type="button" className="chip chip-primary" onClick={() => toggle(m.region_id)} title="点击移除">
                    {regionLabel(regions, m.region_id)} ×
                  </button>
                ))}
              </span>
            )}
          </div>
          <div>
            <span className="small muted">放射/串到的位置：</span>
            {radiation.length === 0 ? (
              <span className="small muted">未选择</span>
            ) : (
              <span className="chips">
                {radiation.map((m) => (
                  <button
                    key={m.region_id}
                    type="button"
                    className="chip chip-radiation"
                    onClick={() => {
                      setMode('radiation')
                      setMarks((prev) => prev.filter((x) => x.region_id !== m.region_id))
                    }}
                    title="点击移除"
                  >
                    {regionLabel(regions, m.region_id)} ×
                  </button>
                ))}
              </span>
            )}
          </div>
        </div>
      </section>

      <ErrorBox error={error} onClose={() => setError(null)} />

      <button type="button" className="btn btn-primary btn-lg btn-block" disabled={busy || marks.length === 0} onClick={submit}>
        {busy ? '正在保存…' : '保存标记，下一步'}
      </button>
      <Link to={`/p/e/${id}/describe`} className="btn btn-ghost btn-block">
        先不标记，直接用文字描述
      </Link>
    </div>
  )
}
