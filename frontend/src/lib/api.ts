import type {
  Alert,
  Analytics,
  AppSettings,
  DashboardStats,
  Detection,
  DetectionCategory,
  Page,
  Severity,
  SystemStatus,
  TokenResponse,
  User,
  Video,
  VideoStatus,
} from './types'

const RAW_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
export const API_BASE = RAW_BASE.replace(/\/$/, '')
const TOKEN_KEY = 'bss.token'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

type Query = Record<string, string | number | boolean | null | undefined>

function buildUrl(path: string, query?: Query): string {
  const url = `${API_BASE}${path}`
  if (!query) return url
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === '') continue
    params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `${url}?${qs}` : url
}

async function request<T>(
  path: string,
  options: RequestInit & { query?: Query } = {},
): Promise<T> {
  const { query, headers, ...rest } = options
  const token = getToken()
  const response = await fetch(buildUrl(path, query), {
    ...rest,
    headers: {
      ...(rest.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  })

  if (response.status === 401) {
    setToken(null)
    throw new ApiError('Session expired. Please sign in again.', 401)
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
      else if (body.detail) detail = JSON.stringify(body.detail)
    } catch {
      /* response had no JSON body */
    }
    throw new ApiError(detail, response.status)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** Media URLs carry the token in the query string so <video>/<img> tags can load them. */
export function mediaUrl(path: string, query?: Query): string {
  return buildUrl(path, { ...query, token: getToken() })
}

export function snapshotUrl(name: string): string {
  return mediaUrl(`/api/media/snapshots/${encodeURIComponent(name)}`)
}

export function videoStreamUrl(videoId: number, annotated = false): string {
  return mediaUrl(`/api/videos/${videoId}/stream`, { annotated })
}

export function websocketUrl(): string {
  const base = API_BASE || window.location.origin
  const url = new URL(`${base}/api/ws`, window.location.origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.searchParams.set('token', getToken() ?? '')
  return url.toString()
}

export const api = {
  login: (username: string, password: string) =>
    request<TokenResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  me: () => request<User>('/api/auth/me'),

  uploadVideo: (
    file: File,
    options: { checkpoint?: string; notes?: string; autoProcess?: boolean },
    onProgress?: (percent: number) => void,
  ) =>
    new Promise<Video>((resolve, reject) => {
      const form = new FormData()
      form.append('file', file)
      if (options.checkpoint) form.append('checkpoint', options.checkpoint)
      if (options.notes) form.append('notes', options.notes)
      form.append('auto_process', String(options.autoProcess ?? true))

      const xhr = new XMLHttpRequest()
      xhr.open('POST', buildUrl('/api/videos'))
      const token = getToken()
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          onProgress(Math.round((event.loaded / event.total) * 100))
        }
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText) as Video)
          return
        }
        let detail = `Upload failed (${xhr.status})`
        try {
          const body = JSON.parse(xhr.responseText) as { detail?: string }
          if (body.detail) detail = body.detail
        } catch {
          /* no JSON body */
        }
        reject(new ApiError(detail, xhr.status))
      }
      xhr.onerror = () => reject(new ApiError('Network error during upload', 0))
      xhr.send(form)
    }),

  videos: (query?: { status?: VideoStatus | ''; search?: string; limit?: number; offset?: number }) =>
    request<Page<Video>>('/api/videos', { query }),

  video: (id: number) => request<Video>(`/api/videos/${id}`),

  reprocessVideo: (id: number) =>
    request<Video>(`/api/videos/${id}/reprocess`, { method: 'POST' }),

  deleteVideo: (id: number) => request<void>(`/api/videos/${id}`, { method: 'DELETE' }),

  detections: (query?: {
    video_id?: number
    category?: DetectionCategory | ''
    min_confidence?: number
    search?: string
    limit?: number
    offset?: number
    order?: 'asc' | 'desc'
  }) => request<Page<Detection>>('/api/detections', { query }),

  detectionCategories: (videoId?: number) =>
    request<Record<string, number>>('/api/detections/categories', {
      query: { video_id: videoId },
    }),

  alerts: (query?: {
    video_id?: number
    severity?: Severity | ''
    category?: DetectionCategory | ''
    acknowledged?: boolean | ''
    limit?: number
    offset?: number
  }) => request<Page<Alert>>('/api/alerts', { query }),

  alertTimeline: (videoId: number) => request<Alert[]>(`/api/alerts/video/${videoId}/timeline`),

  acknowledgeAlert: (id: number, acknowledged = true) =>
    request<Alert>(`/api/alerts/${id}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify({ acknowledged }),
    }),

  acknowledgeAll: (videoId?: number) =>
    request<{ acknowledged: number }>('/api/alerts/acknowledge-all', {
      method: 'POST',
      query: { video_id: videoId },
    }),

  dashboard: () => request<DashboardStats>('/api/analytics/dashboard'),

  analytics: (days = 14) => request<Analytics>('/api/analytics', { query: { days } }),

  systemStatus: () => request<SystemStatus>('/api/system/status'),

  downloadModels: () =>
    request<{ status: string }>('/api/system/models/download', { method: 'POST' }),

  settings: () => request<AppSettings>('/api/settings'),

  saveSettings: (payload: AppSettings) =>
    request<AppSettings>('/api/settings', { method: 'PUT', body: JSON.stringify(payload) }),

  exportUrl: (videoId: number) => mediaUrl(`/api/videos/${videoId}/export`),
}
