import { useEffect, useState } from 'react'
import { errorMessage, protocolApi } from './api/client'
import type { ProtocolDetail, Region } from './api/types'

export function useBodyRegions(): { regions: Region[]; error: string | null } {
  const [regions, setRegions] = useState<Region[]>([])
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    protocolApi
      .regions()
      .then((r) => {
        if (alive) setRegions(r)
      })
      .catch((e) => {
        if (alive) setError(errorMessage(e))
      })
    return () => {
      alive = false
    }
  }, [])
  return { regions, error }
}

export function useProtocol(id: string | null | undefined): { protocol: ProtocolDetail | null; error: string | null } {
  const [protocol, setProtocol] = useState<ProtocolDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (!id) return
    let alive = true
    protocolApi
      .get(id)
      .then((p) => {
        if (alive) setProtocol(p)
      })
      .catch((e) => {
        if (alive) setError(errorMessage(e))
      })
    return () => {
      alive = false
    }
  }, [id])
  return { protocol, error }
}
