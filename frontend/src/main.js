import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './assets/style.css'

import StreamersView from './views/StreamersView.vue'
import RecordingsView from './views/RecordingsView.vue'
import PostprocessView from './views/PostprocessView.vue'
import SettingsView from './views/SettingsView.vue'

const routes = [
  { path: '/', redirect: '/streamers' },
  { path: '/streamers', component: StreamersView },
  { path: '/recordings', component: RecordingsView },
  { path: '/postprocess', component: PostprocessView },
  { path: '/settings', component: SettingsView }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

createApp(App).use(router).mount('#app')
