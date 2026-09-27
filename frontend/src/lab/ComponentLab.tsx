import { useMemo, useState } from 'react'
import type { Alert, Entry, Evidence, Fact, Mark, MarkKind, Region } from '../api/types'
import { BodyMap } from '../components/BodyMap'
import { MARK_KIND_LABEL } from '../components/bodyRegionLabels'
import { QuoteTrace } from '../components/QuoteTrace'

/**
 * 组件试验页 /lab：QuoteTrace 与 BodyMap（疼痛轨迹）的样张。
 * 这里的患者原话、事实、红旗、身体图标记全部是写死的模拟数据，不连后端、不写库。
 */

// ---------------------------------------------------------------- 模拟：身体区域（与 protocols/body_regions.yaml 一致）

const REGION_ROWS: [string, string, Region['view'], Region['side'], string][] = [
  ['head_front', '头部（前）', 'front', 'center', '头颈'],
  ['neck_front', '颈前', 'front', 'center', '头颈'],
  ['shoulder_left_front', '左肩（前）', 'front', 'left', '上肢'],
  ['shoulder_right_front', '右肩（前）', 'front', 'right', '上肢'],
  ['chest_left', '左胸', 'front', 'left', '躯干'],
  ['chest_right', '右胸', 'front', 'right', '躯干'],
  ['upper_abdomen', '上腹', 'front', 'center', '躯干'],
  ['abdomen_left', '左腹', 'front', 'left', '躯干'],
  ['abdomen_right', '右腹', 'front', 'right', '躯干'],
  ['lower_abdomen', '下腹', 'front', 'center', '躯干'],
  ['upper_arm_left_front', '左上臂（前）', 'front', 'left', '上肢'],
  ['upper_arm_right_front', '右上臂（前）', 'front', 'right', '上肢'],
  ['forearm_left_front', '左前臂（前）', 'front', 'left', '上肢'],
  ['forearm_right_front', '右前臂（前）', 'front', 'right', '上肢'],
  ['hand_left', '左手', 'front', 'left', '上肢'],
  ['hand_right', '右手', 'front', 'right', '上肢'],
  ['hip_left_front', '左髋/腹股沟', 'front', 'left', '下肢'],
  ['hip_right_front', '右髋/腹股沟', 'front', 'right', '下肢'],
  ['thigh_left_front', '左大腿（前）', 'front', 'left', '下肢'],
  ['thigh_right_front', '右大腿（前）', 'front', 'right', '下肢'],
  ['knee_left_front', '左膝（前）', 'front', 'left', '下肢'],
  ['knee_right_front', '右膝（前）', 'front', 'right', '下肢'],
  ['shin_left', '左小腿（前）', 'front', 'left', '下肢'],
  ['shin_right', '右小腿（前）', 'front', 'right', '下肢'],
  ['foot_left_top', '左足背', 'front', 'left', '下肢'],
  ['foot_right_top', '右足背', 'front', 'right', '下肢'],
  ['head_back', '头部（后）', 'back', 'center', '头颈'],
  ['neck_back', '颈后', 'back', 'center', '头颈'],
  ['shoulder_left_back', '左肩（后）', 'back', 'left', '上肢'],
  ['shoulder_right_back', '右肩（后）', 'back', 'right', '上肢'],
  ['upper_back_left', '左上背', 'back', 'left', '腰背'],
  ['upper_back_right', '右上背', 'back', 'right', '腰背'],
  ['mid_back_left', '左中背', 'back', 'left', '腰背'],
  ['mid_back_right', '右中背', 'back', 'right', '腰背'],
  ['lower_back_left', '左腰', 'back', 'left', '腰背'],
  ['lower_back_center', '腰部正中', 'back', 'center', '腰背'],
  ['lower_back_right', '右腰', 'back', 'right', '腰背'],
  ['sacrum', '骶尾部', 'back', 'center', '腰背'],
  ['buttock_left', '左臀', 'back', 'left', '腰背'],
  ['buttock_right', '右臀', 'back', 'right', '腰背'],
  ['upper_arm_left_back', '左上臂（后）', 'back', 'left', '上肢'],
  ['upper_arm_right_back', '右上臂（后）', 'back', 'right', '上肢'],
  ['forearm_left_back', '左前臂（后）', 'back', 'left', '上肢'],
  ['forearm_right_back', '右前臂（后）', 'back', 'right', '上肢'],
  ['hand_left_back', '左手背', 'back', 'left', '上肢'],
  ['hand_right_back', '右手背', 'back', 'right', '上肢'],
  ['thigh_left_back', '左大腿（后）', 'back', 'left', '下肢'],
  ['thigh_right_back', '右大腿（后）', 'back', 'right', '下肢'],
  ['knee_left_back', '左腘窝', 'back', 'left', '下肢'],
  ['knee_right_back', '右腘窝', 'back', 'right', '下肢'],
  ['calf_left', '左小腿（后）', 'back', 'left', '下肢'],
  ['calf_right', '右小腿（后）', 'back', 'right', '下肢'],
  ['heel_left', '左足跟', 'back', 'left', '下肢'],
  ['heel_right', '右足跟', 'back', 'right', '下肢'],
]
const REGIONS: Region[] = REGION_ROWS.map(([id, label, view, side, group]) => ({ id, label, view, side, group }))

const marks = (primary: string[], radiation: string[]): Mark[] => [
  ...primary.map((region_id) => ({ region_id, kind: 'primary' as const })),
  ...radiation.map((region_id) => ({ region_id, kind: 'radiation' as const })),
]

// ---------------------------------------------------------------- 模拟：一位腰痛患者（P-模拟）

const T0 = '2026-09-25T09:00:00Z'
const TEXT_1 = '腰痛三个月了，最近越来越痛，左腿麻，走路走久了左腿发软。这两天小便有点憋不住，不好意思跟家里人说。晚上睡觉翻身也疼。'
const TEXT_2 = '还是左腿麻，蹲下再站起来的时候最明显。'
const BLADDER_QUOTE = '小便有点憋不住'

const entry = (id: string, seq: number, kind: string, payload: Record<string, unknown>): Entry => ({ id, seq, kind, payload, created_at: T0 })

function buildCase(disputed: boolean) {
  const decision = disputed ? 'reject' : 'confirm'
  const word = disputed ? '不对' : '对'
  const entries: Entry[] = [
    entry('lab_ent_body', 1, 'body_map', { marks: marks(['lower_back_center'], ['thigh_left_back', 'calf_left']) }),
    entry('lab_ent_text1', 2, 'free_text', { text: TEXT_1 }),
    entry('lab_ent_verify', 3, 'answer', {
      question_id: 'verify:urgent:1',
      kind: 'verification',
      decisions: { bladder_bowel_change: decision },
      items: [{ fact_key: 'bladder_bowel_change', label: '大小便控制是否出现变化', value_label: '有', quote: BLADDER_QUOTE }],
    }),
    entry('lab_ent_text2', 4, 'free_text', { text: TEXT_2 }),
  ]
  const t1 = (quote: string): Evidence => ({ entry_id: 'lab_ent_text1', quote, kind: 'free_text' })
  const t2 = (quote: string): Evidence => ({ entry_id: 'lab_ent_text2', quote, kind: 'free_text' })
  const body = (quote: string): Evidence => ({ entry_id: 'lab_ent_body', quote, kind: 'body_map' })
  const verify: Evidence = { entry_id: 'lab_ent_verify', quote: `患者核对「大小便控制是否出现变化：有」：${word}`, kind: 'answer' }

  let n = 0
  const fact = (key: string, label: string, category: string, status: Fact['status'], value_label: string, evidence: Evidence[]): Fact => ({
    id: `lab_fact_${++n}`,
    key,
    status,
    value: null,
    evidence,
    source: evidence[0]?.kind === 'body_map' ? 'body_map' : 'extraction',
    version: 1,
    patient_confirmed: false,
    label,
    type: 'enum',
    category,
    required: false,
    critical: false,
    value_label,
  })

  const facts: Fact[] = [
    fact('pain_regions', '疼痛部位', 'location', 'present', '腰部正中', [body('身体图标记：腰部正中')]),
    fact('radiation_regions', '放射到的部位', 'radiation', 'present', '左大腿（后）、左小腿（后）', [
      body('身体图放射标记：左大腿（后）、左小腿（后）'),
    ]),
    fact('onset_timing', '这次不舒服开始多久了', 'onset', 'present', '6 到 12 周', [t1('腰痛三个月了')]),
    fact('onset_mode', '起病方式', 'onset', 'present', '慢慢出现', [t1('最近越来越痛')]),
    fact('course', '最近的变化趋势', 'timing', 'present', '在加重', [t1('最近越来越痛')]),
    fact('leg_numbness', '腿或脚是否发麻', 'associated', 'present', '是', [t1('左腿麻'), t2('左腿麻')]),
    fact('aggravating', '什么情况会加重', 'aggravating', 'present', '走路、蹲起', [t1('走路走久了'), t2('蹲下再站起来')]),
    fact('leg_weakness', '腿是否无力', 'associated', 'present', '是', [t1('左腿发软')]),
    // 患者在核对里说"不对"后，后端把事实退回"未询问"，新版本不带原话证据；红线靠 alerts 里触发时的证据接上
    disputed
      ? fact('bladder_bowel_change', '大小便控制是否出现变化', 'red_flag', 'not_asked', '未询问', [verify])
      : fact('bladder_bowel_change', '大小便控制是否出现变化', 'red_flag', 'present', '是', [t1(BLADDER_QUOTE), verify]),
    fact('night_pain', '是否夜间痛醒', 'red_flag', 'present', '是', [t1('晚上睡觉翻身也疼')]),
    // 模拟一条模型给错的引文：原话里没有这几个字 → 不画线，卡片报警
    fact('character', '疼痛的感觉', 'character', 'present', '刺痛', [t1('像针扎一样')]),
  ]

  const alerts: Alert[] = [
    {
      id: 'lab_alr_1',
      rule_id: 'rf_bladder_bowel',
      severity: 'urgent',
      label: '大小便控制变化',
      patient_message: '（模拟）',
      evidence: [{ fact_key: 'bladder_bowel_change', status: 'present', value: true, evidence: [t1(BLADDER_QUOTE)] }],
      notice_shown: true,
      patient_disputed: disputed,
      created_at: T0,
    },
  ]
  return { entries, facts, alerts }
}

// ---------------------------------------------------------------- 页面

const box: React.CSSProperties = { background: '#fff', border: '1px solid #dde3ea', borderRadius: 10, padding: 16 }
const tag: React.CSSProperties = {
  display: 'inline-block',
  padding: '1px 8px',
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 600,
  background: '#eef1f5',
  color: '#475467',
  border: '1px dashed #98a2b3',
}

function Mock() {
  return <span style={tag}>模拟</span>
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <h2 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {title} <Mock />
      </h2>
      {hint && <p className="small muted">{hint}</p>}
      {children}
    </section>
  )
}

export default function ComponentLab() {
  const [disputed, setDisputed] = useState(true)
  const [compact, setCompact] = useState(false)
  const [run, setRun] = useState(0)
  const data = useMemo(() => buildCase(disputed), [disputed])
  const phoneEntries = useMemo(() => data.entries.filter((e) => e.id !== 'lab_ent_text2'), [data])
  const phoneFacts = useMemo(
    () =>
      data.facts
        .filter((f) => f.evidence.every((ev) => ev.kind !== 'body_map'))
        .map((f) => ({ ...f, evidence: f.evidence.filter((ev) => ev.entry_id !== 'lab_ent_text2') })),
    [data],
  )

  const [patientMarks, setPatientMarks] = useState<Mark[]>(marks(['lower_back_center'], ['buttock_left', 'thigh_left_back', 'calf_left']))
  const [mode, setMode] = useState<MarkKind>('radiation')
  const toggle = (id: string) =>
    setPatientMarks((prev) => {
      const cur = prev.find((m) => m.region_id === id)
      if (cur && cur.kind === mode) return prev.filter((m) => m.region_id !== id)
      return [...prev.filter((m) => m.region_id !== id), { region_id: id, kind: mode }]
    })

  const thumbs: { title: string; marks: Mark[] }[] = [
    { title: '腰 → 左腿', marks: marks(['lower_back_center'], ['buttock_left', 'thigh_left_back', 'calf_left', 'heel_left']) },
    { title: '腰 → 双腿', marks: marks(['lower_back_center'], ['thigh_left_back', 'thigh_right_back', 'calf_left', 'calf_right']) },
    { title: '右髋 → 大腿前', marks: marks(['hip_right_front'], ['thigh_right_front', 'knee_right_front', 'shin_right']) },
    { title: '颈 → 右臂', marks: marks(['neck_back'], ['shoulder_right_back', 'upper_arm_right_back', 'forearm_right_back', 'hand_right_back']) },
    { title: '只有腰痛', marks: marks(['lower_back_left', 'lower_back_center'], []) },
    { title: '未标记', marks: [] },
  ]

  return (
    <div style={{ maxWidth: 1180, margin: '0 auto', padding: '28px 20px 80px', display: 'flex', flexDirection: 'column', gap: 28 }}>
      <header style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          组件试验页 <Mock />
        </h1>
        <p className="muted">
          出处连线 QuoteTrace 与身体图"疼痛轨迹"的样张。页面上的原话、事实、红旗和身体图标记全部是写死的模拟数据，不连后端、不写库。
        </p>
      </header>

      <div style={{ ...box, display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
        <span className="small strong">「{BLADDER_QUOTE}」核对结果：</span>
        <label className="check-inline small">
          <input type="radio" checked={!disputed} onChange={() => setDisputed(false)} /> 对（红旗已触发 · 红色实线）
        </label>
        <label className="check-inline small">
          <input type="radio" checked={disputed} onChange={() => setDisputed(true)} /> 不对（患者否认 · 红色虚线，待电话核实）
        </label>
        <label className="check-inline small">
          <input type="checkbox" checked={compact} onChange={(e) => setCompact(e.target.checked)} /> 桌面样张用紧凑版
        </label>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => setRun((r) => r + 1)}>
          重播连线动画
        </button>
      </div>

      <Section
        title="QuoteTrace · 桌面宽"
        hint="两段原话 + 身体图 + 一键核对。悬停卡片或下划线可高亮对应连线；「像针扎一样」是故意放进去的错引文，原话里没有，所以不画线、卡片报警。"
      >
        <div style={box}>
          <QuoteTrace key={`d${run}`} entries={data.entries} facts={data.facts} alerts={data.alerts} compact={compact} />
        </div>
      </Section>

      <Section title="QuoteTrace · 手机宽（375px）" hint="患者描述结果页的样子：卡片在下方，连线绕右侧走线槽、横穿、再从左侧接进卡片，互不交叉。">
        <div style={{ width: 375, maxWidth: '100%', border: '8px solid #16233b', borderRadius: 28, overflow: 'hidden', background: '#f4f6f9' }}>
          <div style={{ padding: 16 }}>
            <div style={{ ...box, padding: 14 }}>
              <QuoteTrace key={`p${run}`} entries={phoneEntries} facts={phoneFacts} alerts={data.alerts} />
            </div>
          </div>
        </div>
      </Section>

      <Section title="BodyMap · 疼痛轨迹" hint="区域热区保持透明，悬停或键盘聚焦时才描边；光晕裁在轮廓内；轨迹从主要疼痛质心自上而下连到放射区域。">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 16, alignItems: 'start' }}>
          <div style={{ ...box, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h3>背面 · 医生端（只读，静止）</h3>
            <BodyMap regions={REGIONS} marks={marks(['lower_back_center'], ['buttock_left', 'thigh_left_back', 'calf_left', 'heel_left'])} size="compact" initialView="back" />
          </div>
          <div style={{ ...box, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h3>正面 · 医生端（只读，静止）</h3>
            <BodyMap regions={REGIONS} marks={marks(['hip_right_front'], ['thigh_right_front', 'knee_right_front', 'shin_right'])} size="compact" initialView="front" />
          </div>
          <div style={{ ...box, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h3>患者端（可点选，轨迹流动）</h3>
            <div className="seg" role="radiogroup" aria-label="标记类型">
              {(['primary', 'radiation'] as MarkKind[]).map((k) => (
                <button key={k} type="button" className={`seg-btn${mode === k ? ' active' : ''}`} onClick={() => setMode(k)}>
                  {MARK_KIND_LABEL[k]}
                </button>
              ))}
            </div>
            <BodyMap regions={REGIONS} marks={patientMarks} mode={mode} onToggle={toggle} initialView="back" />
          </div>
        </div>
        <div style={{ ...box, display: 'flex', flexWrap: 'wrap', gap: 20 }}>
          {thumbs.map((t) => (
            <figure key={t.title} style={{ margin: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
              <BodyMap regions={REGIONS} marks={t.marks} size="thumb" />
              <figcaption className="small muted">{t.title}</figcaption>
            </figure>
          ))}
        </div>
      </Section>
    </div>
  )
}
