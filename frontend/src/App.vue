<template>
  <div class="app-layout">
    <header class="app-header">
      <div class="logo">
        <span class="logo-icon">📡</span>
        <span class="logo-text">IPTV 组播流媒体质量监测</span>
      </div>
      <div class="header-right">
        <button
          :class="['nav-btn', { active: activeView === 'grid' }]"
          @click="activeView = 'grid'"
        >大屏监控</button>
        <button
          :class="['nav-btn', { active: activeView === 'alerts' }]"
          @click="activeView = 'alerts'"
        >
          告警列表
          <span v-if="alertCount > 0" class="alert-badge">{{ alertCount }}</span>
        </button>
        <button
          :class="['nav-btn', { active: activeView === 'channels' }]"
          @click="activeView = 'channels'"
        >📋 频道管理</button>
        <button
          :class="['nav-btn', { active: activeView === 'sim' }]"
          @click="activeView = 'sim'"
        >仿真测试</button>
        <span class="clock">{{ currentTime }}</span>
      </div>
    </header>
    <main class="app-main">
      <ChannelGrid v-if="activeView === 'grid'" />
      <AlertView v-else-if="activeView === 'alerts'" />
      <ChannelManager v-else-if="activeView === 'channels'" />
      <SimView v-else-if="activeView === 'sim'" />
    </main>
    <AlertPopup />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import ChannelGrid from './components/ChannelGrid.vue'
import AlertView from './components/AlertView.vue'
import ChannelManager from './components/ChannelManager.vue'
import SimView from './components/SimView.vue'
import AlertPopup from './components/AlertPopup.vue'
import { useAlertsStore } from './stores/alerts'

const activeView = ref<'grid' | 'alerts' | 'channels' | 'sim'>('grid')
const alertsStore = useAlertsStore()
const alertCount = computed(() => alertsStore.activeAlerts.length)
const currentTime = ref('')

let timer: ReturnType<typeof setInterval>

function updateClock() {
  currentTime.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

onMounted(() => {
  updateClock()
  timer = setInterval(updateClock, 1000)
})

onUnmounted(() => clearInterval(timer))
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app { width: 100%; height: 100%; background: #0a0e1a; font-family: 'Microsoft YaHei', -apple-system, BlinkMacSystemFont, sans-serif; }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #475569; }
</style>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 52px;
  background: linear-gradient(90deg, #0d1117 0%, #0f1b2d 100%);
  border-bottom: 1px solid #1e3a5f;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-icon { font-size: 22px; }

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: #93c5fd;
  letter-spacing: 0.05em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.nav-btn {
  position: relative;
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid #1e3a5f;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.nav-btn:hover {
  background: #1e293b;
  color: #e2e8f0;
}
.nav-btn.active {
  background: #1e40af;
  color: #fff;
  border-color: #3b82f6;
}

.alert-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #ef4444;
  color: #fff;
  border-radius: 8px;
  padding: 1px 5px;
  font-size: 10px;
  font-weight: 700;
}

.clock {
  font-size: 14px;
  color: #64748b;
  font-family: 'Courier New', monospace;
  min-width: 70px;
  text-align: right;
}

.app-main {
  flex: 1;
  overflow: hidden;
}
</style>
