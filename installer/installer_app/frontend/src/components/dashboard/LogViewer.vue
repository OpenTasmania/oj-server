<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useApi } from '@/composables/useApi'

const props = defineProps({
  source: {
    type: String,
    default: 'system' // system, deployment, build
  },
  autoRefresh: {
    type: Boolean,
    default: true
  },
  maxLogs: {
    type: Number,
    default: 1000
  }
})

const emit = defineEmits(['log-selected', 'export-complete'])

// State
const logs = ref([])
const filteredLogs = ref([])
const isLoading = ref(false)
const isConnected = ref(false)
const searchQuery = ref('')
const selectedLogLevel = ref('all')
const selectedTimeRange = ref('1h')
const selectedComponent = ref('all')
const showTimestamps = ref(true)
const autoScroll = ref(true)
const selectedLog = ref(null)
const isExporting = ref(false)

// WebSocket for real-time logs
const { isConnected: wsConnected, messages, send } = useWebSocket(
  `ws://localhost:5000/ws/logs/${props.source}`
)

// API composable
const { get, post } = useApi()

// Log levels with colors
const logLevels = [
  { value: 'all', label: 'All Levels', color: 'gray' },
  { value: 'debug', label: 'Debug', color: 'blue' },
  { value: 'info', label: 'Info', color: 'green' },
  { value: 'warning', label: 'Warning', color: 'yellow' },
  { value: 'error', label: 'Error', color: 'red' },
  { value: 'critical', label: 'Critical', color: 'purple' }
]

// Time ranges
const timeRanges = [
  { value: '15m', label: 'Last 15 minutes' },
  { value: '1h', label: 'Last hour' },
  { value: '6h', label: 'Last 6 hours' },
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
  { value: 'all', label: 'All time' }
]

// Available components (would be fetched from API)
const components = ref([
  { value: 'all', label: 'All Components' },
  { value: 'deployment', label: 'Deployment Service' },
  { value: 'build', label: 'Build Service' },
  { value: 'system', label: 'System' },
  { value: 'api', label: 'API Server' },
  { value: 'websocket', label: 'WebSocket Server' }
])

// Computed properties
const filteredAndSearchedLogs = computed(() => {
  let filtered = logs.value

  // Filter by log level
  if (selectedLogLevel.value !== 'all') {
    filtered = filtered.filter(log => log.level === selectedLogLevel.value)
  }

  // Filter by component
  if (selectedComponent.value !== 'all') {
    filtered = filtered.filter(log => log.component === selectedComponent.value)
  }

  // Filter by time range
  if (selectedTimeRange.value !== 'all') {
    const now = new Date()
    const timeLimit = getTimeLimit(selectedTimeRange.value)
    filtered = filtered.filter(log => new Date(log.timestamp) >= timeLimit)
  }

  // Search filter
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(log => 
      log.message.toLowerCase().includes(query) ||
      log.component.toLowerCase().includes(query) ||
      (log.context && JSON.stringify(log.context).toLowerCase().includes(query))
    )
  }

  return filtered.slice(-props.maxLogs)
})

const logStats = computed(() => {
  const stats = {
    total: filteredAndSearchedLogs.value.length,
    debug: 0,
    info: 0,
    warning: 0,
    error: 0,
    critical: 0
  }

  filteredAndSearchedLogs.value.forEach(log => {
    if (stats.hasOwnProperty(log.level)) {
      stats[log.level]++
    }
  })

  return stats
})

// Methods
const getTimeLimit = (range) => {
  const now = new Date()
  switch (range) {
    case '15m': return new Date(now - 15 * 60 * 1000)
    case '1h': return new Date(now - 60 * 60 * 1000)
    case '6h': return new Date(now - 6 * 60 * 60 * 1000)
    case '24h': return new Date(now - 24 * 60 * 60 * 1000)
    case '7d': return new Date(now - 7 * 24 * 60 * 60 * 1000)
    default: return new Date(0)
  }
}

const getLevelColor = (level) => {
  const levelConfig = logLevels.find(l => l.value === level)
  return levelConfig ? levelConfig.color : 'gray'
}

const formatTimestamp = (timestamp) => {
  return new Date(timestamp).toLocaleString()
}

const loadLogs = async () => {
  isLoading.value = true
  try {
    const params = {
      source: props.source,
      level: selectedLogLevel.value !== 'all' ? selectedLogLevel.value : undefined,
      component: selectedComponent.value !== 'all' ? selectedComponent.value : undefined,
      timeRange: selectedTimeRange.value,
      limit: props.maxLogs
    }

    const response = await get('/api/v1/logs', { params })
    logs.value = response.data.logs || []
  } catch (error) {
    console.error('Failed to load logs:', error)
  } finally {
    isLoading.value = false
  }
}

const clearLogs = () => {
  logs.value = []
  selectedLog.value = null
}

const selectLog = (log) => {
  selectedLog.value = log
  emit('log-selected', log)
}

const exportLogs = async (format = 'json') => {
  isExporting.value = true
  try {
    const exportData = {
      logs: filteredAndSearchedLogs.value,
      filters: {
        level: selectedLogLevel.value,
        component: selectedComponent.value,
        timeRange: selectedTimeRange.value,
        search: searchQuery.value
      },
      exportedAt: new Date().toISOString(),
      source: props.source
    }

    let content, filename, mimeType

    switch (format) {
      case 'json':
        content = JSON.stringify(exportData, null, 2)
        filename = `logs-${props.source}-${Date.now()}.json`
        mimeType = 'application/json'
        break
      case 'csv':
        content = convertToCSV(filteredAndSearchedLogs.value)
        filename = `logs-${props.source}-${Date.now()}.csv`
        mimeType = 'text/csv'
        break
      case 'txt':
        content = filteredAndSearchedLogs.value
          .map(log => `[${log.timestamp}] ${log.level.toUpperCase()} ${log.component}: ${log.message}`)
          .join('\n')
        filename = `logs-${props.source}-${Date.now()}.txt`
        mimeType = 'text/plain'
        break
    }

    // Create and download file
    const blob = new Blob([content], { type: mimeType })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    emit('export-complete', { format, filename, count: filteredAndSearchedLogs.value.length })
  } catch (error) {
    console.error('Failed to export logs:', error)
  } finally {
    isExporting.value = false
  }
}

const convertToCSV = (logs) => {
  const headers = ['timestamp', 'level', 'component', 'message', 'context']
  const rows = logs.map(log => [
    log.timestamp,
    log.level,
    log.component,
    log.message.replace(/"/g, '""'), // Escape quotes
    log.context ? JSON.stringify(log.context).replace(/"/g, '""') : ''
  ])

  return [
    headers.join(','),
    ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
  ].join('\n')
}

const scrollToBottom = () => {
  const container = document.querySelector('.log-container')
  if (container) {
    container.scrollTop = container.scrollHeight
  }
}

// Watch for new WebSocket messages
watch(messages, (newMessages) => {
  if (newMessages.length > 0) {
    const latestMessage = newMessages[newMessages.length - 1]
    if (latestMessage.type === 'log') {
      logs.value.push(latestMessage.data)
      
      // Limit logs to maxLogs
      if (logs.value.length > props.maxLogs) {
        logs.value = logs.value.slice(-props.maxLogs)
      }

      // Auto-scroll if enabled
      if (autoScroll.value) {
        setTimeout(scrollToBottom, 100)
      }
    }
  }
}, { deep: true })

// Watch for filter changes to reload logs
watch([selectedLogLevel, selectedComponent, selectedTimeRange], () => {
  if (!props.autoRefresh) return
  loadLogs()
})

// Lifecycle
onMounted(() => {
  loadLogs()
  isConnected.value = wsConnected.value
})

onUnmounted(() => {
  // Cleanup if needed
})
</script>

<template>
  <div class="log-viewer bg-white rounded-lg shadow-sm border">
    <!-- Header with controls -->
    <div class="border-b border-gray-200 p-4">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-medium text-gray-900">
          Log Viewer - {{ props.source }}
        </h3>
        <div class="flex items-center space-x-2">
          <!-- Connection status -->
          <div class="flex items-center space-x-2">
            <div :class="[
              'w-2 h-2 rounded-full',
              wsConnected ? 'bg-green-500' : 'bg-red-500'
            ]"></div>
            <span class="text-sm text-gray-600">
              {{ wsConnected ? 'Live' : 'Disconnected' }}
            </span>
          </div>
          
          <!-- Export dropdown -->
          <div class="relative">
            <select 
              @change="exportLogs($event.target.value)"
              class="text-sm border border-gray-300 rounded-md px-3 py-1"
              :disabled="isExporting"
            >
              <option value="">Export...</option>
              <option value="json">JSON</option>
              <option value="csv">CSV</option>
              <option value="txt">Text</option>
            </select>
          </div>
          
          <!-- Clear logs -->
          <button
            @click="clearLogs"
            class="text-sm bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded-md"
          >
            Clear
          </button>
        </div>
      </div>

      <!-- Filters -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
        <!-- Search -->
        <div>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search logs..."
            class="w-full text-sm border border-gray-300 rounded-md px-3 py-2"
          />
        </div>

        <!-- Log level filter -->
        <div>
          <select
            v-model="selectedLogLevel"
            class="w-full text-sm border border-gray-300 rounded-md px-3 py-2"
          >
            <option v-for="level in logLevels" :key="level.value" :value="level.value">
              {{ level.label }}
            </option>
          </select>
        </div>

        <!-- Component filter -->
        <div>
          <select
            v-model="selectedComponent"
            class="w-full text-sm border border-gray-300 rounded-md px-3 py-2"
          >
            <option v-for="component in components" :key="component.value" :value="component.value">
              {{ component.label }}
            </option>
          </select>
        </div>

        <!-- Time range filter -->
        <div>
          <select
            v-model="selectedTimeRange"
            class="w-full text-sm border border-gray-300 rounded-md px-3 py-2"
          >
            <option v-for="range in timeRanges" :key="range.value" :value="range.value">
              {{ range.label }}
            </option>
          </select>
        </div>
      </div>

      <!-- Stats and options -->
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-4 text-sm text-gray-600">
          <span>Total: {{ logStats.total }}</span>
          <span v-if="logStats.error > 0" class="text-red-600">
            Errors: {{ logStats.error }}
          </span>
          <span v-if="logStats.warning > 0" class="text-yellow-600">
            Warnings: {{ logStats.warning }}
          </span>
        </div>
        
        <div class="flex items-center space-x-4">
          <label class="flex items-center text-sm">
            <input
              v-model="showTimestamps"
              type="checkbox"
              class="mr-2"
            />
            Show timestamps
          </label>
          <label class="flex items-center text-sm">
            <input
              v-model="autoScroll"
              type="checkbox"
              class="mr-2"
            />
            Auto-scroll
          </label>
        </div>
      </div>
    </div>

    <!-- Log content -->
    <div class="log-container h-96 overflow-y-auto p-4 bg-gray-50 font-mono text-sm">
      <div v-if="isLoading" class="flex items-center justify-center h-full">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
      
      <div v-else-if="filteredAndSearchedLogs.length === 0" class="flex items-center justify-center h-full text-gray-500">
        No logs found matching the current filters
      </div>
      
      <div v-else class="space-y-1">
        <div
          v-for="log in filteredAndSearchedLogs"
          :key="log.id || `${log.timestamp}-${log.message}`"
          @click="selectLog(log)"
          :class="[
            'log-entry p-2 rounded cursor-pointer hover:bg-white transition-colors',
            selectedLog?.id === log.id ? 'bg-blue-50 border border-blue-200' : 'hover:bg-white'
          ]"
        >
          <div class="flex items-start space-x-2">
            <!-- Level indicator -->
            <div :class="[
              'w-2 h-2 rounded-full mt-2 flex-shrink-0',
              `bg-${getLevelColor(log.level)}-500`
            ]"></div>
            
            <!-- Log content -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center space-x-2 mb-1">
                <span v-if="showTimestamps" class="text-gray-500 text-xs">
                  {{ formatTimestamp(log.timestamp) }}
                </span>
                <span :class="[
                  'text-xs px-2 py-1 rounded uppercase font-medium',
                  `bg-${getLevelColor(log.level)}-100 text-${getLevelColor(log.level)}-800`
                ]">
                  {{ log.level }}
                </span>
                <span class="text-gray-600 text-xs">{{ log.component }}</span>
              </div>
              
              <div class="text-gray-900 break-words">
                {{ log.message }}
              </div>
              
              <!-- Context data -->
              <div v-if="log.context && Object.keys(log.context).length > 0" class="mt-1">
                <details class="text-xs">
                  <summary class="cursor-pointer text-gray-500 hover:text-gray-700">
                    Context
                  </summary>
                  <pre class="mt-1 p-2 bg-gray-100 rounded text-xs overflow-x-auto">{{ JSON.stringify(log.context, null, 2) }}</pre>
                </details>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.log-container {
  scrollbar-width: thin;
  scrollbar-color: #cbd5e0 #f7fafc;
}

.log-container::-webkit-scrollbar {
  width: 6px;
}

.log-container::-webkit-scrollbar-track {
  background: #f7fafc;
}

.log-container::-webkit-scrollbar-thumb {
  background: #cbd5e0;
  border-radius: 3px;
}

.log-container::-webkit-scrollbar-thumb:hover {
  background: #a0aec0;
}

.log-entry {
  border-left: 3px solid transparent;
}

.log-entry:hover {
  border-left-color: #e2e8f0;
}
</style>