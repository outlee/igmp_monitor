import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import type { Alert } from '@/types'

export const useAlertsStore = defineStore('alerts', () => {
  const alerts = ref<Alert[]>([])
  const loading = ref(false)

  const activeAlerts = computed(() =>
    alerts.value.filter((a) => a.status === 'ACTIVE')
  )

  async function fetchAlerts(status?: string) {
    loading.value = true
    try {
      const params: Record<string, string> = { limit: '200' }
      if (status) params.status = status
      const { data } = await axios.get<Alert[]>('/api/v1/alerts', { params })
      alerts.value = data
    } finally {
      loading.value = false
    }
  }

  function addAlert(alert: Alert) {
    const idx = alerts.value.findIndex((a) => a.id === alert.id)
    if (idx === -1) {
      alerts.value.unshift(alert)
      if (alerts.value.length > 500) {
        alerts.value.splice(500)
      }
    }
  }

  async function ackAlert(alertId: number) {
    await axios.post(`/api/v1/alerts/${alertId}/ack`)
    const a = alerts.value.find((a) => a.id === alertId)
    if (a) a.status = 'ACKNOWLEDGED'
  }

  function resolveAlert(alertId: number) {
    const a = alerts.value.find((a) => a.id === alertId)
    if (a) a.status = 'RESOLVED'
  }

  return {
    alerts,
    activeAlerts,
    loading,
    fetchAlerts,
    addAlert,
    ackAlert,
    resolveAlert,
  }
})
