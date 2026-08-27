import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { websocketUrl } from '../lib/api'
import type { LiveEvent } from '../lib/types'
import { useAuth } from './AuthContext'

export interface LiveAlert {
  id: number
  videoId: number
  severity: string
  category: string
  title: string
  message: string
  timestampSec: number
  snapshot: string | null
  receivedAt: number
}

export interface JobProgress {
  videoId: number
  progress: number
  detections: number
  alerts: number
  peopleInFrame: number
  anomalyScore: number
  timestampSec: number
}

interface LiveValue {
  connected: boolean
  events: LiveEvent[]
  alerts: LiveAlert[]
  toasts: LiveAlert[]
  progress: Record<number, JobProgress>
  completions: number
  dismissToast: (id: number) => void
  clearAlerts: () => void
}

const LiveContext = createContext<LiveValue | null>(null)
const MAX_EVENTS = 120
const MAX_ALERTS = 60
const TOAST_TTL_MS = 9000

export function LiveProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [connected, setConnected] = useState(false)
  const [events, setEvents] = useState<LiveEvent[]>([])
  const [alerts, setAlerts] = useState<LiveAlert[]>([])
  const [toasts, setToasts] = useState<LiveAlert[]>([])
  const [progress, setProgress] = useState<Record<number, JobProgress>>({})
  const [completions, setCompletions] = useState(0)
  const socketRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<number>(0)

  const dismissToast = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const clearAlerts = useCallback(() => setAlerts([]), [])

  const handleEvent = useCallback((event: LiveEvent) => {
    if (event.type === 'heartbeat') return
    setEvents((current) => [event, ...current].slice(0, MAX_EVENTS))

    if (event.type === 'progress' && event.video_id !== undefined) {
      setProgress((current) => ({
        ...current,
        [event.video_id as number]: {
          videoId: event.video_id as number,
          progress: event.progress ?? 0,
          detections: event.detections ?? 0,
          alerts: event.alerts ?? 0,
          peopleInFrame: event.people_in_frame ?? 0,
          anomalyScore: event.anomaly_score ?? 0,
          timestampSec: event.timestamp_sec ?? 0,
        },
      }))
      return
    }

    if (event.type === 'alert' && event.alert_id !== undefined) {
      const alert: LiveAlert = {
        id: event.alert_id,
        videoId: event.video_id ?? 0,
        severity: event.severity ?? 'medium',
        category: event.category ?? 'unknown',
        title: event.title ?? 'Alert',
        message: event.message ?? '',
        timestampSec: event.timestamp_sec ?? 0,
        snapshot: event.snapshot_name ?? null,
        receivedAt: Date.now(),
      }
      setAlerts((current) => [alert, ...current].slice(0, MAX_ALERTS))
      setToasts((current) => [alert, ...current].slice(0, 4))
      window.setTimeout(() => dismissToast(alert.id), TOAST_TTL_MS)
      return
    }

    if (event.type === 'video_completed' || event.type === 'video_failed') {
      setCompletions((value) => value + 1)
    }
  }, [dismissToast])

  useEffect(() => {
    if (!user) {
      socketRef.current?.close()
      socketRef.current = null
      setConnected(false)
      return
    }

    let disposed = false
    let reconnectTimer = 0

    const connect = () => {
      if (disposed) return
      const socket = new WebSocket(websocketUrl())
      socketRef.current = socket

      socket.onopen = () => {
        retryRef.current = 0
        setConnected(true)
      }
      socket.onmessage = (message) => {
        try {
          handleEvent(JSON.parse(message.data as string) as LiveEvent)
        } catch {
          /* ignore malformed frames */
        }
      }
      socket.onclose = () => {
        setConnected(false)
        if (disposed) return
        retryRef.current = Math.min(retryRef.current + 1, 6)
        reconnectTimer = window.setTimeout(connect, 1000 * retryRef.current)
      }
      socket.onerror = () => socket.close()
    }

    connect()
    return () => {
      disposed = true
      window.clearTimeout(reconnectTimer)
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [user, handleEvent])

  const value = useMemo(
    () => ({
      connected,
      events,
      alerts,
      toasts,
      progress,
      completions,
      dismissToast,
      clearAlerts,
    }),
    [connected, events, alerts, toasts, progress, completions, dismissToast, clearAlerts],
  )

  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>
}

export function useLive(): LiveValue {
  const context = useContext(LiveContext)
  if (!context) throw new Error('useLive must be used inside LiveProvider')
  return context
}
