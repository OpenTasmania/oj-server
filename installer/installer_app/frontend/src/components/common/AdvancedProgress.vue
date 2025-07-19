<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

const props = defineProps({
  // Progress data
  steps: {
    type: Array,
    required: true,
    // Expected format: [{ id, name, status, progress, startTime, endTime, error, substeps }]
  },
  currentStep: {
    type: Number,
    default: 0
  },
  overallProgress: {
    type: Number,
    default: 0
  },
  
  // Configuration
  showTimeline: {
    type: Boolean,
    default: true
  },
  showSubsteps: {
    type: Boolean,
    default: true
  },
  showEstimatedTime: {
    type: Boolean,
    default: true
  },
  showProgressBars: {
    type: Boolean,
    default: true
  },
  
  // Real-time updates
  websocketUrl: {
    type: String,
    default: null
  },
  
  // Styling
  variant: {
    type: String,
    default: 'default', // default, compact, detailed
    validator: (value) => ['default', 'compact', 'detailed'].includes(value)
  }
})

const emit = defineEmits(['step-click', 'progress-complete', 'progress-error', 'step-retry'])

// State
const expandedSteps = ref(new Set())
const showDetails = ref(false)
const startTime = ref(null)
const estimatedCompletion = ref(null)
const progressHistory = ref([])

// WebSocket connection for real-time updates
const { isConnected, messages } = props.websocketUrl 
  ? useWebSocket(props.websocketUrl)
  : { isConnected: ref(false), messages: ref([]) }

// Computed properties
const totalSteps = computed(() => props.steps.length)

const completedSteps = computed(() => 
  props.steps.filter(step => step.status === 'completed').length
)

const failedSteps = computed(() => 
  props.steps.filter(step => step.status === 'failed').length
)

const currentStepData = computed(() => 
  props.steps[props.currentStep] || null
)

const isComplete = computed(() => 
  props.overallProgress >= 100 || completedSteps.value === totalSteps.value
)

const hasFailed = computed(() => 
  failedSteps.value > 0
)

const estimatedTimeRemaining = computed(() => {
  if (!startTime.value || props.overallProgress === 0) return null
  
  const elapsed = Date.now() - startTime.value
  const rate = props.overallProgress / elapsed
  const remaining = (100 - props.overallProgress) / rate
  
  return remaining > 0 ? remaining : 0
})

const progressStats = computed(() => {
  const totalDuration = props.steps.reduce((acc, step) => {
    if (step.startTime && step.endTime) {
      return acc + (new Date(step.endTime) - new Date(step.startTime))
    }
    return acc
  }, 0)

  return {
    totalSteps: totalSteps.value,
    completedSteps: completedSteps.value,
    failedSteps: failedSteps.value,
    inProgressSteps: props.steps.filter(s => s.status === 'in-progress').length,
    totalDuration: totalDuration,
    averageStepTime: totalDuration / Math.max(completedSteps.value, 1)
  }
})

// Methods
const getStepIcon = (step) => {
  switch (step.status) {
    case 'completed':
      return 'check-circle'
    case 'failed':
      return 'x-circle'
    case 'in-progress':
      return 'clock'
    case 'pending':
      return 'circle'
    case 'skipped':
      return 'minus-circle'
    default:
      return 'circle'
  }
}

const getStepColor = (step) => {
  switch (step.status) {
    case 'completed':
      return 'text-green-500'
    case 'failed':
      return 'text-red-500'
    case 'in-progress':
      return 'text-blue-500'
    case 'pending':
      return 'text-gray-400'
    case 'skipped':
      return 'text-yellow-500'
    default:
      return 'text-gray-400'
  }
}

const getProgressBarColor = (step) => {
  switch (step.status) {
    case 'completed':
      return 'bg-green-500'
    case 'failed':
      return 'bg-red-500'
    case 'in-progress':
      return 'bg-blue-500'
    case 'skipped':
      return 'bg-yellow-500'
    default:
      return 'bg-gray-300'
  }
}

const formatDuration = (ms) => {
  if (!ms) return '0s'
  
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  
  if (hours > 0) {
    return `${hours}h ${minutes % 60}m ${seconds % 60}s`
  } else if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`
  } else {
    return `${seconds}s`
  }
}

const formatEstimatedTime = (ms) => {
  if (!ms) return 'Unknown'
  
  const minutes = Math.ceil(ms / (1000 * 60))
  if (minutes < 60) {
    return `~${minutes}m`
  } else {
    const hours = Math.floor(minutes / 60)
    const remainingMinutes = minutes % 60
    return `~${hours}h ${remainingMinutes}m`
  }
}

const toggleStepExpansion = (stepIndex) => {
  if (expandedSteps.value.has(stepIndex)) {
    expandedSteps.value.delete(stepIndex)
  } else {
    expandedSteps.value.add(stepIndex)
  }
}

const handleStepClick = (step, index) => {
  emit('step-click', { step, index })
  if (props.showSubsteps && step.substeps?.length > 0) {
    toggleStepExpansion(index)
  }
}

const handleStepRetry = (step, index) => {
  emit('step-retry', { step, index })
}

const exportProgress = () => {
  const exportData = {
    timestamp: new Date().toISOString(),
    overallProgress: props.overallProgress,
    currentStep: props.currentStep,
    steps: props.steps,
    stats: progressStats.value,
    history: progressHistory.value
  }

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { 
    type: 'application/json' 
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `progress-${Date.now()}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// Watch for progress changes
watch(() => props.overallProgress, (newProgress, oldProgress) => {
  if (newProgress !== oldProgress) {
    progressHistory.value.push({
      timestamp: Date.now(),
      progress: newProgress,
      currentStep: props.currentStep
    })

    // Limit history size
    if (progressHistory.value.length > 100) {
      progressHistory.value = progressHistory.value.slice(-100)
    }
  }

  if (newProgress >= 100 && oldProgress < 100) {
    emit('progress-complete')
  }
})

// Watch for failed steps
watch(() => failedSteps.value, (newCount, oldCount) => {
  if (newCount > oldCount) {
    const failedStep = props.steps.find(s => s.status === 'failed')
    emit('progress-error', failedStep)
  }
})

// Handle WebSocket messages
watch(messages, (newMessages) => {
  // Handle real-time progress updates
  newMessages.forEach(message => {
    if (message.type === 'progress-update') {
      // Progress updates would be handled by parent component
      // This is just for logging/tracking
      console.log('Progress update received:', message.data)
    }
  })
}, { deep: true })

// Lifecycle
onMounted(() => {
  startTime.value = Date.now()
})
</script>

<template>
  <div :class="[
    'advanced-progress',
    `variant-${variant}`,
    { 'is-complete': isComplete, 'has-failed': hasFailed }
  ]">
    <!-- Header with overall progress -->
    <div class="progress-header">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center space-x-4">
          <h3 class="text-lg font-medium text-gray-900">
            Progress Tracker
          </h3>
          <div class="flex items-center space-x-2 text-sm text-gray-600">
            <span>{{ completedSteps }}/{{ totalSteps }} steps</span>
            <span v-if="hasFailed" class="text-red-600">
              ({{ failedSteps }} failed)
            </span>
          </div>
        </div>
        
        <div class="flex items-center space-x-2">
          <button
            @click="showDetails = !showDetails"
            class="text-sm text-gray-600 hover:text-gray-800"
          >
            {{ showDetails ? 'Hide' : 'Show' }} Details
          </button>
          <button
            @click="exportProgress"
            class="text-sm bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded-md"
          >
            Export
          </button>
        </div>
      </div>

      <!-- Overall progress bar -->
      <div class="mb-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-medium text-gray-700">
            Overall Progress
          </span>
          <span class="text-sm text-gray-600">
            {{ Math.round(overallProgress) }}%
          </span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-3">
          <div
            :class="[
              'h-3 rounded-full transition-all duration-300',
              isComplete ? 'bg-green-500' : hasFailed ? 'bg-red-500' : 'bg-blue-500'
            ]"
            :style="{ width: `${overallProgress}%` }"
          ></div>
        </div>
      </div>

      <!-- Stats (if details are shown) -->
      <div v-if="showDetails" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 text-sm">
        <div class="bg-gray-50 p-3 rounded">
          <div class="font-medium text-gray-900">Total Time</div>
          <div class="text-gray-600">{{ formatDuration(progressStats.totalDuration) }}</div>
        </div>
        <div class="bg-gray-50 p-3 rounded">
          <div class="font-medium text-gray-900">Avg Step Time</div>
          <div class="text-gray-600">{{ formatDuration(progressStats.averageStepTime) }}</div>
        </div>
        <div v-if="showEstimatedTime && estimatedTimeRemaining" class="bg-gray-50 p-3 rounded">
          <div class="font-medium text-gray-900">Est. Remaining</div>
          <div class="text-gray-600">{{ formatEstimatedTime(estimatedTimeRemaining) }}</div>
        </div>
        <div class="bg-gray-50 p-3 rounded">
          <div class="font-medium text-gray-900">Status</div>
          <div :class="[
            'font-medium',
            isComplete ? 'text-green-600' : hasFailed ? 'text-red-600' : 'text-blue-600'
          ]">
            {{ isComplete ? 'Complete' : hasFailed ? 'Failed' : 'In Progress' }}
          </div>
        </div>
      </div>
    </div>

    <!-- Steps list -->
    <div class="steps-container">
      <div v-if="variant === 'compact'" class="space-y-2">
        <!-- Compact view -->
        <div
          v-for="(step, index) in steps"
          :key="step.id || index"
          @click="handleStepClick(step, index)"
          class="flex items-center space-x-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer"
        >
          <div :class="['w-6 h-6 flex items-center justify-center', getStepColor(step)]">
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <!-- Icon based on step status -->
              <path v-if="step.status === 'completed'" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"/>
              <path v-else-if="step.status === 'failed'" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"/>
              <path v-else-if="step.status === 'in-progress'" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"/>
              <path v-else d="M10 18a8 8 0 100-16 8 8 0 000 16z"/>
            </svg>
          </div>
          <div class="flex-1">
            <div class="font-medium text-gray-900">{{ step.name }}</div>
            <div v-if="step.progress !== undefined && showProgressBars" class="mt-1">
              <div class="w-full bg-gray-200 rounded-full h-1">
                <div
                  :class="['h-1 rounded-full', getProgressBarColor(step)]"
                  :style="{ width: `${step.progress}%` }"
                ></div>
              </div>
            </div>
          </div>
          <div class="text-sm text-gray-500">
            {{ step.progress !== undefined ? `${Math.round(step.progress)}%` : '' }}
          </div>
        </div>
      </div>

      <div v-else class="space-y-4">
        <!-- Detailed view -->
        <div
          v-for="(step, index) in steps"
          :key="step.id || index"
          class="step-item border border-gray-200 rounded-lg overflow-hidden"
        >
          <div
            @click="handleStepClick(step, index)"
            :class="[
              'step-header p-4 cursor-pointer hover:bg-gray-50',
              step.status === 'in-progress' ? 'bg-blue-50' : '',
              step.status === 'completed' ? 'bg-green-50' : '',
              step.status === 'failed' ? 'bg-red-50' : ''
            ]"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-3">
                <div :class="['w-8 h-8 flex items-center justify-center rounded-full', getStepColor(step)]">
                  <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path v-if="step.status === 'completed'" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"/>
                    <path v-else-if="step.status === 'failed'" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"/>
                    <path v-else-if="step.status === 'in-progress'" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"/>
                    <path v-else d="M10 18a8 8 0 100-16 8 8 0 000 16z"/>
                  </svg>
                </div>
                <div>
                  <h4 class="font-medium text-gray-900">{{ step.name }}</h4>
                  <p v-if="step.description" class="text-sm text-gray-600">{{ step.description }}</p>
                </div>
              </div>
              
              <div class="flex items-center space-x-4">
                <div v-if="step.startTime" class="text-sm text-gray-500">
                  {{ formatDuration(step.endTime ? new Date(step.endTime) - new Date(step.startTime) : Date.now() - new Date(step.startTime)) }}
                </div>
                <div class="text-sm font-medium">
                  {{ step.progress !== undefined ? `${Math.round(step.progress)}%` : '' }}
                </div>
                <button
                  v-if="step.status === 'failed'"
                  @click.stop="handleStepRetry(step, index)"
                  class="text-sm bg-red-100 hover:bg-red-200 text-red-800 px-3 py-1 rounded-md"
                >
                  Retry
                </button>
              </div>
            </div>

            <!-- Progress bar -->
            <div v-if="step.progress !== undefined && showProgressBars" class="mt-3">
              <div class="w-full bg-gray-200 rounded-full h-2">
                <div
                  :class="['h-2 rounded-full transition-all duration-300', getProgressBarColor(step)]"
                  :style="{ width: `${step.progress}%` }"
                ></div>
              </div>
            </div>

            <!-- Error message -->
            <div v-if="step.error" class="mt-3 p-3 bg-red-100 border border-red-200 rounded-md">
              <p class="text-sm text-red-800">{{ step.error }}</p>
            </div>
          </div>

          <!-- Substeps (if expanded) -->
          <div
            v-if="showSubsteps && step.substeps?.length > 0 && expandedSteps.has(index)"
            class="substeps border-t border-gray-200 bg-gray-50 p-4"
          >
            <div class="space-y-2">
              <div
                v-for="(substep, subIndex) in step.substeps"
                :key="substep.id || subIndex"
                class="flex items-center space-x-3 text-sm"
              >
                <div :class="['w-4 h-4 flex items-center justify-center', getStepColor(substep)]">
                  <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path v-if="substep.status === 'completed'" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"/>
                    <path v-else-if="substep.status === 'failed'" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"/>
                    <path v-else d="M10 18a8 8 0 100-16 8 8 0 000 16z"/>
                  </svg>
                </div>
                <span class="flex-1">{{ substep.name }}</span>
                <span v-if="substep.progress !== undefined" class="text-gray-500">
                  {{ Math.round(substep.progress) }}%
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.advanced-progress {
  @apply bg-white rounded-lg shadow-sm border p-6;
}

.variant-compact .steps-container {
  @apply max-h-96 overflow-y-auto;
}

.variant-detailed .step-item {
  transition: all 0.2s ease;
}

.variant-detailed .step-item:hover {
  @apply shadow-sm;
}

.is-complete .progress-header {
  @apply border-l-4 border-green-500 pl-4;
}

.has-failed .progress-header {
  @apply border-l-4 border-red-500 pl-4;
}
</style>