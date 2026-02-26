import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import type { ChannelStatus, ChannelStatusValue, OverviewStats } from '@/types'

export const useChannelsStore = defineStore('channels', () => {
  const channels = ref<Map<string, ChannelStatus>>(new Map())
  const loading = ref(false)
  const lastUpdate = ref(0)

  const channelList = computed(() =>
    Array.from(channels.value.values()).sort((a, b) => a.sort_order - b.sort_order)
  )

  const stats = computed<OverviewStats>(() => {
    const s = { NORMAL: 0, WARNING: 0, ALARM: 0, OFFLINE: 0, total: 0 }
    for (const ch of channels.value.values()) {
      const k = ch.status as ChannelStatusValue
      if (k in s) s[k]++
      s.total++
    }
    return s
  })

  async function fetchChannels() {
    loading.value = true
    try {
      const { data } = await axios.get<ChannelStatus[]>('/api/v1/channels')
      const map = new Map<string, ChannelStatus>()
      for (const ch of data) {
        map.set(ch.channel_id, ch)
      }
      channels.value = map
      lastUpdate.value = Date.now()
    } finally {
      loading.value = false
    }
  }

  function updateChannel(update: Partial<ChannelStatus> & { channel_id: string }) {
    const existing = channels.value.get(update.channel_id)
    if (existing) {
      channels.value.set(update.channel_id, { ...existing, ...update })
    } else {
      channels.value.set(update.channel_id, update as ChannelStatus)
    }
    lastUpdate.value = Date.now()
  }

  function batchUpdate(updates: ChannelStatus[]) {
    for (const ch of updates) {
      const existing = channels.value.get(ch.channel_id)
      if (existing) {
        channels.value.set(ch.channel_id, { ...existing, ...ch })
      } else {
        channels.value.set(ch.channel_id, ch)
      }
    }
    lastUpdate.value = Date.now()
  }

  return {
    channels,
    channelList,
    stats,
    loading,
    lastUpdate,
    fetchChannels,
    updateChannel,
    batchUpdate,
  }
})
