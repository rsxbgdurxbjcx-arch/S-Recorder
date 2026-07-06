<script setup>
import { ref, inject, onMounted, onUnmounted } from 'vue'
import StreamerCard from '../components/StreamerCard.vue'
import AddStreamerDialog from '../components/AddStreamerDialog.vue'
import { api, onEvent } from '../composables/api.js'

const toast = inject('toast')
const streamers = ref([])
const loading = ref(false)
const showAdd = ref(false)
let pollTimer = null

async function load() {
  loading.value = true
  try {
    streamers.value = await api.listStreamers()
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    loading.value = false
  }
}

function updateStreamer(username, patch) {
  const idx = streamers.value.findIndex(s => s.username === username)
  if (idx >= 0) {
    streamers.value[idx] = { ...streamers.value[idx], ...patch }
  }
}

async function handleToggleAuto(username, enabled) {
  try {
    await api.setAutoRecord(username, enabled)
    updateStreamer(username, { auto_record: enabled })
    toast('自动录制已' + (enabled ? '开启' : '关闭'), 'success')
  } catch (e) {
    toast(e.message, 'error')
  }
}

async function handleStart(username) {
  try {
    await api.startRecording(username)
    updateStreamer(username, { is_recording: true })
    toast(`开始录制 ${username}`, 'success')
  } catch (e) {
    toast(e.message, 'error')
  }
}

async function handleStop(username) {
  try {
    await api.stopRecording(username)
    updateStreamer(username, { is_recording: false })
    toast(`已停止录制 ${username}`, 'info')
  } catch (e) {
    toast(e.message, 'error')
  }
}

async function handleRemove(username) {
  if (!confirm(`确定删除主播 ${username}？`)) return
  try {
    await api.removeStreamer(username)
    streamers.value = streamers.value.filter(s => s.username !== username)
    toast('已删除', 'success')
  } catch (e) {
    toast(e.message, 'error')
  }
}

onMounted(() => {
  load()
  pollTimer = setInterval(load, 5000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="p-4 max-w-3xl mx-auto">
    <header class="flex items-center justify-between mb-5">
      <div>
        <h1 class="text-xl font-bold">主播列表</h1>
        <p class="text-sm text-muted-foreground">
          共 {{ streamers.length }} 位主播，{{ streamers.filter(s => s.is_recording).length }} 位录制中
        </p>
      </div>
      <button
        @click="showAdd = true"
        class="bg-primary text-primary-foreground px-4 py-2 rounded-xl text-sm font-medium active:scale-95 transition-transform"
      >
        + 添加主播
      </button>
    </header>

    <div v-if="loading && streamers.length === 0" class="text-center text-muted-foreground py-20">
      加载中...
    </div>

    <div v-else-if="streamers.length === 0" class="text-center py-20">
      <p class="text-muted-foreground mb-4">暂无主播，请先添加</p>
      <button
        @click="showAdd = true"
        class="bg-primary text-primary-foreground px-5 py-2 rounded-xl text-sm font-medium"
      >
        添加主播
      </button>
    </div>

    <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <StreamerCard
        v-for="s in streamers"
        :key="s.username"
        :streamer="s"
        @toggle-auto="handleToggleAuto"
        @start="handleStart"
        @stop="handleStop"
        @remove="handleRemove"
      />
    </div>

    <AddStreamerDialog
      v-if="showAdd"
      @close="showAdd = false"
      @added="showAdd = false; load()"
    />
  </div>
</template>
