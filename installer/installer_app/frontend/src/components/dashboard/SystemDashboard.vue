<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useSystemStore } from '@/stores/system'
import { useDeploymentStore } from '@/stores/deployment'
import { useBuildStore } from '@/stores/build'
import ComponentStatus from './ComponentStatus.vue'

const systemStore = useSystemStore()
const deploymentStore = useDeploymentStore()
const buildStore = useBuildStore()

const refreshInterval = ref(null)
const lastUpdated = ref(new Date())

// System metrics
const systemMetrics = ref({
  cpu: {
    usage: 45,
    cores: 8,
    load: [1.2, 1.5, 1.8]
  },
  memory: {
    used: 6.2,
    total: 16,
    usage: 39
  },
  disk: {
    used: 120,
    total: 500,
    usage: 24
  },
  network: {
    inbound: 2.5,
    outbound: 1.8
  }
})

// Deployment overview
const deploymentOverview = ref({
  total: 3,
  active: 2,
  failed: 1,
  pending: 0
})

// Build overview
const buildOverview = ref({
  total: 12,
  successful: 9,
  failed: 2,
  running: 1
})

// Recent activities
const recentActivities = ref([
  {
    id: 1,
    type: 'deployment',
    action: 'Deployment completed',
    target: 'openjourney-production',
    timestamp: '2024-07-19T14:30:00Z',
    status: 'success'
  },
  {
    id: 2,
    type: 'build',
    action: 'Build started',
    target: 'AMD64 Installer',
    timestamp: '2024-07-19T14:25:00Z',
    status: 'info'
  },
  {
    id: 3,
    type: 'system',
    action: 'High memory usage detected',
    target: 'System Monitor',
    timestamp: '2024-07-19T14:20:00Z',
    status: 'warning'
  },
  {
    id: 4,
    type: 'deployment',
    action: 'Deployment failed',
    target: 'openjourney-staging',
    timestamp: '2024-07-19T14:15:00Z',
    status: 'error'
  }
])

// System components
const systemComponents = ref([
  {
    id: 'openjourney-server',
    name: 'OpenJourney Server',
    status: 'healthy',
    uptime: '5d 12h 30m',
    version: '1.2.3',
    cpu: 15,
    memory: 512
  },
  {
    id: 'postgresql',
    name: 'PostgreSQL Database',
    status: 'healthy',
    uptime: '5d 12h 30m',
    version: '15.4',
    cpu: 8,
    memory: 2048
  },
  {
    id: 'redis',
    name: 'Redis Cache',
    status: 'healthy',
    uptime: '5d 12h 30m',
    version: '7.0.12',
    cpu: 2,
    memory: 256
  },
  {
    id: 'nginx',
    name: 'Nginx Proxy',
    status: 'warning',
    uptime: '2d 8h 15m',
    version: '1.24.0',
    cpu: 3,
    memory: 128
  }
])

const systemHealth = computed(() => {
  const healthyComponents = systemComponents.value.filter(c => c.status === 'healthy').length
  const totalComponents = systemComponents.value.length
  const healthPercentage = (healthyComponents / totalComponents) * 100
  
  if (healthPercentage >= 90) return { status: 'excellent', color: 'green', label: 'Excellent' }
  if (healthPercentage >= 75) return { status: 'good', color: 'blue', label: 'Good' }
  if (healthPercentage >= 50) return { status: 'fair', color: 'yellow', label: 'Fair' }
  return { status: 'poor', color: 'red', label: 'Poor' }
})

const getActivityIcon = (type) => {
  switch (type) {
    case 'deployment': return '🚀'
    case 'build': return '🔨'
    case 'system': return '⚙️'
    default: return '📋'
  }
}

const getActivityStatusClass = (status) => {
  switch (status) {
    case 'success': return 'text-green-600 bg-green-50'
    case 'error': return 'text-red-600 bg-red-50'
    case 'warning': return 'text-yellow-600 bg-yellow-50'
    default: return 'text-blue-600 bg-blue-50'
  }
}

const formatTimestamp = (timestamp) => {
  return new Date(timestamp).toLocaleString()
}

const formatUptime = (uptime) => {
  return uptime
}

const refreshData = async () => {
  try {
    // Simulate data refresh
    systemMetrics.value.cpu.usage = Math.floor(Math.random() * 100)
    systemMetrics.value.memory.usage = Math.floor(Math.random() * 100)
    systemMetrics.value.disk.usage = Math.floor(Math.random() * 100)
    
    lastUpdated.value = new Date()
  } catch (error) {
    console.error('Failed to refresh dashboard data:', error)
  }
}

onMounted(() => {
  // Initial data load
  refreshData()
  
  // Set up auto-refresh every 30 seconds
  refreshInterval.value = setInterval(refreshData, 30000)
})

onUnmounted(() => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value)
  }
})
</script>

<template>
  <div class="system-dashboard">
    <!-- Dashboard Header -->
    <div class="mb-8">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-3xl font-bold text-gray-900 mb-2">System Dashboard</h1>
          <p class="text-gray-600">
            Monitor system health, deployments, and build status in real-time.
          </p>
        </div>
        <div class="text-right">
          <div class="text-sm text-gray-500">Last updated</div>
          <div class="text-sm font-medium text-gray-900">
            {{ formatTimestamp(lastUpdated) }}
          </div>
        </div>
      </div>
    </div>

    <!-- System Health Overview -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
      <div class="card p-6 text-center">
        <div class="text-3xl mb-2" :class="`text-${systemHealth.color}-600`">
          {{ systemHealth.status === 'excellent' ? '💚' : 
             systemHealth.status === 'good' ? '💙' :
             systemHealth.status === 'fair' ? '💛' : '❤️' }}
        </div>
        <div class="text-lg font-semibold text-gray-900 mb-1">{{ systemHealth.label }}</div>
        <div class="text-sm text-gray-600">System Health</div>
      </div>
      
      <div class="card p-6 text-center">
        <div class="text-3xl font-bold text-blue-600 mb-2">{{ deploymentOverview.active }}</div>
        <div class="text-sm text-gray-600">Active Deployments</div>
      </div>
      
      <div class="card p-6 text-center">
        <div class="text-3xl font-bold text-green-600 mb-2">{{ buildOverview.running }}</div>
        <div class="text-sm text-gray-600">Running Builds</div>
      </div>
      
      <div class="card p-6 text-center">
        <div class="text-3xl font-bold text-purple-600 mb-2">{{ systemComponents.length }}</div>
        <div class="text-sm text-gray-600">System Components</div>
      </div>
    </div>

    <!-- System Metrics -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
      <!-- CPU Usage -->
      <div class="card p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">CPU Usage</h3>
        <div class="flex items-center justify-between mb-2">
          <span class="text-2xl font-bold text-blue-600">{{ systemMetrics.cpu.usage }}%</span>
          <span class="text-sm text-gray-600">{{ systemMetrics.cpu.cores }} cores</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-3 mb-4">
          <div 
            class="bg-blue-600 h-3 rounded-full transition-all duration-500"
            :style="{ width: `${systemMetrics.cpu.usage}%` }"
          ></div>
        </div>
        <div class="text-sm text-gray-600">
          Load: {{ systemMetrics.cpu.load.join(', ') }}
        </div>
      </div>

      <!-- Memory Usage -->
      <div class="card p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Memory Usage</h3>
        <div class="flex items-center justify-between mb-2">
          <span class="text-2xl font-bold text-green-600">{{ systemMetrics.memory.usage }}%</span>
          <span class="text-sm text-gray-600">{{ systemMetrics.memory.used }}GB / {{ systemMetrics.memory.total }}GB</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-3 mb-4">
          <div 
            class="bg-green-600 h-3 rounded-full transition-all duration-500"
            :style="{ width: `${systemMetrics.memory.usage}%` }"
          ></div>
        </div>
        <div class="text-sm text-gray-600">
          Available: {{ (systemMetrics.memory.total - systemMetrics.memory.used).toFixed(1) }}GB
        </div>
      </div>

      <!-- Disk Usage -->
      <div class="card p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Disk Usage</h3>
        <div class="flex items-center justify-between mb-2">
          <span class="text-2xl font-bold text-purple-600">{{ systemMetrics.disk.usage }}%</span>
          <span class="text-sm text-gray-600">{{ systemMetrics.disk.used }}GB / {{ systemMetrics.disk.total }}GB</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-3 mb-4">
          <div 
            class="bg-purple-600 h-3 rounded-full transition-all duration-500"
            :style="{ width: `${systemMetrics.disk.usage}%` }"
          ></div>
        </div>
        <div class="text-sm text-gray-600">
          Free: {{ systemMetrics.disk.total - systemMetrics.disk.used }}GB
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <!-- System Components -->
      <div class="card">
        <div class="p-6 border-b border-gray-200">
          <h2 class="text-xl font-semibold text-gray-900">System Components</h2>
        </div>
        <div class="p-6">
          <ComponentStatus :components="systemComponents" />
        </div>
      </div>

      <!-- Recent Activities -->
      <div class="card">
        <div class="p-6 border-b border-gray-200">
          <h2 class="text-xl font-semibold text-gray-900">Recent Activities</h2>
        </div>
        <div class="p-6">
          <div class="space-y-4">
            <div
              v-for="activity in recentActivities"
              :key="activity.id"
              class="flex items-start space-x-3"
            >
              <div class="flex-shrink-0 text-lg">
                {{ getActivityIcon(activity.type) }}
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between">
                  <p class="text-sm font-medium text-gray-900">
                    {{ activity.action }}
                  </p>
                  <span 
                    class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
                    :class="getActivityStatusClass(activity.status)"
                  >
                    {{ activity.status }}
                  </span>
                </div>
                <p class="text-sm text-gray-600">{{ activity.target }}</p>
                <p class="text-xs text-gray-500">{{ formatTimestamp(activity.timestamp) }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  @apply bg-white border border-gray-200 rounded-lg shadow-sm;
}
</style>