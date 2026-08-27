import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../lib/api'
import { categoryLabel, formatClock } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import type { Analytics as AnalyticsData } from '../lib/types'
import { EmptyState, ErrorState, Panel, Spinner, StatCard } from '../components/ui'
import { useLive } from '../state/LiveContext'

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ff4d4f',
  high: '#ff9f43',
  medium: '#ffd166',
  low: '#7bdcb5',
}

const RANGES = [7, 14, 30]

const tooltipStyle = {
  backgroundColor: '#0f0f11',
  border: '1px solid #26262b',
  borderRadius: 12,
  fontSize: 12,
  color: '#e5e5e5',
}

export default function Analytics() {
  const { completions } = useLive()
  const [days, setDays] = useState(14)
  const analytics = useAsync<AnalyticsData>(() => api.analytics(days), [days, completions])

  if (analytics.loading && !analytics.data) return <Spinner label="Crunching analytics…" />
  if (analytics.error) return <ErrorState message={analytics.error} onRetry={analytics.reload} />
  if (!analytics.data) return null

  const data = analytics.data
  const categoryData = Object.entries(data.detections_by_category).map(([key, value]) => ({
    name: categoryLabel(key),
    value,
  }))
  const severityData = Object.entries(data.alerts_by_severity).map(([key, value]) => ({
    name: key,
    value,
    color: SEVERITY_COLORS[key] ?? '#a3a3a3',
  }))
  const throughput = data.processing_throughput

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Analytics</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Detection trends, alert mix, checkpoint hotspots and inference throughput.
          </p>
        </div>
        <div className="flex gap-2">
          {RANGES.map((option) => (
            <button
              key={option}
              type="button"
              className={`chip ${days === option ? 'border-neutral-300 text-white' : ''}`}
              onClick={() => setDays(option)}
            >
              {option}d
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Frames analysed"
          value={Math.round(throughput.frames_analyzed ?? 0)}
          hint="Sampled frames across all completed clips"
        />
        <StatCard
          label="Inference speed"
          value={`${(throughput.frames_per_second ?? 0).toFixed(2)} fps`}
          hint="Analysed frames per second of compute"
        />
        <StatCard
          label="Realtime factor"
          value={`${(throughput.realtime_factor ?? 0).toFixed(2)}×`}
          hint="Footage seconds processed per compute second"
        />
        <StatCard
          label="Compute time"
          value={formatClock(throughput.processing_seconds ?? 0)}
          hint={`Over ${formatClock(throughput.footage_seconds ?? 0)} of footage`}
        />
      </div>

      <Panel title="Detections & alerts over time" subtitle={`Last ${days} days`}>
        <div className="h-72 px-3 py-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data.detections_per_day}>
              <CartesianGrid stroke="#1c1c20" vertical={false} />
              <XAxis
                dataKey="bucket"
                tick={{ fill: '#737373', fontSize: 11 }}
                tickFormatter={(value: string) => value.slice(5)}
                stroke="#26262b"
              />
              <YAxis tick={{ fill: '#737373', fontSize: 11 }} stroke="#26262b" allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line
                type="monotone"
                dataKey="detections"
                stroke="#f5f5f5"
                strokeWidth={2}
                dot={false}
              />
              <Line type="monotone" dataKey="alerts" stroke="#ff9f43" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Detections by category" subtitle="All analysed footage">
          {categoryData.length === 0 ? (
            <EmptyState title="No detections yet" />
          ) : (
            <div className="h-64 px-3 py-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={categoryData}>
                  <CartesianGrid stroke="#1c1c20" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: '#737373', fontSize: 11 }} stroke="#26262b" />
                  <YAxis
                    tick={{ fill: '#737373', fontSize: 11 }}
                    stroke="#26262b"
                    allowDecimals={false}
                  />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#ffffff08' }} />
                  <Bar dataKey="value" fill="#e5e5e5" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel title="Alert severity mix" subtitle="How urgent the raised alerts are">
          {severityData.length === 0 ? (
            <EmptyState title="No alerts yet" />
          ) : (
            <div className="h-64 px-3 py-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={severityData}>
                  <CartesianGrid stroke="#1c1c20" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: '#737373', fontSize: 11 }} stroke="#26262b" />
                  <YAxis
                    tick={{ fill: '#737373', fontSize: 11 }}
                    stroke="#26262b"
                    allowDecimals={false}
                  />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#ffffff08' }} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                    {severityData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Checkpoint hotspots" subtitle="Alert volume per checkpoint">
          {data.top_checkpoints.length === 0 ? (
            <EmptyState title="No checkpoint data yet" />
          ) : (
            <ul className="divide-y divide-ink-800">
              {data.top_checkpoints.map((row) => (
                <li
                  key={row.checkpoint ?? 'unassigned'}
                  className="flex items-center justify-between px-5 py-3 text-sm"
                >
                  <span className="text-neutral-300">
                    {row.checkpoint || 'Unassigned checkpoint'}
                  </span>
                  <span className="flex gap-2 text-xs text-neutral-500">
                    <span className="chip text-neutral-400">{row.videos} clips</span>
                    <span className="chip text-neutral-400">{row.alerts} alerts</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Recent number plates" subtitle="OCR output from plate detections">
          {data.recent_plates.length === 0 ? (
            <EmptyState
              title="No plates read yet"
              hint="Enable plate OCR in settings and analyse footage containing vehicles."
            />
          ) : (
            <ul className="divide-y divide-ink-800">
              {data.recent_plates.map((plate) => (
                <li
                  key={plate.detection_id}
                  className="flex items-center justify-between px-5 py-3"
                >
                  <span className="font-mono text-sm text-white">{plate.plate}</span>
                  <Link
                    to={`/videos/${plate.video_id}?t=${Math.floor(plate.timestamp_sec)}`}
                    className="text-xs text-neutral-400 underline decoration-ink-600 underline-offset-4 hover:text-white"
                  >
                    clip {plate.video_id} · {formatClock(plate.timestamp_sec)}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  )
}
