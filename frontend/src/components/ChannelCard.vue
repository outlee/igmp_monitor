<template>
  <div
    class="channel-card"
    :class="[`status-${channel.status}`, { 'alarm-blink': channel.status === 'ALARM' }]"
    :title="`${channel.channel_name}\n码率: ${formatBitrate(channel.bitrate_kbps)}\nPCR抖动: ${channel.pcr_jitter_ms.toFixed(1)}ms`"
    @click="$emit('click', channel)"
    @mouseenter="showThumb = true"
    @mouseleave="showThumb = false"
  >
    <div class="thumb-wrap" v-if="showThumb && channel.status !== 'OFFLINE'">
      <img
        :src="`/api/v1/thumbnails/${channel.channel_id}/latest?t=${thumbTs}`"
        class="thumbnail"
        @error="showThumb = false"
        loading="lazy"
      />
    </div>
    <div class="status-dot"></div>
    <div class="channel-name">{{ channel.channel_name }}</div>
    <div class="channel-id">{{ channel.channel_id }}</div>
    <div class="bitrate">{{ formatBitrate(channel.bitrate_kbps) }}</div>
    <div class="alert-icons">
      <span v-if="channel.is_black" title="黑屏">⬛</span>
      <span v-if="channel.is_frozen" title="冻屏">❄️</span>
      <span v-if="channel.is_silent" title="静音">🔇</span>
      <span v-if="channel.is_clipping" title="爆音">🔊</span>
      <span v-if="channel.is_mosaic" title="花屏">🌀</span>
      <span v-if="channel.is_stuttering" title="音频卡顿">🔄</span>
      <span v-if="channel.cc_errors_per_sec > 5" title="CC错误">⚠️</span>
      <span v-if="channel.pcr_jitter_ms > 40" title="PCR抖动">📡</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ChannelStatus } from '@/types'

const props = defineProps<{ channel: ChannelStatus }>()
const emit = defineEmits<{ click: [channel: ChannelStatus] }>()

const showThumb = ref(false)
const thumbTs = ref(Date.now())

setInterval(() => {
  if (showThumb.value) thumbTs.value = Date.now()
}, 5000)

function formatBitrate(kbps: number): string {
  if (kbps >= 1000) return `${(kbps / 1000).toFixed(1)}Mbps`
  if (kbps > 0) return `${kbps.toFixed(0)}kbps`
  return '--'
}
</script>

<style scoped>
.channel-card {
  position: relative;
  width: 160px;
  height: 90px;
  border-radius: 6px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  padding: 6px 8px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow: hidden;
  user-select: none;
}

.channel-card:hover {
  transform: scale(1.04);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
  z-index: 10;
}

.status-NORMAL {
  background: #0d1f0d;
  border: 1.5px solid #00c853;
}
.status-WARNING {
  background: #1f1a00;
  border: 1.5px solid #ffd600;
}
.status-ALARM {
  background: #1f0000;
  border: 1.5px solid #d50000;
}
.status-OFFLINE {
  background: #111115;
  border: 1.5px solid #424242;
}

@keyframes blink {
  0%, 100% { border-color: #d50000; box-shadow: 0 0 6px #d50000; }
  50% { border-color: #ff5252; box-shadow: 0 0 12px #ff5252; }
}
.alarm-blink {
  animation: blink 1.2s ease-in-out infinite;
}

.status-dot {
  position: absolute;
  top: 5px;
  right: 6px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-NORMAL .status-dot { background: #00c853; }
.status-WARNING .status-dot { background: #ffd600; }
.status-ALARM .status-dot { background: #d50000; }
.status-OFFLINE .status-dot { background: #616161; }

.channel-name {
  font-size: 12px;
  font-weight: 600;
  color: #e8eaf6;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 130px;
}

.channel-id {
  font-size: 10px;
  color: #78909c;
}

.bitrate {
  font-size: 11px;
  font-family: 'Courier New', monospace;
  color: #90caf9;
}

.alert-icons {
  font-size: 11px;
  line-height: 1;
  min-height: 14px;
}

.thumb-wrap {
  position: absolute;
  bottom: 100%;
  left: 0;
  z-index: 20;
  background: #000;
  border: 1px solid #333;
  border-radius: 4px;
  overflow: hidden;
  box-shadow: 0 -4px 12px rgba(0,0,0,0.8);
}

.thumbnail {
  display: block;
  width: 320px;
  height: 180px;
  object-fit: cover;
}
</style>
