import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, Outlet, useLocation, useParams } from 'react-router-dom'
import { errorMessage, patientApi, track } from '../api/client'
import type { Alert, PatientState } from '../api/types'
import { ErrorBox, Loading } from '../components/Boxes'
import { LOCKED_STATUSES, PatientContext, type PatientCtx } from './PatientContext'
import { PatientShell } from './PatientShell'

export default function EncounterLayout() {
  const { id = '' } = useParams()
  const location = useLocation()
  const [state, setState] = useState<PatientState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [extra, setExtra] = useState<Alert[]>([])

  const refresh = useCallback(async () => {
    try {
      const s = await patientApi.state(id)
      setState(s)
      setError(null)
      return s
    } catch (e) {
      setError(errorMessage(e))
      return null
    }
  }, [id])

  // 每个患者页面加载时都重新拉取，保证 notices（紧急提示）随时可见
  useEffect(() => {
    let active = true
    patientApi.state(id).then(s => {
      if (active) { setState(s); setError(null) }
    }).catch(e => { if (active) setError(errorMessage(e)) })
    track(id, 'page_view', { page: location.pathname.split('/').pop() ?? '' })
    return () => { active = false }
  }, [location.pathname, id])

  const addAlerts = useCallback((alerts: Alert[]) => {
    if (alerts.length) setExtra((prev) => [...prev, ...alerts])
  }, [])

  const alerts = useMemo(() => {
    const seen = new Set<string>()
    const out: Alert[] = []
    for (const a of [...(state?.notices ?? []), ...extra]) {
      if (!seen.has(a.id)) {
        seen.add(a.id)
        out.push(a)
      }
    }
    return out
  }, [state, extra])

  const ctx = useMemo<PatientCtx>(
    () => ({ id, state, error, refresh, alerts, addAlerts }),
    [id, state, error, refresh, alerts, addAlerts],
  )

  const locked = !!state && LOCKED_STATUSES.includes(state.status)
  if (locked && !location.pathname.endsWith('/done')) {
    return <Navigate to={`/p/e/${id}/done`} replace />
  }

  return (
    <PatientContext.Provider value={ctx}>
      <PatientShell
        notices={alerts}
        emergency={state?.protocol.emergency_notice}
        patientCode={state?.patient_code}
        subtitle={state?.kind === 'follow_up' ? '诊后随访' : '就诊前症状表达'}
      >
        {!state && error ? (
          <div className="stack">
            <ErrorBox error={error} />
            <Link to="/p" className="btn btn-secondary btn-block">
              返回开始页
            </Link>
          </div>
        ) : !state ? (
          <Loading />
        ) : (
          <Outlet />
        )}
      </PatientShell>
    </PatientContext.Provider>
  )
}
