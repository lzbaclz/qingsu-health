// localStorage 在隐私模式/禁用时可能抛错，统一包一层。

export const CURRENT_ENCOUNTER_KEY = 'tiji.patient.currentEncounter'
export const LAST_ENCOUNTER_KEY = 'tiji.patient.lastConfirmedEncounter'
export const ACTOR_KEY = 'tiji.doctor.actor'
export const EMERGENCY_OPEN_KEY = 'tiji.patient.emergencyOpen'

/** 前台平板模式（?kiosk=1）：不记住"上次未完成"，提交后提示交还平板并自动回到开始页 */
export function isKiosk(): boolean {
  try {
    return sessionStorage.getItem('tiji.kiosk') === '1'
  } catch {
    return false
  }
}

export function setKiosk(on: boolean): void {
  try {
    if (on) sessionStorage.setItem('tiji.kiosk', '1')
    else sessionStorage.removeItem('tiji.kiosk')
  } catch {
    // ignore
  }
}

export function storageGet(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

export function storageSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // ignore
  }
}

export function storageRemove(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    // ignore
  }
}
