import { useEffect, useMemo, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { protocolApi } from '../api/client'
import type { ClockInfo, HealthInfo, ProbeResult } from '../api/types'
import { providerLabel } from '../labels'
import { useStaff } from '../auth/AuthContext'
import { ActorContext, type ActorCtx } from './ActorContext'

export default function DoctorLayout() {
  const { user, logout } = useStaff()
  const actor = user.actor
  const ctx = useMemo<ActorCtx>(() => ({ actor, setActor: () => {} }), [actor])
  const [health, setHealth] = useState<HealthInfo | null>(null)
  const [probe, setProbe] = useState<ProbeResult | null>(null)
  const [probing, setProbing] = useState(false)
  useEffect(() => {
    protocolApi.health().then(setHealth).catch(() => setHealth(null))
  }, [])
  const llm = health?.llm
  const llmName = llm?.name ?? health?.llm_provider
  const isReal = !!llmName && llmName !== 'mock'
  // 真实模型未就绪或最近一次失败：顶栏如实写"已退回离线词表"，演示时一眼能看到
  const degraded = isReal && (llm?.ready === false || llm?.last_used === 'mock(fallback)')
  const lastProbe = probe ?? llm?.last_probe ?? null

  async function runProbe() {
    setProbing(true)
    try {
      setProbe(await protocolApi.probe())
      setHealth(await protocolApi.health())
    } catch {
      setProbe(null)
    } finally {
      setProbing(false)
    }
  }

  return (
    <ActorContext.Provider value={ctx}>
      <div className="d-shell">
        <header className="d-topbar">
          <Link to="/" className="brand">
            体迹 AI
          </Link>
          <span className="d-topbar-sub">医生端</span>
          <span className="d-proto-note">原型 · 演示数据均为模拟，非真实患者</span>
          <span
            className={`d-llm-badge${isReal ? ' real' : ''}${degraded ? ' degraded' : ''}`}
            title={
              llm?.not_ready_reason || llm?.last_error
                ? `最近的问题：${llm?.not_ready_reason ?? llm?.last_error}`
                : '抽取与叙述使用的模型；真实模型失败时自动退回离线词表'
            }
          >
            抽取：{providerLabel(llmName)}
            {llm?.ready === false ? ' · 未就绪，正在用离线词表' : degraded ? ' · 最近一次失败，已退回离线词表' : llm?.fallback === 'mock' ? ' · 失败兜底：离线词表' : ''}
          </span>
          {isReal && (
            <button type="button" className="btn btn-secondary btn-sm d-probe-btn" onClick={runProbe} disabled={probing} title="用一句固定的测试原话调用一次真实模型">
              {probing ? '自检中…' : '模型自检'}
            </button>
          )}
          {health?.clock && <DemoClock clock={health.clock} canSet={!!health.dev_endpoints} onChanged={() => protocolApi.health().then(setHealth).catch(() => undefined)} />}
          {isReal && lastProbe && (
            <span className={`small ${lastProbe.ok ? 'text-ok' : 'text-red'}`} title={lastProbe.detail}>
              {lastProbe.ok ? `自检通过 · ${lastProbe.seconds ?? '?'} 秒` : '自检失败'}
            </span>
          )}
          <div className="row wrap"><span>{user.display_name} · {user.role === 'doctor' ? '医生' : user.role === 'nurse' ? '护士' : '工作人员'}</span><button className="btn btn-secondary btn-sm" onClick={() => { void logout() }}>退出登录</button></div>
        </header>
        <div className="d-body">
          <nav className="d-sidebar" aria-label="医生端导航">
            {(user.role === 'doctor' || user.role === 'nurse') && <NavLink to="/d" end className={({ isActive }) => `d-nav${isActive ? ' active' : ''}`}>
              就诊列表
            </NavLink>}
            <NavLink to="/d/tasks" className={({ isActive }) => `d-nav${isActive ? ' active' : ''}`}>
              任务
            </NavLink>
            <NavLink to="/d/protocols" className={({ isActive }) => `d-nav${isActive ? ' active' : ''}`}>
              协议
            </NavLink>
            <div className="d-sidebar-foot small muted">
              模型整理原话和复述差异；问什么、何时升级，由临床协议决定并交医护核实。
            </div>
          </nav>
          <main className="d-main">
            <Outlet />
          </main>
        </div>
      </div>
    </ActorContext.Provider>
  )
}


/** 门诊本地时间与是否开诊；演示环境可把时间拨到"晚上 22:47"或"次日 08:30"（/api/dev/clock） */
function DemoClock({ clock, canSet, onChanged }: { clock: ClockInfo; canSet: boolean; onChanged: () => void }) {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState('')
  async function apply(at: string | null) {
    await protocolApi.setClock(at)
    setOpen(false)
    onChanged()
  }
  const today = clock.now_local.slice(0, 10)
  return (
    <span className="d-clock">
      <button type="button" className={`link-btn small${clock.demo_clock ? ' strong' : ''}`} onClick={() => canSet && setOpen((o) => !o)} title={clock.service_hours ?? ''}>
        {clock.demo_clock ? '演示时钟 ' : ''}
        {clock.now_local.slice(5)} · {clock.in_service_hours === null ? '未设服务时段' : clock.in_service_hours ? '开诊中' : '已停诊'}
      </button>
      {open && (
        <span className="d-clock-pop">
          <button type="button" className="btn btn-sm btn-secondary" onClick={() => apply(`${today}T22:47:00+08:00`)}>
            今晚 22:47
          </button>
          <button type="button" className="btn btn-sm btn-secondary" onClick={() => {
            const d = new Date(`${today}T00:00:00+08:00`)
            d.setDate(d.getDate() + 1)
            const y = d.toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' })
            void apply(`${y}T08:31:00+08:00`)
          }}>
            次日 08:31
          </button>
          <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="2026-10-15T10:00:00+08:00" className="input-sm" />
          <button type="button" className="btn btn-sm btn-secondary" disabled={!value.trim()} onClick={() => apply(value.trim())}>
            设定
          </button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => apply(null)}>
            恢复真实时间
          </button>
        </span>
      )}
    </span>
  )
}
