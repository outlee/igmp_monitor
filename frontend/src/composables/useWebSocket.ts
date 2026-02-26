import { ref, onUnmounted } from 'vue'
import type { WSMessage } from '@/types'

type MessageHandler = (msg: WSMessage) => void

const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/realtime`

export function useWebSocket(onMessage: MessageHandler) {
  const connected = ref(false)
  let ws: WebSocket | null = null
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let retryDelay = 1000
  let destroyed = false

  function connect() {
    if (destroyed) return
    try {
      ws = new WebSocket(WS_URL)

      ws.onopen = () => {
        connected.value = true
        retryDelay = 1000
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as WSMessage
          onMessage(msg)
        } catch {
          // ignore parse errors
        }
      }

      ws.onclose = () => {
        connected.value = false
        ws = null
        if (!destroyed) {
          retryTimer = setTimeout(() => {
            retryDelay = Math.min(retryDelay * 2, 30000)
            connect()
          }, retryDelay)
        }
      }

      ws.onerror = () => {
        ws?.close()
      }
    } catch {
      if (!destroyed) {
        retryTimer = setTimeout(connect, retryDelay)
        retryDelay = Math.min(retryDelay * 2, 30000)
      }
    }
  }

  function disconnect() {
    destroyed = true
    if (retryTimer) clearTimeout(retryTimer)
    ws?.close()
    ws = null
  }

  connect()
  onUnmounted(disconnect)

  return { connected }
}
