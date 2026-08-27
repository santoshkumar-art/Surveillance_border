import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertOctagon,
  Bell,
  Clock4,
  Film,
  PlaneTakeoff,
  ScanFace,
  ShieldAlert,
  Users,
} from 'lucide-react'
import { api, snapshotUrl } from '../lib/api'
import { categoryLabel, formatClock, formatDateTime, timeAgo } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import type { Alert, DashboardStats, Page, Video } from '../lib/types'
import {
  CategoryBadge,
  EmptyState,
  ErrorState,
  Panel,
  ProgressBar,
  SeverityBadge,
  Spinner,
  StatCard,
  StatusBadge,
} from '../components/ui'
import { useLive } from '../state/LiveContext'

export default function Dashboard() {
  const { completions, progress, alerts: liveAlerts } = useLive()
  const stats = useAsync<DashboardStats>(() => api.dashboard(), [completions, liveAlerts.length])
  const videos = useAsync<Page<Video>>(() => api.videos({ limit: 5 }), [completions])
  const alerts = useAsync<Page<Alert>>(
    () => api.alerts({ limit: 6, acknowledged: false }),
    [completions, liveAlerts.length],
  )

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (Object.keys(progress).length > 0) videos.reload()
    }, 4000)
    return () => window.clearInterval(timer)
  }, [progress, videos])

  if (stats.loading && !stats.data) return <Spinner label="Loading operations overview…" />
  if (stats.error) return <ErrorState message={stats.error} onRetry={stats.reload} />

  const data = stats.data
  const categories = data?.detections_by_category ?? {}

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Operations overview</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Real-time posture across analysed border footage, detections and standing alerts.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Footage analysed"
          value={data?.videos_completed ?? 0}
          hint={`${data?.footage_hours ?? 0} h of CCTV · ${data?.videos_total ?? 0} uploads`}
          icon={<Film className="h-4 w-4" />}
        />
        <StatCard
          label="Detections"
          value={data?.detections_total ?? 0}
          hint={`${Object.keys(categories).length} categories observed`}
          icon={<ScanFace className="h-4 w-4" />}
        />
        <StatCard
          label="Open alerts"
          value={data?.alerts_unacknowledged ?? 0}
          hint={`${data?.alerts_total ?? 0} raised in total`}
          icon={<Bell className="h-4 w-4" />}
          accent={
            (data?.alerts_unacknowledged ?? 0) > 0 ? 'text-severity-high' : 'text-severity-low'
          }
        />
        <StatCard
          label="Critical alerts"
          value={data?.alerts_critical ?? 0}
          hint="Drones, weapons, vandalism with subjects"
          icon={<AlertOctagon className="h-4 w-4" />}
          accent={(data?.alerts_critical ?? 0) > 0 ? 'text-severity-critical' : 'text-white'}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Panel
          className="lg:col-span-2"
          title="Recent footage"
          subtitle="Latest uploads and their analysis state"
          actions={
            <Link to="/videos" className="text-xs text-neutral-400 hover:text-white">
              View all
            </Link>
          }
        >
          {videos.loading && !videos.data ? (
            <Spinner />
          ) : videos.error ? (
            <ErrorState message={videos.error} onRetry={videos.reload} />
          ) : (videos.data?.items.length ?? 0) === 0 ? (
            <EmptyState
              title="No footage uploaded yet"
              hint="Upload a CCTV clip to run face, vehicle, plate, drone and vandalism detection."
            />
          ) : (
            <ul className="divide-y divide-ink-800">
              {videos.data?.items.map((video) => {
                const live = progress[video.id]
                const shown = live?.progress ?? video.progress
                return (
                  <li key={video.id} className="px-5 py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <Link
                          to={`/videos/${video.id}`}
                          className="truncate text-sm font-medium text-white hover:underline"
                        >
                          {video.original_name}
                        </Link>
                        <p className="mt-1 text-xs text-neutral-500">
                          {video.checkpoint || 'Unassigned checkpoint'} ·{' '}
                          {formatClock(video.duration_sec)} · {formatDateTime(video.created_at)}
                        </p>
                      </div>
                      <StatusBadge status={video.status} />
                    </div>
                    {(video.status === 'processing' || video.status === 'queued') && (
                      <div className="mt-3">
                        <ProgressBar
                          value={shown}
                          label={`${shown.toFixed(0)}% analysed${
                            live ? ` · ${live.detections} detections · ${live.alerts} alerts` : ''
                          }`}
                        />
                      </div>
                    )}
                    {video.status === 'completed' && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className="chip text-neutral-400">
                          {video.detection_count} detections
                        </span>
                        <span className="chip text-neutral-400">{video.alert_count} alerts</span>
                        {Object.entries(video.category_counts).map(([category, count]) => (
                          <span key={category} className="chip text-neutral-500">
                            {categoryLabel(category)} · {count}
                          </span>
                        ))}
                      </div>
                    )}
                    {video.status === 'failed' && video.error_message && (
                      <p className="mt-2 text-xs text-severity-critical">{video.error_message}</p>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </Panel>

        <div className="space-y-6">
          <Panel title="Threat mix" subtitle="Detections by category">
            {Object.keys(categories).length === 0 ? (
              <EmptyState title="No detections yet" />
            ) : (
              <ul className="space-y-3 px-5 py-4">
                {Object.entries(categories)
                  .sort((a, b) => b[1] - a[1])
                  .map(([category, count]) => {
                    const max = Math.max(...Object.values(categories))
                    const Icon =
                      category === 'drone'
                        ? PlaneTakeoff
                        : category === 'person'
                          ? Users
                          : category === 'vandalism'
                            ? ShieldAlert
                            : ScanFace
                    return (
                      <li key={category}>
                        <div className="flex items-center justify-between text-xs text-neutral-400">
                          <span className="flex items-center gap-2">
                            <Icon className="h-3.5 w-3.5" />
                            {categoryLabel(category)}
                          </span>
                          <span className="font-mono text-neutral-300">{count}</span>
                        </div>
                        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-ink-700">
                          <div
                            className="h-full rounded-full bg-neutral-200 transition-all duration-700"
                            style={{ width: `${(count / max) * 100}%` }}
                          />
                        </div>
                      </li>
                    )
                  })}
              </ul>
            )}
          </Panel>

          <Panel
            title="Standing alerts"
            subtitle="Unacknowledged, newest first"
            actions={
              <Link to="/alerts" className="text-xs text-neutral-400 hover:text-white">
                Alert desk
              </Link>
            }
          >
            {alerts.loading && !alerts.data ? (
              <Spinner />
            ) : (alerts.data?.items.length ?? 0) === 0 ? (
              <EmptyState title="No open alerts" hint="All detections have been reviewed." />
            ) : (
              <ul className="divide-y divide-ink-800">
                {alerts.data?.items.map((alert) => (
                  <li key={alert.id} className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <SeverityBadge severity={alert.severity} />
                      <CategoryBadge category={alert.category} />
                      <span className="ml-auto flex items-center gap-1 text-[11px] text-neutral-600">
                        <Clock4 className="h-3 w-3" />
                        {timeAgo(alert.created_at)}
                      </span>
                    </div>
                    <Link
                      to={`/videos/${alert.video_id}?t=${Math.floor(alert.timestamp_sec)}`}
                      className="mt-2 block text-sm text-neutral-200 hover:underline"
                    >
                      {alert.title}
                    </Link>
                    {alert.snapshot_name && (
                      <img
                        src={snapshotUrl(alert.snapshot_name)}
                        alt={alert.title}
                        loading="lazy"
                        className="mt-2 h-20 w-full rounded-xl border border-ink-700 object-cover"
                      />
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  )
}
