<template>
  <div class="metrics-chart">
    <div class="chart-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >{{ tab.label }}</button>
    </div>
    <v-chart
      v-if="chartOption"
      :option="chartOption"
      :autoresize="true"
      class="echart"
    />
    <div v-else class="no-data">暂无数据</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { use } from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import axios from 'axios'
import type { MetricPoint } from '@/types'

use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

const props = defineProps<{ channelId: string }>()

const tabs = [
  { key: 'bitrate', label: '码率' },
  { key: 'pcr', label: 'PCR抖动' },
  { key: 'audio', label: '音频' },
  { key: 'errors', label: 'CC错误' },
]
const activeTab = ref('bitrate')
const metrics = ref<MetricPoint[]>([])
const loading = ref(false)

async function loadMetrics() {
  loading.value = true
  try {
    const { data } = await axios.get<MetricPoint[]>(`/api/v1/channels/${props.channelId}/metrics`, {
      params: { range: '10m' },
    })
    metrics.value = data
  } catch {
    metrics.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadMetrics)
watch(() => props.channelId, loadMetrics)

const chartOption = computed(() => {
  if (!metrics.value.length) return null
  const times = metrics.value.map((m) => m.time.substring(11, 19))

  const commonAxis = {
    xAxis: {
      type: 'category' as const,
      data: times,
      axisLabel: { color: '#90caf9', fontSize: 10 },
      axisLine: { lineStyle: { color: '#374151' } },
    },
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: '#1e293b',
      borderColor: '#334155',
      textStyle: { color: '#e2e8f0' },
    },
    grid: { top: 30, right: 20, bottom: 40, left: 55 },
    dataZoom: [{ type: 'inside' as const }],
  }

  if (activeTab.value === 'bitrate') {
    return {
      ...commonAxis,
      yAxis: { type: 'value' as const, name: 'Mbps', axisLabel: { color: '#90caf9', fontSize: 10, formatter: (v: number) => (v / 1000).toFixed(1) }, splitLine: { lineStyle: { color: '#1e293b' } } },
      series: [{
        name: '码率',
        type: 'line' as const,
        data: metrics.value.map((m) => m.bitrate_kbps),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#00c853', width: 2 },
        areaStyle: { color: 'rgba(0,200,83,0.08)' },
      }],
    }
  }
  if (activeTab.value === 'pcr') {
    return {
      ...commonAxis,
      yAxis: { type: 'value' as const, name: 'ms', axisLabel: { color: '#90caf9', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e293b' } } },
      series: [{
        name: 'PCR抖动',
        type: 'line' as const,
        data: metrics.value.map((m) => m.pcr_jitter_ms),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#ffd600', width: 2 },
      }],
    }
  }
  if (activeTab.value === 'audio') {
    return {
      ...commonAxis,
      yAxis: { type: 'value' as const, name: 'RMS', axisLabel: { color: '#90caf9', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e293b' } } },
      series: [{
        name: '音频RMS',
        type: 'line' as const,
        data: metrics.value.map((m) => m.audio_rms.toFixed(4)),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#ab47bc', width: 2 },
      }],
    }
  }
  return {
    ...commonAxis,
    yAxis: { type: 'value' as const, name: '次/秒', axisLabel: { color: '#90caf9', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e293b' } } },
    series: [{
      name: 'CC错误',
      type: 'bar' as const,
      data: metrics.value.map((m) => m.cc_errors_per_sec),
      itemStyle: { color: '#ef5350' },
    }],
  }
})
</script>

<style scoped>
.metrics-chart {
  display: flex;
  flex-direction: column;
  height: 300px;
  background: #0f172a;
  border-radius: 8px;
  padding: 12px;
}
.chart-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.tab-btn {
  padding: 4px 12px;
  border-radius: 4px;
  border: 1px solid #334155;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}
.tab-btn.active {
  background: #1e40af;
  color: #fff;
  border-color: #2563eb;
}
.echart {
  flex: 1;
}
.no-data {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #475569;
  font-size: 14px;
}
</style>
