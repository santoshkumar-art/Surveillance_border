import { Link } from 'react-router-dom'
import { BellRing, X } from 'lucide-react'
import { SEVERITY_STYLES, categoryLabel, formatClock } from '../lib/format'
import type { Severity } from '../lib/types'
import { useLive } from '../state/LiveContext'
import { snapshotUrl } from '../lib/api'

export default function AlertToasts() {
  const { toasts, dismissToast } = useLive()
  if (toasts.length === 0) return null

  return (
    <div className="pointer-events-none fixed right-4 top-20 z-50 flex w-[min(360px,calc(100vw-2rem))] flex-col gap-3">
      {toasts.map((toast) => {
        const style = SEVERITY_STYLES[toast.severity as Severity] ?? SEVERITY_STYLES.medium
        return (
          <div
            key={toast.id}
            className={`pointer-events-auto animate-slide-in rounded-2xl border bg-ink-900/95 p-4 shadow-2xl backdrop-blur ${style.border} ${
              toast.severity === 'critical' ? 'animate-pulse-ring' : ''
            }`}
            role="alert"
          >
            <div className="flex items-start gap-3">
              <BellRing className={`mt-0.5 h-4 w-4 shrink-0 ${style.text}`} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-semibold uppercase tracking-wider ${style.text}`}>
                    {toast.severity}
                  </span>
                  <span className="text-[10px] uppercase tracking-wider text-neutral-500">
                    {categoryLabel(toast.category)}
                  </span>
                </div>
                <p className="mt-1 truncate text-sm font-medium text-white">{toast.title}</p>
                <p className="mt-1 line-clamp-2 text-xs text-neutral-400">{toast.message}</p>
                {toast.snapshot && (
                  <img
                    src={snapshotUrl(toast.snapshot)}
                    alt={toast.title}
                    className="mt-2 h-24 w-full rounded-xl border border-ink-700 object-cover"
                  />
                )}
                <Link
                  to={`/videos/${toast.videoId}?t=${Math.floor(toast.timestampSec)}`}
                  onClick={() => dismissToast(toast.id)}
                  className="mt-2 inline-block text-xs text-neutral-300 underline decoration-neutral-600 underline-offset-4 hover:text-white"
                >
                  Review footage at {formatClock(toast.timestampSec)}
                </Link>
              </div>
              <button
                type="button"
                onClick={() => dismissToast(toast.id)}
                className="text-neutral-500 transition-colors hover:text-white"
                aria-label="Dismiss alert"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
