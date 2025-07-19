<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({
      cpu: '',
      memory: '',
      storage: ''
    })
  },
  options: {
    type: Object,
    default: () => ({
      overwrite: false,
      production: false,
      autoScale: false
    })
  }
})

const emit = defineEmits(['update:modelValue', 'update:options', 'next', 'back'])

const resources = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const deploymentOptions = computed({
  get: () => props.options,
  set: (value) => emit('update:options', value)
})

const resourcePresets = ref([
  {
    name: 'Development',
    description: 'Minimal resources for development and testing',
    icon: '🧪',
    cpu: '2',
    memory: '4',
    storage: '50',
    recommended: 'local'
  },
  {
    name: 'Small Production',
    description: 'Small production deployment for limited users',
    icon: '🏢',
    cpu: '4',
    memory: '8',
    storage: '100',
    recommended: 'staging'
  },
  {
    name: 'Medium Production',
    description: 'Medium production deployment for moderate load',
    icon: '🏭',
    cpu: '8',
    memory: '16',
    storage: '200',
    recommended: 'production'
  },
  {
    name: 'Large Production',
    description: 'Large production deployment for high load',
    icon: '🌐',
    cpu: '16',
    memory: '32',
    storage: '500',
    recommended: 'production'
  }
])

const storageTypes = ref([
  { value: 'standard', label: 'Standard SSD', description: 'Good performance for most workloads' },
  { value: 'fast', label: 'Fast SSD', description: 'High performance for demanding applications' },
  { value: 'network', label: 'Network Storage', description: 'Shared storage with backup capabilities' }
])

const selectedStorageType = ref('standard')

const applyPreset = (preset) => {
  resources.value = {
    cpu: preset.cpu,
    memory: preset.memory,
    storage: preset.storage
  }
}

const isValidResource = (value, type) => {
  const num = parseFloat(value)
  if (isNaN(num) || num <= 0) return false
  
  switch (type) {
    case 'cpu':
      return num >= 0.5 && num <= 64
    case 'memory':
      return num >= 1 && num <= 256
    case 'storage':
      return num >= 10 && num <= 2000
    default:
      return false
  }
}

const resourceValidation = computed(() => ({
  cpu: {
    valid: isValidResource(resources.value.cpu, 'cpu'),
    message: 'CPU must be between 0.5 and 64 cores'
  },
  memory: {
    valid: isValidResource(resources.value.memory, 'memory'),
    message: 'Memory must be between 1 and 256 GB'
  },
  storage: {
    valid: isValidResource(resources.value.storage, 'storage'),
    message: 'Storage must be between 10 and 2000 GB'
  }
}))

const isFormValid = computed(() => {
  return Object.values(resourceValidation.value).every(field => field.valid)
})

const estimatedCost = computed(() => {
  if (!isFormValid.value) return 0
  
  const cpu = parseFloat(resources.value.cpu) || 0
  const memory = parseFloat(resources.value.memory) || 0
  const storage = parseFloat(resources.value.storage) || 0
  
  // Rough cost estimation (per month)
  const cpuCost = cpu * 30 // $30 per core
  const memoryCost = memory * 5 // $5 per GB
  const storageCost = storage * 0.1 // $0.10 per GB
  
  return Math.round((cpuCost + memoryCost + storageCost) * 100) / 100
})

const handleNext = () => {
  if (isFormValid.value) {
    emit('next')
  }
}

const handleBack = () => {
  emit('back')
}

// Watch for changes in options
watch(deploymentOptions, (newOptions) => {
  emit('update:options', newOptions)
}, { deep: true })
</script>

<template>
  <div class="deployment-config">
    <div class="mb-6">
      <h2 class="text-2xl font-semibold text-gray-900 mb-2">Resource Configuration</h2>
      <p class="text-gray-600">
        Configure the resource allocation and deployment options for your OpenJourney Server installation.
      </p>
    </div>

    <!-- Resource Presets -->
    <div class="mb-8">
      <h3 class="text-lg font-medium text-gray-900 mb-4">Quick Presets</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div
          v-for="preset in resourcePresets"
          :key="preset.name"
          class="preset-card cursor-pointer border-2 border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors"
          @click="applyPreset(preset)"
        >
          <div class="text-center">
            <div class="text-2xl mb-2">{{ preset.icon }}</div>
            <h4 class="font-semibold text-gray-900 mb-1">{{ preset.name }}</h4>
            <p class="text-xs text-gray-600 mb-3">{{ preset.description }}</p>
            <div class="text-xs text-gray-500 space-y-1">
              <div>{{ preset.cpu }} CPU cores</div>
              <div>{{ preset.memory }} GB RAM</div>
              <div>{{ preset.storage }} GB storage</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Manual Resource Configuration -->
    <div class="mb-8">
      <h3 class="text-lg font-medium text-gray-900 mb-4">Custom Resource Allocation</h3>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <!-- CPU Configuration -->
        <div>
          <label class="form-label">CPU Cores</label>
          <div class="relative">
            <input
              v-model="resources.cpu"
              type="number"
              step="0.5"
              min="0.5"
              max="64"
              class="form-input"
              :class="{
                'border-red-300 focus:border-red-500': !resourceValidation.cpu.valid && resources.cpu,
                'border-green-300 focus:border-green-500': resourceValidation.cpu.valid && resources.cpu
              }"
              placeholder="e.g., 2"
            >
            <div class="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
              <span class="text-gray-500 text-sm">cores</span>
            </div>
          </div>
          <p v-if="!resourceValidation.cpu.valid && resources.cpu" class="text-red-600 text-sm mt-1">
            {{ resourceValidation.cpu.message }}
          </p>
          <p v-else class="text-gray-500 text-sm mt-1">
            Number of CPU cores to allocate
          </p>
        </div>

        <!-- Memory Configuration -->
        <div>
          <label class="form-label">Memory (RAM)</label>
          <div class="relative">
            <input
              v-model="resources.memory"
              type="number"
              step="1"
              min="1"
              max="256"
              class="form-input"
              :class="{
                'border-red-300 focus:border-red-500': !resourceValidation.memory.valid && resources.memory,
                'border-green-300 focus:border-green-500': resourceValidation.memory.valid && resources.memory
              }"
              placeholder="e.g., 4"
            >
            <div class="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
              <span class="text-gray-500 text-sm">GB</span>
            </div>
          </div>
          <p v-if="!resourceValidation.memory.valid && resources.memory" class="text-red-600 text-sm mt-1">
            {{ resourceValidation.memory.message }}
          </p>
          <p v-else class="text-gray-500 text-sm mt-1">
            Amount of RAM to allocate
          </p>
        </div>

        <!-- Storage Configuration -->
        <div>
          <label class="form-label">Storage</label>
          <div class="relative">
            <input
              v-model="resources.storage"
              type="number"
              step="10"
              min="10"
              max="2000"
              class="form-input"
              :class="{
                'border-red-300 focus:border-red-500': !resourceValidation.storage.valid && resources.storage,
                'border-green-300 focus:border-green-500': resourceValidation.storage.valid && resources.storage
              }"
              placeholder="e.g., 50"
            >
            <div class="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
              <span class="text-gray-500 text-sm">GB</span>
            </div>
          </div>
          <p v-if="!resourceValidation.storage.valid && resources.storage" class="text-red-600 text-sm mt-1">
            {{ resourceValidation.storage.message }}
          </p>
          <p v-else class="text-gray-500 text-sm mt-1">
            Persistent storage allocation
          </p>
        </div>
      </div>
    </div>

    <!-- Storage Type Selection -->
    <div class="mb-8">
      <h3 class="text-lg font-medium text-gray-900 mb-4">Storage Type</h3>
      <div class="space-y-3">
        <div
          v-for="storageType in storageTypes"
          :key="storageType.value"
          class="flex items-center"
        >
          <input
            :id="storageType.value"
            v-model="selectedStorageType"
            :value="storageType.value"
            type="radio"
            class="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300"
          >
          <label :for="storageType.value" class="ml-3 flex-1">
            <div class="font-medium text-gray-900">{{ storageType.label }}</div>
            <div class="text-sm text-gray-600">{{ storageType.description }}</div>
          </label>
        </div>
      </div>
    </div>

    <!-- Deployment Options -->
    <div class="mb-8">
      <h3 class="text-lg font-medium text-gray-900 mb-4">Deployment Options</h3>
      <div class="space-y-4">
        <div class="flex items-start">
          <input
            id="overwrite"
            v-model="deploymentOptions.overwrite"
            type="checkbox"
            class="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded mt-1"
          >
          <label for="overwrite" class="ml-3">
            <div class="font-medium text-gray-900">Overwrite existing deployment</div>
            <div class="text-sm text-gray-600">Replace any existing OpenJourney Server deployment</div>
          </label>
        </div>

        <div class="flex items-start">
          <input
            id="production"
            v-model="deploymentOptions.production"
            type="checkbox"
            class="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded mt-1"
          >
          <label for="production" class="ml-3">
            <div class="font-medium text-gray-900">Production mode</div>
            <div class="text-sm text-gray-600">Enable production optimizations and security settings</div>
          </label>
        </div>

        <div class="flex items-start">
          <input
            id="autoScale"
            v-model="deploymentOptions.autoScale"
            type="checkbox"
            class="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded mt-1"
          >
          <label for="autoScale" class="ml-3">
            <div class="font-medium text-gray-900">Enable auto-scaling</div>
            <div class="text-sm text-gray-600">Automatically scale resources based on demand</div>
          </label>
        </div>
      </div>
    </div>

    <!-- Resource Summary and Cost Estimation -->
    <div class="mb-8 p-6 bg-gray-50 rounded-lg">
      <h4 class="text-lg font-semibold text-gray-900 mb-4">Configuration Summary</h4>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h5 class="font-medium text-gray-900 mb-2">Resource Allocation</h5>
          <div class="space-y-2 text-sm">
            <div class="flex justify-between">
              <span class="text-gray-600">CPU:</span>
              <span class="font-medium">{{ resources.cpu || '0' }} cores</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">Memory:</span>
              <span class="font-medium">{{ resources.memory || '0' }} GB</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">Storage:</span>
              <span class="font-medium">{{ resources.storage || '0' }} GB ({{ selectedStorageType }})</span>
            </div>
          </div>
        </div>
        <div>
          <h5 class="font-medium text-gray-900 mb-2">Estimated Monthly Cost</h5>
          <div class="text-3xl font-bold text-primary-600 mb-2">
            ${{ estimatedCost.toFixed(2) }}
          </div>
          <p class="text-sm text-gray-600">
            Estimated cost based on resource allocation
          </p>
        </div>
      </div>
    </div>

    <!-- Action buttons -->
    <div class="flex justify-between">
      <button
        @click="handleBack"
        class="btn btn-secondary"
      >
        Back to Components
      </button>
      
      <button
        @click="handleNext"
        :disabled="!isFormValid"
        class="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Continue to Review
      </button>
    </div>
  </div>
</template>

<style scoped>
.preset-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.preset-card:active {
  transform: translateY(0);
}
</style>