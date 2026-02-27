export type ChannelStatusValue = 'NORMAL' | 'WARNING' | 'ALARM' | 'OFFLINE'

export interface ChannelStatus {
  channel_id: string
  channel_name: string
  status: ChannelStatusValue
  bitrate_kbps: number
  is_black: boolean
  is_frozen: boolean
  is_silent: boolean
  is_clipping: boolean
  is_mosaic: boolean
  mosaic_ratio: number
  is_stuttering: boolean
  stutter_count: number
  cc_errors_per_sec: number
  pcr_jitter_ms: number
  audio_rms: number
  video_brightness: number
  thumbnail_path: string
  updated_at: number
  group_name: string
  sort_order: number
}

export interface Alert {
  id: number
  channel_id: string
  channel_name: string | null
  alert_type: string
  severity: string
  status: string
  message: string | null
  started_at: string
  resolved_at: string | null
  ack_at: string | null
  thumbnail_path: string | null
}

export interface MetricPoint {
  time: string
  bitrate_kbps: number
  cc_errors_per_sec: number
  pcr_jitter_ms: number
  video_brightness: number
  audio_rms: number
  is_black: number
  is_frozen: number
  is_silent: number
  status: string
}

export interface OverviewStats {
  NORMAL: number
  WARNING: number
  ALARM: number
  OFFLINE: number
  total: number
}

export type WSMessage =
  | { type: 'channel_status'; channel_id: string; status: ChannelStatusValue; channel_name: string; bitrate_kbps: number; is_black: boolean; is_frozen: boolean; is_silent: boolean; is_clipping: boolean; is_mosaic: boolean; mosaic_ratio: number; is_stuttering: boolean; stutter_count: number; cc_errors_per_sec: number; pcr_jitter_ms: number; audio_rms: number; video_brightness: number; thumbnail_path: string; ts: number }
  | { type: 'alert_new'; alert_id: number; channel_id: string; channel_name: string; alert_type: string; severity: string; status: string; ts: number }
  | { type: 'alert_resolved'; alert_id: number; channel_id: string }
  | { type: 'batch_update'; channels: ChannelStatus[]; ts: number }

export const ALERT_TYPE_LABELS: Record<string, string> = {
  BLACK_SCREEN: '黑屏',
  FROZEN: '冻屏',
  SILENT: '静音',
  CLIPPING: '爆音',
  CC_ERROR: 'CC错误',
  PCR_JITTER: 'PCR抖动',
  BITRATE_ABNORMAL: '码率异常',
  OFFLINE: '离线',
  MOSAIC: '花屏',
  AUDIO_STUTTER: '音频卡顿',
}

export const STATUS_COLORS: Record<ChannelStatusValue, string> = {
  NORMAL: '#00C853',
  WARNING: '#FFD600',
  ALARM: '#D50000',
  OFFLINE: '#616161',
}

export const STATUS_LABELS: Record<ChannelStatusValue, string> = {
  NORMAL: '正常',
  WARNING: '注意',
  ALARM: '告警',
  OFFLINE: '离线',
}
