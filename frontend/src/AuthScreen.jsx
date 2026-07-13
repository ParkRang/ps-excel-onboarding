import { useState } from 'react'
import { getMe, login, register } from './api/auth'
import './App.css'

export default function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const isRegister = mode === 'register'

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (isRegister) {
        await register(email, password)
      }
      await login(email, password) // 토큰 저장
      const user = await getMe()
      onAuthenticated(user)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="page-shell auth-shell">
      <div className="auth-card">
        <p className="eyebrow">ORDER EXPORT</p>
        <h1>{isRegister ? '회원가입' : '로그인'}</h1>
        <p className="description">
          {isRegister ? '계정을 만들어 주문 엑셀을 관리하세요.' : '계정으로 로그인하세요.'}
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            이메일
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            비밀번호
            <input
              type="password"
              autoComplete={isRegister ? 'new-password' : 'current-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>

          {error && <div className="alert" role="alert">{error}</div>}

          <button className="primary-button" type="submit" disabled={busy}>
            {busy ? '처리 중…' : isRegister ? '회원가입' : '로그인'}
          </button>
        </form>

        <p className="auth-switch">
          {isRegister ? '이미 계정이 있으신가요?' : '아직 계정이 없으신가요?'}{' '}
          <button
            type="button"
            className="text-button"
            onClick={() => {
              setMode(isRegister ? 'login' : 'register')
              setError('')
            }}
          >
            {isRegister ? '로그인' : '회원가입'}
          </button>
        </p>
      </div>
    </main>
  )
}
