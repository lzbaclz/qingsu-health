import type { MarkKind, Region } from '../api/types'

export const MARK_KIND_LABEL: Record<MarkKind, string> = {
  primary: '主要疼痛位置',
  radiation: '放射/串到的位置',
}

export function regionLabel(regions: Region[], id: string): string {
  return regions.find(r => r.id === id)?.label ?? id
}
