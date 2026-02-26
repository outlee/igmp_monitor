<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="close">
      <div class="modal-container">
        <div class="modal-header">
          <span class="modal-title">{{ channel?.channel_name }} - 缩略图预览</span>
          <button class="close-btn" @click="close">✕</button>
        </div>
        <div class="modal-body">
          <div class="thumb-section">
            <div class="section-title">最新帧</div>
            <img
              v-if="channel"
              :src="`/api/v1/thumbnails/${channel.channel_id}/latest?t=${Date.now()}`"
              class="main-thumb"
              alt="最新帧"
              @error="latestError = true"
            />
            <div v-if="latestError" class="no-thumb">暂无缩略图</div>
          </div>
          <div class="thumb-section" v-if="alarmThumbs.length">
            <div class="section-title">告警截图 ({{ alarmThumbs.length }})</div>
            <div class="alarm-grid">
              <img
                v-for="url in alarmThumbs.slice(0, 20)"
                :key="url"
                :src="url"
                class="alarm-thumb"
                :title="url"
                @click="viewAlarm(url)"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="zoomUrl" class="zoom-backdrop" @click="zoomUrl = ''">
      <img :src="zoomUrl" class="zoom-img" />
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import axios from 'axios'
import type { ChannelStatus } from '@/types'

const props = defineProps<{
  visible: boolean
  channel: ChannelStatus | null
}>()
const emit = defineEmits<{ 'update:visible': [v: boolean] }>()

const alarmThumbs = ref<string[]>([])
const latestError = ref(false)
const zoomUrl = ref('')

function close() {
  emit('update:visible', false)
}

function viewAlarm(url: string) {
  zoomUrl.value = url
}

watch(
  () => props.channel,
  async (ch) => {
    alarmThumbs.value = []
    latestError.value = false
    if (ch) {
      try {
        const { data } = await axios.get<string[]>(`/api/v1/thumbnails/${ch.channel_id}/alarms`)
        alarmThumbs.value = data
      } catch {
        alarmThumbs.value = []
      }
    }
  }
)
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.8);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-container {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 12px;
  width: min(900px, 95vw);
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
}

.modal-title {
  font-size: 16px;
  font-weight: 700;
  color: #f1f5f9;
}

.close-btn {
  background: transparent;
  border: 1px solid #475569;
  color: #94a3b8;
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 14px;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section-title {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 10px;
  font-weight: 600;
}

.main-thumb {
  width: 320px;
  height: 180px;
  object-fit: contain;
  background: #000;
  border-radius: 6px;
  border: 1px solid #334155;
}

.no-thumb {
  width: 320px;
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1e293b;
  color: #475569;
  border-radius: 6px;
}

.alarm-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.alarm-thumb {
  width: 160px;
  height: 90px;
  object-fit: cover;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid #334155;
  transition: transform 0.15s;
}
.alarm-thumb:hover {
  transform: scale(1.05);
  border-color: #ef4444;
}

.zoom-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.95);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: zoom-out;
}

.zoom-img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
}
</style>
