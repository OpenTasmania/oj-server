<script setup>
import { ref, onMounted } from 'vue'

const systemStatus = ref({
  overall: 'healthy',
  uptime: '2h 34m',
  cpu: 45,
  memory: 62,
  disk: 78
})

const deployments = ref([
  {
    id: 1,
    name: 'Local Development',
    environment: 'local',
    status: 'running',
    components: ['server', 'web', 'api'],
    lastUpdated: '2 minutes ago'
  }
])

const recentBuilds = ref([
  {
    id: 1,
    type: 'Debian Package',
    architecture: 'amd64',
    status: 'completed',
    createdAt: '1 hour ago'
  }
])

const systemMetrics = ref({
  requests: 1247,
  errors: 3,
  responseTime: 145
})

const refreshData = async () => {
  // TODO: Replace with actual API calls
  console.log('Refreshing dashboard data...')
  
  // Simulate API call
  await new Promise(resolve => setTimeout(resolve, 1000))
  
  // Update with mock data
  systemStatus.value.uptime = Math.floor(Math.random() * 10) + 'h ' + Math.floor(Math.random() * 60) + 'm'
  systemStatus.value.cpu = Math.floor(Math.random() * 100)
  systemStatus.value.memory = Math.floor(Math.random() * 100)
  systemStatus.value.disk = Math.floor(Math.random() * 100)
}

const getStatusColor = (status) => {
  switch (status) {
    case 'healthy':
    case 'running':
    case 'completed':
      return 'success'
    case 'warning':
      return 'warning'
    case 'error':
    case 'failed':
      return 'error'
    default:
      return 'gray'
  }
}

const getMetricColor = (value, type) => {
  if (type === 'cpu' || type === 'memory' || type === 'disk') {
    if (value < 50) return 'success'
    if (value < 80) return 'warning'
    return 'error'
  }
  return 'primary'
}

onMounted(() => {
  // Auto-refresh every 30 seconds
  const interval = setInterval(refreshData, 30000)
  
  // Cleanup on unmount
  return () => clearInterval(interval)
})
</script>

<template>
  <div class="max-w-7xl mx-auto">
    <div class="mb-8 flex justify-between items-center">
      <div>
        <h1 class="text-3xl font-bold text-gray-900 mb-2">System Dashboard</h1>
        <p class="text-gray-600">
          Monitor your OpenJourney Server deployments and system health.
        </p>
      </div>
      <button @click="refreshData" class="btn btn-primary">
        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Refresh
      </button>
    </div>

    <!-- System Status Overview -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      <div class="card p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0">
            <div :class="`w-8 h-8 bg-${getStatusColor(systemStatus.overall)}-100 rounded-full flex items-center justify-center`">
              <div :class="`w-3 h-3 bg-${getStatusColor(systemStatus.overall)}-500 rounded-full`"></div>
            </div>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-500">System Status</p>
            <p class="text-2xl font-semibold text-gray-900 capitalize">{{ systemStatus.overall }}</p>
          </div>
        </div>
      </div>

      <div class="card p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0">
            <svg class="w-8 h-8 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-500">Uptime</p>
            <p class="text-2xl font-semibold text-gray-900">{{ systemStatus.uptime }}</p>
          </div>
        </div>
      </div>

      <div class="card p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0">
            <svg class="w-8 h-8 text-success-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-500">Active Deployments</p>
            <p class="text-2xl font-semibold text-gray-900">{{ deployments.length }}</p>
          </div>
        </div>
      </div>

      <div class="card p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0">
            <svg class="w-8 h-8 text-warning-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-500">Recent Builds</p>
            <p class="text-2xl font-semibold text-gray-900">{{ recentBuilds.length }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- System Metrics -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
      <div class="card p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">CPU Usage</h3>
        <div class="flex items-center">
          <div class="flex-1">
            <div class="w-full bg-gray-200 rounded-full h-3">
              <div 
                :class="`bg-${getMetricColor(systemStatus.cpu, 'cpu')}-500 h-3 rounded-full transition-all duration-300`"
                :style="`width: ${systemStatus.cpu}%`"
              ></div>
            </div>
          </div>
          <span class="ml-3 text-sm font-medium text-gray-900">{{ systemStatus.cpu }}%</span>
        </div>
      </div>

      <div class="card p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Memory Usage</h3>
        <div class="flex items-center">
          <div class="flex-1">
            <div class="w-full bg-gray-200 rounded-full h-3">
              <div 
                :class="`bg-${getMetricColor(systemStatus.memory, 'memory')}-500 h-3 rounded-full transition-all duration-300`"
                :style="`width: ${systemStatus.memory}%`"
              ></div>
            </div>
          </div>
          <span class="ml-3 text-sm font-medium text-gray-900">{{ systemStatus.memory }}%</span>
        </div>
      </div>

      <div class="card p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Disk Usage</h3>
        <div class="flex items-center">
          <div class="flex-1">
            <div class="w-full bg-gray-200 rounded-full h-3">
              <div 
                :class="`bg-${getMetricColor(systemStatus.disk, 'disk')}-500 h-3 rounded-full transition-all duration-300`"
                :style="`width: ${systemStatus.disk}%`"
              ></div>
            </div>
          </div>
          <span class="ml-3 text-sm font-medium text-gray-900">{{ systemStatus.disk }}%</span>
        </div>
      </div>
    </div>

    <!-- Active Deployments -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
      <div class="card p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Active Deployments</h3>
        <div class="space-y-4">
          <div v-for="deployment in deployments" :key="deployment.id" class="border border-gray-200 rounded-lg p-4">
            <div class="flex items-center justify-between mb-2">
              <h4 class="font-medium text-gray-900">{{ deployment.name }}</h4>
              <span :class="`px-2 py-1 text-xs font-medium rounded-full bg-${getStatusColor(deployment.status)}-100 text-${getStatusColor(deployment.status)}-800`">
                {{ deployment.status }}
              </span>
            </div>
            <p class="text-sm text-gray-600 mb-2">Environment: {{ deployment.environment }}</p>
            <p class="text-sm text-gray-600 mb-2">Components: {{ deployment.components.join(', ') }}</p>
            <p class="text-xs text-gray-500">Last updated: {{ deployment.lastUpdated }}</p>
          </div>
          <div v-if="deployments.length === 0" class="text-center py-8 text-gray-500">
            No active deployments
          </div>
        </div>
      </div>

      <div class="card p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Recent Builds</h3>
        <div class="space-y-4">
          <div v-for="build in recentBuilds" :key="build.id" class="border border-gray-200 rounded-lg p-4">
            <div class="flex items-center justify-between mb-2">
              <h4 class="font-medium text-gray-900">{{ build.type }}</h4>
              <span :class="`px-2 py-1 text-xs font-medium rounded-full bg-${getStatusColor(build.status)}-100 text-${getStatusColor(build.status)}-800`">
                {{ build.status }}
              </span>
            </div>
            <p class="text-sm text-gray-600 mb-2">Architecture: {{ build.architecture }}</p>
            <p class="text-xs text-gray-500">Created: {{ build.createdAt }}</p>
          </div>
          <div v-if="recentBuilds.length === 0" class="text-center py-8 text-gray-500">
            No recent builds
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="card p-6">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h3>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <RouterLink to="/deploy" class="btn btn-primary text-center">
          <svg class="w-5 h-5 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          New Deployment
        </RouterLink>
        <RouterLink to="/build" class="btn btn-success text-center">
          <svg class="w-5 h-5 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
          </svg>
          Build Package
        </RouterLink>
        <button @click="refreshData" class="btn btn-secondary text-center">
          <svg class="w-5 h-5 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh Data
        </button>
      </div>
    </div>
  </div>
</template>