<template>
  <div class="audio-alarm-manager">
    <button
      :class="['tts-toggle', { enabled: suppression.ttsEnabled.value }]"
      @click="toggleTTS"
      :title="suppression.ttsEnabled.value ? '点击关闭语音告警' : '点击开启语音告警'"
    >
      {{ suppression.ttsEnabled.value ? '🔔 语音告警: 开' : '🔕 语音告警: 关' }}
    </button>
    <button class="test-btn" @click="suppression.testSpeak()" title="测试语音">测试</button>
    <button class="clear-btn" @click="suppression.clearSuppression()" title="清除抑制">清除抑制</button>
  </div>
</template>

<script setup lang="ts">
import { useAlarmSuppression } from '@/composables/useAlarmSuppression'

const suppression = useAlarmSuppression()

defineExpose({ suppression })

function toggleTTS() {
  suppression.ttsEnabled.value = !suppression.ttsEnabled.value
}
</script>

<style scoped>
.audio-alarm-manager {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tts-toggle {
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid #334155;
  background: #1e293b;
  color: #94a3b8;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}
.tts-toggle.enabled {
  background: #14532d;
  color: #86efac;
  border-color: #16a34a;
}

.test-btn,
.clear-btn {
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #334155;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  font-size: 11px;
}
.test-btn:hover,
.clear-btn:hover {
  background: #1e293b;
  color: #94a3b8;
}
</style>
