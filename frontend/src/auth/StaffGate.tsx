import { useEffect, useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { authApi, errorMessage } from '../api/client'
import { ErrorBox, Loading } from '../components/Boxes'
import { AuthContext, type StaffUser } from './AuthContext'

export default function StaffGate() {
  const [user, setUser] = useState<StaffUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  useEffect(() => {
    let active = true
    authApi.me().then(u => { if (active) setUser(u) })
      .catch(() => { if (active) setUser(null) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])
  async function logout() {
    await authApi.logout()
    setUser(null)
  }
  if (loading) return <Loading text="正在检查登录…" />
  if (user) return <AuthContext.Provider value={{ user, logout }}><Outlet /></AuthContext.Provider>
  return <main className="home"><div className="card stack" style={{ maxWidth: 440, margin: '32px auto' }}>
    <Link to="/" className="brand">体迹 AI</Link>
    <h1>医护登录</h1>
    <p>请使用机构为你分配的账号。操作将以登录身份记录。</p>
    <form className="stack" onSubmit={async e => {
      e.preventDefault(); setBusy(true); setError(null)
      try { setUser(await authApi.login(username.trim(), password)); setPassword('') }
      catch (err) { setError(errorMessage(err)) }
      finally { setBusy(false) }
    }}>
      <label>账号<input className="input" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required /></label>
      <label>口令<input className="input" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
      <ErrorBox error={error} />
      <button className="btn btn-primary" disabled={busy} type="submit">{busy ? '登录中…' : '登录'}</button>
    </form>
  </div></main>
}
