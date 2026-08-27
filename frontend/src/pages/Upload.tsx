import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CloudUpload, FileVideo, Loader2, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatBytes } from '../lib/format'
import { Panel, ProgressBar } from '../components/ui'

const ACCEPTED = '.mp4,.avi,.mov,.mkv,.webm,.mpg,.mpeg,.m4v'

export default function Upload() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [checkpoint, setCheckpoint] = useState('')
  const [notes, setNotes] = useState('')
  const [autoProcess, setAutoProcess] = useState(true)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [percent, setPercent] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!file) return
    setUploading(true)
    setError(null)
    setPercent(0)
    try {
      const video = await api.uploadVideo(
        file,
        { checkpoint: checkpoint.trim(), notes: notes.trim(), autoProcess },
        setPercent,
      )
      navigate(`/videos/${video.id}`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Upload CCTV footage</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Footage is analysed on the server with real detection models: people & faces, vehicles &
          number plates, drones and vandalism/abnormal motion.
        </p>
      </div>

      <form onSubmit={submit} className="space-y-6">
        <Panel>
          <div
            className={`m-5 flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed px-6 py-12 text-center transition-colors duration-200 ${
              dragging ? 'border-neutral-300 bg-ink-800/60' : 'border-ink-600'
            }`}
            onDragOver={(event) => {
              event.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDragging(false)
              const dropped = event.dataTransfer.files?.[0]
              if (dropped) setFile(dropped)
            }}
          >
            <CloudUpload className="h-7 w-7 text-neutral-400" />
            <p className="text-sm text-neutral-300">Drag a surveillance clip here</p>
            <p className="text-xs text-neutral-600">MP4, AVI, MOV, MKV, WEBM, MPG, M4V</p>
            <button
              type="button"
              className="btn-ghost mt-2"
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
            >
              Browse files
            </button>
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED}
              className="hidden"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </div>

          {file && (
            <div className="mx-5 mb-5 flex items-center gap-3 rounded-xl border border-ink-700 bg-ink-850 px-4 py-3">
              <FileVideo className="h-4 w-4 text-neutral-400" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-neutral-200">{file.name}</p>
                <p className="text-xs text-neutral-500">{formatBytes(file.size)}</p>
              </div>
              {!uploading && (
                <button
                  type="button"
                  onClick={() => setFile(null)}
                  className="text-neutral-500 hover:text-white"
                  aria-label="Remove selected file"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          )}
        </Panel>

        <Panel title="Case details" subtitle="Recorded with the footage for the audit trail">
          <div className="space-y-4 px-5 py-4">
            <div>
              <label htmlFor="checkpoint" className="label mb-2 block">
                Checkpoint / sector
              </label>
              <input
                id="checkpoint"
                className="input"
                value={checkpoint}
                onChange={(event) => setCheckpoint(event.target.value)}
                placeholder="e.g. Sector 7 — North fence"
              />
            </div>
            <div>
              <label htmlFor="notes" className="label mb-2 block">
                Officer notes
              </label>
              <textarea
                id="notes"
                className="input min-h-[88px] resize-y"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Context, patrol shift, reported incident…"
              />
            </div>
            <label className="flex items-center gap-3 text-sm text-neutral-300">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-ink-600 bg-ink-850"
                checked={autoProcess}
                onChange={(event) => setAutoProcess(event.target.checked)}
              />
              Start AI analysis immediately after upload
            </label>
          </div>
        </Panel>

        {uploading && (
          <Panel>
            <div className="px-5 py-4">
              <ProgressBar value={percent} label={`Uploading… ${percent}%`} />
            </div>
          </Panel>
        )}

        {error && (
          <p className="rounded-xl border border-severity-critical/40 bg-severity-critical/10 px-4 py-3 text-sm text-severity-critical">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-3">
          <button type="button" className="btn-ghost" onClick={() => navigate('/videos')}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={!file || uploading}>
            {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CloudUpload className="h-4 w-4" />}
            {uploading ? 'Uploading…' : 'Upload & analyse'}
          </button>
        </div>
      </form>
    </div>
  )
}
