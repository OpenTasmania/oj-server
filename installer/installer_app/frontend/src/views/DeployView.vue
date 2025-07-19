<script setup>
import { ref, reactive } from 'vue'

const isDeploying = ref(false)
const deploymentForm = reactive({
  env: 'local',
  images: [],
  overwrite: false,
  production: false
})

const availableImages = ref([
  'openjourney-server',
  'openjourney-web',
  'openjourney-api',
  'openjourney-database'
])

const environments = ref([
  { value: 'local', label: 'Local Development' },
  { value: 'staging', label: 'Staging' },
  { value: 'production', label: 'Production' }
])

const handleDeploy = async () => {
  isDeploying.value = true
  
  try {
    // TODO: Replace with actual API call
    console.log('Deploying with config:', deploymentForm)
    
    // Simulate deployment process
    await new Promise(resolve => setTimeout(resolve, 2000))
    
    alert('Deployment started successfully!')
  } catch (error) {
    console.error('Deployment failed:', error)
    alert('Deployment failed. Please try again.')
  } finally {
    isDeploying.value = false
  }
}

const toggleImage = (image) => {
  const index = deploymentForm.images.indexOf(image)
  if (index > -1) {
    deploymentForm.images.splice(index, 1)
  } else {
    deploymentForm.images.push(image)
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-2">Deploy OpenJourney Server</h1>
      <p class="text-gray-600">
        Configure and deploy OpenJourney Server to your chosen environment.
      </p>
    </div>

    <div class="card p-8">
      <form @submit.prevent="handleDeploy" class="space-y-6">
        <!-- Environment Selection -->
        <div>
          <label class="form-label">Environment</label>
          <select v-model="deploymentForm.env" class="form-input">
            <option v-for="env in environments" :key="env.value" :value="env.value">
              {{ env.label }}
            </option>
          </select>
          <p class="text-sm text-gray-500 mt-1">
            Select the target environment for deployment.
          </p>
        </div>

        <!-- Image Selection -->
        <div>
          <label class="form-label">Components to Deploy</label>
          <div class="space-y-2">
            <div v-for="image in availableImages" :key="image" class="flex items-center">
              <input
                :id="image"
                type="checkbox"
                :checked="deploymentForm.images.includes(image)"
                @change="toggleImage(image)"
                class="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
              >
              <label :for="image" class="ml-2 text-sm text-gray-700 capitalize">
                {{ image.replace('-', ' ') }}
              </label>
            </div>
          </div>
          <p class="text-sm text-gray-500 mt-1">
            Select which components to include in the deployment.
          </p>
        </div>

        <!-- Deployment Options -->
        <div class="space-y-4">
          <div class="flex items-center">
            <input
              id="overwrite"
              v-model="deploymentForm.overwrite"
              type="checkbox"
              class="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
            >
            <label for="overwrite" class="ml-2 text-sm text-gray-700">
              Overwrite existing deployment
            </label>
          </div>

          <div class="flex items-center">
            <input
              id="production"
              v-model="deploymentForm.production"
              type="checkbox"
              class="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
            >
            <label for="production" class="ml-2 text-sm text-gray-700">
              Production mode
            </label>
          </div>
        </div>

        <!-- Deployment Summary -->
        <div class="bg-gray-50 p-4 rounded-lg">
          <h3 class="text-sm font-medium text-gray-900 mb-2">Deployment Summary</h3>
          <div class="text-sm text-gray-600 space-y-1">
            <p><strong>Environment:</strong> {{ deploymentForm.env }}</p>
            <p><strong>Components:</strong> 
              {{ deploymentForm.images.length > 0 ? deploymentForm.images.join(', ') : 'None selected' }}
            </p>
            <p><strong>Options:</strong>
              <span v-if="deploymentForm.overwrite" class="ml-1">Overwrite enabled</span>
              <span v-if="deploymentForm.production" class="ml-1">Production mode</span>
              <span v-if="!deploymentForm.overwrite && !deploymentForm.production" class="ml-1">Default settings</span>
            </p>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex justify-end space-x-4">
          <RouterLink to="/" class="btn btn-secondary">
            Cancel
          </RouterLink>
          <button
            type="submit"
            :disabled="isDeploying || deploymentForm.images.length === 0"
            class="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="isDeploying" class="flex items-center">
              <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              Deploying...
            </span>
            <span v-else>Start Deployment</span>
          </button>
        </div>
      </form>
    </div>

    <!-- Deployment Status -->
    <div v-if="isDeploying" class="mt-8 card p-6">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">Deployment Progress</h3>
      <div class="space-y-3">
        <div class="flex items-center">
          <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-600 mr-3"></div>
          <span class="text-sm text-gray-600">Initializing deployment...</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-2">
          <div class="bg-primary-600 h-2 rounded-full animate-pulse" style="width: 30%"></div>
        </div>
      </div>
    </div>
  </div>
</template>