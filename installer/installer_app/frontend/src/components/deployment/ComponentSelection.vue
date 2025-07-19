<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'next', 'back'])

const selectedComponents = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const availableComponents = ref([
  {
    id: 'openjourney-server',
    name: 'OpenJourney Server',
    description: 'Core server application with routing and API services',
    icon: '🚀',
    required: true,
    category: 'core',
    resources: { cpu: '500m', memory: '1Gi', storage: '5Gi' },
    dependencies: [],
    features: ['REST API', 'Route planning', 'Data processing', 'Plugin system']
  },
  {
    id: 'openjourney-web',
    name: 'Web Interface',
    description: 'Frontend web application for user interaction',
    icon: '🌐',
    required: false,
    category: 'frontend',
    resources: { cpu: '100m', memory: '256Mi', storage: '1Gi' },
    dependencies: ['openjourney-server'],
    features: ['Interactive maps', 'Route visualization', 'User dashboard', 'Mobile responsive']
  },
  {
    id: 'openjourney-api',
    name: 'API Gateway',
    description: 'API gateway for external integrations and rate limiting',
    icon: '🔌',
    required: false,
    category: 'integration',
    resources: { cpu: '200m', memory: '512Mi', storage: '2Gi' },
    dependencies: ['openjourney-server'],
    features: ['Rate limiting', 'Authentication', 'API versioning', 'Request routing']
  },
  {
    id: 'openjourney-database',
    name: 'Database',
    description: 'PostgreSQL database with PostGIS extensions',
    icon: '🗄️',
    required: true,
    category: 'data',
    resources: { cpu: '1000m', memory: '2Gi', storage: '20Gi' },
    dependencies: [],
    features: ['PostGIS support', 'Automated backups', 'High availability', 'Performance tuning']
  },
  {
    id: 'openjourney-redis',
    name: 'Redis Cache',
    description: 'In-memory caching and session storage',
    icon: '⚡',
    required: false,
    category: 'data',
    resources: { cpu: '100m', memory: '512Mi', storage: '1Gi' },
    dependencies: [],
    features: ['Session storage', 'Query caching', 'Real-time data', 'Pub/Sub messaging']
  },
  {
    id: 'openjourney-monitoring',
    name: 'Monitoring Stack',
    description: 'Prometheus, Grafana, and alerting services',
    icon: '📊',
    required: false,
    category: 'ops',
    resources: { cpu: '300m', memory: '1Gi', storage: '10Gi' },
    dependencies: [],
    features: ['Metrics collection', 'Dashboards', 'Alerting', 'Log aggregation']
  }
])

const categories = computed(() => {
  const cats = {}
  availableComponents.value.forEach(comp => {
    if (!cats[comp.category]) {
      cats[comp.category] = []
    }
    cats[comp.category].push(comp)
  })
  return cats
})

const categoryLabels = {
  core: 'Core Services',
  frontend: 'Frontend',
  integration: 'Integration',
  data: 'Data Layer',
  ops: 'Operations'
}

const toggleComponent = (component) => {
  if (component.required) return // Can't deselect required components
  
  const index = selectedComponents.value.findIndex(c => c === component.id)
  if (index > -1) {
    // Remove component and its dependents
    const newSelection = selectedComponents.value.filter(id => {
      const comp = availableComponents.value.find(c => c.id === id)
      return !comp.dependencies.includes(component.id) && id !== component.id
    })
    selectedComponents.value = newSelection
  } else {
    // Add component and its dependencies
    const newSelection = [...selectedComponents.value]
    component.dependencies.forEach(depId => {
      if (!newSelection.includes(depId)) {
        newSelection.push(depId)
      }
    })
    newSelection.push(component.id)
    selectedComponents.value = newSelection
  }
}

const isComponentSelected = (componentId) => {
  return selectedComponents.value.includes(componentId)
}

const isComponentDisabled = (component) => {
  // Component is disabled if it's required or if its dependencies aren't selected
  if (component.required) return false
  return component.dependencies.some(depId => !selectedComponents.value.includes(depId))
}

const totalResources = computed(() => {
  const selected = availableComponents.value.filter(comp => 
    selectedComponents.value.includes(comp.id)
  )
  
  return selected.reduce((total, comp) => {
    return {
      cpu: total.cpu + parseInt(comp.resources.cpu),
      memory: total.memory + parseFloat(comp.resources.memory),
      storage: total.storage + parseInt(comp.resources.storage)
    }
  }, { cpu: 0, memory: 0, storage: 0 })
})

// Auto-select required components on mount
const initializeSelection = () => {
  const required = availableComponents.value
    .filter(comp => comp.required)
    .map(comp => comp.id)
  
  if (selectedComponents.value.length === 0) {
    selectedComponents.value = required
  }
}

initializeSelection()

const handleNext = () => {
  if (selectedComponents.value.length > 0) {
    emit('next')
  }
}

const handleBack = () => {
  emit('back')
}
</script>

<template>
  <div class="component-selection">
    <div class="mb-6">
      <h2 class="text-2xl font-semibold text-gray-900 mb-2">Select Components</h2>
      <p class="text-gray-600">
        Choose which OpenJourney Server components to deploy. Required components are automatically selected.
      </p>
    </div>

    <!-- Component Categories -->
    <div class="space-y-8">
      <div v-for="(components, category) in categories" :key="category">
        <h3 class="text-lg font-medium text-gray-900 mb-4">
          {{ categoryLabels[category] }}
        </h3>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div
            v-for="component in components"
            :key="component.id"
            class="component-card relative"
          >
            <div
              class="border-2 rounded-lg p-4 transition-all duration-200 cursor-pointer"
              :class="{
                'border-primary-500 bg-primary-50': isComponentSelected(component.id),
                'border-gray-200 hover:border-gray-300': !isComponentSelected(component.id) && !isComponentDisabled(component),
                'border-gray-100 bg-gray-50 cursor-not-allowed': isComponentDisabled(component)
              }"
              @click="toggleComponent(component)"
            >
              <!-- Selection indicator -->
              <div class="absolute top-3 right-3">
                <div
                  class="w-5 h-5 rounded border-2 flex items-center justify-center"
                  :class="{
                    'border-primary-500 bg-primary-500': isComponentSelected(component.id),
                    'border-gray-300': !isComponentSelected(component.id)
                  }"
                >
                  <svg
                    v-if="isComponentSelected(component.id)"
                    class="w-3 h-3 text-white"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
                  </svg>
                </div>
              </div>

              <!-- Required badge -->
              <div
                v-if="component.required"
                class="absolute top-1 left-1 bg-red-100 text-red-800 text-xs font-medium px-2 py-1 rounded"
              >
                Required
              </div>

              <div class="flex items-start space-x-3">
                <div class="text-2xl">{{ component.icon }}</div>
                <div class="flex-1">
                  <h4 class="text-lg font-semibold text-gray-900 mb-1">
                    {{ component.name }}
                  </h4>
                  <p class="text-sm text-gray-600 mb-3">
                    {{ component.description }}
                  </p>
                  
                  <!-- Resource requirements -->
                  <div class="text-xs text-gray-500 mb-2">
                    <span class="mr-3">CPU: {{ component.resources.cpu }}</span>
                    <span class="mr-3">Memory: {{ component.resources.memory }}</span>
                    <span>Storage: {{ component.resources.storage }}</span>
                  </div>
                  
                  <!-- Features -->
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="feature in component.features.slice(0, 2)"
                      :key="feature"
                      class="inline-block bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded"
                    >
                      {{ feature }}
                    </span>
                    <span
                      v-if="component.features.length > 2"
                      class="inline-block text-gray-500 text-xs px-1"
                    >
                      +{{ component.features.length - 2 }} more
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Resource Summary -->
    <div class="mt-8 p-6 bg-gray-50 rounded-lg">
      <h4 class="text-lg font-semibold text-gray-900 mb-4">Resource Requirements Summary</h4>
      <div class="grid grid-cols-3 gap-4 text-center">
        <div class="bg-white p-4 rounded-lg">
          <div class="text-2xl font-bold text-blue-600">{{ totalResources.cpu }}m</div>
          <div class="text-sm text-gray-600">CPU</div>
        </div>
        <div class="bg-white p-4 rounded-lg">
          <div class="text-2xl font-bold text-green-600">{{ totalResources.memory.toFixed(1) }}Gi</div>
          <div class="text-sm text-gray-600">Memory</div>
        </div>
        <div class="bg-white p-4 rounded-lg">
          <div class="text-2xl font-bold text-purple-600">{{ totalResources.storage }}Gi</div>
          <div class="text-sm text-gray-600">Storage</div>
        </div>
      </div>
    </div>

    <!-- Selected Components Summary -->
    <div v-if="selectedComponents.length > 0" class="mt-6 p-4 bg-blue-50 rounded-lg">
      <h5 class="font-medium text-blue-900 mb-2">Selected Components ({{ selectedComponents.length }})</h5>
      <div class="flex flex-wrap gap-2">
        <span
          v-for="componentId in selectedComponents"
          :key="componentId"
          class="inline-block bg-blue-100 text-blue-800 text-sm px-3 py-1 rounded-full"
        >
          {{ availableComponents.find(c => c.id === componentId)?.name }}
        </span>
      </div>
    </div>

    <!-- Action buttons -->
    <div class="flex justify-between mt-8">
      <button
        @click="handleBack"
        class="btn btn-secondary"
      >
        Back to Environment
      </button>
      
      <button
        @click="handleNext"
        :disabled="selectedComponents.length === 0"
        class="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Continue to Configuration
      </button>
    </div>
  </div>
</template>

<style scoped>
.component-card {
  transition: transform 0.1s ease;
}

.component-card:hover:not(.cursor-not-allowed) {
  transform: translateY(-1px);
}

.component-card:active:not(.cursor-not-allowed) {
  transform: translateY(0);
}
</style>