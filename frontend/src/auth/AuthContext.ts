import { createContext, useContext } from 'react'

export interface StaffUser {
  id: string
  display_name: string
  clinic_id: string
  role: 'doctor' | 'nurse' | 'frontdesk' | 'admin'
  actor: string
}

export const AuthContext = createContext<{ user: StaffUser; logout: () => Promise<void> } | null>(null)

export function useStaff() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('请先登录')
  return value
}
