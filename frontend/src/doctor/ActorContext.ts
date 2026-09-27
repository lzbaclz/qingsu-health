import { createContext, useContext } from 'react'

export interface ActorCtx {
  actor: string
  setActor: (actor: string) => void
}

export const ActorContext = createContext<ActorCtx>({ actor: 'dr_demo', setActor: () => {} })

export function useActor(): ActorCtx {
  return useContext(ActorContext)
}
