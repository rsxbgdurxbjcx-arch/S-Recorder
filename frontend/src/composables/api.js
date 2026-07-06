const API_BASE = ''

async function request(method, path, body) {
  const url = `${API_BASE}${path}`
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json'
    }
  }
  if (body !== undefined) {
    options.body = JSON.stringify(body)
  }
  const res = await fetch(url, options)
  const text = await res.text()
  let data
  try {
    data = JSON.parse(text)
  } catch {
    data = text
  }
  if (!res.ok) {
    throw new Error(data?.detail || data || `HTTP ${res.status}`)
  }
  return data
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  delete: (path) => request('DELETE', path),

  // streamers
  listStreamers: () => api.get('/api/streamers'),
  addStreamers: (input) => api.post('/api/streamers', { input }),
  removeStreamer: (name) => api.delete(`/api/streamers/${encodeURIComponent(name)}`),
  setAutoRecord: (name, enabled) => api.post(`/api/streamers/${encodeURIComponent(name)}/auto-record`, { enabled }),
  startRecording: (name) => api.post(`/api/streamers/${encodeURIComponent(name)}/start`),
  stopRecording: (name) => api.post(`/api/streamers/${encodeURIComponent(name)}/stop`),
  verifyStreamer: (name) => api.get(`/api/streamers/${encodeURIComponent(name)}/verify`),

  // recordings
  listRecordings: () => api.get('/api/recordings'),
  deleteRecording: (path) => api.post('/api/recordings/delete', { path }),
  runPostprocess: (path) => api.post('/api/recordings/postprocess', { path }),
  cancelPostprocess: (path) => api.post('/api/recordings/postprocess-cancel', { path }),

  // settings
  getSettings: () => api.get('/api/settings'),
  saveSettings: (settings) => api.post('/api/settings', settings),
  getDiskSpace: () => api.get('/api/disk-space'),

  // postprocess
  listModules: () => api.get('/api/modules'),
  getPipeline: () => api.get('/api/pipeline'),
  savePipeline: (pipeline) => api.post('/api/pipeline', pipeline),
  getPostprocessTasks: () => api.get('/api/postprocess-tasks')
}

let eventSource = null
const listeners = new Map()

export function connectEvents() {
  if (eventSource) return
  eventSource = new EventSource('/api/events')
  eventSource.onmessage = (e) => {
    try {
      const { event, payload } = JSON.parse(e.data)
      const cbs = listeners.get(event)
      if (cbs) cbs.forEach(cb => cb(payload))
    } catch {}
  }
  eventSource.onerror = () => {
    eventSource.close()
    eventSource = null
    setTimeout(connectEvents, 3000)
  }
}

export function onEvent(event, cb) {
  if (!listeners.has(event)) listeners.set(event, new Set())
  listeners.get(event).add(cb)
  return () => listeners.get(event).delete(cb)
}
