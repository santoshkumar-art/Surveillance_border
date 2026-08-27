import { useEffect, useState } from 'react'
import { CheckCircle2, CircleDashed, Cpu, Download, HardDrive, MemoryStick } from 'lucide-react'
import { api } from '../lib/api'
import { formatClock } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import type { SystemStatus } from '../lib/types'
import { ErrorState, Panel, ProgressBar, Spinner, StatCard } from '../components/ui'
import { useLive } from '../state/LiveContext'

export default function SystemStatusPage() {
  const { connected } = useLive()
  const [tick, setTick] = useState(0)
  const [downloading, setDownloading] = useState(false)
  const status = useAsync<SystemStatus>(() => api.systemStatus(), [tick])

  useEffect(() => {
    const timer = window.setInterval(() => setTick((value) => value + 1), 10000)
    return () => window.clearInterval(timer)
  }, [])

  if (status.loading && !status.data) return <Spinner label="Reading system telemetry…" />
  if (status.error) return <ErrorState message={status.error} onRetry={status.reload} />
  if (!status.data) return null

  const data = status.data

  const triggerDownload = async () => {
    setDownloading(true)
    try {
      await api.downloadModels()
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">System status</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Inference runtime, model availability, processing queue and storage health.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Service"
          value={data.status}
          hint={`v${data.version} · uptime ${formatClock(data.uptime_seconds)}`}
          accent="text-severity-low"
        />
        <StatCard
          label="Live feed"
          value={connected ? 'connected' : 'offline'}
          hint="WebSocket channel for detections and alerts"
          accent={connected ? 'text-severity-low' : 'text-severity-high'}
        />
        <StatCard
          label="Processing queue"
          value={data.queue_depth}
          hint={data.active_job ? `Analysing clip #${data.active_job}` : 'Worker idle'}
          icon={<Cpu className="h-4 w-4" />}
        />
        <StatCard
          label="Disk free"
          value={`${data.disk_free_gb.toFixed(1)} GB`}
          hint={`Uploads ${((data.storage.uploads_mb ?? 0) / 1024).toFixed(2)} GB · renders ${(
            (data.storage.processed_mb ?? 0) / 1024
          ).toFixed(2)} GB`}
          icon={<HardDrive className="h-4 w-4" />}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Panel title="Runtime" subtitle="Compute environment used for inference">
          <dl className="divide-y divide-ink-800 text-sm">
            {[
              ['Device', data.device],
              ['PyTorch', data.torch_version],
              ['OpenCV', data.opencv_version],
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between px-5 py-3">
                <dt className="text-neutral-500">{label}</dt>
                <dd className="font-mono text-xs text-neutral-200">{value}</dd>
              </div>
            ))}
          </dl>
        </Panel>

        <Panel title="Load" subtitle="Host utilisation">
          <div className="space-y-5 px-5 py-5">
            <div>
              <div className="mb-2 flex items-center justify-between text-xs text-neutral-400">
                <span className="flex items-center gap-2">
                  <Cpu className="h-3.5 w-3.5" /> CPU
                </span>
                <span className="font-mono">{data.cpu_percent.toFixed(0)}%</span>
              </div>
              <ProgressBar value={data.cpu_percent} />
            </div>
            <div>
              <div className="mb-2 flex items-center justify-between text-xs text-neutral-400">
                <span className="flex items-center gap-2">
                  <MemoryStick className="h-3.5 w-3.5" /> Memory
                </span>
                <span className="font-mono">{data.memory_percent.toFixed(0)}%</span>
              </div>
              <ProgressBar value={data.memory_percent} />
            </div>
          </div>
        </Panel>

        <Panel
          title="Model weights"
          subtitle="Downloaded on demand from public checkpoints"
          actions={
            <button
              type="button"
              className="btn-ghost text-xs"
              onClick={triggerDownload}
              disabled={downloading}
            >
              <Download className="h-3.5 w-3.5" />
              {downloading ? 'Started…' : 'Fetch missing'}
            </button>
          }
        >
          <ul className="divide-y divide-ink-800">
            {data.models.map((model) => (
              <li key={model.key} className="px-5 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-neutral-200">{model.name}</p>
                    <p className="text-[11px] text-neutral-600">{model.task}</p>
                  </div>
                  <span
                    className={`chip ${
                      model.available
                        ? 'border-severity-low/40 text-severity-low'
                        : 'border-severity-high/40 text-severity-high'
                    }`}
                  >
                    {model.available ? (
                      <CheckCircle2 className="h-3 w-3" />
                    ) : (
                      <CircleDashed className="h-3 w-3" />
                    )}
                    {model.available
                      ? model.weights_mb
                        ? `${model.weights_mb.toFixed(1)} MB`
                        : 'ready'
                      : 'missing'}
                  </span>
                </div>
                <p className="mt-1 text-[11px] text-neutral-500">
                  {model.loaded ? 'loaded in memory' : 'lazy — loads on first frame'}
                </p>
                {model.error && (
                  <p className="mt-1 text-[11px] text-severity-critical">{model.error}</p>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  )
}
