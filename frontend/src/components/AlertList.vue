<template>
  <div class="alert-list">
    <div class="alert-header">
      <span class="title">⚠️ 告警列表</span>
      <span class="badge">{{ activeAlerts.length }}</span>
      <button class="refresh-btn" @click="refresh" title="刷新">↻</button>
    </div>
    <div class="alert-filters">
      <button
        v-for="f in filters"
        :key="f.value"
        :class="['filter-btn', { active: activeFilter === f.value }]"
        @click="activeFilter = f.value"
      >{{ f.label }}</button>
    </div>
    <div class="alert-scroll">
      <div
        v-for="alert in filteredAlerts"
        :key="alert.id"
        :class="['alert-item', `severity-${alert.severity}`, `status-${alert.status}`]"
      >
        <div class="alert-top">
          <span class="alert-type">{{ ALERT_TYPE_LABELS[alert.alert_type] || alert.alert_type }}</span>
          <span :class="['severity-badge', alert.severity.toLowerCase()]">{{ alert.severity }}</span>
        </div>
        <div class="alert-channel">{{ alert.channel_name || alert.channel_id }}</div>
        <div class="alert-time">{{ formatTime(alert.started_at) }}</div>
        <div class="alert-actions" v-if="alert.status === 'ACTIVE'">
          <button class="ack-btn" @click.stop="ackAlert(alert.id)">确认</button>
        </div>
        <div class="alert-resolved" v-else>
          {{ alert.status === 'RESOLVED' ? '已恢复' : '已确认' }}
        </div>
      </div>
      <div v-if="!filteredAlerts.length" class="empty-state">
        {{ loading ? '加载中...' : '暂无告警' }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAlertsStore } from '@/stores/alerts'
import { ALERT_TYPE_LABELS } from '@/types'

const store = useAlertsStore()
const activeFilter = ref('ACTIVE')

const filters = [
  { value: 'ACTIVE', label: '活跃' },
  { value: 'ACKNOWLEDGED', label: '已确认' },
  { value: 'RESOLVED', label: '已恢复' },
  { value: '', label: '全部' },
]

const loading = computed(() => store.loading)
const activeAlerts = computed(() => store.activeAlerts)

const filteredAlerts = computed(() => {
  if (!activeFilter.value) return store.alerts.slice(0, 100)
  return store.alerts.filter((a) => a.status === activeFilter.value).slice(0, 100)
})

async function refresh() {
  await store.fetchAlerts()
}

async function ackAlert(id: number) {
  await store.ackAlert(id)
}

function formatTime(iso: string): string {
  return iso.replace('T', ' ').substring(0, 19)
}
</script>

<style scoped>
.alert-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #0f172a;
  border-radius: 8px;
  overflow: hidden;
}

.alert-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
}

.title {
  font-size: 14px;
  font-weight: 700;
  color: #e2e8f0;
  flex: 1;
}

.badge {
  background: #ef4444;
  color: #fff;
  border-radius: 10px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 600;
}

.refresh-btn {
  background: transparent;
  border: 1px solid #475569;
  color: #94a3b8;
  border-radius: 4px;
  padding: 2px 8px;
  cursor: pointer;
  font-size: 14px;
}

.alert-filters {
  display: flex;
  gap: 4px;
  padding: 8px 12px;
  border-bottom: 1px solid #1e293b;
}

.filter-btn {
  padding: 3px 10px;
  border-radius: 4px;
  border: 1px solid #334155;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  font-size: 11px;
  transition: all 0.2s;
}
.filter-btn.active {
  background: #1e3a5f;
  color: #93c5fd;
  border-color: #2563eb;
}

.alert-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.alert-item {
  background: #1e293b;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 6px;
  border-left: 3px solid #475569;
  transition: opacity 0.2s;
}

.alert-item.severity-CRITICAL { border-left-color: #ef4444; }
.alert-item.severity-WARNING { border-left-color: #f59e0b; }
.alert-item.status-RESOLVED { opacity: 0.5; }
.alert-item.status-ACKNOWLEDGED { opacity: 0.7; }

.alert-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.alert-type {
  font-size: 13px;
  font-weight: 600;
  color: #f1f5f9;
}

.severity-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
}
.severity-badge.critical { background: #7f1d1d; color: #fca5a5; }
.severity-badge.warning { background: #78350f; color: #fcd34d; }

.alert-channel {
  font-size: 12px;
  color: #93c5fd;
  margin-bottom: 2px;
}

.alert-time {
  font-size: 10px;
  color: #64748b;
  margin-bottom: 4px;
}

.ack-btn {
  background: #1e40af;
  border: none;
  color: #fff;
  border-radius: 4px;
  padding: 2px 10px;
  cursor: pointer;
  font-size: 11px;
}

.alert-resolved {
  font-size: 11px;
  color: #64748b;
}

.empty-state {
  text-align: center;
  padding: 32px 0;
  color: #475569;
  font-size: 14px;
}
</style>
