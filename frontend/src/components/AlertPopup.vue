<template>
  <teleport to="body">
    <div class="popup-container">
      <transition-group name="popup-slide" tag="div">
        <div
          v-for="popup in visiblePopups"
          :key="popup.id"
          :class="['popup-card', `severity-${popup.severity}`]"
          @click="dismiss(popup.id)"
        >
          <span class="popup-icon">{{ ALERT_ICONS[popup.alert_type] || '⚠️' }}</span>
          <div class="popup-body">
            <div class="popup-type">{{ ALERT_TYPE_LABELS[popup.alert_type] || popup.alert_type }}</div>
            <div class="popup-channel">{{ popup.channel_name || popup.channel_id }}</div>
          </div>
        </div>
      </transition-group>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAlertsStore } from '@/stores/alerts'
import { ALERT_TYPE_LABELS } from '@/types'

const ALERT_ICONS: Record<string, string> = {
  BLACK_SCREEN: '⬛',
  FROZEN: '❄️',
  SILENT: '🔇',
  CLIPPING: '🔊',
  CC_ERROR: '⚠️',
  PCR_JITTER: '📡',
  BITRATE_ABNORMAL: '📊',
  OFFLINE: '🔴',
  MOSAIC: '🌀',
  AUDIO_STUTTER: '🔄',
}

interface PopupItem {
  id: number
  alert_type: string
  severity: string
  channel_name: string | null
  channel_id: string
}

const alertsStore = useAlertsStore()
const visiblePopups = ref<PopupItem[]>([])
const MAX_POPUPS = 5
const AUTO_DISMISS_MS = 5000
const shownIds = new Set<number>()

function dismiss(id: number) {
  visiblePopups.value = visiblePopups.value.filter(p => p.id !== id)
}

watch(
  () => alertsStore.alerts.length,
  () => {
    for (const alert of alertsStore.alerts) {
      if (alert.status !== 'ACTIVE') continue
      if (shownIds.has(alert.id)) continue
      shownIds.add(alert.id)
      if (visiblePopups.value.length < MAX_POPUPS) {
        visiblePopups.value.unshift({
          id: alert.id,
          alert_type: alert.alert_type,
          severity: alert.severity,
          channel_name: alert.channel_name,
          channel_id: alert.channel_id,
        })
        setTimeout(() => dismiss(alert.id), AUTO_DISMISS_MS)
      }
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.popup-container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}
.popup-card {
  pointer-events: all;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  background: #1e293b;
  border-left: 4px solid #f59e0b;
  cursor: pointer;
  min-width: 220px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
}
.popup-card.severity-CRITICAL { border-left-color: #ef4444; }
.popup-card.severity-WARNING  { border-left-color: #f59e0b; }
.popup-icon { font-size: 20px; }
.popup-type { font-size: 13px; font-weight: 700; color: #f1f5f9; }
.popup-channel { font-size: 11px; color: #94a3b8; }
.popup-slide-enter-active, .popup-slide-leave-active { transition: all 0.3s ease; }
.popup-slide-enter-from { opacity: 0; transform: translateX(60px); }
.popup-slide-leave-to   { opacity: 0; transform: translateX(60px); }
</style>
