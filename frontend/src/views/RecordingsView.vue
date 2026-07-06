<script setup>
import { ref, inject, onMounted, onUnmounted, computed } from 'vue'
import { api } from '../composables/api.js'

const toast = inject('toast')
const files = ref([])
const tasks = ref({})
const loading = ref(false)
const diskSpace = ref(null)
let pollTimer = null

async function load() {
  loading.value = true
  try {
    const [f, t, d] = await Promise.all([
      api.listRecordings(),
      api.getPostprocessTasks().catch(() => ({})),
      api.getDiskSpace().catch(() => null)
    ])
    files.value = f
    tasks.value = t
    diskSpace.value = d
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    loading.value = false
  }
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  const units = ['KiB', 'MiB', 'GiB', 'TiB']
  let size = bytes / 1024
  for (const unit of units) {
    if (size < 1024) return size.toFixed(2) + ' ' + unit
    size /= 1024
  }
  return size.toFixed(2) + ' PiB'
}

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return '-'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function formatDate(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

function statusText(f) {
  if (f.is_recording) return '录制中'
  const task = tasks.value[f.path]
  if (task?.status === 'running') return `后处理中 ${task.pct?.toFixed?.(0) || 0}%`
  if (task?.status === 'waiting') return '等待后处理'
  if (f.status === 'pp_error') return '后处理失败'
  if (f.status === 'merging') return '合并中'
  return '完成'
}

function statusClass(f) {
  if (f.is_recording) return 'bg-red-100 text-red-700'
  const task = tasks.value[f.path]
  if (task?.status === 'running' || task?.status === 'waiting') return 'bg-amber-100 text-amber-700'
  if (f.status === 'pp_error') return 'bg-red-100 text-red-700'
  if (f.status === 'merging') return 'bg-blue-100 text-blue-700'
  return 'bg-green-100 text-green-700'
}

async function deleteFile(f) {
  if (!confirm(`确定删除 ${f.name}？`)) return
  try {
    await api.deleteRecording(f.path)
    files.value = files.value.filter(item => item.path !== f.path)
    toast('已删除', 'success')
  } catch (e) {
    toast(e.message, 'error')
  }
}

async function runPP(f) {
  try {
    await api.runPostprocess(f.path)
    toast('已开始后处理', 'success')
  } catch (e) {
    toast(e.message, 'error')
  }
}

async function cancelPP(f) {
  try {
    await api.cancelPostprocess(f.path)
    toast('已取消后处理', 'info')
  } catch (e) {
    toast(e.message, 'error')
  }
}

const diskUsagePct = computed(() => {
  if (!diskSpace.value) return 0
  return Math.round((diskSpace.value.used_bytes / diskSpace.value.total_bytes) * 100)
})

onMounted(() => {
  load()
  pollTimer = setInterval(load, 3000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="p-4 max-w-3xl mx-auto">
    <header class="mb-5">
      <h1 class="text-xl font-bold">录制文件</h1>
      <p class="text-sm text-muted-foreground">
        共 {{ files.length }} 个文件
      </p>
    </header>

    <!-- Disk space -->
    <div v-if="diskSpace" class="bg-card rounded-2xl border border-border p-4 mb-4 shadow-sm">
      <div class="flex items-center justify-between text-sm mb-2">
        <span class="font-medium">磁盘空间</span>
        <span class="text-muted-foreground">{{ formatSize(diskSpace.available_bytes) }} 可用 / {{ formatSize(diskSpace.total_bytes) }} 总计</span>
      </div>
      <div class="h-2 bg-muted rounded-full overflow-hidden">
        <div class="h-full bg-primary rounded-full transition-all" :style="{ width: diskUsagePct + '%' }"></div>
      </div>
    </div>

    <div v-if="loading && files.length === 0" class="text-center text-muted-foreground py-20">
      加载中...
    </div>

    <div v-else-if="files.length === 0" class="text-center py-20 text-muted-foreground">
      暂无录制文件
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="f in files"
        :key="f.path"
        class="bg-card rounded-2xl border border-border p-4 shadow-sm"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <h3 class="font-medium text-sm truncate">{{ f.name }}</h3>
            <p class="text-xs text-muted-foreground mt-1">{{ formatDate(f.started_at) }}</p>
            <div class="flex items-center gap-2 mt-2">
              <span class="text-xs px-2 py-0.5 rounded-full font-medium" :class="statusClass(f)">
                {{ statusText(f) }}
              </span>
              <span class="text-xs text-muted-foreground">{{ formatSize(f.size_bytes) }}</span>
              <span v-if="f.video_duration_secs" class="text-xs text-muted-foreground">{{ formatDuration(f.video_duration_secs) }}</span>
              <span v-else-if="f.record_duration_secs" class="text-xs text-muted-foreground">已录 {{ formatDuration(f.record_duration_secs) }}</span>
            </div>
          </div>
          <div class="flex flex-col gap-1">
            <button
              v-if="!f.is_recording && (!tasks[f.path] || tasks[f.path].status === 'done' || tasks[f.path].status === 'error')"
              @click="runPP(f)"
              class="text-xs bg-muted hover:bg-gray-200 px-3 py-1.5 rounded-lg"
            >
              后处理
            </button>
            <button
              v-if="tasks[f.path]?.status === 'running' || tasks[f.path]?.status === 'waiting'"
              @click="cancelPP(f)"
              class="text-xs bg-amber-100 text-amber-700 px-3 py-1.5 rounded-lg"
            >
              取消
            </button>
            <button
              @click="deleteFile(f)"
              class="text-xs text-danger hover:bg-red-50 px-3 py-1.5 rounded-lg"
            >
              删除
            </button>
          </div>
        </div>
        <div v-if="tasks[f.path]?.status === 'running'" class="mt-3">
          <div class="h-1.5 bg-muted rounded-full overflow-hidden">
            <div class="h-full bg-primary rounded-full transition-all" :style="{ width: (tasks[f.path].pct || 0) + '%' }"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
