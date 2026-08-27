import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, BellRing, Check, Download, Layers, RefreshCw } from 'lucide-react'
import { api, snapshotUrl, videoStreamUrl } from '../lib/api'
import { formatClock, formatDateTime } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import type { Alert, Detection, Page, Video } from '../lib/types'
import {
  CategoryBadge,
  ConfidenceBar,
  EmptyState,
  ErrorState,
  Panel,
  ProgressBar,
  SeverityBadge,
  Spinner,
  StatusBadge,
} from '../components/ui'
import { useLive } from '../state/LiveContext'

export default function VideoDetail() {
  const { videoId } = useParams()
  const id = Number(videoId)
  const [searchParams] = useSearchParams()
  const { progress, completions, events } = useLive()
  const playerRef = useRef<HTMLVideoElement>(null)
  const [annotated, setAnnotated] = useState(true)
  const [ackBusy, setAckBusy] = useState<number | null>(null)

  const liveDetectionCount = useMemo(
    () => events.filter((event) => event.type === 'detection' && event.video_id === id).length,
    [events, id],
  )

  const video = useAsync<Video>(() => api.video(id), [id, completions])
  const detections = useAsync<Page<Detection>>(
    () => api.detections({ video_id: id, limit: 200, order: 'asc' }),
    [id, completions, liveDetectionCount],
  )
  const alerts = useAsync<Alert[]>(() => api.alertTimeline(id), [id, completions, liveDetectionCount])

  const live = progress[id]
  const status = video.data?.status
  const isRunning = status === 'processing' || status === 'queued'

  useEffect(() => {
    if (!isRunning) return
    const timer = window.setInterval(() => video.reload(), 5000)
    return () => window.clearInterval(timer)
  }, [isRunning, video])

  useEffect(() => {
    const start = Number(searchParams.get('t'))
    if (!Number.isFinite(start) || start <= 0) return
    const player = playerRef.current
    if (!player) return
    const seek = () => {
      player.currentTime = start
    }
    if (player.readyState >= 1) seek()
    else player.addEventListener('loadedmetadata', seek, { once: true })
  }, [searchParams, annotated, video.data?.status])

  const seek = (seconds: number) => {
    const player = playerRef.current
    if (!player) return
    player.currentTime = Math.max(0, seconds)
    void player.play()
  }

  const acknowledge = async (alertId: number) => {
    setAckBusy(alertId)
    try {
      await api.acknowledgeAlert(alertId)
      alerts.reload()
    } finally {
      setAckBusy(null)
    }
  }

  if (video.loading && !video.data) return <Spinner label="Loading case file…" />
  if (video.error) return <ErrorState message={video.error} onRetry={video.reload} />
  if (!video.data) return null

  const data = video.data
  const canShowAnnotated = Boolean(data.annotated_name)
  const showAnnotated = annotated && canShowAnnotated

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Link
            to="/videos"
            className="inline-flex items-center gap-1 text-xs text-neutral-500 hover:text-white"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Event history
          </Link>
          <h1 className="mt-2 truncate text-2xl font-semibold tracking-tight text-white">
            {data.original_name}
          </h1>
          <p className="mt-1 text-sm text-neutral-500">
            {data.checkpoint || 'Unassigned checkpoint'} · {data.width}×{data.height} ·{' '}
            {data.fps.toFixed(1)} fps · {formatClock(data.duration_sec)} ·{' '}
            {formatDateTime(data.created_at)}
          </p>
          {data.notes && <p className="mt-2 max-w-2xl text-sm text-neutral-400">{data.notes}</p>}
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={data.status} />
          <a className="btn-ghost text-xs" href={api.exportUrl(data.id)} download>
            <Download className="h-3.5 w-3.5" />
            Export report
          </a>
          <button
            type="button"
            className="btn-ghost text-xs"
            onClick={async () => {
              await api.reprocessVideo(data.id)
              video.reload()
            }}
            disabled={isRunning}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Re-analyse
          </button>
        </div>
      </div>

      {isRunning && (
        <Panel>
          <div className="space-y-2 px-5 py-4">
            <ProgressBar
              value={live?.progress ?? data.progress}
              label={`Analysing… ${(live?.progress ?? data.progress).toFixed(0)}%`}
            />
            <div className="flex flex-wrap gap-2 text-[11px] text-neutral-500">
              <span className="chip text-neutral-400">{live?.detections ?? 0} detections</span>
              <span className="chip text-neutral-400">{live?.alerts ?? 0} alerts</span>
              <span className="chip text-neutral-400">{live?.peopleInFrame ?? 0} people in frame</span>
              <span className="chip text-neutral-400">
                anomaly score {(live?.anomalyScore ?? 0).toFixed(2)}
              </span>
              {live && <span className="chip text-neutral-400">at {formatClock(live.timestampSec)}</span>}
            </div>
          </div>
        </Panel>
      )}

      {data.status === 'failed' && data.error_message && (
        <p className="rounded-xl border border-severity-critical/40 bg-severity-critical/10 px-4 py-3 text-sm text-severity-critical">
          Analysis failed: {data.error_message}
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Panel
            title="Footage viewer"
            subtitle={
              showAnnotated
                ? 'Annotated render with detection overlays'
                : 'Original uploaded footage'
            }
            actions={
              <button
                type="button"
                className="btn-ghost text-xs"
                onClick={() => setAnnotated((value) => !value)}
                disabled={!canShowAnnotated}
                title={
                  canShowAnnotated
                    ? 'Toggle detection overlays'
                    : 'Annotated render not available for this clip'
                }
              >
                <Layers className="h-3.5 w-3.5" />
                {showAnnotated ? 'Show original' : 'Show overlays'}
              </button>
            }
          >
            <div className="px-5 py-4">
              <video
                ref={playerRef}
                key={`${data.id}-${showAnnotated}`}
                className="w-full rounded-xl border border-ink-700 bg-black"
                src={videoStreamUrl(data.id, showAnnotated)}
                controls
                preload="metadata"
              />
            </div>
          </Panel>

          <Panel
            title="Detections"
            subtitle={`${detections.data?.total ?? 0} tracked events`}
          >
            {detections.loading && !detections.data ? (
              <Spinner />
            ) : detections.error ? (
              <ErrorState message={detections.error} onRetry={detections.reload} />
            ) : (detections.data?.items.length ?? 0) === 0 ? (
              <EmptyState
                title="No detections recorded"
                hint={
                  isRunning
                    ? 'Analysis is still running — results stream in live.'
                    : 'The models found nothing above the configured confidence thresholds.'
                }
              />
            ) : (
              <div className="max-h-[420px] overflow-auto">
                <table className="w-full">
                  <thead className="sticky top-0 bg-ink-900/95 backdrop-blur">
                    <tr className="border-b border-ink-700 text-left">
                      <th className="table-cell label">Time</th>
                      <th className="table-cell label">Category</th>
                      <th className="table-cell label">Label</th>
                      <th className="table-cell label">Confidence</th>
                      <th className="table-cell label">Snapshot</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detections.data?.items.map((detection) => (
                      <tr
                        key={detection.id}
                        className="border-b border-ink-800 transition-colors hover:bg-ink-850/70"
                      >
                        <td className="table-cell">
                          <button
                            type="button"
                            className="font-mono text-xs text-neutral-300 underline decoration-ink-600 underline-offset-4 hover:text-white"
                            onClick={() => seek(detection.timestamp_sec)}
                          >
                            {formatClock(detection.timestamp_sec)}
                          </button>
                        </td>
                        <td className="table-cell">
                          <CategoryBadge category={detection.category} />
                        </td>
                        <td className="table-cell">
                          {detection.plate_text ? (
                            <span className="font-mono text-sm text-white">
                              {detection.plate_text}
                            </span>
                          ) : (
                            detection.label
                          )}
                        </td>
                        <td className="table-cell">
                          <ConfidenceBar value={detection.confidence} />
                        </td>
                        <td className="table-cell">
                          {detection.snapshot_name ? (
                            <img
                              src={snapshotUrl(detection.snapshot_name)}
                              alt={detection.label}
                              loading="lazy"
                              className="h-12 w-20 rounded-lg border border-ink-700 object-cover"
                            />
                          ) : (
                            <span className="text-xs text-neutral-600">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>

        <Panel title="Alert timeline" subtitle="Click an alert to jump to that moment">
          {alerts.loading && !alerts.data ? (
            <Spinner />
          ) : (alerts.data?.length ?? 0) === 0 ? (
            <EmptyState title="No alerts for this clip" />
          ) : (
            <ul className="max-h-[640px] divide-y divide-ink-800 overflow-auto">
              {alerts.data?.map((alert) => (
                <li key={alert.id} className="px-5 py-4">
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={alert.severity} />
                    <CategoryBadge category={alert.category} />
                    {alert.acknowledged && (
                      <span className="chip border-severity-low/40 text-severity-low">ack</span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => seek(alert.timestamp_sec)}
                    className="mt-2 block text-left text-sm font-medium text-white hover:underline"
                  >
                    {formatClock(alert.timestamp_sec)} · {alert.title}
                  </button>
                  <p className="mt-1 text-xs text-neutral-500">{alert.message}</p>
                  {alert.snapshot_name && (
                    <img
                      src={snapshotUrl(alert.snapshot_name)}
                      alt={alert.title}
                      loading="lazy"
                      className="mt-2 h-24 w-full rounded-xl border border-ink-700 object-cover"
                    />
                  )}
                  {!alert.acknowledged && (
                    <button
                      type="button"
                      className="btn-ghost mt-3 w-full text-xs"
                      onClick={() => acknowledge(alert.id)}
                      disabled={ackBusy === alert.id}
                    >
                      {ackBusy === alert.id ? (
                        <BellRing className="h-3.5 w-3.5" />
                      ) : (
                        <Check className="h-3.5 w-3.5" />
                      )}
                      Acknowledge
                    </button>
                  )}
                  {alert.acknowledged && alert.acknowledged_by && (
                    <p className="mt-2 text-[11px] text-neutral-600">
                      Acknowledged by {alert.acknowledged_by} · {formatDateTime(alert.acknowledged_at)}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  )
}
