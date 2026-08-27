import type { ReactNode } from 'react'
import { AlertTriangle, Inbox, Loader2 } from 'lucide-react'
import { SEVERITY_STYLES, STATUS_STYLES, categoryLabel } from '../lib/format'
import type { Severity } from '../lib/types'

export function Panel({
  children,
  className = '',
  title,
  subtitle,
  actions,
}: {
  children: ReactNode
  className?: string
  title?: string
  subtitle?: string
  actions?: ReactNode
}) {
  return (
    <section className={`panel animate-fade-in ${className}`}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-4 border-b border-ink-700 px-5 py-4">
          <div>
            {title && <h2 className="text-sm font-semibold tracking-wide text-white">{title}</h2>}
            {subtitle && <p className="mt-1 text-xs text-neutral-500">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 px-5 py-10 text-sm text-neutral-500">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label ?? 'Loading…'}
    </div>
  )
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-5 py-12 text-center">
      <Inbox className="h-6 w-6 text-neutral-600" />
      <p className="text-sm text-neutral-400">{title}</p>
      {hint && <p className="max-w-sm text-xs text-neutral-600">{hint}</p>}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-5 py-10 text-center">
      <AlertTriangle className="h-6 w-6 text-severity-critical" />
      <p className="text-sm text-neutral-300">{message}</p>
      {onRetry && (
        <button type="button" className="btn-ghost" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const style = SEVERITY_STYLES[severity]
  return (
    <span
      className={`chip ${style.text} ${style.border} ${style.bg}`}
      title={`Severity: ${severity}`}
    >
      {severity}
    </span>
  )
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`chip ${STATUS_STYLES[status] ?? 'text-neutral-400 border-ink-600'}`}>
      {status === 'processing' && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" />
      )}
      {status}
    </span>
  )
}

export function CategoryBadge({ category }: { category: string }) {
  return <span className="chip text-neutral-300">{categoryLabel(category)}</span>
}

export function ConfidenceBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1 w-16 overflow-hidden rounded-full bg-ink-600">
        <div
          className="h-full rounded-full bg-neutral-200 transition-all duration-500"
          style={{ width: `${Math.min(100, Math.max(4, value * 100))}%` }}
        />
      </div>
      <span className="font-mono text-xs text-neutral-400">{(value * 100).toFixed(0)}%</span>
    </div>
  )
}

export function ProgressBar({ value, label }: { value: number; label?: string }) {
  return (
    <div className="w-full">
      <div className="h-1.5 overflow-hidden rounded-full bg-ink-700">
        <div
          className="h-full rounded-full bg-neutral-100 transition-all duration-500"
          style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        />
      </div>
      {label && <p className="mt-1 text-[11px] text-neutral-500">{label}</p>}
    </div>
  )
}

export function StatCard({
  label,
  value,
  hint,
  icon,
  accent,
}: {
  label: string
  value: string | number
  hint?: string
  icon?: ReactNode
  accent?: string
}) {
  return (
    <div className="panel panel-hover animate-fade-in px-5 py-4">
      <div className="flex items-center justify-between">
        <p className="label">{label}</p>
        {icon && <span className="text-neutral-500">{icon}</span>}
      </div>
      <p className={`mt-3 text-3xl font-semibold tracking-tight ${accent ?? 'text-white'}`}>
        {value}
      </p>
      {hint && <p className="mt-1 text-xs text-neutral-500">{hint}</p>}
    </div>
  )
}

export function Toggle({
  checked,
  onChange,
  label,
  hint,
}: {
  checked: boolean
  onChange: (value: boolean) => void
  label: string
  hint?: string
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 py-2">
      <span>
        <span className="block text-sm text-neutral-200">{label}</span>
        {hint && <span className="block text-xs text-neutral-500">{hint}</span>}
      </span>
      <span className="relative inline-flex">
        <input
          type="checkbox"
          className="peer sr-only"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
        />
        <span className="h-6 w-11 rounded-full border border-ink-600 bg-ink-800 transition-colors peer-checked:border-neutral-300 peer-checked:bg-neutral-200" />
        <span className="absolute left-1 top-1 h-4 w-4 rounded-full bg-neutral-500 transition-transform duration-200 peer-checked:translate-x-5 peer-checked:bg-black" />
      </span>
    </label>
  )
}
