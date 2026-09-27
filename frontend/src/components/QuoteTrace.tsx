import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import type { Alert, Entry, Evidence, Fact, Severity } from '../api/types'
import { EVIDENCE_KIND, SEVERITY, VERIFY_DECISION } from '../labels'
import './quoteTrace.css'

/**
 * 出处连线：患者原话里被整理引用的片段画下划线，用一根线连到它整理成的事实卡。
 * - 迹蓝 = 普通事实；信号红 = 已触发的红旗；红色虚线 = 患者核对时否认过的红旗（"待电话核实"，线不会断）。
 * - 没被任何引用覆盖的字保持灰色：没整理到的话，医生照样看得到。
 * - 引文在原文里找不到时不画线，卡片明确标"引文未在原文中找到"：这是安全信号，不吞掉。
 * - 身体图、核对等非原话证据在卡片上标来源小标签。
 * 宽容器（≥560px，compact ≥500px）原话在左、卡片在右；窄容器卡片在下，连线绕右侧、再从左侧接进卡片，互不交叉。
 */

export type QuoteTraceEntry = Pick<Entry, 'id' | 'kind' | 'payload'> & Partial<Pick<Entry, 'seq' | 'created_at'>>

export type QuoteTraceFact = Pick<Fact, 'key' | 'label' | 'value_label' | 'evidence'> &
  Partial<Pick<Fact, 'status' | 'category'>> & {
    /** 被否认红旗"现在的情况"（summary.content.disputed[].now），传了就显示在卡片上 */
    now?: string
  }

/** Alert 与 SummaryAlert 都能直接传 */
export type QuoteTraceAlert = Pick<Alert, 'label' | 'severity' | 'evidence'> & { patient_disputed?: boolean }

export interface QuoteTraceProps {
  /** 原始记录。只渲染 kind='free_text' 的条目（payload.text）；其它条目用于识别"核对"来源，可一起传 */
  entries: QuoteTraceEntry[]
  /** 事实。同一 key 出现多次会合并证据（例如 view.facts 再拼上 summary.content.disputed） */
  facts: QuoteTraceFact[]
  /** 患者核对时否认过的红旗事实 key：画红色虚线，标"待电话核实" */
  disputedKeys?: string[]
  /**
   * 建议传 view.alerts：
   * 1. 只有真正触发了的红旗才用信号红（不传时退回按 category='red_flag' 且状态为有/不确定/矛盾来判断）；
   * 2. 患者否认后，当前版本的事实已不带原话证据（后端 reject_extracted_fact 会丢掉），
   *    红线要靠 alert 里触发时的证据接上，否则被否认的红旗画不出线。
   */
  alerts?: QuoteTraceAlert[]
  /** 紧凑版：医生速览等窄卡片里用，字号和卡片更小 */
  compact?: boolean
  /** 挂载时逐条画出连线（默认开）；系统开启"减少动态效果"时总是关闭 */
  animate?: boolean
  className?: string
}

// ---------------------------------------------------------------- 数据整理

type Tone = 'blue' | 'red'

interface LinkModel {
  id: string
  cardKey: string
  entryId: string
  start: number
  end: number
  tone: Tone
  dashed: boolean
  /** 引文最后一个文字片段的 key：连线从这里出发 */
  segKey: string
  order: number
}

interface CardModel {
  key: string
  label: string
  value: string
  note?: string
  tone: Tone
  disputed: boolean
  flag?: string
  sources: string[]
  missing: string[]
  quotes: string[]
  links: LinkModel[]
}

interface SegModel {
  key: string
  text: string
  links: LinkModel[]
}

interface TextModel {
  id: string
  head: string | null
  segs: SegModel[]
}

interface Model {
  texts: TextModel[]
  cards: CardModel[]
  links: LinkModel[]
  cardByKey: Map<string, CardModel>
  hasGray: boolean
  missingCount: number
}

const LIVE = new Set(['present', 'uncertain', 'conflicting'])
const SEV_RANK: Record<string, number> = { urgent: 3, same_day: 2, routine: 1 }

function allIndexes(text: string, q: string): number[] {
  const out: number[] = []
  let i = text.indexOf(q)
  while (i !== -1) {
    out.push(i)
    i = text.indexOf(q, i + 1)
  }
  return out
}

/** 是否"核对"类证据；是则返回 对/不对/不确定（未知时返回空串），不是返回 null */
function verifyDecision(ev: Evidence, key: string, entry: QuoteTraceEntry | undefined): string | null {
  if (ev.kind !== 'answer') return null
  const p = entry?.payload
  const isVerify = p?.kind === 'verification'
  if (isVerify) {
    const d = (p?.decisions as Record<string, string> | undefined)?.[key]
    if (d) return VERIFY_DECISION[d] ?? d
  }
  const m = /^患者核对.*：(对|不对|不确定)$/.exec(ev.quote ?? '')
  if (m) return m[1]
  return isVerify ? '' : null
}

function buildModel(
  entries: QuoteTraceEntry[],
  facts: QuoteTraceFact[],
  disputedKeys: string[] | undefined,
  alerts: QuoteTraceAlert[] | undefined,
): Model {
  const entryById = new Map(entries.map((e) => [e.id, e]))
  const texts = entries.filter((e) => e.kind === 'free_text' && typeof e.payload?.text === 'string')
  if (texts.every((e) => typeof e.seq === 'number')) texts.sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0))
  const textById = new Map(texts.map((e) => [e.id, String(e.payload.text)]))
  const textOrder = new Map(texts.map((e, i) => [e.id, i]))

  // 同一 key 合并证据（去重），保留第一次出现的顺序与文字
  const merged = new Map<string, { fact: QuoteTraceFact; evidence: Evidence[]; seen: Set<string> }>()
  const addEvidence = (key: string, evs: Evidence[]) => {
    const m = merged.get(key)
    if (!m) return
    for (const ev of evs) {
      const k = `${ev.kind}|${ev.entry_id}|${ev.quote}`
      if (m.seen.has(k)) continue
      m.seen.add(k)
      m.evidence.push(ev)
    }
  }
  for (const f of facts) {
    const m = merged.get(f.key)
    if (!m) merged.set(f.key, { fact: f, evidence: [], seen: new Set() })
    else if (f.now && !m.fact.now) m.fact = { ...m.fact, now: f.now }
    addEvidence(f.key, f.evidence ?? [])
  }

  const disputed = new Set(disputedKeys ?? [])
  const triggered = new Set<string>()
  const severity = new Map<string, Severity>()
  for (const a of alerts ?? []) {
    for (const ae of a.evidence ?? []) {
      const k = ae.fact_key
      if (a.patient_disputed) {
        disputed.add(k)
        if (!merged.has(k)) {
          merged.set(k, { fact: { key: k, label: a.label, value_label: '', evidence: [], category: 'red_flag' }, evidence: [], seen: new Set() })
        }
        // 触发时的原话证据：当前事实版本可能已经不带了
        addEvidence(k, (ae.evidence ?? []).filter((ev) => ev.kind === 'free_text' && ev.quote))
      } else {
        triggered.add(k)
      }
      const cur = severity.get(k)
      if (!cur || (SEV_RANK[a.severity] ?? 0) > (SEV_RANK[cur] ?? 0)) severity.set(k, a.severity)
    }
  }
  const alertsGiven = alerts !== undefined

  const cards: CardModel[] = []
  const jobs: { card: CardModel; entryId: string; quote: string; seq: number }[] = []
  for (const { fact: f, evidence } of merged.values()) {
    const isDisputed = disputed.has(f.key)
    const red =
      isDisputed || triggered.has(f.key) || (!alertsGiven && f.category === 'red_flag' && LIVE.has(String(f.status ?? 'present')))
    const textEv = evidence.filter((ev) => ev.kind === 'free_text' && ev.quote && ev.quote.trim())
    const hasBody = evidence.some((ev) => ev.kind === 'body_map')
    // 只有问答来的事实不上卡片：这里讲的是"原话被整理成了什么"
    if (!textEv.length && !hasBody && !red) continue

    const sources: string[] = hasBody ? [EVIDENCE_KIND.body_map ?? '身体图'] : []
    for (const ev of evidence) {
      if (ev.kind === 'free_text' || ev.kind === 'body_map') continue
      const d = verifyDecision(ev, f.key, entryById.get(ev.entry_id))
      const label = d === null ? (EVIDENCE_KIND[ev.kind] ?? ev.kind) : d ? `核对：${d}` : '核对'
      if (!sources.includes(label)) sources.push(label)
    }
    const sev = severity.get(f.key)
    const card: CardModel = {
      key: f.key,
      label: f.label || f.key,
      value: isDisputed ? '原话提到，核对时说不对' : f.value_label,
      note: isDisputed ? f.now : undefined,
      tone: red ? 'red' : 'blue',
      disputed: isDisputed,
      flag: red ? (sev ? `红旗 · ${SEVERITY[sev] ?? sev}` : '红旗') : undefined,
      sources,
      missing: [],
      quotes: [],
      links: [],
    }
    cards.push(card)
    const seenQuote = new Set<string>()
    for (const ev of textEv) {
      const q = ev.quote.trim()
      const k = `${ev.entry_id}|${q}`
      if (seenQuote.has(k)) continue
      seenQuote.add(k)
      jobs.push({ card, entryId: ev.entry_id, quote: q, seq: jobs.length })
    }
  }

  // 定位引文：长的先占位；同一段话出现多次时取第一个还没被占用的位置；
  // 都被占了（两条事实引用同一句）就共用那一处；原文里根本没有 → 不画线，卡片报"引文未在原文中找到"
  const taken = new Map<string, [number, number][]>()
  jobs.sort((a, b) => b.quote.length - a.quote.length || a.seq - b.seq)
  for (const job of jobs) {
    const text = textById.get(job.entryId)
    const hits = text === undefined ? [] : allIndexes(text, job.quote)
    if (!hits.length) {
      job.card.missing.push(job.quote)
      continue
    }
    const L = job.quote.length
    const used = taken.get(job.entryId) ?? []
    const free = hits.find((s) => !used.some(([a, b]) => s < b && a < s + L))
    const same = hits.find((s) => used.some(([a, b]) => a === s && b === s + L))
    const start = free ?? same ?? hits[0]
    used.push([start, start + L])
    taken.set(job.entryId, used)
    job.card.quotes.push(job.quote)
    job.card.links.push({
      id: `${job.card.key}@${job.entryId}:${start}-${start + L}`,
      cardKey: job.card.key,
      entryId: job.entryId,
      start,
      end: start + L,
      tone: job.card.tone,
      dashed: job.card.disputed,
      segKey: '',
      order: 0,
    })
  }

  // 卡片顺序：有连线的按原文先后，其次是引文找不到的，最后是只有身体图等来源的
  const pos = (l: LinkModel) => (textOrder.get(l.entryId) ?? 0) * 1e7 + l.start
  for (const c of cards) c.links.sort((a, b) => pos(a) - pos(b))
  const rank = (c: CardModel) => (c.links.length ? 0 : c.missing.length ? 1 : 2)
  const ordered = cards
    .map((c, i) => ({ c, i }))
    .sort(
      (a, b) =>
        rank(a.c) - rank(b.c) || (a.c.links.length && b.c.links.length ? pos(a.c.links[0]) - pos(b.c.links[0]) : 0) || a.i - b.i,
    )
    .map((x) => x.c)
  const links = ordered.flatMap((c) => c.links)
  links.forEach((l, i) => (l.order = i))

  let hasGray = false
  const textModels: TextModel[] = texts.map((e, idx) => {
    const text = textById.get(e.id) ?? ''
    const mine = links.filter((l) => l.entryId === e.id)
    const cuts = new Set([0, text.length])
    for (const l of mine) {
      cuts.add(l.start)
      cuts.add(l.end)
    }
    const bounds = [...cuts].sort((a, b) => a - b)
    const segs: SegModel[] = []
    for (let i = 0; i < bounds.length - 1; i++) {
      const a = bounds[i]
      const b = bounds[i + 1]
      const cover = mine.filter((l) => l.start <= a && l.end >= b)
      const piece = text.slice(a, b)
      const key = `${e.id}:${a}-${b}`
      if (!cover.length && /[\p{L}\p{N}]/u.test(piece)) hasGray = true
      for (const l of cover) if (l.end === b) l.segKey = key
      segs.push({ key, text: piece, links: cover })
    }
    return { id: e.id, head: texts.length > 1 ? `第 ${idx + 1} 段${typeof e.seq === 'number' ? ` · 记录 #${e.seq}` : ''}` : null, segs }
  })

  return {
    texts: textModels,
    cards: ordered,
    links,
    cardByKey: new Map(ordered.map((c) => [c.key, c])),
    hasGray,
    missingCount: ordered.reduce((n, c) => n + c.missing.length, 0),
  }
}

// ---------------------------------------------------------------- 几何

type P = [number, number]

interface Wire {
  id: string
  cardKey: string
  d: string
  x: number
  y: number
  tone: Tone
  dashed: boolean
  order: number
}

interface Geom {
  w: number
  h: number
  wires: Wire[]
  sig: string
}

const f1 = (n: number) => Math.round(n * 10) / 10

/** 横平竖直的折线，拐角用小圆角 */
function roundedPath(input: P[], r: number): string {
  const pts: P[] = []
  for (const q of input) {
    const last = pts[pts.length - 1]
    if (!last || Math.hypot(q[0] - last[0], q[1] - last[1]) > 0.5) pts.push(q)
  }
  if (pts.length < 2) return ''
  let d = `M ${f1(pts[0][0])},${f1(pts[0][1])}`
  for (let i = 1; i < pts.length - 1; i++) {
    const [ax, ay] = pts[i - 1]
    const [bx, by] = pts[i]
    const [cx, cy] = pts[i + 1]
    const l1 = Math.hypot(bx - ax, by - ay)
    const l2 = Math.hypot(cx - bx, cy - by)
    const rr = Math.min(r, l1 / 2, l2 / 2)
    const p1: P = [bx + ((ax - bx) / l1) * rr, by + ((ay - by) / l1) * rr]
    const p2: P = [bx + ((cx - bx) / l2) * rr, by + ((cy - by) / l2) * rr]
    d += ` L ${f1(p1[0])},${f1(p1[1])} Q ${f1(bx)},${f1(by)} ${f1(p2[0])},${f1(p2[1])}`
  }
  const z = pts[pts.length - 1]
  return `${d} L ${f1(z[0])},${f1(z[1])}`
}

/** 窄布局里每条线在两侧"走线槽"里占一条道 */
const laneStep = (n: number) => (n > 8 ? 3 : 4)

// ---------------------------------------------------------------- 动画节奏

const FIRST_MS = 150
const STEP_MS = 520
const DRAW_MS = 600

function useReducedMotion(): boolean {
  const query = '(prefers-reduced-motion: reduce)'
  const [reduced, setReduced] = useState(() => typeof window !== 'undefined' && !!window.matchMedia?.(query)?.matches)
  useEffect(() => {
    const mq = window.matchMedia?.(query)
    if (!mq) return
    const on = () => setReduced(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return reduced
}

const cx = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(' ')

// ---------------------------------------------------------------- 组件

export function QuoteTrace({ entries, facts, disputedKeys, alerts, compact = false, animate = true, className }: QuoteTraceProps) {
  const model = useMemo(() => buildModel(entries, facts, disputedKeys, alerts), [entries, facts, disputedKeys, alerts])
  const uid = `qt${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`

  const rootRef = useRef<HTMLDivElement>(null)
  const sourceRef = useRef<HTMLDivElement>(null)
  const textsRef = useRef<HTMLDivElement>(null)
  const cardsRef = useRef<HTMLDivElement>(null)
  const segEls = useRef(new Map<string, HTMLSpanElement>())
  const cardEls = useRef(new Map<string, HTMLLIElement>())

  const [layout, setLayout] = useState<'side' | 'stack'>('side')
  const [geom, setGeom] = useState<Geom | null>(null)
  const [hot, setHot] = useState<string | null>(null)

  const reduced = useReducedMotion()
  const [settled, setSettled] = useState(false)
  const nLinks = model.links.length
  const anim = animate && !reduced && !settled && nLinks > 0

  // 动画只在挂载后播一次：播完摘掉动画类（终态与静态一致，不会闪）
  useEffect(() => {
    if (!animate || reduced || settled || nLinks === 0) return
    const t = window.setTimeout(() => setSettled(true), FIRST_MS + nLinks * STEP_MS + DRAW_MS + 500)
    return () => window.clearTimeout(t)
  }, [animate, reduced, settled, nLinks])

  const measure = useCallback(() => {
    const root = rootRef.current
    const texts = textsRef.current
    const src = sourceRef.current
    if (!root || !texts || !src) return
    const rb = root.getBoundingClientRect()
    const want = rb.width >= (compact ? 500 : 560) ? 'side' : 'stack'
    if (want !== layout) {
      setLayout(want)
      return // 重新渲染后 layout effect 会再量一次
    }
    const ox = rb.left
    const oy = rb.top
    const tb = texts.getBoundingClientRect()
    const sb = src.getBoundingClientRect()
    const lineH = parseFloat(getComputedStyle(texts).lineHeight) || 32

    // 1. 每条线的起点：引文最后一个字的下划线末端
    type Start = { l: LinkModel; x: number; y: number; bottom: number; gap: number }
    const starts: Start[] = []
    for (const l of model.links) {
      const rects = segEls.current.get(l.segKey)?.getClientRects()
      const r = rects && rects.length ? rects[rects.length - 1] : null
      if (!r) continue
      const bottom = r.bottom - oy
      starts.push({ l, x: r.right - ox, y: bottom - 1, bottom, gap: Math.max(6, lineH - r.height + 3) })
    }

    // 2. 同一行上的多条线：在行间空白里各走一条道（靠左的引文走上面那条）
    const laneY = new Map<string, number>()
    const rows = new Map<number, Start[]>()
    for (const s of starts) {
      const k = Math.round(s.bottom)
      const row = rows.get(k) ?? []
      row.push(s)
      rows.set(k, row)
    }
    for (const row of rows.values()) {
      row.sort((a, b) => a.x - b.x || a.l.order - b.l.order)
      const room = Math.max(2, row[0].gap - 6)
      const stepY = row.length > 1 ? Math.min(3.2, room / (row.length - 1)) : 0
      row.forEach((s, i) => laneY.set(s.l.id, s.bottom + 3 + i * stepY))
    }

    // 3. 卡片上的落点：同一张卡有多条线时上下错开
    const perCard = new Map<string, string[]>()
    for (const s of starts) perCard.set(s.l.cardKey, [...(perCard.get(s.l.cardKey) ?? []), s.l.id])
    const anchor = (l: LinkModel): P | null => {
      const el = cardEls.current.get(l.cardKey)
      if (!el) return null
      const cr = el.getBoundingClientRect()
      const sibs = perCard.get(l.cardKey) ?? [l.id]
      const i = sibs.indexOf(l.id)
      const base = cr.top - oy + Math.min(22, cr.height / 2)
      const y = base + (i - (sibs.length - 1) / 2) * 7
      return [cr.left - ox, Math.min(Math.max(y, cr.top - oy + 8), cr.bottom - oy - 8)]
    }

    // 4. 路径
    const wires: Wire[] = []
    const N = model.links.length
    const step = laneStep(N)
    for (const s of starts) {
      const a = anchor(s.l)
      const ly = laneY.get(s.l.id)
      if (!a || ly === undefined) continue
      let d: string
      if (want === 'side') {
        // 下划线末端 → 行间空白 → 文字栏右缘 → 贝塞尔到卡片左缘
        const x0 = Math.max(tb.right - ox + 8, s.x + 6)
        const k = Math.max(18, (a[0] - x0) * 0.5)
        d = `${roundedPath([[s.x, s.y], [s.x, ly], [x0, ly]], 3)} C ${f1(x0 + k)},${f1(ly)} ${f1(a[0] - k)},${f1(a[1])} ${f1(a[0])},${f1(a[1])}`
      } else {
        // 窄布局：右侧走线槽下行 → 文字与卡片之间横穿 → 左侧走线槽下行 → 从左边接进卡片。
        // 第 k 条线：右槽越早越靠外、越晚越先横穿；左槽越早越靠里 → 线与线不交叉
        const k = s.l.order
        const xR = tb.right - ox + 7 + (N - 1 - k) * step
        const band = sb.bottom - oy + 9 + (N - 1 - k) * 4
        const xL = a[0] - 7 - k * step
        d = roundedPath(
          [
            [s.x, s.y],
            [s.x, ly],
            [xR, ly],
            [xR, band],
            [xL, band],
            [xL, a[1]],
            [a[0], a[1]],
          ],
          6,
        )
      }
      wires.push({ id: s.l.id, cardKey: s.l.cardKey, d, x: a[0], y: a[1], tone: s.l.tone, dashed: s.l.dashed, order: s.l.order })
    }
    const sig = `${Math.round(rb.width)}x${Math.round(rb.height)}|${wires.map((w) => w.id + w.d).join('|')}`
    setGeom((g) => (g && g.sig === sig ? g : { w: rb.width, h: rb.height, wires, sig }))
  }, [model, compact, layout])

  useLayoutEffect(() => {
    measure()
  }, [measure])

  useEffect(() => {
    const root = rootRef.current
    if (!root) return
    let raf = 0
    const schedule = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(measure)
    }
    const ro = new ResizeObserver(schedule)
    ro.observe(root)
    if (sourceRef.current) ro.observe(sourceRef.current)
    if (cardsRef.current) ro.observe(cardsRef.current)
    document.fonts?.ready.then(schedule).catch(() => undefined)
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
    }
  }, [measure])

  const delayOf = (l: LinkModel) => FIRST_MS + l.order * STEP_MS
  const step = laneStep(nLinks)
  const gutter = nLinks ? 12 + nLinks * step : 0
  const rootStyle = {
    '--qt-gutter': `${gutter}px`,
    '--qt-band': `${nLinks ? 18 + nLinks * 4 : 14}px`,
    '--qt-draw': `${DRAW_MS}ms`,
  } as CSSProperties

  const hotIds = hot ? new Set(model.cardByKey.get(hot)?.links.map((l) => l.id) ?? []) : null

  return (
    <div
      ref={rootRef}
      className={cx('qt', `qt-${layout}`, compact && 'qt-compact', anim && 'qt-anim', hot && 'has-hot', className)}
      style={rootStyle}
    >
      <div className="qt-grid">
        <div className="qt-source" ref={sourceRef}>
          <div className="qt-col-head">原话</div>
          <div className="qt-texts" ref={textsRef}>
            {model.texts.length === 0 && <p className="qt-empty">没有文字原话。</p>}
            {model.texts.map((t) => (
              <div key={t.id} className="qt-entry">
                {t.head && <div className="qt-entry-head">{t.head}</div>}
                <p className="qt-text">
                  {t.segs.map((s) => {
                    if (!s.links.length) {
                      return (
                        <span key={s.key} className="qt-gray">
                          {s.text}
                        </span>
                      )
                    }
                    const red = s.links.some((l) => l.tone === 'red')
                    const solidRed = s.links.some((l) => l.tone === 'red' && !l.dashed)
                    const first = s.links.reduce((a, b) => (a.order <= b.order ? a : b))
                    return (
                      <span
                        key={s.key}
                        ref={(el) => {
                          if (el) segEls.current.set(s.key, el)
                          else segEls.current.delete(s.key)
                        }}
                        className={cx(
                          'qt-u',
                          red && 'is-red',
                          red && !solidRed && 'is-dashed',
                          hot && s.links.some((l) => l.cardKey === hot) && 'is-hot',
                        )}
                        style={{ '--qt-d': `${delayOf(first)}ms` } as CSSProperties}
                        title={s.links
                          .map((l) => {
                            const c = model.cardByKey.get(l.cardKey)
                            return c ? `${c.label}：${c.value}` : ''
                          })
                          .join('\n')}
                        onMouseEnter={() => setHot(first.cardKey)}
                        onMouseLeave={() => setHot(null)}
                      >
                        {s.text}
                      </span>
                    )
                  })}
                </p>
              </div>
            ))}
          </div>
          {model.hasGray && (
            <p className="qt-note">
              <span className="qt-note-key">灰字</span>没整理到的话，医生照样看得到
            </p>
          )}
        </div>

        <div className="qt-cards-col" ref={cardsRef}>
          <div className="qt-col-head">整理出的信息</div>
          {model.missingCount > 0 && (
            <p className="qt-banner" role="note">
              有 {model.missingCount} 条引文未在原文中找到：以原话为准，请人工核对
            </p>
          )}
          {model.cards.length === 0 ? (
            <p className="qt-empty">还没有整理出条目。</p>
          ) : (
            <ol className="qt-cards">
              {model.cards.map((c) => {
                const first = c.links[0]
                return (
                  <li
                    key={c.key}
                    ref={(el) => {
                      if (el) cardEls.current.set(c.key, el)
                      else cardEls.current.delete(c.key)
                    }}
                    className={cx(
                      'qt-card',
                      `is-${c.tone}`,
                      c.disputed && 'is-disputed',
                      first ? 'is-linked' : 'is-unlinked',
                      c.missing.length > 0 && 'is-warn',
                      hot === c.key && 'is-hot',
                    )}
                    style={first ? ({ '--qt-d': `${delayOf(first) + DRAW_MS * 0.75}ms` } as CSSProperties) : undefined}
                    onMouseEnter={() => setHot(c.key)}
                    onMouseLeave={() => setHot(null)}
                  >
                    <div className="qt-card-label">{c.label}</div>
                    <div className="qt-card-value">{c.value || '—'}</div>
                    {c.note && <div className="qt-card-note">{c.note}</div>}
                    {(c.flag || c.disputed || c.sources.length > 0 || c.missing.length > 0) && (
                      <div className="qt-card-tags">
                        {c.flag && <span className="qt-tag qt-tag-flag">{c.flag}</span>}
                        {c.disputed && <span className="qt-tag qt-tag-verify">待电话核实</span>}
                        {c.sources.map((s) => (
                          <span key={s} className="qt-tag qt-tag-src">
                            {s}
                          </span>
                        ))}
                        {c.missing.length > 0 && <span className="qt-tag qt-tag-warn">引文未在原文中找到</span>}
                      </div>
                    )}
                    {c.missing.map((q, i) => (
                      <div key={i} className="qt-missing">
                        整理时给出的引文：「{q}」
                      </div>
                    ))}
                    {c.quotes.length > 0 && <span className="qt-sr">出处：{c.quotes.map((q) => `「${q}」`).join('、')}</span>}
                  </li>
                )
              })}
            </ol>
          )}
        </div>
      </div>

      <svg className="qt-wires" width={geom?.w ?? 0} height={geom?.h ?? 0} aria-hidden="true" focusable="false">
        {anim && geom && (
          <defs>
            {geom.wires.map((w) => (
              <mask key={w.id} id={`${uid}-m${w.order}`} maskUnits="userSpaceOnUse" x={-40} y={-40} width={geom.w + 80} height={geom.h + 80}>
                <path className="qt-reveal" d={w.d} pathLength={1} style={{ animationDelay: `${FIRST_MS + w.order * STEP_MS}ms` }} />
              </mask>
            ))}
          </defs>
        )}
        {geom?.wires.map((w) => (
          <g
            key={w.id}
            className={cx('qt-link', `is-${w.tone}`, w.dashed && 'is-dashed', hotIds?.has(w.id) && 'is-hot')}
          >
            <g mask={anim ? `url(#${uid}-m${w.order})` : undefined}>
              <path className="qt-wire qt-wire-halo" d={w.d} />
              <path className="qt-wire qt-wire-line" d={w.d} />
            </g>
            <circle
              className="qt-dot"
              cx={w.x}
              cy={w.y}
              r={3.4}
              style={{ animationDelay: `${FIRST_MS + w.order * STEP_MS + DRAW_MS - 80}ms` }}
            />
          </g>
        ))}
      </svg>
    </div>
  )
}
