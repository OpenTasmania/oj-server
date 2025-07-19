<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useDeploymentStore } from '@/stores/deployment'
import { useWebSocket } from '@/composables/useWebSocket'

const props = defineProps({
  config: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['deploy', 'back'])

const deploymentStore = useDeploymentStore()
const isDeploying = ref(false)
const deploymentProgress = ref(0)
const deploymentLogs = ref([])

// WebSocket connection for real-time updates
const wsUrl = `ws://${window.location.host}/ws/deployment`
const { isConnected, connect, send, on, off } = useWebSocket(wsUrl, {
  autoConnect: false,
  reconnectInterval: 3000,
  maxReconnectAttempts: 5
})

const environmentLabels = {
  local: 'Local Development',
  staging: 'Staging Environment',
  production: 'Production Environment'
}

const componentNames = {
  'openjourney-server': 'OpenJourney Server',
  'openjourney-web': 'Web Interface',
  'openjourney-api': 'API Gateway',
  'openjourney-database': 'Database',
  'openjourney-redis': 'Redis Cache',
  'openjourney-monitoring': 'Monitoring Stack'
}

const selectedComponents = computed(() => {
  return props.config.components.map(id => ({
    id,
    name: componentNames[id] || id
  }))
})

const totalResources = computed(() => {
  const cpu = parseFloat(props.config.resources.cpu) || 0
  const memory = parseFloat(props.config.resources.memory) || 0
  const storage = parseFloat(props.config.resources.storage) || 0
  
  return { cpu, memory, storage }
})

const estimatedCost = computed(() => {
  const { cpu, memory, storage } = totalResources.value
  const cpuCost = cpu * 30
  const memoryCost = memory * 5
  const storageCost = storage * 0.1
  
  return Math.round((cpuCost + memoryCost + storageCost) * 100) / 100
})

const deploymentSteps = ref([
  { id: 1, name: 'Validating configuration', status: 'pending' },
  { id: 2, name: 'Creating namespace', status: 'pending' },
  { id: 3, name: 'Deploying database', status: 'pending' },
  { id: 4, name: 'Deploying core services', status: 'pending' },
  { id: 5, name: 'Deploying additional components', status: 'pending' },
  { id: 6, name: 'Configuring networking', status: 'pending' },
  { id: 7, name: 'Running health checks', status: 'pending' },
  { id: 8, name: 'Finalizing deployment', status: 'pending' }
])

const startRealTimeDeployment = async () => {
  isDeploying.value = true
  deploymentProgress.value = 0
  deploymentLogs.value = []
  
  try {
    // Connect to WebSocket if not already connected
    if (!isConnected.value) {
      await connect()
    }
    
    // Send deployment start message
    const deploymentId = `deployment-${Date.now()}`
    send({
      type: 'start_deployment',
      deploymentId,
      config: props.config
    })
    
    // Set up event listeners for deployment updates
    setupDeploymentListeners(deploymentId)
    
  } catch (error) {
    console.error('Failed to start deployment:', error)
    deploymentLogs.value.push({
      id: Date.now(),
      timestamp: new Date().toLocaleTimeString(),
      level: 'error',
      message: `Failed to start deployment: ${error.message}`
    })
    isDeploying.value = false
  }
}

const setupDeploymentListeners = (deploymentId) => {
  // Listen for deployment progress updates
  on('deployment_progress', (data) => {
    if (data.deploymentId === deploymentId) {
      deploymentProgress.value = data.progress
      
      // Update step status
      if (data.currentStep && data.currentStep <= deploymentSteps.value.length) {
        const step = deploymentSteps.value[data.currentStep - 1]
        if (step) {
          step.status = data.stepStatus || 'running'
        }
      }
    }
  })
  
  // Listen for deployment logs
  on('deployment_log', (data) => {
    if (data.deploymentId === deploymentId) {
      deploymentLogs.value.push({
        id: Date.now() + Math.random(),
        timestamp: new Date().toLocaleTimeString(),
        level: data.level || 'info',
        message: data.message
      })
    }
  })
  
  // Listen for deployment completion
  on('deployment_complete', (data) => {
    if (data.deploymentId === deploymentId) {
      isDeploying.value = false
      deploymentProgress.value = 100
      
      deploymentLogs.value.push({
        id: Date.now(),
        timestamp: new Date().toLocaleTimeString(),
        level: 'success',
        message: 'Deployment completed successfully!'
      })
      
      // Mark all steps as completed
      deploymentSteps.value.forEach(step => {
        if (step.status !== 'completed') {
          step.status = 'completed'
        }
      })
      
      setTimeout(() => {
        emit('deploy')
      }, 2000)
    }
  })
  
  // Listen for deployment errors
  on('deployment_error', (data) => {
    if (data.deploymentId === deploymentId) {
      isDeploying.value = false
      
      deploymentLogs.value.push({
        id: Date.now(),
        timestamp: new Date().toLocaleTimeString(),
        level: 'error',
        message: `Deployment failed: ${data.error}`
      })
      
      // Mark current step as failed
      const currentStep = deploymentSteps.value.find(step => step.status === 'running')
      if (currentStep) {
        currentStep.status = 'failed'
      }
    }
  })
}

const handleDeploy = () => {
  startRealTimeDeployment()
}

const handleBack = () => {
  if (!isDeploying.value) {
    emit('back')
  }
}

const getStepIcon = (status) => {
  switch (status) {
    case 'completed':
      return '✓'
    case 'running':
      return '⟳'
    case 'failed':
      return '✗'
    default:
      return '○'
  }
}

const getLogLevelClass = (level) => {
  switch (level) {
    case 'error':
      return 'text-red-600'
    case 'warning':
      return 'text-yellow-600'
    case 'success':
      return 'text-green-600'
    default:
      return 'text-gray-600'
  }
}
</script>

<template>
  <div class="deployment-review">
    <div class="mb-6">
      <h2 class="text-2xl font-semibold text-gray-900 mb-2">Review & Deploy</h2>
      <p class="text-gray-600">
        Review your configuration and start the deployment process.
      </p>
    </div>

    <!-- Configuration Review -->
    <div v-if="!isDeploying" class="space-y-6">
      <!-- Environment Summary -->
      <div class="card p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Environment Configuration</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 class="font-medium text-gray-900 mb-2">Target Environment</h4>
            <div class="flex items-center space-x-3">
              <div class="text-2xl">
                {{ config.environment === 'local' ? '💻' : config.environment === 'staging' ? '🧪' : '🚀' }}
              </div>
              <div>
                <div class="font-medium">{{ environmentLabels[config.environment] }}</div>
                <div class="text-sm text-gray-600">{{ config.environment }} deployment</div>
              </div>
            </div>
          </div>
          <div>
            <h4 class="font-medium text-gray-900 mb-2">Deployment Options</h4>
            <div class="space-y-1 text-sm">
              <div class="flex items-center">
                <span class="w-4 h-4 mr-2">{{ config.options.overwrite ? '✓' : '○' }}</span>
                <span :class="config.options.overwrite ? 'text-gray-900' : 'text-gray-500'">
                  Overwrite existing deployment
                </span>
              </div>
              <div class="flex items-center">
                <span class="w-4 h-4 mr-2">{{ config.options.production ? '✓' : '○' }}</span>
                <span :class="config.options.production ? 'text-gray-900' : 'text-gray-500'">
                  Production mode
                </span>
              </div>
              <div class="flex items-center">
                <span class="w-4 h-4 mr-2">{{ config.options.autoScale ? '✓' : '○' }}</span>
                <span :class="config.options.autoScale ? 'text-gray-900' : 'text-gray-500'">
                  Auto-scaling enabled
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Components Summary -->
      <div class="card p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Selected Components</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="component in selectedComponents"
            :key="component.id"
            class="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg"
          >
            <div class="w-2 h-2 bg-green-500 rounded-full"></div>
            <span class="font-medium text-gray-900">{{ component.name }}</span>
          </div>
        </div>
        <div class="mt-4 text-sm text-gray-600">
          Total components: {{ selectedComponents.length }}
        </div>
      </div>

      <!-- Resource Summary -->
      <div class="card p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Resource Allocation</h3>
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div class="text-center">
            <div class="text-3xl font-bold text-blue-600">{{ totalResources.cpu }}</div>
            <div class="text-sm text-gray-600">CPU Cores</div>
          </div>
          <div class="text-center">
            <div class="text-3xl font-bold text-green-600">{{ totalResources.memory }}</div>
            <div class="text-sm text-gray-600">GB Memory</div>
          </div>
          <div class="text-center">
            <div class="text-3xl font-bold text-purple-600">{{ totalResources.storage }}</div>
            <div class="text-sm text-gray-600">GB Storage</div>
          </div>
          <div class="text-center">
            <div class="text-3xl font-bold text-orange-600">${{ estimatedCost.toFixed(2) }}</div>
            <div class="text-sm text-gray-600">Monthly Cost</div>
          </div>
        </div>
      </div>

      <!-- Pre-deployment Checklist -->
      <div class="card p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Pre-deployment Checklist</h3>
        <div class="space-y-3">
          <div class="flex items-center">
            <span class="w-4 h-4 mr-3 text-green-500">✓</span>
            <span class="text-gray-700">Configuration validated</span>
          </div>
          <div class="flex items-center">
            <span class="w-4 h-4 mr-3 text-green-500">✓</span>
            <span class="text-gray-700">Resource requirements verified</span>
          </div>
          <div class="flex items-center">
            <span class="w-4 h-4 mr-3 text-green-500">✓</span>
            <span class="text-gray-700">Component dependencies resolved</span>
          </div>
          <div class="flex items-center">
            <span class="w-4 h-4 mr-3 text-green-500">✓</span>
            <span class="text-gray-700">Target environment accessible</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Deployment Progress -->
    <div v-if="isDeploying" class="space-y-6">
      <!-- Progress Overview -->
      <div class="card p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Deployment Progress</h3>
        <div class="mb-4">
          <div class="flex justify-between text-sm text-gray-600 mb-2">
            <span>Progress</span>
            <span>{{ deploymentProgress }}%</span>
          </div>
          <div class="w-full bg-gray-200 rounded-full h-3">
            <div
              class="bg-primary-600 h-3 rounded-full transition-all duration-500"
              :style="{ width: `${deploymentProgress}%` }"
            ></div>
          </div>
        </div>
      </div>

      <!-- Deployment Steps -->
      <div class="card p-6">
        <h4 class="font-semibold text-gray-900 mb-4">Deployment Steps</h4>
        <div class="space-y-3">
          <div
            v-for="step in deploymentSteps"
            :key="step.id"
            class="flex items-center space-x-3"
          >
            <div
              class="w-6 h-6 rounded-full flex items-center justify-center text-sm font-medium"
              :class="{
                'bg-green-100 text-green-600': step.status === 'completed',
                'bg-blue-100 text-blue-600 animate-spin': step.status === 'running',
                'bg-red-100 text-red-600': step.status === 'failed',
                'bg-gray-100 text-gray-400': step.status === 'pending'
              }"
            >
              {{ getStepIcon(step.status) }}
            </div>
            <span
              class="flex-1"
              :class="{
                'text-gray-900 font-medium': step.status === 'running',
                'text-green-600': step.status === 'completed',
                'text-red-600': step.status === 'failed',
                'text-gray-500': step.status === 'pending'
              }"
            >
              {{ step.name }}
            </span>
          </div>
        </div>
      </div>

      <!-- Deployment Logs -->
      <div class="card p-6">
        <h4 class="font-semibold text-gray-900 mb-4">Deployment Logs</h4>
        <div class="bg-gray-900 rounded-lg p-4 max-h-64 overflow-y-auto">
          <div
            v-for="log in deploymentLogs"
            :key="log.id"
            class="text-sm font-mono mb-1"
          >
            <span class="text-gray-400">{{ log.timestamp }}</span>
            <span class="mx-2" :class="getLogLevelClass(log.level)">
              {{ log.message }}
            </span>
          </div>
          <div v-if="deploymentLogs.length === 0" class="text-gray-400 text-sm">
            Waiting for deployment to start...
          </div>
        </div>
      </div>
    </div>

    <!-- Action buttons -->
    <div class="flex justify-between mt-8">
      <button
        @click="handleBack"
        :disabled="isDeploying"
        class="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Back to Configuration
      </button>
      
      <button
        v-if="!isDeploying"
        @click="handleDeploy"
        class="btn btn-primary bg-green-600 hover:bg-green-700 border-green-600"
      >
        <span class="flex items-center">
          <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3l14 9-14 9V3z"></path>
          </svg>
          Start Deployment
        </span>
      </button>
      
      <button
        v-else
        disabled
        class="btn btn-primary opacity-50 cursor-not-allowed"
      >
        <span class="flex items-center">
          <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
          Deploying...
        </span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.card {
  @apply bg-white border border-gray-200 rounded-lg shadow-sm;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.animate-spin {
  animation: spin 1s linear infinite;
}
</style>