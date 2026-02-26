<template>
  <div class="channel-grid-page">
    <div class="toolbar">
      <div class="stats-bar">
        <span
          v-for="(count, key) in stats"
          v-show="key !== 'total'"
          :key="key"
          :class="['stat-chip', `stat-${key}`]"
          @click="toggleFilter(key as string)"
          :title="`筛选${STATUS_LABELS[key as ChannelStatusValue]}`"
        >
          {{ STATUS_LABELS[key as ChannelStatusValue] }} {{ count }}
        </span>
        <span class="stat-chip stat-total">共 {{ stats.total }} 路</span>
      </div>
      <div class="search-wrap">
        <input
          v-model="searchQuery"
          placeholder="搜索频道名称/ID..."
          class="search-input"
        />
      </div>
      <div class="group-filter">
        <select v-model="selectedGroup" class="group-select">
          <option value="">全部分组</option>
          <option v-for="g in groups" :key="g" :value="g">{{ g }}</option>
        </select>
      </div>
      <AudioAlarmManager ref="alarmManagerRef" />
      <div class="ws-status" :class="{ connected: wsConnected }">
        {{ wsConnected ? '● 已连接' : '○ 重连中' }}
      </div>
    </div>

    <div class="grid-container">
      <ChannelCard
        v-for="ch in filteredChannels"
        :key="ch.channel_id"
        :channel="ch"
        @click="openDetail"
      />
      <div v-if="!filteredChannels.length" class="empty-grid">
        {{ channelsStore.loading ? '加载中...' : '暂无匹配频道' }}
      </div>
    </div>

    <div v-if="detailChannel" class="detail-panel">
      <div class="detail-header">
        <span class="detail-title">{{ detailChannel.channel_name }}</span>
        <span :class="['detail-status', `status-${detailChannel.status}`]">
          {{ STATUS_LABELS[detailChannel.status as ChannelStatusValue] }}
        </span>
        <button class="thumb-btn" @click="thumbVisible = true">📷 缩略图</button>
        <button class="close-detail" @click="detailChannel = null">✕</button>
      </div>
      <div class="detail-metrics">
        <div class="metric-item">
          <span class="metric-label">码率</span>
          <span class="metric-value">{{ formatBitrate(detailChannel.bitrate_kbps) }}</span>
        </div>
        <div class="metric-item">
          <span class="metric-label">PCR抖动</span>
          <span class="metric-value">{{ detailChannel.pcr_jitter_ms.toFixed(1) }}ms</span>
        </div>
        <div class="metric-item">
          <span class="metric-label">CC错误/s</span>
          <span class="metric-value">{{ detailChannel.cc_errors_per_sec.toFixed(1) }}</span>
        </div>
        <div class="metric-item">
          <span class="metric-label">亮度</span>
          <span class="metric-value">{{ detailChannel.video_brightness.toFixed(0) }}</span>
        </div>
        <div class="metric-item">
          <span class="metric-label">音频RMS</span>
          <span class="metric-value">{{ detailChannel.audio_rms.toFixed(4) }}</span>
        </div>
      </div>
      <MetricsChart :channel-id="detailChannel.channel_id" />
      <ThumbnailModal v-model:visible="thumbVisible" :channel="detailChannel" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useChannelsStore } from '@/stores/channels'
import { useAlertsStore } from '@/stores/alerts'
import { useWebSocket } from '@/composables/useWebSocket'
import { useAlarmSuppression } from '@/composables/useAlarmSuppression'
import { STATUS_LABELS, STATUS_COLORS } from '@/types'
import type { ChannelStatus, ChannelStatusValue, WSMessage, Alert } from '@/types'
import ChannelCard from './ChannelCard.vue'
import MetricsChart from './MetricsChart.vue'
import AlertList from './AlertList.vue'
import ThumbnailModal from './ThumbnailModal.vue'
import AudioAlarmManager from './AudioAlarmManager.vue'

const channelsStore = useChannelsStore()
const alertsStore = useAlertsStore()
const alarmSuppression = useAlarmSuppression()
const alarmManagerRef = ref()

const searchQuery = ref('')
const selectedGroup = ref('')
const activeStatusFilter = ref<string>('')
const detailChannel = ref<ChannelStatus | null>(null)
const thumbVisible = ref(false)

const groups = computed(() => {
  const s = new Set<string>()
  for (const ch of channelsStore.channelList) {
    if (ch.group_name) s.add(ch.group_name)
  }
  return Array.from(s).sort()
})

const stats = computed(() => channelsStore.stats)

const filteredChannels = computed(() => {
  let list = channelsStore.channelList
  if (activeStatusFilter.value) {
    list = list.filter((ch) => ch.status === activeStatusFilter.value)
  }
  if (selectedGroup.value) {
    list = list.filter((ch) => ch.group_name === selectedGroup.value)
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter(
      (ch) =>
        ch.channel_name.toLowerCase().includes(q) ||
        ch.channel_id.toLowerCase().includes(q)
    )
  }
  return list
})

function toggleFilter(status: string) {
  activeStatusFilter.value = activeStatusFilter.value === status ? '' : status
}

function openDetail(ch: ChannelStatus) {
  detailChannel.value = ch
  thumbVisible.value = false
}

function formatBitrate(kbps: number): string {
  if (kbps >= 1000) return `${(kbps / 1000).toFixed(2)} Mbps`
  if (kbps > 0) return `${kbps.toFixed(0)} kbps`
  return '--'
}

function handleWsMessage(msg: WSMessage) {
  if (msg.type === 'channel_status') {
    channelsStore.updateChannel({
      channel_id: msg.channel_id,
      channel_name: msg.channel_name,
      status: msg.status,
      bitrate_kbps: msg.bitrate_kbps,
      is_black: msg.is_black,
      is_frozen: msg.is_frozen,
      is_silent: msg.is_silent,
      is_clipping: msg.is_clipping,
      cc_errors_per_sec: msg.cc_errors_per_sec,
      pcr_jitter_ms: msg.pcr_jitter_ms,
      audio_rms: msg.audio_rms,
      video_brightness: msg.video_brightness,
      thumbnail_path: msg.thumbnail_path,
      updated_at: msg.ts,
    } as ChannelStatus)
    if (detailChannel.value?.channel_id === msg.channel_id) {
      detailChannel.value = channelsStore.channels.get(msg.channel_id) || detailChannel.value
    }
  } else if (msg.type === 'batch_update') {
    channelsStore.batchUpdate(msg.channels)
  } else if (msg.type === 'alert_new') {
    const alert: Alert = {
      id: msg.alert_id,
      channel_id: msg.channel_id,
      channel_name: msg.channel_name,
      alert_type: msg.alert_type,
      severity: msg.severity,
      status: 'ACTIVE',
      message: null,
      started_at: new Date(msg.ts * 1000).toISOString(),
      resolved_at: null,
      ack_at: null,
      thumbnail_path: null,
    }
    alertsStore.addAlert(alert)
    alarmSuppression.addAlert(alert)
  } else if (msg.type === 'alert_resolved') {
    alertsStore.resolveAlert(msg.alert_id)
  }
}

const { connected: wsConnected } = useWebSocket(handleWsMessage)

onMounted(async () => {
  await channelsStore.fetchChannels()
  await alertsStore.fetchAlerts('ACTIVE')
})
</script>

<style scoped>
.channel-grid-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #0a0e1a;
  overflow: hidden;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: #0d1117;
  border-bottom: 1px solid #1e293b;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.stats-bar {
  display: flex;
  gap: 6px;
  flex-wrap: nowrap;
}

.stat-chip {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s;
  white-space: nowrap;
}
.stat-chip:hover { opacity: 0.85; transform: scale(1.03); }
.stat-NORMAL { background: #052e16; color: #4ade80; border-color: #16a34a; }
.stat-WARNING { background: #431407; color: #fcd34d; border-color: #d97706; }
.stat-ALARM { background: #450a0a; color: #f87171; border-color: #dc2626; }
.stat-OFFLINE { background: #1c1917; color: #a8a29e; border-color: #44403c; }
.stat-total { background: #0f172a; color: #94a3b8; border-color: #334155; cursor: default; }

.search-input {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 5px 12px;
  color: #e2e8f0;
  font-size: 13px;
  width: 200px;
  outline: none;
}
.search-input::placeholder { color: #475569; }
.search-input:focus { border-color: #3b82f6; }

.group-select {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 5px 10px;
  color: #e2e8f0;
  font-size: 13px;
  outline: none;
  cursor: pointer;
}

.ws-status {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}
.ws-status.connected { color: #4ade80; }

.grid-container {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-content: flex-start;
}

.empty-grid {
  width: 100%;
  text-align: center;
  padding: 48px;
  color: #475569;
  font-size: 16px;
}

.detail-panel {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: 480px;
  background: #0f172a;
  border-left: 1px solid #1e293b;
  z-index: 100;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 16px;
  gap: 16px;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.detail-title {
  font-size: 16px;
  font-weight: 700;
  color: #f1f5f9;
  flex: 1;
}

.detail-status {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 12px;
  font-weight: 600;
}
.detail-status.status-NORMAL { background: #052e16; color: #4ade80; }
.detail-status.status-WARNING { background: #431407; color: #fcd34d; }
.detail-status.status-ALARM { background: #450a0a; color: #f87171; }
.detail-status.status-OFFLINE { background: #1c1917; color: #a8a29e; }

.thumb-btn {
  background: #1e293b;
  border: 1px solid #334155;
  color: #94a3b8;
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 12px;
}

.close-detail {
  background: transparent;
  border: 1px solid #475569;
  color: #94a3b8;
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 14px;
}

.detail-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.metric-item {
  background: #1e293b;
  border-radius: 6px;
  padding: 10px;
  text-align: center;
}

.metric-label {
  display: block;
  font-size: 11px;
  color: #64748b;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 16px;
  font-weight: 700;
  color: #e2e8f0;
  font-family: 'Courier New', monospace;
}
</style>
