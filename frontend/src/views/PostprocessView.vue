<script setup>
import { ref, inject, onMounted } from 'vue'
import { api } from '../composables/api.js'

const toast = inject('toast')
const modules = ref([])
const pipeline = ref({ nodes: [] })
const loading = ref(false)
const selectedModule = ref('')
const draggedNode = ref(null)

async function load() {
  loading.value = true
  try {
    const [m, p] = await Promise.all([api.listModules(), api.getPipeline()])
    modules.value = m
    pipeline.value = p
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    loading.value = false
  }
}

function findModule(id) {
  return modules.value.find(m => m.id === id)
}

function addNode() {
  if (!selectedModule.value) return
  const mod = findModule(selectedModule.value)
  const params = {}
  if (mod?.params) {
    mod.params.forEach(p => {
      params[p.key] = p.default || ''
    })
  }
  pipeline.value.nodes.push({
    nodeId: `node-${Date.now()}`,
    moduleId: mod.id,
    params,
    enabled: true
  })
  selectedModule.value = ''
}

function removeNode(index) {
  pipeline.value.nodes.splice(index, 1)
}

function moveNode(index, dir) {
  const newIndex = index + dir
  if (newIndex < 0 || newIndex >= pipeline.value.nodes.length) return
  const nodes = [...pipeline.value.nodes]
  const temp = nodes[index]
  nodes[index] = nodes[newIndex]
  nodes[newIndex] = temp
  pipeline.value.nodes = nodes
}

async function savePipeline() {
  try {
    await api.savePipeline(pipeline.value)
    toast('流水线已保存', 'success')
  } catch (e) {
    toast(e.message, 'error')
  }
}

onMounted(load)
</script>

<template>
  <div class="p-4 max-w-3xl mx-auto pb-28">
    <header class="mb-5">
      <h1 class="text-xl font-bold">后处理</h1>
      <p class="text-sm text-muted-foreground">配置录制完成后的自动化流水线</p>
    </header>

    <!-- Available modules -->
    <section class="bg-card rounded-2xl border border-border p-4 mb-4 shadow-sm">
      <h2 class="font-semibold text-sm mb-3">可用模块</h2>
      <div v-if="modules.length === 0" class="text-sm text-muted-foreground">
        未发现后处理模块，请确保 modules 目录存在可执行模块。
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="m in modules"
          :key="m.id"
          class="flex items-center justify-between p-3 bg-muted rounded-xl"
        >
          <div>
            <div class="font-medium text-sm">{{ m.name }}</div>
            <div class="text-xs text-muted-foreground">{{ m.description }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Pipeline builder -->
    <section class="bg-card rounded-2xl border border-border p-4 shadow-sm">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-semibold text-sm">处理流水线</h2>
        <button
          @click="savePipeline"
          class="bg-primary text-primary-foreground px-4 py-1.5 rounded-lg text-sm font-medium active:scale-95 transition-transform"
        >
          保存
        </button>
      </div>

      <div class="flex gap-2 mb-4">
        <select
          v-model="selectedModule"
          class="flex-1 border border-border rounded-xl px-3 py-2 text-sm bg-white"
        >
          <option value="">选择模块</option>
          <option v-for="m in modules" :key="m.id" :value="m.id">{{ m.name }}</option>
        </select>
        <button
          @click="addNode"
          :disabled="!selectedModule"
          class="bg-primary text-primary-foreground px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-40"
        >
          添加
        </button>
      </div>

      <div v-if="pipeline.nodes.length === 0" class="text-center py-8 text-muted-foreground text-sm">
        暂无节点，请添加模块
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="(node, idx) in pipeline.nodes"
          :key="node.nodeId"
          class="border border-border rounded-xl p-3"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="flex items-center gap-2 min-w-0">
              <span class="text-xs font-mono text-muted-foreground">#{{ idx + 1 }}</span>
              <div>
                <div class="font-medium text-sm truncate">{{ findModule(node.moduleId)?.name || node.moduleId }}</div>
                <div class="text-xs text-muted-foreground">{{ findModule(node.moduleId)?.description || '' }}</div>
              </div>
            </div>
            <div class="flex items-center gap-1 shrink-0">
              <button @click="moveNode(idx, -1)" :disabled="idx === 0" class="p-1 text-muted-foreground disabled:opacity-30">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" /></svg>
              </button>
              <button @click="moveNode(idx, 1)" :disabled="idx === pipeline.nodes.length - 1" class="p-1 text-muted-foreground disabled:opacity-30">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
              </button>
              <button @click="removeNode(idx)" class="p-1 text-danger">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
          </div>

          <div class="mt-3 grid grid-cols-1 gap-2" v-if="findModule(node.moduleId)?.params?.length">
            <div v-for="param in findModule(node.moduleId).params" :key="param.key" class="flex flex-col">
              <label class="text-xs text-muted-foreground mb-1">{{ param.label || param.name || param.key }}</label>
              <input
                v-model="node.params[param.key]"
                :type="param.type === 'number' ? 'number' : 'text'"
                :placeholder="param.description || ''"
                class="border border-border rounded-lg px-3 py-1.5 text-sm"
              />
            </div>
          </div>

          <div class="mt-2 flex items-center gap-2">
            <input
              type="checkbox"
              :id="`enabled-${node.nodeId}`"
              v-model="node.enabled"
              class="w-4 h-4 rounded border-gray-300 text-primary"
            />
            <label :for="`enabled-${node.nodeId}`" class="text-sm">启用该节点</label>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
