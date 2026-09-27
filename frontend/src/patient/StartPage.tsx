import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { DEFAULT_PROTOCOL_ID, authApi, errorMessage, patientApi, protocolApi, track } from '../api/client'
import type { EncounterKind, ProtocolDetail, Respondent } from '../api/types'
import { ErrorBox, Loading } from '../components/Boxes'
import { CURRENT_ENCOUNTER_KEY, LAST_ENCOUNTER_KEY, isKiosk, setKiosk, storageGet, storageSet } from '../storage'
import { PatientShell } from './PatientShell'

export default function StartPage() {
  const nav = useNavigate()
  const [inviteToken] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('invite') ?? '')
  const [inviteProtocol, setInviteProtocol] = useState('')
  const [params] = useSearchParams()
  const [proto, setProto] = useState<ProtocolDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [agreed, setAgreed] = useState(false)
  // 适用范围逐条确认（协议 scope.eligibility，如年满 18 岁、没有怀孕）；任何一条"不对"都不进入采集
  const [elig, setElig] = useState<Record<string, boolean>>({})
  // 可用性测试：主持人打开 /p?code=UT-P01-A，编号自动带入（UT- 开头的记录会进入测试汇总）
  const [code, setCode] = useState(() => params.get('code') ?? '')
  const [mode, setMode] = useState<EncounterKind>(() => (params.get('mode') === 'follow_up' ? 'follow_up' : 'pre_visit'))
  const [parentId, setParentId] = useState(() => params.get('parent') ?? storageGet(LAST_ENCOUNTER_KEY) ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // 谁在填（第 1 轮团队评审 · 工业设计）：本人 / 家属代述（本人在场）/ 前台代录
  const [respondent, setRespondent] = useState<Respondent>('self')
  const [relation, setRelation] = useState('')
  const [proxyConsent, setProxyConsent] = useState(false)
  // 从随访卡扫码进来（链接里已带 mode、parent、code）：不再让患者手输编号、不显示模式切换
  const scanned = params.get('mode') === 'follow_up' && !!params.get('parent')
  if (params.get('kiosk') === '1') setKiosk(true)
  const kiosk = isKiosk()
  const current = kiosk ? null : storageGet(CURRENT_ENCOUNTER_KEY)

  // 协议可由链接指定（如 /p?protocol=knee_adult_v0.1），默认腰背痛
  const protocolId = inviteProtocol || params.get('protocol') || DEFAULT_PROTOCOL_ID
  useEffect(() => {
    protocolApi
      .get(protocolId)
      .then(setProto)
      .catch((e) => setLoadError(errorMessage(e)))
  }, [protocolId])

  useEffect(() => {
    if (!inviteToken) return
    let active = true
    authApi.inspect(inviteToken).then(i => {
      if (!active) return
      setInviteProtocol(i.protocol_id); setCode(i.patient_code); setMode(i.kind); setParentId(i.parent_encounter_id ?? '')
    }).catch(e => { if (active) setLoadError(errorMessage(e)) })
    return () => { active = false }
  }, [inviteToken])

  const eligItems = proto?.scope.eligibility ?? []
  const eligBlocked = eligItems.find((it) => elig[it.id] === false)
  const eligOk = eligItems.every((it) => elig[it.id] === true)
  const canStart = agreed && eligOk && (!inviteToken || !!inviteProtocol) && !loadError

  async function start(kind: EncounterKind) {
    if (!eligOk) {
      setError(eligBlocked ? eligBlocked.if_not : '请先逐条确认适用范围。')
      return
    }
    if (!agreed) {
      setError('请先勾选"我已了解本工具不做诊断，也不提供治疗或用药建议"。')
      return
    }
    if (kind === 'follow_up' && !parentId.trim()) {
      setError('开始签到需要上次就诊的记录：请扫随访卡上的二维码，或填写上次完成页显示的编号。')
      return
    }
    if (respondent !== 'self' && !proxyConsent) {
      setError('代填时需要患者本人在场并同意：请勾选确认。')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const s = await patientApi.create({
        invite_token: inviteToken || undefined,
        patient_code: code.trim() || undefined,
        protocol_id: protocolId,
        kind,
        parent_encounter_id: kind === 'follow_up' ? parentId.trim() : undefined,
        eligibility: eligItems.length ? elig : undefined,
        respondent,
        respondent_relation: respondent === 'family' ? relation.trim() || undefined : undefined,
        proxy_consent: respondent !== 'self' ? proxyConsent : undefined,
      })
      if (!kiosk) storageSet(CURRENT_ENCOUNTER_KEY, s.id)
      track(s.id, 'session_start', { kind, test: (code.trim() || '').startsWith('UT-') })
      nav(`/p/e/${s.id}/body`)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <PatientShell subtitle="开始之前">
      <div className="stack">
        {loadError && <ErrorBox error={loadError} />}
        {!proto && !loadError && <Loading text="正在加载协议信息…" />}
        {proto && (
          <>
            <section className="card">
              <h1 className="p-title">{mode === 'follow_up' ? '治疗前签到 · 说说这几天怎么样' : '首诊前 · 先把腰背的情况说清楚'}</h1>
              <p className="p-text">
                {mode === 'follow_up'
                  ? '记录近况和变化，交给门诊核对。所需时间因问题和回答而异。'
                  : '可以打字，也可以使用手机输入法语音。按实际情况回答，不清楚可以如实选择。'}
              </p>
              <p className="muted small">
                协议版本 {proto.version} · {proto.status === 'approved' ? '已批准' : proto.course?.simulated ? '内容为模拟临床稿，待医生审定（原型演示）' : '尚未临床审核（原型演示）'}
              </p>
            </section>

            <section className="card">
              <h2 className="card-title">这个工具能做什么、不能做什么</h2>
              <p className="p-text">{proto.scope.service_notice}</p>
              <p className="muted small">服务时间：{proto.scope.service_hours}</p>
            </section>

            <section className="box box-emergency" role="note">
              <strong>紧急情况提示</strong>
              <p>{proto.scope.emergency_notice}</p>
            </section>

            {eligItems.length > 0 && (
              <section className="card">
                <h2 className="card-title">先确认这个工具适合你</h2>
                <div className="stack-sm">
                  {eligItems.map((it) => (
                    <div key={it.id} className="elig-row">
                      <p className="p-text">{it.text}</p>
                      <div className="seg seg-block">
                        <button
                          type="button"
                          className={`seg-btn${elig[it.id] === true ? ' active' : ''}`}
                          onClick={() => setElig((prev) => ({ ...prev, [it.id]: true }))}
                        >
                          对
                        </button>
                        <button
                          type="button"
                          className={`seg-btn${elig[it.id] === false ? ' active' : ''}`}
                          onClick={() => setElig((prev) => ({ ...prev, [it.id]: false }))}
                        >
                          {it.no_label}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                {eligBlocked && (
                  <div className="box box-warn" role="note">
                    <p>{eligBlocked.if_not}</p>
                  </div>
                )}
              </section>
            )}

            <section className="card">
              <label className="check-row">
                <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
                <span>我已了解本工具不做诊断，也不提供治疗或用药建议。</span>
              </label>

              <div className="field">
                <span className="field-label">谁在填？</span>
                <div className="respondent-grid" role="radiogroup">
                  {(proto.course?.respondent?.options?.length
                    ? proto.course.respondent.options
                    : [
                        { value: 'self' as Respondent, label: '我自己' },
                        { value: 'family' as Respondent, label: '家属帮我填（我在旁边）' },
                        { value: 'staff' as Respondent, label: '前台帮我填' },
                      ]
                  ).map((o) => (
                    <button
                      key={o.value}
                      type="button"
                      role="radio"
                      aria-checked={respondent === o.value}
                      className={`opt-btn${respondent === o.value ? ' selected' : ''}`}
                      onClick={() => setRespondent(o.value)}
                    >
                      {o.label}
                    </button>
                  ))}
                </div>
                {respondent === 'family' && (
                  <input value={relation} onChange={(e) => setRelation(e.target.value)} placeholder="你和患者的关系（可不填），如：女儿" />
                )}
                {respondent !== 'self' && (
                  <label className="check-row">
                    <input type="checkbox" checked={proxyConsent} onChange={(e) => setProxyConsent(e.target.checked)} />
                    <span>患者本人就在旁边，同意由我代填；答案按患者本人的说法填写。</span>
                  </label>
                )}
              </div>

              {!scanned && (
              <div className="field">
                <label className="field-label" htmlFor="patient-code">
                  患者编号（可选，如 P-0005；留空将自动分配）
                </label>
                <input
                  id="patient-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="P-0005"
                  autoComplete="off"
                />
              </div>
              )}

              {!scanned && (
              <div className="seg seg-block">
                <button
                  type="button"
                  className={`seg-btn${mode === 'pre_visit' ? ' active' : ''}`}
                  onClick={() => setMode('pre_visit')}
                >
                  就诊前填写
                </button>
                <button
                  type="button"
                  className={`seg-btn${mode === 'follow_up' ? ' active' : ''}`}
                  onClick={() => setMode('follow_up')}
                >
                  治疗前签到 / 随访
                </button>
              </div>
              )}

              {mode === 'follow_up' && !scanned && (
                <div className="field">
                  <label className="field-label" htmlFor="parent-id">
                    上次就诊的记录编号（上次完成页显示的 enc_… 编号）
                  </label>
                  <input
                    id="parent-id"
                    value={parentId}
                    onChange={(e) => setParentId(e.target.value)}
                    placeholder="enc_xxxxxxxxxxxx"
                    autoComplete="off"
                    className="mono"
                  />
                  <p className="small muted">只有医生已确认的就诊才能进入随访；随访患者编号需与上次一致。</p>
                </div>
              )}

              <ErrorBox error={error} onClose={() => setError(null)} />

              {mode === 'pre_visit' ? (
                <button
                  type="button"
                  className="btn btn-primary btn-lg btn-block"
                  disabled={busy || !canStart}
                  onClick={() => start('pre_visit')}
                >
                  {busy ? '正在创建…' : '开始就诊前填写'}
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn-primary btn-lg btn-block"
                  disabled={busy || !canStart}
                  onClick={() => start('follow_up')}
                >
                  {busy ? '正在创建…' : '开始签到'}
                </button>
              )}

              {current && (
                <p className="small center">
                  上次未完成的填写：
                  <Link to={`/p/e/${current}/body`} className="mono">
                    {current}
                  </Link>
                </p>
              )}
            </section>
          </>
        )}
        <p className="small muted center">原型演示 · 你填写的内容会由门诊医生查看，系统本身不做医学判断。</p>
      </div>
    </PatientShell>
  )
}
