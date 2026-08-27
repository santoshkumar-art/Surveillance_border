import { useState } from 'react'
import { Link } from 'react-router-dom'
import { BellOff, Check, CheckCheck } from 'lucide-react'
import { api, snapshotUrl } from '../lib/api'
import { SEVERITY_ORDER, categoryLabel, formatClock, timeAgo } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import type { Alert, Page, Severity } from '../lib/types'
import {
  CategoryBadge,
  EmptyState,
  ErrorState,
  Panel,
  SeverityBadge,
  Spinner,
} from '../components/ui'
import { useLive } from '../state/LiveContext'

const PAGE_SIZE = 20

export default function Alerts() {
  const { alerts: liveAlerts, completions } = useLive()
  const [severity, setSeverity] = useState<Severity | ''>('')
  const [openOnly, setOpenOnly] = useState(true)
  const [offset, setOffset] = useState(0)
  const [busy, setBusy] = useState<number | 'all' | null>(null)

  const alerts = useAsync<Page<Alert>>(
    () =>
      api.alerts({
        severity,
        acknowledged: openOnly ? false : '',
        limit: PAGE_SIZE,
        offset,
      }),
    [severity, openOnly, offset, completions, liveAlerts.length],
  )

  const acknowledge = async (id: number) => {
    setBusy(id)
    try {
      await api.acknowledgeAlert(id)
      alerts.reload()
    } finally {
      setBusy(null)
    }
  }

  const acknowledgeAll = async () => {
    setBusy('all')
    try {
      await api.acknowledgeAll()
      alerts.reload()
    } finally {
      setBusy(null)
    }
  }

  const total = alerts.data?.total ?? 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Alert desk</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Security alerts raised by the detection rules, newest first. New alerts also appear as
            live pop-ups.
          </p>
        </div>
        <button
          type="button"
          className="btn-ghost"
          onClick={acknowledgeAll}
          disabled={busy === 'all' || total === 0}
        >
          <CheckCheck className="h-4 w-4" />
          Acknowledge all
        </button>
      </div>

      <Panel>
        <div className="flex flex-wrap items-center gap-2 px-5 py-4">
          <button
            type="button"
            className={`chip ${severity === '' ? 'border-neutral-300 text-white' : ''}`}
            onClick={() => {
              setOffset(0)
              setSeverity('')
            }}
          >
            all severities
          </button>
          {SEVERITY_ORDER.map((option) => (
            <button
              key={option}
              type="button"
              className={`chip ${severity === option ? 'border-neutral-300 text-white' : ''}`}
              onClick={() => {
                setOffset(0)
                setSeverity(option)
              }}
            >
              {option}
            </button>
          ))}
          <label className="ml-auto flex items-center gap-2 text-xs text-neutral-400">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-ink-600 bg-ink-850"
              checked={openOnly}
              onChange={(event) => {
                setOffset(0)
                setOpenOnly(event.target.checked)
              }}
            />
            Unacknowledged only
          </label>
        </div>
      </Panel>

      {alerts.loading && !alerts.data ? (
        <Spinner label="Loading alerts…" />
      ) : alerts.error ? (
        <ErrorState message={alerts.error} onRetry={alerts.reload} />
      ) : total === 0 ? (
        <Panel>
          <EmptyState
            title={openOnly ? 'No open alerts' : 'No alerts recorded'}
            hint="Alerts are raised automatically when the models detect drones, weapons, vandalism, plates, vehicles or crowds."
          />
        </Panel>
      ) : (
        <div className="space-y-3">
          {alerts.data?.items.map((alert) => (
            <article
              key={alert.id}
              className="panel panel-hover animate-fade-in flex flex-col gap-4 px-5 py-4 sm:flex-row"
            >
              {alert.snapshot_name && (
                <img
                  src={snapshotUrl(alert.snapshot_name)}
                  alt={alert.title}
                  loading="lazy"
                  className="h-28 w-full rounded-xl border border-ink-700 object-cover sm:w-48"
                />
              )}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={alert.severity} />
                  <CategoryBadge category={alert.category} />
                  {alert.acknowledged ? (
                    <span className="chip border-severity-low/40 text-severity-low">
                      acknowledged
                    </span>
                  ) : (
                    <span className="chip border-severity-high/40 text-severity-high">open</span>
                  )}
                  <span className="ml-auto text-[11px] text-neutral-600">
                    {timeAgo(alert.created_at)}
                  </span>
                </div>
                <h2 className="mt-2 text-sm font-medium text-white">{alert.title}</h2>
                <p className="mt-1 text-sm text-neutral-400">{alert.message}</p>
                <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-neutral-500">
                  <span>{alert.checkpoint || 'Unassigned checkpoint'}</span>
                  <span className="text-neutral-700">•</span>
                  <span className="truncate">{alert.video_name}</span>
                  <Link
                    to={`/videos/${alert.video_id}?t=${Math.floor(alert.timestamp_sec)}`}
                    className="underline decoration-ink-600 underline-offset-4 hover:text-white"
                  >
                    Review at {formatClock(alert.timestamp_sec)}
                  </Link>
                </div>
                {alert.acknowledged && alert.acknowledged_by && (
                  <p className="mt-2 flex items-center gap-1 text-[11px] text-neutral-600">
                    <BellOff className="h-3 w-3" />
                    Cleared by {alert.acknowledged_by}
                  </p>
                )}
              </div>
              {!alert.acknowledged && (
                <div className="flex items-start">
                  <button
                    type="button"
                    className="btn-ghost text-xs"
                    onClick={() => acknowledge(alert.id)}
                    disabled={busy === alert.id}
                  >
                    <Check className="h-3.5 w-3.5" />
                    Acknowledge
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-xs text-neutral-500">
          <span>
            {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total} ·{' '}
            {categoryLabel(severity || 'all')}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              className="btn-ghost text-xs"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </button>
            <button
              type="button"
              className="btn-ghost text-xs"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
