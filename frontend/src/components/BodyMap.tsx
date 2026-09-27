import { MARK_KIND_LABEL, regionLabel } from './bodyRegionLabels'
import { useId, useMemo, useState } from 'react'
import type { BodyView, Mark, MarkKind, Region } from '../api/types'
import './bodyMap.css'

/**
 * 身体地图 · 疼痛轨迹。
 * 看得见的是一条平滑人体轮廓：主要疼痛是红橙光晕，放射区域是琥珀光晕（都裁在轮廓内），
 * 再从主要疼痛区域的质心画一条琥珀色轨迹，自上而下连到各放射区域。
 * 可点击的仍是下面 GEOMETRY 里的区域形状：保持透明，只在悬停或键盘聚焦时描边。
 * 区域 id 与 protocols/body_regions.yaml 一一对应；几何在这里定义。
 * 左右以患者自身为准：正面视图里患者的左侧在画面右侧，背面视图里患者的左侧在画面左侧。
 */

type Shape =
  | { kind: 'rect'; x: number; y: number; w: number; h: number; rx: number }
  | { kind: 'ellipse'; cx: number; cy: number; rx: number; ry: number }
  | { kind: 'poly'; points: [number, number][] }

const CX = 150
const VIEW_W = 300
const VIEW_H = 620

const rect = (x: number, y: number, w: number, h: number, rx = 6): Shape => ({ kind: 'rect', x, y, w, h, rx })
const ellipse = (cx: number, cy: number, rx: number, ry: number): Shape => ({ kind: 'ellipse', cx, cy, rx, ry })
const poly = (points: [number, number][]): Shape => ({ kind: 'poly', points })

function mirror(s: Shape): Shape {
  switch (s.kind) {
    case 'rect':
      return { ...s, x: 2 * CX - s.x - s.w }
    case 'ellipse':
      return { ...s, cx: 2 * CX - s.cx }
    case 'poly':
      return { kind: 'poly', points: s.points.map(([x, y]) => [2 * CX - x, y]) }
  }
}

// 画面右半侧的形状（正面 = 患者左侧；背面 = 患者右侧），左半侧用 mirror 得到。
const R = {
  shoulder: rect(168, 110, 66, 34, 12),
  chest: rect(150, 146, 48, 52),
  abdomen: rect(150, 232, 48, 44),
  upperArm: poly([
    [206, 148],
    [238, 150],
    [247, 228],
    [211, 228],
  ]),
  forearm: poly([
    [211, 232],
    [247, 232],
    [249, 316],
    [214, 316],
  ]),
  hand: rect(214, 320, 35, 36, 10),
  hip: rect(152, 306, 48, 34),
  thigh: rect(153, 342, 44, 88),
  knee: rect(154, 432, 41, 34),
  shin: rect(154, 468, 40, 94),
  foot: rect(152, 564, 46, 40, 10),
  upperBack: rect(150, 146, 48, 54),
  midBack: rect(150, 200, 48, 46),
  lowerBackSide: rect(164, 246, 36, 54),
  buttock: rect(151, 300, 50, 52, 12),
}

const C = {
  head: ellipse(150, 48, 30, 36),
  neck: rect(137, 86, 26, 24),
  upperAbdomen: rect(110, 198, 80, 34),
  lowerAbdomen: rect(110, 276, 80, 30),
  lowerBackCenter: rect(136, 246, 28, 54),
  sacrum: poly([
    [135, 300],
    [165, 300],
    [158, 336],
    [142, 336],
  ]),
}

const GEOMETRY: Record<string, Shape> = {
  // ---- 正面 ----
  head_front: C.head,
  neck_front: C.neck,
  shoulder_left_front: R.shoulder,
  shoulder_right_front: mirror(R.shoulder),
  chest_left: R.chest,
  chest_right: mirror(R.chest),
  upper_abdomen: C.upperAbdomen,
  abdomen_left: R.abdomen,
  abdomen_right: mirror(R.abdomen),
  lower_abdomen: C.lowerAbdomen,
  upper_arm_left_front: R.upperArm,
  upper_arm_right_front: mirror(R.upperArm),
  forearm_left_front: R.forearm,
  forearm_right_front: mirror(R.forearm),
  hand_left: R.hand,
  hand_right: mirror(R.hand),
  hip_left_front: R.hip,
  hip_right_front: mirror(R.hip),
  thigh_left_front: R.thigh,
  thigh_right_front: mirror(R.thigh),
  knee_left_front: R.knee,
  knee_right_front: mirror(R.knee),
  shin_left: R.shin,
  shin_right: mirror(R.shin),
  foot_left_top: R.foot,
  foot_right_top: mirror(R.foot),
  // ---- 背面 ----
  head_back: C.head,
  neck_back: C.neck,
  shoulder_left_back: mirror(R.shoulder),
  shoulder_right_back: R.shoulder,
  upper_back_left: mirror(R.upperBack),
  upper_back_right: R.upperBack,
  mid_back_left: mirror(R.midBack),
  mid_back_right: R.midBack,
  lower_back_left: mirror(R.lowerBackSide),
  lower_back_center: C.lowerBackCenter,
  lower_back_right: R.lowerBackSide,
  sacrum: C.sacrum,
  buttock_left: mirror(R.buttock),
  buttock_right: R.buttock,
  upper_arm_left_back: mirror(R.upperArm),
  upper_arm_right_back: R.upperArm,
  forearm_left_back: mirror(R.forearm),
  forearm_right_back: R.forearm,
  hand_left_back: mirror(R.hand),
  hand_right_back: R.hand,
  thigh_left_back: mirror(R.thigh),
  thigh_right_back: R.thigh,
  knee_left_back: mirror(R.knee),
  knee_right_back: R.knee,
  calf_left: mirror(R.shin),
  calf_right: R.shin,
  heel_left: mirror(R.foot),
  heel_right: R.foot,
}

// 后画的在上层：骶尾部叠在两侧臀部之上
const Z_TOP = new Set(['sacrum'])

// ------------------------------------------------------------------
// 可见人体：平滑轮廓。只定义画面右半侧（从头顶沿外侧到裆部），左半侧镜像后反向接上。
// 坐标与上面的热区同一个 300×620 画布，热区都落在轮廓内或贴着轮廓。
// ------------------------------------------------------------------
type Pt = [number, number]
type Seg = [Pt, Pt, Pt] // 三次贝塞尔：控制点 1、控制点 2、终点

const OUTLINE_START: Pt = [150, 11]

const UPPER: Seg[] = [
  // 头
  [[167, 11], [180, 25], [180, 45]],
  [[180, 60], [175, 72], [166, 79]],
  // 颈、斜方肌、三角肌
  [[163, 83], [162, 88], [163, 95]],
  [[163, 100], [164, 103], [167, 105]],
  [[180, 110], [196, 111], [208, 114]],
  [[226, 118], [237, 130], [238, 150]],
  // 上臂、前臂外侧
  [[240, 176], [244, 204], [244, 228]],
  [[245, 258], [248, 288], [248, 316]],
  // 手
  [[250, 326], [252, 340], [250, 350]],
  [[248, 358], [238, 362], [230, 361]],
  [[221, 360], [215, 354], [214, 344]],
  [[213, 334], [214, 324], [213, 318]],
  // 前臂、上臂内侧，腋窝
  [[212, 290], [209, 262], [208, 234]],
  [[207, 208], [206, 182], [204, 162]],
  [[203, 154], [200, 151], [198, 156]],
  // 躯干侧面：胸、腰、髋
  [[197, 180], [193, 210], [193, 236]],
  [[192, 262], [201, 282], [202, 306]],
  // 大腿外侧到膝、小腿、踝
  [[203, 334], [201, 366], [199, 396]],
  [[197, 420], [196, 436], [196, 452]],
  [[197, 478], [199, 500], [196, 528]],
  [[193, 548], [191, 560], [191, 572]],
]

// 正面看到足背（脚尖略向外），背面看到足跟（更窄更圆）
const FOOT_FRONT: Seg[] = [
  [[195, 584], [201, 594], [200, 602]],
  [[199, 609], [186, 610], [172, 609]],
  [[162, 608], [155, 606], [154, 599]],
  [[153, 588], [156, 576], [157, 566]],
]
const FOOT_BACK: Seg[] = [
  [[193, 586], [191, 600], [182, 605]],
  [[175, 609], [163, 608], [158, 603]],
  [[155, 596], [156, 578], [157, 566]],
]

const LOWER_INNER: Seg[] = [
  // 小腿内侧、膝内侧、大腿内侧，到裆部回到中线
  [[157, 540], [154, 512], [154, 484]],
  [[154, 466], [153, 452], [153, 438]],
  [[153, 404], [152, 372], [151, 354]],
  [[150.6, 350], [150.3, 348], [150, 346]],
]

const r1 = (n: number) => Math.round(n * 10) / 10
const mirrorPt = ([x, y]: Pt): Pt => [2 * CX - x, y]
const fmt = (p: Pt) => `${r1(p[0])} ${r1(p[1])}`

function buildOutline(segs: Seg[]): string {
  let d = `M ${fmt(OUTLINE_START)}`
  for (const [c1, c2, e] of segs) d += ` C ${fmt(c1)}, ${fmt(c2)}, ${fmt(e)}`
  // 左半侧：同一串曲线镜像后反向走回头顶
  const ends: Pt[] = [OUTLINE_START, ...segs.map((s) => s[2])]
  for (let i = segs.length - 1; i >= 0; i--) {
    const [c1, c2] = segs[i]
    d += ` C ${fmt(mirrorPt(c2))}, ${fmt(mirrorPt(c1))}, ${fmt(mirrorPt(ends[i]))}`
  }
  return `${d} Z`
}

const OUTLINE: Record<BodyView, string> = {
  front: buildOutline([...UPPER, ...FOOT_FRONT, ...LOWER_INNER]),
  back: buildOutline([...UPPER, ...FOOT_BACK, ...LOWER_INNER]),
}

/** 帮助分清正面/背面的几笔解剖提示（很淡，不参与点击） */
function mirrored(d: string): string {
  return d.replace(/(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/g, (_, x: string, y: string) => `${r1(2 * CX - Number(x))},${y}`)
}
const pair = (d: string) => [d, mirrored(d)]

const DETAIL: Record<BodyView, { lines: string[]; dashed?: string[]; dots?: Pt[] }> = {
  front: {
    lines: [
      ...pair('M154,112 C164,117 181,116 197,118'), // 锁骨
      ...pair('M165,452 C170,459 180,459 186,452'), // 髌骨下缘
    ],
    dots: [[150, 262]], // 肚脐
  },
  back: {
    lines: [
      ...pair('M167,153 C181,150 190,158 188,173 C187,183 181,189 172,190'), // 肩胛
      'M150,303 L150,338', // 臀沟
      ...pair('M154,351 C167,357 185,357 199,349'), // 臀横纹
      ...pair('M161,452 C169,449 181,449 189,452'), // 腘窝横纹
    ],
    dashed: ['M150,108 L150,298'], // 脊柱
  },
}

function ShapeEl({ shape }: { shape: Shape }) {
  switch (shape.kind) {
    case 'rect':
      return <rect x={shape.x} y={shape.y} width={shape.w} height={shape.h} rx={shape.rx} />
    case 'ellipse':
      return <ellipse cx={shape.cx} cy={shape.cy} rx={shape.rx} ry={shape.ry} />
    case 'poly':
      return <polygon points={shape.points.map((p) => p.join(',')).join(' ')} />
  }
}

function bbox(s: Shape): { x: number; y: number; w: number; h: number } {
  switch (s.kind) {
    case 'rect':
      return { x: s.x, y: s.y, w: s.w, h: s.h }
    case 'ellipse':
      return { x: s.cx - s.rx, y: s.cy - s.ry, w: 2 * s.rx, h: 2 * s.ry }
    case 'poly': {
      const xs = s.points.map((p) => p[0])
      const ys = s.points.map((p) => p[1])
      const x = Math.min(...xs)
      const y = Math.min(...ys)
      return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y }
    }
  }
}

/** 区域质心（多边形用面积质心） */
function centroid(s: Shape): Pt {
  switch (s.kind) {
    case 'rect':
      return [s.x + s.w / 2, s.y + s.h / 2]
    case 'ellipse':
      return [s.cx, s.cy]
    case 'poly': {
      let a = 0
      let cx = 0
      let cy = 0
      const p = s.points
      for (let i = 0; i < p.length; i++) {
        const [x0, y0] = p[i]
        const [x1, y1] = p[(i + 1) % p.length]
        const cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
      }
      if (Math.abs(a) < 1e-6) return [p[0][0], p[0][1]]
      return [cx / (3 * a), cy / (3 * a)]
    }
  }
}

// ------------------------------------------------------------------
// 放射轨迹：每个放射区域按侧别（左/右/中）分组，自上而下排好，
// 从离它最近的主要疼痛质心出发连成一条平滑曲线；在主要疼痛上方的放射区域另成一支向上走。
// ------------------------------------------------------------------
interface Trajectory {
  d: string
  start: Pt
  nodes: Pt[]
}

function smoothPath(pts: Pt[]): string {
  if (pts.length < 2) return ''
  if (pts.length === 2) {
    // 两点之间给一点向外的弧度，像沿着肢体走，而不是一根直棍
    const [a, b] = pts
    const dx = b[0] - a[0]
    const dy = b[1] - a[1]
    const len = Math.hypot(dx, dy) || 1
    let nx = -dy / len
    let ny = dx / len
    const outward = b[0] - CX
    if (Math.abs(outward) < 4) {
      nx = 0
      ny = 0
    } else if (Math.sign(nx) !== Math.sign(outward)) {
      nx = -nx
      ny = -ny
    }
    const bow = Math.min(22, len * 0.08)
    const c: Pt = [(a[0] + b[0]) / 2 + nx * bow, (a[1] + b[1]) / 2 + ny * bow]
    return `M ${fmt(a)} Q ${fmt(c)}, ${fmt(b)}`
  }
  // Catmull-Rom → 三次贝塞尔
  let d = `M ${fmt(pts[0])}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[i + 2] ?? p2
    const c1: Pt = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6]
    const c2: Pt = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6]
    d += ` C ${fmt(c1)}, ${fmt(c2)}, ${fmt(p2)}`
  }
  return d
}

function buildTrajectories(visible: Region[], markByRegion: Map<string, MarkKind>): Trajectory[] {
  const starts: Pt[] = []
  const groups = new Map<string, Pt[]>()
  for (const r of visible) {
    const kind = markByRegion.get(r.id)
    if (!kind) continue
    const c = centroid(GEOMETRY[r.id])
    if (kind === 'primary') starts.push(c)
    else {
      const g = groups.get(r.side) ?? []
      g.push(c)
      groups.set(r.side, g)
    }
  }
  if (starts.length === 0 || groups.size === 0) return []
  const nearest = (p: Pt) =>
    starts.reduce((best, s) => (Math.hypot(s[0] - p[0], s[1] - p[1]) < Math.hypot(best[0] - p[0], best[1] - p[1]) ? s : best))

  const out: Trajectory[] = []
  for (const side of ['left', 'center', 'right']) {
    const nodes = groups.get(side)
    if (!nodes) continue
    const byY = [...nodes].sort((a, b) => a[1] - b[1])
    const top = nearest(byY[0])
    const down = byY.filter((p) => p[1] >= top[1] - 6)
    const up = byY.filter((p) => p[1] < top[1] - 6).reverse()
    for (const chain of [down, up]) {
      if (!chain.length) continue
      const start = nearest(chain[0])
      out.push({ d: smoothPath([start, ...chain]), start, nodes: chain })
    }
  }
  return out
}

function autoView(regions: Region[], marks: Mark[]): BodyView {
  const viewOf = new Map(regions.map((r) => [r.id, r.view] as const))
  let front = 0
  let back = 0
  for (const m of marks) {
    const v = viewOf.get(m.region_id) ?? (m.region_id.endsWith('_front') ? 'front' : 'back')
    if (v === 'front') front++
    else back++
  }
  return front > back ? 'front' : 'back'
}

export interface BodyMapProps {
  regions: Region[]
  marks: Mark[]
  /** 不传 onToggle 即为只读 */
  onToggle?: (regionId: string) => void
  mode?: MarkKind
  /** 不传时默认背面；thumb 尺寸不传时自动选标记更多的一面 */
  initialView?: BodyView
  /** thumb：约 48×100 的列表缩略图，不显示工具栏、图例和文字，也不可点选 */
  size?: 'normal' | 'compact' | 'thumb'
  showLegend?: boolean
  /** 放射轨迹上的流动动画。默认：可点选（患者端）时开启，只读（医生端）时静止；系统开启"减少动态效果"时总是关闭 */
  flow?: boolean
}

export function BodyMap({ regions, marks, onToggle, mode, initialView, size = 'normal', showLegend = true, flow }: BodyMapProps) {
  const thumb = size === 'thumb'
  const [pickedView, setView] = useState<BodyView>(initialView ?? 'back')
  const view: BodyView = thumb ? (initialView ?? autoView(regions, marks)) : pickedView
  const interactive = !!onToggle && !thumb
  const flowing = (flow ?? interactive) && !thumb
  const uid = `bm${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`

  const markByRegion = useMemo(() => {
    const m = new Map<string, MarkKind>()
    for (const mk of marks) {
      // 同一区域同时是主要与放射时，以主要为准显示
      const cur = m.get(mk.region_id)
      if (!cur || mk.kind === 'primary') m.set(mk.region_id, mk.kind)
    }
    return m
  }, [marks])

  const visible = useMemo(() => {
    const list = regions.filter((r) => r.view === view && GEOMETRY[r.id])
    return list.sort((a, b) => Number(Z_TOP.has(a.id)) - Number(Z_TOP.has(b.id)))
  }, [regions, view])

  const glows = useMemo(
    () =>
      visible
        .filter((r) => markByRegion.has(r.id))
        // 放射先画、主要后画：主要疼痛的红橙压在琥珀之上
        .sort((a, b) => Number(markByRegion.get(a.id) === 'primary') - Number(markByRegion.get(b.id) === 'primary'))
        .map((r) => {
          const shape = GEOMETRY[r.id]
          const b = bbox(shape)
          const [cx, cy] = centroid(shape)
          const pad = thumb ? 14 : 9
          return { id: r.id, kind: markByRegion.get(r.id)!, cx, cy, rx: b.w / 2 + pad, ry: b.h / 2 + pad }
        }),
    [visible, markByRegion, thumb],
  )

  const trajectories = useMemo(() => buildTrajectories(visible, markByRegion), [visible, markByRegion])

  const missingCount = regions.filter((r) => r.view === view && !GEOMETRY[r.id]).length

  const leftLabel = view === 'front' ? '患者右侧' : '患者左侧'
  const rightLabel = view === 'front' ? '患者左侧' : '患者右侧'
  const viewName = view === 'front' ? '正面' : '背面'

  const ariaLabel = useMemo(() => {
    if (!thumb) return `身体地图（${viewName}）`
    const names = (k: MarkKind) =>
      marks
        .filter((m) => markByRegion.get(m.region_id) === k)
        .map((m) => regionLabel(regions, m.region_id))
        .join('、')
    const p = names('primary')
    const r = names('radiation')
    return `身体图（${viewName}）：主要疼痛 ${p || '无'}；放射 ${r || '无'}`
  }, [thumb, viewName, marks, markByRegion, regions])

  const startDots = useMemo(() => {
    const seen = new Set<string>()
    return trajectories
      .map((t) => t.start)
      .filter((p) => {
        const k = fmt(p)
        if (seen.has(k)) return false
        seen.add(k)
        return true
      })
  }, [trajectories])

  return (
    <div className={`bm-wrap bm-${size}`}>
      {!thumb && (
        <div className="bm-toolbar">
          <div className="seg">
            <button type="button" className={`seg-btn${view === 'front' ? ' active' : ''}`} onClick={() => setView('front')}>
              正面
            </button>
            <button type="button" className={`seg-btn${view === 'back' ? ' active' : ''}`} onClick={() => setView('back')}>
              背面
            </button>
          </div>
          {showLegend && (
            <div className="bm-legend">
              <span className="bm-legend-item">
                <i className="bm-swatch primary" /> 主要疼痛
              </span>
              <span className="bm-legend-item">
                <i className="bm-swatch radiation" /> 放射/串到
              </span>
              {trajectories.length > 0 && (
                <span className="bm-legend-item">
                  <i className="bm-swatch-trace" /> 放射轨迹
                </span>
              )}
            </div>
          )}
        </div>
      )}
      <svg
        className={`bm-map${interactive ? ' interactive' : ''}${mode && interactive ? ` mode-${mode}` : ''}${flowing ? ' is-flowing' : ''}`}
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        role={interactive ? 'group' : 'img'}
        aria-label={ariaLabel}
      >
        <defs>
          <linearGradient id={`${uid}-skin`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#f3f5f9" />
            <stop offset="1" stopColor="#e8ecf2" />
          </linearGradient>
          <radialGradient id={`${uid}-g-primary`}>
            <stop offset="0" stopColor="#d9392a" stopOpacity="0.95" />
            <stop offset="0.38" stopColor="#ec6039" stopOpacity="0.78" />
            <stop offset="0.72" stopColor="#f5894b" stopOpacity="0.3" />
            <stop offset="1" stopColor="#f7a15a" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`${uid}-g-radiation`}>
            <stop offset="0" stopColor="#f0a030" stopOpacity="0.95" />
            <stop offset="0.42" stopColor="#f3b04a" stopOpacity="0.66" />
            <stop offset="0.76" stopColor="#f6c46e" stopOpacity="0.22" />
            <stop offset="1" stopColor="#f8d08a" stopOpacity="0" />
          </radialGradient>
          <clipPath id={`${uid}-clip`}>
            <path d={OUTLINE[view]} />
          </clipPath>
          <filter id={`${uid}-soft`} x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation={thumb ? 5 : 2.5} />
          </filter>
        </defs>

        {!thumb && (
          <>
            <text x={12} y={22} className="bm-side-label">
              {leftLabel}
            </text>
            <text x={VIEW_W - 12} y={22} className="bm-side-label" textAnchor="end">
              {rightLabel}
            </text>
          </>
        )}

        <path className="bm-skin" d={OUTLINE[view]} fill={`url(#${uid}-skin)`} />
        {!thumb && (
          <g className="bm-detail" aria-hidden="true">
            {DETAIL[view].lines.map((d, i) => (
              <path key={i} d={d} />
            ))}
            {DETAIL[view].dashed?.map((d, i) => (
              <path key={`d${i}`} d={d} className="bm-detail-dashed" />
            ))}
            {DETAIL[view].dots?.map(([x, y], i) => (
              <circle key={`c${i}`} cx={x} cy={y} r={1.8} className="bm-detail-dot" />
            ))}
          </g>
        )}

        <g className="bm-glows" clipPath={`url(#${uid}-clip)`} aria-hidden="true">
          {glows.map((g) => (
            <ellipse
              key={g.id}
              className={`bm-glow ${g.kind}`}
              cx={g.cx}
              cy={g.cy}
              rx={g.rx}
              ry={g.ry}
              fill={`url(#${uid}-g-${g.kind})`}
              filter={`url(#${uid}-soft)`}
            />
          ))}
        </g>

        {trajectories.length > 0 && (
          <g className="bm-traj" aria-hidden="true">
            {trajectories.map((t, i) => (
              <path key={`c${i}`} className="bm-traj-casing" d={t.d} />
            ))}
            {trajectories.map((t, i) => (
              <path key={`l${i}`} className="bm-traj-line" d={t.d} />
            ))}
            {flowing && trajectories.map((t, i) => <path key={`f${i}`} className="bm-traj-flow" d={t.d} />)}
            {!thumb &&
              trajectories.flatMap((t, i) => t.nodes.map((p, j) => <circle key={`n${i}-${j}`} className="bm-traj-node" cx={p[0]} cy={p[1]} r={4} />))}
            {!thumb && startDots.map((p, i) => <circle key={`s${i}`} className="bm-traj-start" cx={p[0]} cy={p[1]} r={5} />)}
          </g>
        )}

        {!thumb && (
          <g className="bm-hits">
            {visible.map((r) => {
              const kind = markByRegion.get(r.id)
              return (
                <g
                  key={r.id}
                  className={`bm-hit${kind ? ` is-${kind}` : ''}`}
                  data-region={r.id}
                  onClick={interactive ? () => onToggle?.(r.id) : undefined}
                  tabIndex={interactive ? 0 : undefined}
                  role={interactive ? 'button' : undefined}
                  aria-pressed={interactive ? !!kind : undefined}
                  aria-label={r.label}
                  onKeyDown={
                    interactive
                      ? (e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            onToggle?.(r.id)
                          }
                        }
                      : undefined
                  }
                >
                  <ShapeEl shape={GEOMETRY[r.id]} />
                  <title>{kind ? `${r.label}（${MARK_KIND_LABEL[kind]}）` : r.label}</title>
                </g>
              )
            })}
          </g>
        )}
      </svg>
      {!thumb && missingCount > 0 && <p className="small muted">有 {missingCount} 个区域尚未绘制几何。</p>}
    </div>
  )
}
