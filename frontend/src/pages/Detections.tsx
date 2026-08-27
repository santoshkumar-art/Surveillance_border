import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { api, snapshotUrl } from '../lib/api'
import { categoryLabel, formatClock, formatDateTime } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import type { Detection, DetectionCategory, Page } from '../lib/types'
import {
  CategoryBadge,
  ConfidenceBar,
  EmptyState,
  ErrorState,
  Panel,
  Spinner,
} from '../components/ui'
import { useLive } from '../state/LiveContext'

const PAGE_SIZE = 25
const CATEGORIES: (DetectionCategory | '')[] = [
  '',
  'person',
  'face',
  'vehicle',
  'license_plate',
  'drone',
  'vandalism',
  'weapon',
]

export default function Detections() {
  const { completions } = useLive()
  const [category, setCategory] = useState<DetectionCategory | ''>('')
  const [search, setSearch] = useState('')
  const [minConfidence, setMinConfidence] = useState(0)
  const [offset, setOffset] = useState(0)

  const counts = useAsync<Record<string, number>>(() => api.detectionCategories(), [completions])
  const detections = useAsync<Page<Detection>>(
    () =>
      api.detections({
        category,
        search,
        min_confidence: minConfidence || undefined,
        limit: PAGE_SIZE,
        offset,
      }),
    [category, search, minConfidence, offset, completions],
  )

  const total = detections.data?.total ?? 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Detection results</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Every tracked detection produced by the vision models, searchable by plate text or label.
        </p>
      </div>

      <Panel>
        <div className="space-y-4 px-5 py-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative min-w-[220px] flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-600" />
              <input
                className="input pl-9"
                placeholder="Search label or number plate (e.g. KA01)"
                value={search}
                onChange={(event) => {
                  setOffset(0)
                  setSearch(event.target.value)
                }}
              />
            </div>
            <div className="flex items-center gap-3">
              <label htmlFor="confidence" className="label whitespace-nowrap">
                Min confidence {Math.round(minConfidence * 100)}%
              </label>
              <input
                id="confidence"
                type="range"
                min={0}
                max={0.95}
                step={0.05}
                value={minConfidence}
                onChange={(event) => {
                  setOffset(0)
                  setMinConfidence(Number(event.target.value))
                }}
                className="w-36 accent-neutral-200"
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((option) => (
              <button
                key={option || 'all'}
                type="button"
                onClick={() => {
                  setOffset(0)
                  setCategory(option)
                }}
                className={`chip transition-colors ${
                  category === option ? 'border-neutral-300 text-white' : 'hover:text-neutral-200'
                }`}
              >
                {option ? categoryLabel(option) : 'all'}
                {option && counts.data?.[option] !== undefined && (
                  <span className="font-mono text-neutral-500">{counts.data[option]}</span>
                )}
              </button>
            ))}
          </div>
        </div>
      </Panel>

      <Panel title="Results" subtitle={`${total} detections`}>
        {detections.loading && !detections.data ? (
          <Spinner />
        ) : detections.error ? (
          <ErrorState message={detections.error} onRetry={detections.reload} />
        ) : total === 0 ? (
          <EmptyState
            title="No detections match these filters"
            hint="Try lowering the confidence threshold or clearing the category filter."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px]">
              <thead>
                <tr className="border-b border-ink-700 text-left">
                  <th className="table-cell label">Snapshot</th>
                  <th className="table-cell label">Category</th>
                  <th className="table-cell label">Label / plate</th>
                  <th className="table-cell label">Confidence</th>
                  <th className="table-cell label">Clip time</th>
                  <th className="table-cell label">Recorded</th>
                </tr>
              </thead>
              <tbody>
                {detections.data?.items.map((detection) => (
                  <tr
                    key={detection.id}
                    className="border-b border-ink-800 transition-colors hover:bg-ink-850/70"
                  >
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
                    <td className="table-cell">
                      <CategoryBadge category={detection.category} />
                    </td>
                    <td className="table-cell">
                      {detection.plate_text ? (
                        <span className="font-mono text-sm text-white">{detection.plate_text}</span>
                      ) : (
                        detection.label
                      )}
                    </td>
                    <td className="table-cell">
                      <ConfidenceBar value={detection.confidence} />
                    </td>
                    <td className="table-cell">
                      <Link
                        to={`/videos/${detection.video_id}?t=${Math.floor(detection.timestamp_sec)}`}
                        className="font-mono text-xs text-neutral-300 underline decoration-ink-600 underline-offset-4 hover:text-white"
                      >
                        {formatClock(detection.timestamp_sec)}
                      </Link>
                    </td>
                    <td className="table-cell text-xs text-neutral-500">
                      {formatDateTime(detection.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between border-t border-ink-800 px-5 py-3 text-xs text-neutral-500">
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
      </Panel>
    </div>
  )
}
