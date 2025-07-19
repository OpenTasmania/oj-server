<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  components: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['restart', 'stop', 'viewLogs'])

const selectedComponent = ref(null)
const showDetails = ref(false)

const getStatusIcon = (status) => {
  switch (status) {
    case 'healthy':
      return '✅'
    case 'warning':
      return '⚠️'
    case 'error':
      return '❌'
    case 'stopped':
      return '⏹️'
    case 'starting':
      return '🔄'
    default:
      return '❓'
  }
}

const getStatusClass = (status) => {
  switch (status) {
    case 'healthy':
      return 'text-green-600 bg-green-50 border-green-200'
    case 'warning':
      return 'text-yellow-600 bg-yellow-50 border-yellow-200'
    case 'error':
      return 'text-red-600 bg-red-50 border-red-200'
    case 'stopped':
      return 'text-gray-600 bg-gray-50 border-gray-200'
    case 'starting':
      return 'text-blue-600 bg-blue-50 border-blue-200'
    default:
      return 'text-gray-600 bg-gray-50 border-gray-200'
  }
}

const getResourceUsageClass = (usage) => {
  if (usage < 50) return 'bg-green-500'
  if (usage < 80) return 'bg-yellow-500'
  return 'bg-red-500'
}

const formatMemory = (memory) => {
  if (memory >= 1024) {
    return `${(memory / 1024).toFixed(1)}GB`
  }
  return `${memory}MB`
}

const showComponentDetails = (component) => {
  selectedComponent.value = component
  showDetails.value = true
}

const hideComponentDetails = () => {
  selectedComponent.value = null
  showDetails.value = false
}

const handleRestart = (component) => {
  emit('restart', component)
}

const handleStop = (component) => {
  emit('stop', component)
}

const handleViewLogs = (component) => {
  emit('viewLogs', component)
}

const healthyComponents = computed(() => {
  return props.components.filter(c => c.status === 'healthy').length
})

const totalComponents = computed(() => {
  return props.components.length
})

const healthPercentage = computed(() => {
  return Math.round((healthyComponents.value / totalComponents.value) * 100)
})
</script>

<template>
  <div class="component-status">
    <!-- Summary Header -->
    <div class="mb-6 p-4 bg-gray-50 rounded-lg">
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-lg font-medium text-gray-900">Component Health</h3>
          <p class="text-sm text-gray-600">
            {{ healthyComponents }} of {{ totalComponents }} components healthy
          </p>
        </div>
        <div class="text-right">
          <div class="text-2xl font-bold" :class="{
            'text-green-600': healthPercentage >= 90,
            'text-yellow-600': healthPercentage >= 70 && healthPercentage < 90,
            'text-red-600': healthPercentage < 70
          }">
            {{ healthPercentage }}%
          </div>
          <div class="text-sm text-gray-600">Overall Health</div>
        </div>
      </div>
    </div>

    <!-- Components List -->
    <div class="space-y-4">
      <div
        v-for="component in components"
        :key="component.id"
        class="component-card border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
        :class="getStatusClass(component.status)"
        @click="showComponentDetails(component)"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <div class="text-xl">
              {{ getStatusIcon(component.status) }}
            </div>
            <div>
              <h4 class="font-medium text-gray-900">{{ component.name }}</h4>
              <p class="text-sm text-gray-600">{{ component.version }}</p>
            </div>
          </div>
          
          <div class="flex items-center space-x-4">
            <!-- CPU Usage -->
            <div class="text-center">
              <div class="text-sm font-medium text-gray-900">{{ component.cpu }}%</div>
              <div class="text-xs text-gray-500">CPU</div>
            </div>
            
            <!-- Memory Usage -->
            <div class="text-center">
              <div class="text-sm font-medium text-gray-900">{{ formatMemory(component.memory) }}</div>
              <div class="text-xs text-gray-500">Memory</div>
            </div>
            
            <!-- Uptime -->
            <div class="text-center">
              <div class="text-sm font-medium text-gray-900">{{ component.uptime }}</div>
              <div class="text-xs text-gray-500">Uptime</div>
            </div>
            
            <!-- Status Badge -->
            <div class="text-center">
              <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize"
                    :class="getStatusClass(component.status)">
                {{ component.status }}
              </span>
            </div>
          </div>
        </div>

        <!-- Resource Usage Bars -->
        <div class="mt-4 grid grid-cols-2 gap-4">
          <div>
            <div class="flex justify-between text-xs text-gray-600 mb-1">
              <span>CPU Usage</span>
              <span>{{ component.cpu }}%</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-2">
              <div 
                class="h-2 rounded-full transition-all duration-300"
                :class="getResourceUsageClass(component.cpu)"
                :style="{ width: `${component.cpu}%` }"
              ></div>
            </div>
          </div>
          
          <div>
            <div class="flex justify-between text-xs text-gray-600 mb-1">
              <span>Memory</span>
              <span>{{ formatMemory(component.memory) }}</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-2">
              <div 
                class="h-2 rounded-full transition-all duration-300"
                :class="getResourceUsageClass(Math.min((component.memory / 1024) * 100, 100))"
                :style="{ width: `${Math.min((component.memory / 1024) * 100, 100)}%` }"
              ></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Component Details Modal -->
    <div v-if="showDetails && selectedComponent" 
         class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
         @click="hideComponentDetails">
      <div class="bg-white rounded-lg p-6 max-w-2xl w-full mx-4" @click.stop>
        <div class="flex items-center justify-between mb-6">
          <div class="flex items-center space-x-3">
            <div class="text-2xl">
              {{ getStatusIcon(selectedComponent.status) }}
            </div>
            <div>
              <h2 class="text-xl font-semibold text-gray-900">{{ selectedComponent.name }}</h2>
              <p class="text-gray-600">{{ selectedComponent.version }}</p>
            </div>
          </div>
          <button @click="hideComponentDetails" class="text-gray-400 hover:text-gray-600">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>

        <!-- Component Details -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <div>
            <h3 class="text-lg font-medium text-gray-900 mb-3">Status Information</h3>
            <div class="space-y-2">
              <div class="flex justify-between">
                <span class="text-gray-600">Status:</span>
                <span class="font-medium capitalize" :class="{
                  'text-green-600': selectedComponent.status === 'healthy',
                  'text-yellow-600': selectedComponent.status === 'warning',
                  'text-red-600': selectedComponent.status === 'error'
                }">
                  {{ selectedComponent.status }}
                </span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">Uptime:</span>
                <span class="font-medium">{{ selectedComponent.uptime }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">Version:</span>
                <span class="font-medium">{{ selectedComponent.version }}</span>
              </div>
            </div>
          </div>

          <div>
            <h3 class="text-lg font-medium text-gray-900 mb-3">Resource Usage</h3>
            <div class="space-y-3">
              <div>
                <div class="flex justify-between text-sm mb-1">
                  <span class="text-gray-600">CPU Usage</span>
                  <span class="font-medium">{{ selectedComponent.cpu }}%</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-3">
                  <div 
                    class="h-3 rounded-full transition-all duration-300"
                    :class="getResourceUsageClass(selectedComponent.cpu)"
                    :style="{ width: `${selectedComponent.cpu}%` }"
                  ></div>
                </div>
              </div>
              
              <div>
                <div class="flex justify-between text-sm mb-1">
                  <span class="text-gray-600">Memory Usage</span>
                  <span class="font-medium">{{ formatMemory(selectedComponent.memory) }}</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-3">
                  <div 
                    class="h-3 rounded-full transition-all duration-300"
                    :class="getResourceUsageClass(Math.min((selectedComponent.memory / 1024) * 100, 100))"
                    :style="{ width: `${Math.min((selectedComponent.memory / 1024) * 100, 100)}%` }"
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex justify-end space-x-3">
          <button
            @click="handleViewLogs(selectedComponent)"
            class="btn btn-secondary"
          >
            View Logs
          </button>
          <button
            v-if="selectedComponent.status !== 'stopped'"
            @click="handleStop(selectedComponent)"
            class="btn btn-secondary"
          >
            Stop
          </button>
          <button
            @click="handleRestart(selectedComponent)"
            class="btn btn-primary"
          >
            Restart
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.component-card {
  transition: all 0.2s ease;
}

.component-card:hover {
  transform: translateY(-1px);
}

.btn {
  @apply px-4 py-2 rounded-md font-medium text-sm transition-colors;
}

.btn-primary {
  @apply bg-primary-600 text-white hover:bg-primary-700;
}

.btn-secondary {
  @apply bg-gray-200 text-gray-900 hover:bg-gray-300;
}
</style>