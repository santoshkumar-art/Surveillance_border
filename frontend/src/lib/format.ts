import type { DetectionCategory, Severity } from './types'

export function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

export function formatClock(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(total / 60)
  const secs = total % 60
  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  return formatClock(seconds)
}

export function formatDateTime(value: string | null): string {
  if (!value) return '—'
  const iso = value.endsWith('Z') || value.includes('+') ? value : `${value}Z`
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function timeAgo(value: string | null): string {
  if (!value) return '—'
  const iso = value.endsWith('Z') || value.includes('+') ? value : `${value}Z`
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.round(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

export const CATEGORY_LABELS: Record<DetectionCategory, string> = {
  face: 'Face',
  person: 'Person',
  vehicle: 'Vehicle',
  license_plate: 'Number plate',
  drone: 'Drone',
  vandalism: 'Vandalism',
  weapon: 'Weapon',
}

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category as DetectionCategory] ?? category.replace(/_/g, ' ')
}

export const SEVERITY_ORDER: Severity[] = ['critical', 'high', 'medium', 'low']

export const SEVERITY_STYLES: Record<Severity, { text: string; border: string; bg: string }> = {
  critical: {
    text: 'text-severity-critical',
    border: 'border-severity-critical/50',
    bg: 'bg-severity-critical/10',
  },
  high: { text: 'text-severity-high', border: 'border-severity-high/50', bg: 'bg-severity-high/10' },
  medium: {
    text: 'text-severity-medium',
    border: 'border-severity-medium/50',
    bg: 'bg-severity-medium/10',
  },
  low: { text: 'text-severity-low', border: 'border-severity-low/50', bg: 'bg-severity-low/10' },
}

export const STATUS_STYLES: Record<string, string> = {
  uploaded: 'text-neutral-400 border-ink-600',
  queued: 'text-severity-medium border-severity-medium/40',
  processing: 'text-white border-neutral-400',
  completed: 'text-severity-low border-severity-low/40',
  failed: 'text-severity-critical border-severity-critical/40',
}

export function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}
