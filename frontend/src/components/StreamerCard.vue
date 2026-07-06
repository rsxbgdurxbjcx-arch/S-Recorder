<script setup>
defineProps({ streamer: Object })
const emit = defineEmits(['toggle-auto', 'start', 'stop', 'remove'])
</script>

<template>
  <div class="bg-card rounded-2xl border border-border p-4 shadow-sm transition-shadow hover:shadow-md">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <h3 class="font-semibold text-base truncate">{{ streamer.username }}</h3>
          <span
            class="shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium"
            :class="streamer.is_recording ? 'bg-red-100 text-red-700' : (streamer.is_online ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600')"
          >
            <span class="w-1.5 h-1.5 rounded-full mr-1" :class="streamer.is_recording ? 'bg-red-500 animate-pulse' : (streamer.is_online ? 'bg-green-500' : 'bg-gray-400')"></span>
            {{ streamer.is_recording ? '录制中' : streamer.status }}
          </span>
        </div>
        <p class="text-xs text-muted-foreground mt-1">{{ streamer.viewers }} 观众</p>
      </div>
      <button
        @click="emit('remove', streamer.username)"
        class="text-muted-foreground hover:text-danger p-1"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
      </button>
    </div>

    <div class="flex items-center gap-3 mt-4">
      <label class="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none">
        <input
          type="checkbox"
          :checked="streamer.auto_record"
          @change="emit('toggle-auto', streamer.username, $event.target.checked)"
          class="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary"
        />
        自动录制
      </label>
    </div>

    <div class="flex gap-2 mt-4">
      <button
        v-if="!streamer.is_recording"
        @click="emit('start', streamer.username)"
        :disabled="!streamer.is_recordable"
        class="flex-1 bg-primary text-primary-foreground py-2 rounded-xl text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98] transition-transform"
      >
        开始录制
      </button>
      <button
        v-else
        @click="emit('stop', streamer.username)"
        class="flex-1 bg-danger text-white py-2 rounded-xl text-sm font-medium active:scale-[0.98] transition-transform"
      >
        停止录制
      </button>
    </div>
  </div>
</template>
