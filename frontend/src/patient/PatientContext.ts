import { createContext, useContext } from 'react'
import type { Alert, PatientState } from '../api/types'

export interface PatientCtx {
  id: string
  state: PatientState | null
  error: string | null
  refresh: () => Promise<PatientState | null>
  /** 协议批准的紧急提示（含答题过程中新触发的） */
  alerts: Alert[]
  addAlerts: (alerts: Alert[]) => void
}

export const PatientContext = createContext<PatientCtx | null>(null)

export function usePatient(): PatientCtx {
  const ctx = useContext(PatientContext)
  if (!ctx) throw new Error('usePatient 必须在 EncounterLayout 内使用')
  return ctx
}

/** 患者已确认之后的状态：患者端只能看完成页 */
export const LOCKED_STATUSES = ['ready_for_doctor', 'under_review', 'doctor_confirmed', 'closed']
