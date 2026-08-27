import { useState } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw, Search, Trash2, Upload as UploadIcon } from 'lucide-react'
import { api, snapshotUrl } from '../lib/api'
import { categoryLabel, formatBytes, formatClock, formatDateTime } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import type { Page, Video, VideoStatus } from '../lib/types'
import { EmptyState, ErrorState, Panel, ProgressBar, Spinner, StatusBadge } from '../components/ui'
import { useLive } from '../state/LiveContext'

const PAGE_SIZE = 12
const STATUSES: (VideoStatus | '')[] = ['', 'uploaded', 'queued', 'processing', 'completed', 'failed']

export default function Videos() {
  const { completions, progress } = useLive()
  const [status, setStatus] = useState<VideoStatus | ''>('')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [busyId, setBusyId] = useState<number | null>(null)

  const videos = useAsync<Page<Video>>(
    () => api.videos({ status, search, limit: PAGE_SIZE, offset }),
    [status, search, offset, completions],
  )

  const reprocess = async (id: number) => {
    setBusyId(id)
    try {
      await api.reprocessVideo(id)
      videos.reload()
    } finally {
      setBusyId(null)
    }
  }

  const remove = async (id: number) => {
    if (!window.confirm('Delete this footage and all related detections and alerts?')) return
    setBusyId(id)
    try {
      await api.deleteVideo(id)
      videos.reload()
    } finally {
      setBusyId(null)
    }
  }

  const total = videos.data?.total ?? 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Event history</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Every uploaded clip with its analysis outcome and detection breakdown.
          </p>
        </div>
        <Link to="/upload" className="btn-primary">
          <UploadIcon className="h-4 w-4" />
          Upload footage
        </Link>
      </div>

      <Panel>
        <div className="flex flex-wrap items-center gap-3 px-5 py-4">
          <div className="relative min-w-[220px] flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-600" />
            <input
              className="input pl-9"
              placeholder="Search file name, checkpoint or notes"
              value={search}
              onChange={(event) => {
                setOffset(0)
                setSearch(event.target.value)
              }}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {STATUSES.map((option) => (
              <button
                key={option || 'all'}
                type="button"
                onClick={() => {
                  setOffset(0)
                  setStatus(option)
                }}
                className={`chip transition-colors ${
                  status === option ? 'border-neutral-300 text-white' : 'hover:text-neutral-200'
                }`}
              >
                {option || 'all'}
              </button>
            ))}
          </div>
        </div>
      </Panel>

      {videos.loading && !videos.data ? (
        <Spinner label="Loading footage…" />
      ) : videos.error ? (
        <ErrorState message={videos.error} onRetry={videos.reload} />
      ) : total === 0 ? (
        <Panel>
          <EmptyState
            title="No footage matches this filter"
            hint="Upload a clip or clear the filters to see the full history."
          />
        </Panel>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {videos.data?.items.map((video) => {
            const live = progress[video.id]
            const shown = live?.progress ?? video.progress
            return (
              <article key={video.id} className="panel panel-hover animate-fade-in overflow-hidden">
                <Link to={`/videos/${video.id}`} className="block">
                  {video.thumbnail_name ? (
                    <img
                      src={snapshotUrl(video.thumbnail_name)}
                      alt={video.original_name}
                      loading="lazy"
                      className="h-40 w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-40 items-center justify-center bg-ink-850 text-xs text-neutral-600">
                      Poster frame pending
                    </div>
                  )}
                </Link>
                <div className="space-y-3 px-5 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <Link
                      to={`/videos/${video.id}`}
                      className="truncate text-sm font-medium text-white hover:underline"
                    >
                      {video.original_name}
                    </Link>
                    <StatusBadge status={video.status} />
                  </div>
                  <p className="text-xs text-neutral-500">
                    {video.checkpoint || 'Unassigned checkpoint'} · {formatClock(video.duration_sec)}{' '}
                    · {formatBytes(video.size_bytes)}
                  </p>
                  <p className="text-[11px] text-neutral-600">{formatDateTime(video.created_at)}</p>

                  {(video.status === 'processing' || video.status === 'queued') && (
                    <ProgressBar value={shown} label={`${shown.toFixed(0)}% analysed`} />
                  )}

                  {video.status === 'failed' && video.error_message && (
                    <p className="text-xs text-severity-critical">{video.error_message}</p>
                  )}

                  {video.status === 'completed' && (
                    <div className="flex flex-wrap gap-1.5">
                      <span className="chip text-neutral-400">
                        {video.detection_count} detections
                      </span>
                      <span
                        className={`chip ${
                          video.critical_alert_count > 0
                            ? 'border-severity-critical/40 text-severity-critical'
                            : 'text-neutral-400'
                        }`}
                      >
                        {video.alert_count} alerts
                      </span>
                      {Object.entries(video.category_counts)
                        .slice(0, 3)
                        .map(([category, count]) => (
                          <span key={category} className="chip text-neutral-500">
                            {categoryLabel(category)} {count}
                          </span>
                        ))}
                    </div>
                  )}

                  <div className="flex gap-2 pt-1">
                    <button
                      type="button"
                      className="btn-ghost flex-1 text-xs"
                      onClick={() => reprocess(video.id)}
                      disabled={busyId === video.id || video.status === 'processing'}
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      Re-analyse
                    </button>
                    <button
                      type="button"
                      className="btn-danger text-xs"
                      onClick={() => remove(video.id)}
                      disabled={busyId === video.id}
                      aria-label="Delete footage"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      )}

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-xs text-neutral-500">
          <span>
            {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
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
