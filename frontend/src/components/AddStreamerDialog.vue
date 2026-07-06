<script setup>
import { ref, inject, onMounted } from 'vue'

const emit = defineEmits(['close', 'added'])
const toast = inject('toast')
const input = ref('')
const loading = ref(false)

onMounted(() => {
  document.getElementById('streamer-input')?.focus()
})

async function submit() {
  if (!input.value.trim()) return
  loading.value = true
  try {
    const res = await fetch('/api/streamers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input: input.value })
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '添加失败')
    const addedCount = data.added?.length || 0
    const failedCount = data.failed?.length || 0
    if (addedCount > 0) toast(`成功添加 ${addedCount} 位主播`, 'success')
    if (failedCount > 0) toast(`${failedCount} 位主播添加失败`, 'error')
    emit('added')
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 p-4" @click.self="emit('close')">
    <div class="bg-white rounded-t-3xl sm:rounded-3xl w-full max-w-md p-5 shadow-2xl">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-bold">添加主播</h2>
        <button @click="emit('close')" class="text-muted-foreground">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <p class="text-sm text-muted-foreground mb-3">
        支持主播ID、直播间完整链接，或批量输入（英文逗号分隔）。
      </p>
      <textarea
        id="streamer-input"
        v-model="input"
        rows="4"
        placeholder="例如：Only_KiraRi 或 https://stripchat.com/Only_KiraRi"
        class="w-full border border-border rounded-xl p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none"
      ></textarea>
      <button
        @click="submit"
        :disabled="loading || !input.trim()"
        class="w-full mt-4 bg-primary text-primary-foreground py-3 rounded-xl text-sm font-medium disabled:opacity-40 active:scale-[0.98] transition-transform"
      >
        {{ loading ? '添加中...' : '添加' }}
      </button>
    </div>
  </div>
</template>
