import { useEffect, useState } from 'react'
import { Check, RotateCcw, Save } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import type { AppSettings } from '../lib/types'
import { ErrorState, Panel, Spinner, Toggle } from '../components/ui'
import { useAuth } from '../state/AuthContext'

interface SliderSpec {
  key: keyof AppSettings
  label: string
  hint: string
  min: number
  max: number
  step: number
  suffix?: string
}

const CONFIDENCE_SLIDERS: SliderSpec[] = [
  {
    key: 'detection_confidence',
    label: 'Object confidence',
    hint: 'People, vehicles and weapon-like objects',
    min: 0.05,
    max: 0.95,
    step: 0.05,
  },
  {
    key: 'face_confidence',
    label: 'Face confidence',
    hint: 'YuNet face detector threshold',
    min: 0.05,
    max: 0.95,
    step: 0.05,
  },
  {
    key: 'plate_confidence',
    label: 'Number plate confidence',
    hint: 'Plate localisation before OCR',
    min: 0.05,
    max: 0.95,
    step: 0.05,
  },
  {
    key: 'drone_confidence',
    label: 'Drone confidence',
    hint: 'Raise this if aerial false positives appear',
    min: 0.05,
    max: 0.95,
    step: 0.05,
  },
]

const ALERT_TOGGLES: { key: keyof AppSettings; label: string; hint: string }[] = [
  { key: 'alert_on_drone', label: 'Drone incursions', hint: 'Critical — UAV over the border line' },
  {
    key: 'alert_on_vandalism',
    label: 'Vandalism & abnormal motion',
    hint: 'Fence tampering, sudden violent motion',
  },
  { key: 'alert_on_plate', label: 'Number plate reads', hint: 'Medium — plate captured by OCR' },
  { key: 'alert_on_vehicle', label: 'Vehicle approach', hint: 'Low — vehicle near the perimeter' },
  { key: 'alert_on_face', label: 'Face captures', hint: 'Medium — identifiable subject detected' },
]

export default function SettingsPage() {
  const { user, logout } = useAuth()
  const loaded = useAsync<AppSettings>(() => api.settings(), [])
  const [draft, setDraft] = useState<AppSettings | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (loaded.data) setDraft(loaded.data)
  }, [loaded.data])

  const update = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    setDraft((current) => (current ? { ...current, [key]: value } : current))
    setSaved(false)
  }

  const save = async () => {
    if (!draft) return
    setSaving(true)
    setError(null)
    try {
      const next = await api.saveSettings(draft)
      setDraft(next)
      setSaved(true)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not save settings')
    } finally {
      setSaving(false)
    }
  }

  if (loaded.loading && !draft) return <Spinner label="Loading configuration…" />
  if (loaded.error) return <ErrorState message={loaded.error} onRetry={loaded.reload} />
  if (!draft) return null

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Settings</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Applies to every subsequent analysis job. Existing results are unchanged — re-analyse a
            clip to use new thresholds.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="btn-ghost"
            onClick={() => {
              loaded.reload()
              setSaved(false)
            }}
            disabled={saving}
          >
            <RotateCcw className="h-4 w-4" />
            Revert
          </button>
          <button type="button" className="btn-primary" onClick={save} disabled={saving}>
            {saved ? <Check className="h-4 w-4" /> : <Save className="h-4 w-4" />}
            {saving ? 'Saving…' : saved ? 'Saved' : 'Save changes'}
          </button>
        </div>
      </div>

      {error && (
        <p className="rounded-xl border border-severity-critical/40 bg-severity-critical/10 px-4 py-3 text-sm text-severity-critical">
          {error}
        </p>
      )}

      <Panel title="Inference" subtitle="Speed versus sensitivity trade-off">
        <div className="space-y-6 px-5 py-5">
          <div>
            <div className="flex items-center justify-between">
              <label htmlFor="frame_stride" className="text-sm text-neutral-200">
                Frame stride
              </label>
              <span className="font-mono text-xs text-neutral-400">
                every {draft.frame_stride} frame{draft.frame_stride > 1 ? 's' : ''}
              </span>
            </div>
            <p className="mt-1 text-xs text-neutral-600">
              Higher values analyse fewer frames — much faster on CPU, but brief events may be
              missed.
            </p>
            <input
              id="frame_stride"
              type="range"
              min={1}
              max={30}
              step={1}
              value={draft.frame_stride}
              onChange={(event) => update('frame_stride', Number(event.target.value))}
              className="mt-3 w-full accent-neutral-200"
            />
          </div>

          {CONFIDENCE_SLIDERS.map((slider) => {
            const value = draft[slider.key] as number
            return (
              <div key={slider.key}>
                <div className="flex items-center justify-between">
                  <label htmlFor={slider.key} className="text-sm text-neutral-200">
                    {slider.label}
                  </label>
                  <span className="font-mono text-xs text-neutral-400">
                    {Math.round(value * 100)}%
                  </span>
                </div>
                <p className="mt-1 text-xs text-neutral-600">{slider.hint}</p>
                <input
                  id={slider.key}
                  type="range"
                  min={slider.min}
                  max={slider.max}
                  step={slider.step}
                  value={value}
                  onChange={(event) => update(slider.key, Number(event.target.value) as never)}
                  className="mt-3 w-full accent-neutral-200"
                />
              </div>
            )
          })}

          <div>
            <div className="flex items-center justify-between">
              <label htmlFor="vandalism_sensitivity" className="text-sm text-neutral-200">
                Vandalism sensitivity
              </label>
              <span className="font-mono text-xs text-neutral-400">
                z ≥ {draft.vandalism_sensitivity.toFixed(1)}
              </span>
            </div>
            <p className="mt-1 text-xs text-neutral-600">
              Robust motion-anomaly z-score required to flag vandalism. Lower is more sensitive.
            </p>
            <input
              id="vandalism_sensitivity"
              type="range"
              min={1}
              max={8}
              step={0.5}
              value={draft.vandalism_sensitivity}
              onChange={(event) => update('vandalism_sensitivity', Number(event.target.value))}
              className="mt-3 w-full accent-neutral-200"
            />
          </div>

          <div>
            <div className="flex items-center justify-between">
              <label htmlFor="crowd_threshold" className="text-sm text-neutral-200">
                Crowd threshold
              </label>
              <span className="font-mono text-xs text-neutral-400">
                {draft.crowd_threshold} people
              </span>
            </div>
            <p className="mt-1 text-xs text-neutral-600">
              People visible in one frame before a group-movement alert is raised.
            </p>
            <input
              id="crowd_threshold"
              type="range"
              min={2}
              max={20}
              step={1}
              value={draft.crowd_threshold}
              onChange={(event) => update('crowd_threshold', Number(event.target.value))}
              className="mt-3 w-full accent-neutral-200"
            />
          </div>
        </div>
      </Panel>

      <Panel title="Outputs" subtitle="What the worker produces for each clip">
        <div className="divide-y divide-ink-800">
          <Toggle
            label="Number plate OCR"
            hint="Run text recognition on detected plates (slower, adds plate strings)"
            checked={draft.enable_plate_ocr}
            onChange={(value) => update('enable_plate_ocr', value)}
          />
          <Toggle
            label="Annotated video render"
            hint="Write an MP4 with detection overlays for playback in the viewer"
            checked={draft.write_annotated_video}
            onChange={(value) => update('write_annotated_video', value)}
          />
        </div>
      </Panel>

      <Panel title="Alert rules" subtitle="Which detections escalate to the alert desk">
        <div className="divide-y divide-ink-800">
          {ALERT_TOGGLES.map((toggle) => (
            <Toggle
              key={toggle.key}
              label={toggle.label}
              hint={toggle.hint}
              checked={draft[toggle.key] as boolean}
              onChange={(value) => update(toggle.key, value as never)}
            />
          ))}
        </div>
      </Panel>

      <Panel title="Session" subtitle="Signed-in officer">
        <div className="flex items-center justify-between px-5 py-4">
          <div>
            <p className="text-sm text-neutral-200">{user?.full_name || user?.username}</p>
            <p className="text-xs text-neutral-600">
              {user?.username} · {user?.role}
            </p>
          </div>
          <button type="button" className="btn-danger text-xs" onClick={logout}>
            Sign out
          </button>
        </div>
      </Panel>
    </div>
  )
}
