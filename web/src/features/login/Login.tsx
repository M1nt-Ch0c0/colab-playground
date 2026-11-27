import { motion } from 'motion/react'
import { Zap } from 'lucide-react'
import { useState } from 'react'
import { api } from '../../api/client'

export function Login() {
  const [pw, setPw] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!pw) return
    setBusy(true); setErr('')
    try {
      await api.login(pw)
      history.replaceState(null, '', location.pathname + location.search)
      location.reload()
    } catch (error) {
      setErr(error instanceof Error ? error.message : '连不上服务')
    }
    setBusy(false)
  }
  return (
    <div className="login">
      <motion.form className="login-card glass" onSubmit={submit} initial={{ opacity: 0, y: 16, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ type: 'spring', stiffness: 260, damping: 26 }}>
        <span className="mark lg"><Zap size={22} /></span>
        <h1>Colab Studio</h1>
        <p className="dim">输入访问密码</p>
        <input type="password" autoFocus value={pw} onChange={e => setPw(e.target.value)} placeholder="密码" autoComplete="current-password" />
        {err && <span className="bad-text">{err}</span>}
        <button className="btn primary go" disabled={busy || !pw}>{busy ? <span className="spinner" /> : '进入'}</button>
        {__MOCK__ && <small className="dim">mock 模式下任意密码都能进入</small>}
      </motion.form>
    </div>
  )
}
