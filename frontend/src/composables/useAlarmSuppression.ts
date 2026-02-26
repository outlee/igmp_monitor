import { ref } from 'vue'
import type { Alert } from '@/types'
import { ALERT_TYPE_LABELS } from '@/types'

const SUPPRESSION_WINDOW_MS = 5 * 60 * 1000
const AGGREGATION_THRESHOLD = 5
const AGGREGATION_WINDOW_MS = 10 * 1000

export function useAlarmSuppression() {
  const suppressionMap = new Map<string, number>()
  const pendingAlerts = ref<Alert[]>([])
  let aggregationTimer: ReturnType<typeof setTimeout> | null = null
  let ttsEnabled = ref(true)

  function shouldSuppress(channelId: string, alertType: string): boolean {
    const key = `${channelId}:${alertType}`
    const expiry = suppressionMap.get(key)
    if (expiry && Date.now() < expiry) return true
    suppressionMap.set(key, Date.now() + SUPPRESSION_WINDOW_MS)
    return false
  }

  function addAlert(alert: Alert) {
    if (!ttsEnabled.value) return
    if (shouldSuppress(alert.channel_id, alert.alert_type)) return

    pendingAlerts.value.push(alert)

    if (aggregationTimer) clearTimeout(aggregationTimer)

    if (pendingAlerts.value.length >= AGGREGATION_THRESHOLD) {
      flushAlerts()
      return
    }

    aggregationTimer = setTimeout(flushAlerts, AGGREGATION_WINDOW_MS)
  }

  function flushAlerts() {
    if (aggregationTimer) {
      clearTimeout(aggregationTimer)
      aggregationTimer = null
    }
    const alerts = [...pendingAlerts.value]
    pendingAlerts.value = []

    if (alerts.length === 0) return

    if (alerts.length >= AGGREGATION_THRESHOLD) {
      speak(`警告：${alerts.length}路节目同时异常，上游网络疑似中断，请立即检查`)
    } else {
      for (const a of alerts) {
        const label = ALERT_TYPE_LABELS[a.alert_type] || a.alert_type
        const name = a.channel_name || a.channel_id
        speak(`${name}发生${label}告警`)
      }
    }
  }

  function speak(text: string) {
    if (!ttsEnabled.value) return
    if (!window.speechSynthesis) return
    window.speechSynthesis.cancel()
    const utter = new SpeechSynthesisUtterance(text)
    utter.lang = 'zh-CN'
    utter.rate = 1.1
    utter.volume = 1.0
    window.speechSynthesis.speak(utter)
  }

  function testSpeak() {
    speak('语音告警测试，系统运行正常')
  }

  function clearSuppression() {
    suppressionMap.clear()
  }

  return {
    addAlert,
    speak,
    testSpeak,
    ttsEnabled,
    clearSuppression,
  }
}
