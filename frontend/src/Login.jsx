import { useState } from 'react'
import { Laptop } from 'lucide-react'
import { errorMessage } from './api'
import { useAuth } from './auth'

export default function Login() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (mode === 'login') await login(email.trim(), password)
      else await register(fullName.trim(), email.trim(), password)
    } catch (err) {
      setError(errorMessage(err, 'Cannot reach the server. Is the backend running?'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand"><div className="brand-icon"><Laptop size={21} /></div><span>VoltKart</span></div>
        <h2>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2>
        <p className="auth-sub">
          {mode === 'login' ? 'Sign in to use the shopping assistant.' : 'Sign up to start chatting with the assistant.'}
        </p>

        {mode === 'register' && (
          <label className="field">Full name
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} required maxLength={120} />
          </label>
        )}
        <label className="field">Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
        </label>
        <label className="field">Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
            minLength={mode === 'register' ? 8 : 1} maxLength={72}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
        </label>
        {mode === 'register' && <p className="hint">At least 8 characters.</p>}

        {error && <div className="error-banner">{error}</div>}

        <button className="primary-btn" type="submit" disabled={busy}>
          {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>
        <button type="button" className="link-btn"
          onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
          {mode === 'login' ? 'New here? Create an account' : 'Already have an account? Sign in'}
        </button>
      </form>
    </div>
  )
}