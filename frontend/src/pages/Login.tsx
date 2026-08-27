import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, LockKeyhole, ShieldCheck } from 'lucide-react'
import { useAuth } from '../state/AuthContext'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(username.trim(), password)
      navigate('/', { replace: true })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to sign in')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm animate-fade-in">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-ink-600 bg-ink-900">
            <ShieldCheck className="h-6 w-6 text-white" />
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-white">
            Border Security Surveillance
          </h1>
          <p className="mt-1 text-xs uppercase tracking-[0.2em] text-neutral-500">
            Operations access
          </p>
        </div>

        <form onSubmit={submit} className="panel space-y-4 p-6">
          <div>
            <label htmlFor="username" className="label mb-2 block">
              Officer ID
            </label>
            <input
              id="username"
              className="input"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="officer"
              required
            />
          </div>
          <div>
            <label htmlFor="password" className="label mb-2 block">
              Passcode
            </label>
            <input
              id="password"
              type="password"
              className="input"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          {error && (
            <p className="rounded-xl border border-severity-critical/40 bg-severity-critical/10 px-3 py-2 text-xs text-severity-critical">
              {error}
            </p>
          )}

          <button type="submit" className="btn-primary w-full" disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <LockKeyhole className="h-4 w-4" />}
            {busy ? 'Verifying…' : 'Secure sign in'}
          </button>

          <p className="text-center text-[11px] text-neutral-600">
            Credentials are provisioned by the system administrator via environment configuration.
          </p>
        </form>
      </div>
    </div>
  )
}
