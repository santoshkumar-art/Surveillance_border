export type Severity = 'low' | 'medium' | 'high' | 'critical'

export type DetectionCategory =
  | 'face'
  | 'person'
  | 'vehicle'
  | 'license_plate'
  | 'drone'
  | 'vandalism'
  | 'weapon'

export type VideoStatus = 'uploaded' | 'queued' | 'processing' | 'completed' | 'failed'

export interface User {
  id: number
  username: string
  full_name: string
  role: string
  last_login_at: string | null
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface Video {
  id: number
  original_name: string
  checkpoint: string
  notes: string
  size_bytes: number
  duration_sec: number
  fps: number
  width: number
  height: number
  frame_count: number
  status: VideoStatus
  progress: number
  frames_analyzed: number
  error_message: string | null
  processing_seconds: number
  created_at: string
  started_at: string | null
  completed_at: string | null
  thumbnail_name: string | null
  annotated_name: string | null
  detection_count: number
  alert_count: number
  critical_alert_count: number
  category_counts: Record<string, number>
}

export interface Detection {
  id: number
  video_id: number
  category: DetectionCategory
  label: string
  confidence: number
  frame_index: number
  timestamp_sec: number
  x1: number
  y1: number
  x2: number
  y2: number
  plate_text: string | null
  snapshot_name: string | null
  meta: Record<string, unknown>
  created_at: string
}

export interface Alert {
  id: number
  video_id: number
  detection_id: number | null
  category: DetectionCategory
  severity: Severity
  title: string
  message: string
  timestamp_sec: number
  snapshot_name: string | null
  acknowledged: boolean
  acknowledged_at: string | null
  acknowledged_by: string | null
  created_at: string
  video_name: string | null
  checkpoint: string | null
}

export interface Page<T> {
  total: number
  limit: number
  offset: number
  items: T[]
}

export interface DashboardStats {
  videos_total: number
  videos_processing: number
  videos_completed: number
  videos_failed: number
  detections_total: number
  alerts_total: number
  alerts_unacknowledged: number
  alerts_critical: number
  footage_hours: number
  detections_by_category: Record<string, number>
  alerts_by_severity: Record<string, number>
}

export interface TimeseriesPoint {
  bucket: string
  detections: number
  alerts: number
}

export interface Analytics {
  detections_by_category: Record<string, number>
  alerts_by_severity: Record<string, number>
  detections_per_day: TimeseriesPoint[]
  top_checkpoints: { checkpoint: string | null; videos: number; alerts: number }[]
  recent_plates: { plate: string; timestamp_sec: number; video_id: number; detection_id: number }[]
  processing_throughput: Record<string, number>
}

export interface ModelStatus {
  key: string
  name: string
  task: string
  loaded: boolean
  available: boolean
  weights_path: string | null
  weights_mb: number | null
  source: string
  error: string | null
}

export interface SystemStatus {
  status: string
  version: string
  uptime_seconds: number
  device: string
  torch_version: string
  opencv_version: string
  cpu_percent: number
  memory_percent: number
  disk_free_gb: number
  queue_depth: number
  active_job: number | null
  models: ModelStatus[]
  storage: Record<string, number>
}

export interface AppSettings {
  frame_stride: number
  detection_confidence: number
  face_confidence: number
  plate_confidence: number
  drone_confidence: number
  enable_plate_ocr: boolean
  write_annotated_video: boolean
  vandalism_sensitivity: number
  crowd_threshold: number
  alert_on_face: boolean
  alert_on_vehicle: boolean
  alert_on_plate: boolean
  alert_on_drone: boolean
  alert_on_vandalism: boolean
}

/** Live websocket payloads, flattened as `{type, ...payload}` by the backend bus. */
export interface LiveEvent {
  type: string
  video_id?: number
  detection_id?: number
  alert_id?: number
  category?: DetectionCategory
  severity?: Severity
  label?: string
  title?: string
  message?: string
  confidence?: number
  timestamp_sec?: number
  plate_text?: string | null
  snapshot_name?: string | null
  progress?: number
  detections?: number
  alerts?: number
  people_in_frame?: number
  anomaly_score?: number
  frames_analyzed?: number
  processing_seconds?: number
  name?: string
  error?: string
  acknowledged?: boolean
  by?: string | null
  count?: number
  user?: string
}
