import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { errorMessage, patientApi, track } from '../api/client'
import type { ExtractionResult, FactStatus } from '../api/types'
import { regionLabel } from '../components/bodyRegionLabels'
import { ErrorBox } from '../components/Boxes'
import { useBodyRegions, useProtocol } from '../hooks'
import { usePatient } from './PatientContext'
import { Steps } from './PatientShell'

const PATIENT_STATUS: Record<FactStatus, string> = {
  present: '已记录',
  denied: '记录为「没有」',
  uncertain: '记录为「不太确定」',
  conflicting: '与之前的说法不一致，稍后会请你澄清',
  not_asked: '',
  asked_unanswered: '',
}

// 例句只示范"怎么说"，不含任何红旗说法（红旗由后面的安全检查一屏直接问）
const PREVISIT_EXAMPLES = ['腰疼三天了，弯腰更疼，躺下好一点。', '左边腰和屁股酸，坐久了更明显。', '老毛病又犯了，这次搬东西闪到了。']
const FOLLOWUP_EXAMPLES = ['比上次好一些，但坐久了还是酸。', '差不多，没什么新情况。', '这两天又疼得厉害了。']

export default function DescribePage() {
  const { id, state, addAlerts } = usePatient()
  const nav = useNavigate()
  const { protocol } = useProtocol(state?.protocol.id)
  const { regions } = useBodyRegions()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ExtractionResult | null>(null)
  const [mountedAt] = useState(Date.now)

  function factLabel(key: string): string {
    return protocol?.facts.find((f) => f.key === key)?.label ?? key
  }

  function valueLabel(key: string, value: unknown): string | null {
    if (value === null || value === undefined || typeof value === 'boolean') return null
    const def = protocol?.facts.find((f) => f.key === key)
    const optLabel = (v: string) => def?.options.find((o) => o.value === v)?.label ?? regionLabel(regions, v)
    if (Array.isArray(value)) return value.map((v) => optLabel(String(v))).join('、')
    if (typeof value === 'object') return null
    return optLabel(String(value))
  }

  async function submit() {
    if (!text.trim()) {
      setError('请先写一点描述。')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const t0 = Date.now()
      const r = await patientApi.text(id, text.trim())
      track(id, 'step_submit', { step: 'describe', chars: text.trim().length, ms: t0 - mountedAt, wait_ms: Date.now() - t0,
        provider: r.extraction.provider, applied: r.extraction.applied.length })
      if (r.new_alerts.length) addAlerts(r.new_alerts)
      setResult(r.extraction)
      window.scrollTo({ top: 0 })
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  if (result) {
    const applied = result.applied.filter((a) => PATIENT_STATUS[a.status])
    return (
      <div className="stack">
        <Steps current="describe" />
        <h1 className="p-title">我们从你的描述里整理出的信息</h1>
        <p className="p-text muted">
          共整理出 {applied.length} 条。其中关键的几条，下一步会先请你核对；整理得不对的地方也可以在确认页修改。
        </p>
        {result.provider === 'mock(fallback)' && (
          <p className="small muted">（网络原因，本次用离线方式整理，可能漏掉一些说法；接下来的问题会帮你补全。）</p>
        )}
        <section className="card">
          {applied.length === 0 ? (
            <p className="muted">这段描述里没有识别出可以整理的条目。没关系，医生会看到你的原话；接下来的问题会帮你补充。</p>
          ) : (
            <ul className="fact-list">
              {applied.map((a, i) => {
                const v = valueLabel(a.key, a.value)
                return (
                  <li key={`${a.key}-${i}`} className="fact-item">
                    <span className="fact-label">{factLabel(a.key)}</span>
                    <span className="fact-value">
                      {v ?? ''}
                      <span className={`fact-status st-${a.status}`}>{PATIENT_STATUS[a.status]}</span>
                    </span>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
        {result.unmapped_mentions.length > 0 && (
          <section className="card">
            <h2 className="card-title">以下内容暂时没有对应的条目</h2>
            <p className="small muted">医生会看到你的原话，不会丢失。</p>
            <ul className="plain-list">
              {result.unmapped_mentions.map((m, i) => (
                <li key={i}>「{m}」</li>
              ))}
            </ul>
          </section>
        )}
        <button type="button" className="btn btn-primary btn-lg btn-block" onClick={() => nav(`/p/e/${id}/questions`)}>
          继续回答几个问题
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-block"
          onClick={() => {
            setResult(null)
            setText('')
          }}
        >
          再补充一段描述
        </button>
      </div>
    )
  }

  return (
    <div className="stack">
      <Steps current="describe" />
      <h1 className="p-title">用自己的话说说情况</h1>
      <p className="p-text muted">
        {state?.kind === 'follow_up'
          ? '和上次相比有什么变化？有没有新的情况？想到什么写什么，不用讲究措辞。'
          : '什么时候开始的、怎么开始的、哪里不舒服、什么情况下更明显或轻一些……想到什么写什么。'}
      </p>
      <div className="voice-hint" role="note">
        <span className="voice-mic" aria-hidden="true">🎙</span>
        <div>
          <strong>不想打字？点手机键盘上的话筒，直接说。</strong>
          <p className="small">语言支持取决于手机输入法。请检查转写中的部位、时间和否定词，有误先修改。</p>
        </div>
      </div>
      <textarea
        className="p-textarea"
        rows={7}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={
          state?.kind === 'follow_up'
            ? '比如：比上次好一些了，但坐久了还是酸，没有新的不舒服……'
            : '比如：前两天搬东西后左边腰酸，坐久了更明显，躺着好一些，腿不麻……'
        }
      />
      {!text && (
        <div className="example-chips">
          <span className="small muted">不知道怎么说？点一句改一改：</span>
          {(state?.kind === 'follow_up' ? FOLLOWUP_EXAMPLES : PREVISIT_EXAMPLES).map((ex) => (
            <button key={ex} type="button" className="chip" onClick={() => setText(ex)}>
              {ex}
            </button>
          ))}
        </div>
      )}
      <ErrorBox error={error} onClose={() => setError(null)} />
      <button type="button" className="btn btn-primary btn-lg btn-block" disabled={busy || !text.trim()} onClick={submit}>
        {busy ? '正在读你的话…' : '提交描述'}
      </button>
      {busy && <p className="small muted center reading-note">正在逐句读你的话，每一条都会连回原话；通常几秒钟。</p>}
      <Link to={`/p/e/${id}/questions`} className="btn btn-ghost btn-block">
        不想写，直接回答问题
      </Link>
      <p className="small muted">你写的原话会完整保留给医生；系统整理信息并按协议提醒，不作诊断。</p>
    </div>
  )
}
