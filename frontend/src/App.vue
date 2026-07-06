<script setup>
import { ref, provide, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import BottomNav from './components/BottomNav.vue'
import { connectEvents } from './composables/api.js'

const route = useRoute()
const toasts = ref([])
let toastId = 0

function toast(message, type = 'info') {
  const id = ++toastId
  toasts.value.push({ id, message, type })
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }, 3000)
}

provide('toast', toast)

onMounted(() => {
  connectEvents()
})
</script>

<template>
  <div class="flex flex-col h-full bg-white">
    <!-- Main content -->
    <main class="flex-1 overflow-y-auto pb-20">
      <router-view />
    </main>

    <!-- Bottom Navigation -->
    <BottomNav :active="route.path" />

    <!-- Toast container -->
    <div class="fixed top-4 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2 pointer-events-none">
      <transition-group name="toast">
        <div
          v-for="t in toasts"
          :key="t.id"
          class="px-4 py-2.5 rounded-full text-sm font-medium shadow-lg pointer-events-auto min-w-[200px] text-center"
          :class="{
            'bg-gray-900 text-white': t.type === 'info',
            'bg-green-600 text-white': t.type === 'success',
            'bg-red-500 text-white': t.type === 'error',
            'bg-amber-500 text-white': t.type === 'warning'
          }"
        >
          {{ t.message }}
        </div>
      </transition-group>
    </div>
  </div>
</template>
