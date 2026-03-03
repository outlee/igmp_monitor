<template>
  <div class="channel-manager">
    <div class="cm-header">
      <h2>📋 频道管理</h2>
      <div class="cm-actions">
        <button v-if="sortChanged" class="btn-success" @click="saveSortOrder">💾 保存排序</button>
        <button class="btn-secondary" @click="exportCsv">📤 导出CSV</button>
        <button class="btn-primary" @click="openAdd">+ 新增频道</button>
        <button class="btn-secondary" @click="showImport = true">📥 批量导入CSV</button>
        <button class="btn-default" @click="refresh" :disabled="loading">
          {{ loading ? '加载中...' : '↻ 刷新' }}
        </button>
      </div>
    </div>

    <div class="cm-table-wrap">
      <table class="cm-table">
        <thead>
          <tr>
            <th style="width:36px"><input type="checkbox" :checked="allSelected" @change="toggleAll" /></th>
            <th style="width:28px"></th>
            <th class="sortable-th" @click="sortBy('id')">ID {{ sortIcon('id') }}</th>
            <th class="sortable-th" @click="sortBy('name')">频道名称 {{ sortIcon('name') }}</th>
            <th>组播地址</th>
            <th class="sortable-th" @click="sortBy('group_name')">分组 {{ sortIcon('group_name') }}</th>
            <th class="sortable-th" @click="sortBy('sort_order')">排序 {{ sortIcon('sort_order') }}</th>
            <th>期望码率</th>
            <th class="sortable-th" @click="sortBy('enabled')">状态 {{ sortIcon('enabled') }}</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(ch, index) in displayChannels"
            :key="ch.id"
            :class="{ disabled: !ch.enabled, 'drag-over': dragOverIndex === index }"
            draggable="true"
            @dragstart="onDragStart(index)"
            @dragover="onDragOver($event, index)"
            @drop="onDrop(index)"
            @dragend="onDragEnd"
          >
            <td><input type="checkbox" :checked="selectedIds.has(ch.id)" @change="toggleSelect(ch.id)" /></td>
            <td class="drag-handle">☰</td>
            <td class="channel-id">{{ ch.id }}</td>
            <td>{{ ch.name }}</td>
            <td class="mono">{{ ch.multicast_ip }}:{{ ch.multicast_port }}</td>
            <td>{{ ch.group_name }}</td>
            <td>{{ ch.sort_order }}</td>
            <td>{{ ch.expected_bitrate_kbps.toFixed(1) }} kbps</td>
            <td>
              <span :class="['status-badge', ch.enabled ? 'enabled' : 'disabled']">
                {{ ch.enabled ? '启用' : '禁用' }}
              </span>
            </td>
            <td class="action-col">
              <button class="btn-sm btn-toggle" @click="toggleEnable(ch)">
                {{ ch.enabled ? '禁用' : '启用' }}
              </button>
              <button class="btn-sm btn-edit" @click="openEdit(ch)">编辑</button>
              <button class="btn-sm btn-delete" @click="confirmDelete(ch)">删除</button>
            </td>
          </tr>
          <tr v-if="!channels.length">
            <td colspan="10" class="empty-cell">
              {{ loading ? '加载中...' : '暂无频道数据' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新增/编辑 弹窗 -->
    <Teleport to="body">
      <div v-if="showForm" class="modal-overlay" @click.self="closeForm">
        <div class="modal-box">
          <h3>{{ isEdit ? '编辑频道' : '新增频道' }}</h3>
          <form @submit.prevent="submitForm">
            <div class="form-row">
              <label>频道名称</label>
              <input v-model="form.name" class="sim-input" placeholder="例如：CCTV-1" />
            </div>
            <div class="form-row">
              <label>组播IP</label>
              <input v-model="form.multicast_ip" class="sim-input" placeholder="239.x.x.x" />
            </div>
            <div class="form-row">
              <label>端口</label>
              <input v-model.number="form.multicast_port" type="number" class="sim-input" placeholder="1234" />
            </div>
            <div class="form-row">
              <label>分组</label>
              <input v-model="form.group_name" class="sim-input" placeholder="default" />
            </div>
            <div class="form-row">
              <label>排序</label>
              <input v-model.number="form.sort_order" type="number" class="sim-input" placeholder="0" />
            </div>
            <div class="form-row">
              <label>期望码率(kbps)</label>
              <input v-model.number="form.expected_bitrate_kbps" type="number" step="0.1" class="sim-input" placeholder="5000" />
            </div>
            <div class="form-row">
              <label>状态</label>
              <label class="checkbox-label">
                <input v-model="form.enabled" type="checkbox" />
                <span>启用</span>
              </label>
            </div>
            <div v-if="formError" class="form-error">{{ formError }}</div>
            <div class="modal-actions">
              <button type="submit" class="btn-primary" :disabled="submitting">
                {{ submitting ? '保存中...' : '保存' }}
              </button>
              <button type="button" class="btn-default" @click="closeForm">取消</button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <!-- 批量导入 弹窗 -->
    <Teleport to="body">
      <div v-if="showImport" class="modal-overlay" @click.self="closeImport">
        <div class="modal-box modal-lg">
          <h3>📥 批量导入CSV</h3>
          <p class="import-hint">
            每行格式：<code>频道名,组播IP,端口,分组</code>（分组可省略，默认为default）<br>
            示例：CCTV-1,239.1.1.1,1234,央视
          </p>
          <textarea v-model="csvText" class="csv-textarea" rows="12" placeholder="CCTV-1,239.1.1.1,1234,央视
湖南卫视,239.1.1.2,1234,卫视"></textarea>
          <div v-if="importResult" class="import-result" :class="{ error: importResult.failed > 0 }">
            <div>成功: {{ importResult.success }} 条</div>
            <div v-if="importResult.failed > 0">失败: {{ importResult.failed }} 条</div>
            <ul v-if="importResult.errors.length" class="error-list">
              <li v-for="(err, idx) in importResult.errors.slice(0, 10)" :key="idx">{{ err }}</li>
              <li v-if="importResult.errors.length > 10">...还有 {{ importResult.errors.length - 10 }} 条错误</li>
            </ul>
          </div>
          <div class="modal-actions">
            <button class="btn-primary" @click="doImport" :disabled="importing || !csvText.trim()">
              {{ importing ? '导入中...' : '导入' }}
            </button>
            <button class="btn-default" @click="closeImport">关闭</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 删除确认 弹窗 -->
    <Teleport to="body">
      <div v-if="deleteTarget" class="modal-overlay">
        <div class="modal-box modal-sm">
          <h3>⚠️ 确认删除</h3>
          <p class="confirm-text">
            确认删除频道 <strong>{{ deleteTarget.name }}</strong> ({{ deleteTarget.id }})？<br>
            此操作不可恢复。
          </p>
          <div class="modal-actions">
            <button class="btn-danger" @click="doDelete" :disabled="deleting">
              {{ deleting ? '删除中...' : '确认删除' }}
            </button>
            <button class="btn-default" @click="deleteTarget = null">取消</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import axios from 'axios'
import { useChannelsStore } from '@/stores/channels'

interface ChannelManageItem {
  id: string
  name: string
  multicast_ip: string
  multicast_port: number
  group_name: string
  sort_order: number
  enabled: boolean
  expected_bitrate_kbps: number
}

interface BatchImportResult {
  success: number
  failed: number
  errors: string[]
}

const channels = ref<ChannelManageItem[]>([])
const loading = ref(false)
const showForm = ref(false)
const isEdit = ref(false)
const editingId = ref('')
const submitting = ref(false)
const formError = ref('')
const showImport = ref(false)
const csvText = ref('')
const importing = ref(false)
const importResult = ref<BatchImportResult | null>(null)
const deleteTarget = ref<ChannelManageItem | null>(null)
const deleting = ref(false)

const selectedIds = ref<Set<string>>(new Set())
const sortKey = ref<string>('')
const sortDir = ref<'asc' | 'desc'>('asc')
const sortChanged = ref(false)
const dragSrcIndex = ref<number>(-1)
const dragOverIndex = ref<number>(-1)

const channelsStore = useChannelsStore()

const allSelected = computed(() =>
  channels.value.length > 0 && channels.value.every(ch => selectedIds.value.has(ch.id))
)

const displayChannels = computed(() => {
  const list = [...channels.value]
  if (!sortKey.value) return list
  list.sort((a, b) => {
    const av = (a as any)[sortKey.value]
    const bv = (b as any)[sortKey.value]
    if (av < bv) return sortDir.value === 'asc' ? -1 : 1
    if (av > bv) return sortDir.value === 'asc' ? 1 : -1
    return 0
  })
  return list
})

const form = reactive({
  name: '',
  multicast_ip: '',
  multicast_port: 1234,
  group_name: 'default',
  sort_order: 0,
  enabled: true,
  expected_bitrate_kbps: 0,
})

// IP validation helpers
function ipToNum(ip: string): number {
  return ip.split('.').reduce((acc, p) => (acc << 8) | parseInt(p), 0) >>> 0
}

const MCAST_MIN = ipToNum('224.0.0.0')
const MCAST_MAX = ipToNum('239.255.255.255')

function isValidMulticastIp(ip: string): boolean {
  const parts = ip.split('.').map(Number)
  if (parts.length !== 4 || parts.some(isNaN) || parts.some(p => p < 0 || p > 255)) {
    return false
  }
  const n = ipToNum(ip)
  return n >= MCAST_MIN && n <= MCAST_MAX
}

function validateForm(): string | null {
  if (!form.name.trim()) return '频道名称不能为空'
  if (!isValidMulticastIp(form.multicast_ip)) return '组播IP须在 224.0.0.0 ~ 239.255.255.255 范围内'
  if (form.multicast_port < 1 || form.multicast_port > 65535) return '端口须在 1~65535 范围内'
  return null
}

async function refresh() {
  loading.value = true
  try {
    const { data } = await axios.get<ChannelManageItem[]>('/api/v1/channels/manage')
    channels.value = data
  } finally {
    loading.value = false
  }
}

function openAdd() {
  isEdit.value = false
  editingId.value = ''
  Object.assign(form, {
    name: '',
    multicast_ip: '',
    multicast_port: 1234,
    group_name: 'default',
    sort_order: 0,
    enabled: true,
    expected_bitrate_kbps: 0,
  })
  formError.value = ''
  showForm.value = true
}

function openEdit(ch: ChannelManageItem) {
  isEdit.value = true
  editingId.value = ch.id
  Object.assign(form, {
    name: ch.name,
    multicast_ip: ch.multicast_ip,
    multicast_port: ch.multicast_port,
    group_name: ch.group_name,
    sort_order: ch.sort_order,
    enabled: ch.enabled,
    expected_bitrate_kbps: ch.expected_bitrate_kbps,
  })
  formError.value = ''
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  formError.value = ''
}

async function submitForm() {
  const err = validateForm()
  if (err) {
    formError.value = err
    return
  }
  submitting.value = true
  formError.value = ''
  try {
    if (isEdit.value) {
      await axios.put(`/api/v1/channels/${editingId.value}`, form)
    } else {
      await axios.post('/api/v1/channels', form)
    }
    closeForm()
    await refresh()
    await channelsStore.fetchChannels()
  } catch (e: any) {
    formError.value = e.response?.data?.detail || '操作失败'
  } finally {
    submitting.value = false
  }
}

async function toggleEnable(ch: ChannelManageItem) {
  try {
    await axios.post(`/api/v1/channels/${ch.id}/enable?enabled=${!ch.enabled}`)
    await refresh()
    await channelsStore.fetchChannels()
  } catch (e: any) {
    alert(e.response?.data?.detail || '操作失败')
  }
}

function confirmDelete(ch: ChannelManageItem) {
  deleteTarget.value = ch
}

async function doDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await axios.delete(`/api/v1/channels/${deleteTarget.value.id}`)
    deleteTarget.value = null
    await refresh()
    await channelsStore.fetchChannels()
  } catch (e: any) {
    alert(e.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = false
  }
}

function closeImport() {
  showImport.value = false
  csvText.value = ''
  importResult.value = null
}

async function doImport() {
  if (!csvText.value.trim()) return
  importing.value = true
  importResult.value = null
  try {
    const { data } = await axios.post<BatchImportResult>('/api/v1/channels/batch-import', {
      csv_text: csvText.value,
    })
    importResult.value = data
    if (data.success > 0) {
      await refresh()
      await channelsStore.fetchChannels()
    }
  } catch (e: any) {
    importResult.value = {
      success: 0,
      failed: 0,
      errors: [e.response?.data?.detail || '导入失败'],
    }
  } finally {
    importing.value = false
  }
}

function toggleAll() {
  if (allSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(channels.value.map(ch => ch.id))
  }
}

function toggleSelect(id: string) {
  const s = new Set(selectedIds.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  selectedIds.value = s
}

function sortBy(key: string) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

function sortIcon(key: string) {
  if (sortKey.value !== key) return '↕'
  return sortDir.value === 'asc' ? '↑' : '↓'
}

function onDragStart(index: number) {
  dragSrcIndex.value = index
}

function onDragOver(event: DragEvent, index: number) {
  event.preventDefault()
  dragOverIndex.value = index
}

function onDrop(index: number) {
  if (dragSrcIndex.value === -1 || dragSrcIndex.value === index) return
  const list = [...channels.value]
  const [moved] = list.splice(dragSrcIndex.value, 1)
  list.splice(index, 0, moved)
  list.forEach((ch, i) => { ch.sort_order = (i + 1) * 10 })
  channels.value = list
  sortChanged.value = true
  sortKey.value = ''
  dragSrcIndex.value = -1
  dragOverIndex.value = -1
}

function onDragEnd() {
  dragSrcIndex.value = -1
  dragOverIndex.value = -1
}

async function saveSortOrder() {
  try {
    const orders = channels.value.map(ch => ({ id: ch.id, sort_order: ch.sort_order }))
    await axios.put('/api/v1/channels/batch-sort', { orders })
    sortChanged.value = false
    await channelsStore.fetchChannels()
  } catch (e: any) {
    alert(e.response?.data?.detail || '保存排序失败')
  }
}

function exportCsv() {
  const list = selectedIds.value.size > 0
    ? channels.value.filter(ch => selectedIds.value.has(ch.id))
    : channels.value
  const header = '频道名,组播IP,端口,分组,期望码率kbps,状态'
  const rows = list.map(ch =>
    `${ch.name},${ch.multicast_ip},${ch.multicast_port},${ch.group_name},${ch.expected_bitrate_kbps},${ch.enabled ? '启用' : '禁用'}`
  )
  const csv = '\uFEFF' + [header, ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'channels.csv'
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(refresh)
</script>

<style scoped>
.channel-manager {
  height: 100%;
  background: #0a0e1a;
  display: flex;
  flex-direction: column;
  padding: 20px;
}

.cm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.cm-header h2 {
  font-size: 18px;
  color: #f1f5f9;
  font-weight: 600;
}

.cm-actions {
  display: flex;
  gap: 10px;
}

.cm-table-wrap {
  flex: 1;
  overflow: auto;
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 10px;
}

.cm-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.cm-table th {
  background: #1e293b;
  color: #94a3b8;
  padding: 12px 16px;
  text-align: left;
  font-weight: 600;
  border-bottom: 1px solid #334155;
  position: sticky;
  top: 0;
  z-index: 1;
}

.cm-table td {
  padding: 12px 16px;
  border-bottom: 1px solid #1e293b;
  color: #cbd5e1;
}

.cm-table tbody tr:hover:not(.disabled) {
  background: #1e293b;
}

.cm-table tbody tr.disabled {
  opacity: 0.6;
}

.cm-table tbody tr.disabled td {
  color: #64748b;
}

.channel-id {
  font-family: 'Courier New', monospace;
  font-weight: 600;
  color: #93c5fd;
}

.mono {
  font-family: 'Courier New', monospace;
  color: #94a3b8;
}

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.status-badge.enabled {
  background: #052e16;
  color: #4ade80;
}

.status-badge.disabled {
  background: #1c1917;
  color: #64748b;
}

.action-col {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.empty-cell {
  text-align: center;
  padding: 48px;
  color: #64748b;
}

/* Buttons */
.btn-primary {
  background: #1e40af;
  border: none;
  color: #fff;
  border-radius: 6px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: background 0.2s;
}
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary {
  background: #0f172a;
  border: 1px solid #334155;
  color: #94a3b8;
  border-radius: 6px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.btn-secondary:hover:not(:disabled) { background: #1e293b; color: #e2e8f0; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-default {
  background: transparent;
  border: 1px solid #475569;
  color: #94a3b8;
  border-radius: 6px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.btn-default:hover:not(:disabled) { background: #1e293b; color: #e2e8f0; }
.btn-default:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-danger {
  background: #dc2626;
  border: none;
  color: #fff;
  border-radius: 6px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: background 0.2s;
}
.btn-danger:hover:not(:disabled) { background: #ef4444; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-success {
  background: #15803d;
  border: none;
  color: #fff;
  border-radius: 6px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: background 0.2s;
}
.btn-success:hover:not(:disabled) { background: #16a34a; }
.btn-success:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-sm {
  padding: 4px 10px;
  font-size: 11px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-toggle {
  background: #1e293b;
  color: #94a3b8;
}
.btn-toggle:hover { background: #334155; color: #e2e8f0; }

.btn-edit {
  background: #1e40af;
  color: #fff;
}
.btn-edit:hover { background: #2563eb; }

.btn-delete {
  background: #7f1d1d;
  color: #fca5a5;
}
.btn-delete:hover { background: #dc2626; color: #fff; }

/* Drag & Drop */
.drag-handle {
  cursor: grab;
  color: #475569;
  text-align: center;
  user-select: none;
}
.drag-handle:active { cursor: grabbing; }

.drag-over {
  outline: 2px dashed #3b82f6;
  background: #1e3a5f !important;
}

/* Sortable headers */
.sortable-th {
  cursor: pointer;
  user-select: none;
}
.sortable-th:hover {
  color: #e2e8f0;
  background: #263548;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.modal-box {
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 12px;
  padding: 24px;
  min-width: 480px;
  max-width: 560px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-lg {
  min-width: 600px;
  max-width: 700px;
}

.modal-sm {
  min-width: 360px;
  max-width: 420px;
}

.modal-box h3 {
  font-size: 16px;
  color: #f1f5f9;
  margin-bottom: 20px;
  font-weight: 600;
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

.sim-input {
  flex: 1;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 8px 12px;
  color: #e2e8f0;
  font-size: 13px;
  outline: none;
}
.sim-input:focus {
  border-color: #3b82f6;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: #1e40af;
}

.checkbox-label span {
  color: #e2e8f0;
  font-size: 13px;
}

.form-error {
  margin: 12px 0;
  padding: 10px 12px;
  background: #450a0a;
  color: #f87171;
  border: 1px solid #dc2626;
  border-radius: 6px;
  font-size: 13px;
}

.modal-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
  justify-content: flex-end;
}

/* Import modal */
.import-hint {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 12px;
  line-height: 1.6;
}

.import-hint code {
  background: #1e293b;
  padding: 2px 6px;
  border-radius: 4px;
  color: #93c5fd;
}

.csv-textarea {
  width: 100%;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 12px;
  color: #e2e8f0;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  resize: vertical;
  outline: none;
}
.csv-textarea:focus {
  border-color: #3b82f6;
}

.import-result {
  margin-top: 16px;
  padding: 12px;
  background: #052e16;
  border: 1px solid #16a34a;
  border-radius: 6px;
  font-size: 13px;
  color: #4ade80;
}

.import-result.error {
  background: #1c1917;
  border-color: #dc2626;
  color: #fca5a5;
}

.error-list {
  margin-top: 8px;
  padding-left: 16px;
  color: #f87171;
}

.error-list li {
  margin-bottom: 4px;
}

/* Delete confirm */
.confirm-text {
  font-size: 14px;
  color: #cbd5e1;
  line-height: 1.6;
}

.confirm-text strong {
  color: #f87171;
}
</style>
