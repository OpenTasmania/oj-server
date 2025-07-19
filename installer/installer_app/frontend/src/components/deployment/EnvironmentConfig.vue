<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'next'])

const selectedEnvironment = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const environments = ref([
  {
    value: 'local',
    label: 'Local Development',
    description: 'Deploy to your local development environment for testing and development.',
    icon: '💻',
    features: ['Fast deployment', 'Debug mode enabled', 'Local storage', 'Development tools'],
    recommended: true
  },
  {
    value: 'staging',
    label: 'Staging Environment',
    description: 'Deploy to a staging environment for testing before production.',
    icon: '🧪',
    features: ['Production-like setup', 'Testing environment', 'Shared resources', 'CI/CD integration'],
    recommended: false
  },
  {
    value: 'production',
    label: 'Production Environment',
    description: 'Deploy to the production environment for live usage.',
    icon: '🚀',
    features: ['High availability', 'Optimized performance', 'Monitoring enabled', 'Backup systems'],
    recommended: false
  }
])

const selectEnvironment = (env) => {
  selectedEnvironment.value = env.value
}

const handleNext = () => {
  if (selectedEnvironment.value) {
    emit('next')
  }
}
</script>

<template>
  <div class="environment-config">
    <div class="mb-6">
      <h2 class="text-2xl font-semibold text-gray-900 mb-2">Select Deployment Environment</h2>
      <p class="text-gray-600">
        Choose the target environment where you want to deploy OpenJourney Server.
      </p>
    </div>

    <div class="space-y-4">
      <div
        v-for="env in environments"
        :key="env.value"
        class="environment-option relative cursor-pointer"
        @click="selectEnvironment(env)"
      >
        <div
          class="border-2 rounded-lg p-6 transition-all duration-200 hover:shadow-md"
          :class="{
            'border-primary-500 bg-primary-50': selectedEnvironment === env.value,
            'border-gray-200 hover:border-gray-300': selectedEnvironment !== env.value
          }"
        >
          <!-- Selection indicator -->
          <div class="absolute top-4 right-4">
            <div
              class="w-5 h-5 rounded-full border-2 flex items-center justify-center"
              :class="{
                'border-primary-500 bg-primary-500': selectedEnvironment === env.value,
                'border-gray-300': selectedEnvironment !== env.value
              }"
            >
              <div
                v-if="selectedEnvironment === env.value"
                class="w-2 h-2 bg-white rounded-full"
              ></div>
            </div>
          </div>

          <!-- Recommended badge -->
          <div
            v-if="env.recommended"
            class="absolute top-2 left-2 bg-green-100 text-green-800 text-xs font-medium px-2 py-1 rounded-full"
          >
            Recommended
          </div>

          <div class="flex items-start space-x-4">
            <div class="text-3xl">{{ env.icon }}</div>
            <div class="flex-1">
              <h3 class="text-lg font-semibold text-gray-900 mb-1">
                {{ env.label }}
              </h3>
              <p class="text-gray-600 mb-4">
                {{ env.description }}
              </p>
              
              <!-- Features list -->
              <div class="grid grid-cols-2 gap-2">
                <div
                  v-for="feature in env.features"
                  :key="feature"
                  class="flex items-center text-sm text-gray-500"
                >
                  <svg class="w-4 h-4 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
                  </svg>
                  {{ feature }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Environment Details -->
    <div v-if="selectedEnvironment" class="mt-8 p-6 bg-blue-50 rounded-lg">
      <h4 class="text-lg font-semibold text-blue-900 mb-2">Environment Configuration</h4>
      <div class="text-sm text-blue-800 space-y-2">
        <div v-if="selectedEnvironment === 'local'">
          <p><strong>Namespace:</strong> openjourney-local</p>
          <p><strong>Resource Limits:</strong> Development optimized</p>
          <p><strong>Storage:</strong> Local persistent volumes</p>
          <p><strong>Monitoring:</strong> Basic logging enabled</p>
        </div>
        <div v-else-if="selectedEnvironment === 'staging'">
          <p><strong>Namespace:</strong> openjourney-staging</p>
          <p><strong>Resource Limits:</strong> Medium allocation</p>
          <p><strong>Storage:</strong> Shared network storage</p>
          <p><strong>Monitoring:</strong> Full monitoring stack</p>
        </div>
        <div v-else-if="selectedEnvironment === 'production'">
          <p><strong>Namespace:</strong> openjourney-production</p>
          <p><strong>Resource Limits:</strong> High availability setup</p>
          <p><strong>Storage:</strong> Redundant storage with backups</p>
          <p><strong>Monitoring:</strong> Complete observability suite</p>
        </div>
      </div>
    </div>

    <!-- Action buttons -->
    <div class="flex justify-end mt-8">
      <button
        @click="handleNext"
        :disabled="!selectedEnvironment"
        class="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Continue to Component Selection
      </button>
    </div>
  </div>
</template>

<style scoped>
.environment-option {
  transition: transform 0.1s ease;
}

.environment-option:hover {
  transform: translateY(-1px);
}

.environment-option:active {
  transform: translateY(0);
}
</style>