<template>
  <div class="sim-view">
    <div class="sim-header">
      <h2>仿真测试控制台</h2>
      <p class="sim-desc">用于模拟各类故障，测试告警和监测功能。需要仿真模式已启动（探针服务检测本地视频文件）。</p>
    </div>

    <div class="sim-panel">
      <div class="form-row">
        <label>频道ID</label>
        <input v-model="channelId" placeholder="ch001" class="sim-input" />
      </div>
      <div class="form-row">
        <label>故障类型</label>
        <select v-model="faultType" class="sim-select">
          <option v-for="f in faultTypes" :key="f.value" :value="f.value">{{ f.label }}</option>
        </select>
      </div>
      <div class="form-row">
        <label>持续时长(秒)</label>
        <input v-model.number="duration" type="number" min="5" max="300" class="sim-input" />
      </div>
      <div class="form-actions">
        <button class="trigger-btn" @click="triggerFault" :disabled="loading">
          {{ loading ? '触发中...' : '触发故障' }}
        </button>
        <button class="clear-btn" @click="clearFault" :disabled="loading">清除故障</button>
      </div>
      <div v-if="message" :class="['sim-msg', msgType]">{{ message }}</div>
    </div>

    <div class="sim-info">
      <h3>故障类型说明</h3>
      <table class="fault-table">
        <thead>
          <tr>
            <th>故障类型</th>
            <th>说明</th>
            <th>触发告警</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in faultTypes" :key="f.value">
            <td><code>{{ f.value }}</code></td>
            <td>{{ f.desc }}</td>
            <td>{{ f.alert }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'

const channelId = ref('ch001')
const faultType = ref('BLACK_SCREEN')
const duration = ref(30)
const loading = ref(false)
const message = ref('')
const msgType = ref<'success' | 'error'>('success')

const faultTypes = [
  { value: 'BLACK_SCREEN', label: '黑屏', desc: '视频帧替换为全黑内容', alert: '黑屏告警 (CRITICAL)' },
  { value: 'FROZEN', label: '冻屏', desc: '重复发送上一帧画面', alert: '冻屏告警 (CRITICAL)' },
  { value: 'SILENT', label: '静音', desc: '音频帧替换为静音数据', alert: '静音告警 (CRITICAL)' },
  { value: 'PACKET_LOSS', label: '丢包', desc: '随机丢弃UDP包', alert: 'CC错误/码率异常 (WARNING)' },
  { value: 'BITRATE_DROP', label: '码率降低', desc: '人为延迟发送，降低码率', alert: '码率异常 (WARNING)' },
]

async function triggerFault() {
  if (!channelId.value) return
  loading.value = true
  message.value = ''
  try {
    await axios.post('/api/v1/sim/trigger', {
      channel_id: channelId.value,
      fault_type: faultType.value,
      duration_sec: duration.value,
    })
    message.value = `已向 ${channelId.value} 触发 ${faultType.value} 故障，持续 ${duration.value}秒`
    msgType.value = 'success'
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    message.value = `触发失败: ${err.response?.data?.detail || err.message || '未知错误'}`
    msgType.value = 'error'
  } finally {
    loading.value = false
  }
}

async function clearFault() {
  if (!channelId.value) return
  loading.value = true
  message.value = ''
  try {
    await axios.post('/api/v1/sim/clear', { channel_id: channelId.value })
    message.value = `已清除 ${channelId.value} 的故障`
    msgType.value = 'success'
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    message.value = `清除失败: ${err.response?.data?.detail || err.message || '未知错误'}`
    msgType.value = 'error'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.sim-view {
  height: 100%;
  overflow-y: auto;
  padding: 24px;
  max-width: 800px;
  margin: 0 auto;
}

.sim-header {
  margin-bottom: 24px;
}

.sim-header h2 {
  font-size: 20px;
  color: #f1f5f9;
  margin-bottom: 8px;
}

.sim-desc {
  font-size: 13px;
  color: #64748b;
  line-height: 1.6;
}

.sim-panel {
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 10px;
  padding: 24px;
  margin-bottom: 24px;
}

.form-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.form-row label {
  width: 100px;
  font-size: 13px;
  color: #94a3b8;
  text-align: right;
  flex-shrink: 0;
}

.sim-input,
.sim-select {
  flex: 1;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 8px 12px;
  color: #e2e8f0;
  font-size: 13px;
  outline: none;
}
.sim-input:focus,
.sim-select:focus {
  border-color: #3b82f6;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-left: 112px;
  margin-top: 8px;
}

.trigger-btn {
  background: #dc2626;
  border: none;
  color: #fff;
  border-radius: 6px;
  padding: 8px 20px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: background 0.2s;
}
.trigger-btn:hover:not(:disabled) { background: #ef4444; }
.trigger-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.clear-btn {
  background: #1e293b;
  border: 1px solid #334155;
  color: #94a3b8;
  border-radius: 6px;
  padding: 8px 20px;
  cursor: pointer;
  font-size: 14px;
}
.clear-btn:hover:not(:disabled) { background: #334155; color: #e2e8f0; }
.clear-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.sim-msg {
  margin-top: 12px;
  margin-left: 112px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
}
.sim-msg.success { background: #052e16; color: #4ade80; border: 1px solid #16a34a; }
.sim-msg.error { background: #450a0a; color: #f87171; border: 1px solid #dc2626; }

.sim-info {
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 10px;
  padding: 20px;
}

.sim-info h3 {
  font-size: 16px;
  color: #e2e8f0;
  margin-bottom: 16px;
}

.fault-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.fault-table th {
  text-align: left;
  padding: 8px 12px;
  color: #64748b;
  border-bottom: 1px solid #1e293b;
}

.fault-table td {
  padding: 10px 12px;
  color: #cbd5e1;
  border-bottom: 1px solid #0f172a;
}

.fault-table tr:hover td { background: #1e293b; }

.fault-table code {
  background: #1e293b;
  padding: 2px 6px;
  border-radius: 3px;
  color: #93c5fd;
  font-size: 12px;
}
</style>
