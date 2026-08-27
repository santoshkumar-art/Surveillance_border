import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  Activity,
  BarChart3,
  Bell,
  Cpu,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  ScanSearch,
  Settings,
  ShieldCheck,
  Upload,
  X,
} from 'lucide-react'
import { useAuth } from '../state/AuthContext'
import { useLive } from '../state/LiveContext'
import AlertToasts from './AlertToasts'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/upload', label: 'Upload footage', icon: Upload },
  { to: '/videos', label: 'Event history', icon: History },
  { to: '/detections', label: 'Detections', icon: ScanSearch },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/system', label: 'System status', icon: Cpu },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function AppShell() {
  const { user, logout } = useAuth()
  const { connected, alerts } = useLive()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const unacknowledged = alerts.length

  return (
    <div className="flex min-h-screen bg-ink-950">
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 border-r border-ink-800 bg-ink-900/95 backdrop-blur transition-transform duration-300 lg:static lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center justify-between border-b border-ink-800 px-5">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-white" />
            <div className="leading-tight">
              <p className="text-sm font-semibold text-white">BORDER WATCH</p>
              <p className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">
                Surveillance AI
              </p>
            </div>
          </div>
          <button
            type="button"
            className="text-neutral-500 lg:hidden"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex flex-col gap-1 p-3">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `group flex items-center justify-between rounded-xl px-3 py-2.5 text-sm transition-all duration-200 ${
                  isActive
                    ? 'bg-neutral-100 text-black'
                    : 'text-neutral-400 hover:bg-ink-800 hover:text-white'
                }`
              }
            >
              <span className="flex items-center gap-3">
                <Icon className="h-4 w-4" />
                {label}
              </span>
              {to === '/alerts' && unacknowledged > 0 && (
                <span className="rounded-full bg-severity-critical px-1.5 py-0.5 text-[10px] font-semibold text-black">
                  {unacknowledged}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="absolute bottom-0 w-full border-t border-ink-800 p-4">
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <p className="truncate text-sm text-neutral-200">{user?.full_name}</p>
              <p className="text-[11px] uppercase tracking-wide text-neutral-500">{user?.role}</p>
            </div>
            <button
              type="button"
              className="rounded-xl border border-ink-600 p-2 text-neutral-400 transition-colors hover:border-ink-500 hover:text-white"
              onClick={() => {
                logout()
                navigate('/login')
              }}
              aria-label="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {open && (
        <button
          type="button"
          aria-label="Close navigation overlay"
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-ink-800 bg-ink-950/85 px-4 backdrop-blur lg:px-8">
          <button
            type="button"
            className="rounded-xl border border-ink-600 p-2 text-neutral-300 lg:hidden"
            onClick={() => setOpen(true)}
            aria-label="Open navigation"
          >
            <Menu className="h-4 w-4" />
          </button>
          <div className="hidden items-center gap-2 text-xs text-neutral-500 lg:flex">
            <Activity className="h-3.5 w-3.5" />
            Border Security Surveillance Operations
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`chip ${connected ? 'text-severity-low border-severity-low/40' : 'text-severity-high border-severity-high/40'}`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${connected ? 'bg-severity-low' : 'bg-severity-high'}`}
              />
              {connected ? 'Live feed' : 'Reconnecting'}
            </span>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 lg:px-8">
          <Outlet />
        </main>
      </div>

      <AlertToasts />
    </div>
  )
}
