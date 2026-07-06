<script setup>
import { ref, inject, onMounted } from 'vue'
import { api } from '../composables/api.js'

const toast = inject('toast')
const settings = ref({})
const loading = ref(false)
const saving = ref(false)
const themeColor = ref('#111827')

const languages = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en-US', label: 'English' }
]

async function load() {
  loading.value = true
  try {
    settings.value = await api.getSettings()
    // 从当前主题变量读取
    const root = getComputedStyle(document.documentElement)
    const current = root.getPropertyValue('--color-primary').trim()
    if (current && current !== 'var(--color-primary)') {
      themeColor.value = rgbToHex(current) || '#111827'
    }
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    loading.value = false
  }
}

function rgbToHex(rgb) {
  const m = rgb.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (!m) return null
  return '#' + [m[1], m[2], m[3]].map(x => parseInt(x).toString(16).padStart(2, '0')).join('')
}

function validateDuration(v) {
  return /^\d{1,2}:\d{2}:\d{2}$/.test(v)
}

async function save() {
  if (!validateDuration(settings.value.slice_duration)) {
    toast('切片时长格式必须为 00:00:00', 'error')
    return
  }
  saving.value = true
  try {
    await api.saveSettings(settings.value)
    applyTheme(themeColor.value)
    toast('设置已保存', 'success')
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    saving.value = false
  }
}

function applyTheme(color) {
  document.documentElement.style.setProperty('--color-primary', color)
  const r = parseInt(color.slice(1, 3), 16)
  const g = parseInt(color.slice(3, 5), 16)
  const b = parseInt(color.slice(5, 7), 16)
  const brightness = (r * 299 + g * 587 + b * 114) / 1000
  document.documentElement.style.setProperty('--color-primary-foreground', brightness > 128 ? '#111827' : '#ffffff')
}

onMounted(load)
</script>

<template>
  <div class="p-4 max-w-3xl mx-auto pb-28">
    <header class="mb-5">
      <h1 class="text-xl font-bold">设置</h1>
      <p class="text-sm text-muted-foreground">配置录制器参数</p>
    </header>

    <div v-if="loading" class="text-center text-muted-foreground py-20">加载中...</div>

    <div v-else class="bg-card rounded-2xl border border-border p-4 shadow-sm space-y-5">
      <!-- Output directory -->
      <div>
        <label class="block text-sm font-medium mb-1.5">录制输出目录</label>
        <input
          v-model="settings.output_dir"
          type="text"
          class="w-full border border-border rounded-xl px-3 py-2.5 text-sm"
        />
      </div>

      <!-- Poll interval -->
      <div>
        <label class="block text-sm font-medium mb-1.5">轮询间隔（秒）</label>
        <input
          v-model.number="settings.poll_interval_secs"
          type="number"
          min="5"
          class="w-full border border-border rounded-xl px-3 py-2.5 text-sm"
        />
      </div>

      <!-- Slice duration -->
      <div>
        <label class="block text-sm font-medium mb-1.5">视频切片时长（00:00:00 表示不切片）</label>
        <input
          v-model="settings.slice_duration"
          type="text"
          placeholder="00:00:00"
          class="w-full border border-border rounded-xl px-3 py-2.5 text-sm font-mono"
        />
        <p class="text-xs text-muted-foreground mt-1">格式：时:分:秒。设置后录制将按此时长自动切片，录制结束后自动合并。</p>
      </div>

      <!-- Merge format -->
      <div>
        <label class="block text-sm font-medium mb-1.5">合并格式</label>
        <select v-model="settings.merge_format" class="w-full border border-border rounded-xl px-3 py-2.5 text-sm bg-white">
          <option value="mp4">MP4</option>
          <option value="mkv">MKV</option>
          <option value="mov">MOV</option>
        </select>
      </div>

      <!-- Max concurrent -->
      <div>
        <label class="block text-sm font-medium mb-1.5">最大并发录制数（0 表示不限制）</label>
        <input
          v-model.number="settings.max_concurrent"
          type="number"
          min="0"
          class="w-full border border-border rounded-xl px-3 py-2.5 text-sm"
        />
      </div>

      <!-- Max tmp dir -->
      <div>
        <label class="block text-sm font-medium mb-1.5">临时目录大小上限（GB）</label>
        <input
          v-model.number="settings.max_tmp_dir_gb"
          type="number"
          min="1"
          step="0.1"
          class="w-full border border-border rounded-xl px-3 py-2.5 text-sm"
        />
      </div>

      <!-- Auto record -->
      <div class="flex items-center justify-between">
        <div>
          <div class="text-sm font-medium">默认自动录制</div>
          <div class="text-xs text-muted-foreground">新添加主播默认开启自动录制</div>
        </div>
        <label class="relative inline-flex items-center cursor-pointer">
          <input type="checkbox" v-model="settings.auto_record" class="sr-only peer">
          <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
        </label>
      </div>

      <!-- Theme color -->
      <div>
        <label class="block text-sm font-medium mb-1.5">主题色</label>
        <div class="flex items-center gap-3">
          <input
            v-model="themeColor"
            type="color"
            class="w-12 h-10 rounded-lg border border-border bg-white p-1"
          />
          <span class="text-sm text-muted-foreground font-mono">{{ themeColor }}</span>
        </div>
      </div>

      <!-- Language -->
      <div>
        <label class="block text-sm font-medium mb-1.5">语言</label>
        <select v-model="settings.language" class="w-full border border-border rounded-xl px-3 py-2.5 text-sm bg-white">
          <option v-for="l in languages" :key="l.value" :value="l.value">{{ l.label }}</option>
        </select>
      </div>

      <!-- Server port (display only) -->
      <div>
        <label class="block text-sm font-medium mb-1.5">服务端口</label>
        <input
          v-model.number="settings.server_port"
          type="number"
          disabled
          class="w-full border border-border rounded-xl px-3 py-2.5 text-sm bg-muted"
        />
      </div>

      <button
        @click="save"
        :disabled="saving"
        class="w-full bg-primary text-primary-foreground py-3 rounded-xl text-sm font-medium active:scale-[0.98] transition-transform disabled:opacity-50"
      >
        {{ saving ? '保存中...' : '保存设置' }}
      </button>
    </div>
  </div>
</template>
