<script setup>
import { ref, reactive } from 'vue'

const isDestroying = ref(false)
const showConfirmation = ref(false)
const destroyForm = reactive({
  env: 'local',
  images: []
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

const handleDestroy = async () => {
  isDestroying.value = true
  showConfirmation.value = false
  
  try {
    // TODO: Replace with actual API call
    console.log('Destroying with config:', destroyForm)
    
    // Simulate destroy process
    await new Promise(resolve => setTimeout(resolve, 2000))
    
    alert('Resources destroyed successfully!')
    
    // Reset form
    destroyForm.images = []
  } catch (error) {
    console.error('Destroy failed:', error)
    alert('Destroy operation failed. Please try again.')
  } finally {
    isDestroying.value = false
  }
}

const toggleImage = (image) => {
  const index = destroyForm.images.indexOf(image)
  if (index > -1) {
    destroyForm.images.splice(index, 1)
  } else {
    destroyForm.images.push(image)
  }
}

const confirmDestroy = () => {
  showConfirmation.value = true
}

const cancelDestroy = () => {
  showConfirmation.value = false
}
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-2">Destroy Resources</h1>
      <p class="text-gray-600">
        Clean up and remove deployed OpenJourney Server resources from your environment.
      </p>
    </div>

    <!-- Warning Banner -->
    <div class="bg-error-50 border border-error-200 rounded-lg p-4 mb-8">
      <div class="flex">
        <div class="flex-shrink-0">
          <svg class="h-5 w-5 text-error-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
        </div>
        <div class="ml-3">
          <h3 class="text-sm font-medium text-error-800">Destructive Operation</h3>
          <div class="mt-2 text-sm text-error-700">
            <p>This operation will permanently remove the selected resources. This action cannot be undone.</p>
          </div>
        </div>
      </div>
    </div>

    <div class="card p-8">
      <form @submit.prevent="confirmDestroy" class="space-y-6">
        <!-- Environment Selection -->
        <div>
          <label class="form-label">Environment</label>
          <select v-model="destroyForm.env" class="form-input">
            <option v-for="env in environments" :key="env.value" :value="env.value">
              {{ env.label }}
            </option>
          </select>
          <p class="text-sm text-gray-500 mt-1">
            Select the environment from which to remove resources.
          </p>
        </div>

        <!-- Component Selection -->
        <div>
          <label class="form-label">Components to Remove</label>
          <div class="space-y-2">
            <div v-for="image in availableImages" :key="image" class="flex items-center">
              <input
                :id="image"
                type="checkbox"
                :checked="destroyForm.images.includes(image)"
                @change="toggleImage(image)"
                class="h-4 w-4 text-error-600 focus:ring-error-500 border-gray-300 rounded"
              >
              <label :for="image" class="ml-2 text-sm text-gray-700 capitalize">
                {{ image.replace('-', ' ') }}
              </label>
            </div>
          </div>
          <p class="text-sm text-gray-500 mt-1">
            Select which components to remove from the deployment.
          </p>
        </div>

        <!-- Destroy Summary -->
        <div class="bg-error-50 p-4 rounded-lg border border-error-200">
          <h3 class="text-sm font-medium text-error-900 mb-2">Destruction Summary</h3>
          <div class="text-sm text-error-700 space-y-1">
            <p><strong>Environment:</strong> {{ destroyForm.env }}</p>
            <p><strong>Components to Remove:</strong> 
              {{ destroyForm.images.length > 0 ? destroyForm.images.join(', ') : 'None selected' }}
            </p>
            <p v-if="destroyForm.images.length > 0" class="font-medium">
              ⚠️ This will permanently delete all data associated with these components.
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
            :disabled="isDestroying || destroyForm.images.length === 0"
            class="btn btn-error disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="isDestroying" class="flex items-center">
              <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              Destroying...
            </span>
            <span v-else>Destroy Resources</span>
          </button>
        </div>
      </form>
    </div>

    <!-- Confirmation Modal -->
    <div v-if="showConfirmation" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div class="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
        <div class="mt-3 text-center">
          <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-error-100">
            <svg class="h-6 w-6 text-error-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h3 class="text-lg leading-6 font-medium text-gray-900 mt-4">Confirm Destruction</h3>
          <div class="mt-2 px-7 py-3">
            <p class="text-sm text-gray-500">
              Are you sure you want to destroy the selected resources? This action cannot be undone and will permanently delete all associated data.
            </p>
            <div class="mt-4 text-sm text-gray-700">
              <p><strong>Environment:</strong> {{ destroyForm.env }}</p>
              <p><strong>Components:</strong> {{ destroyForm.images.join(', ') }}</p>
            </div>
          </div>
          <div class="items-center px-4 py-3">
            <div class="flex space-x-3">
              <button
                @click="cancelDestroy"
                class="px-4 py-2 bg-gray-500 text-white text-base font-medium rounded-md shadow-sm hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-300"
              >
                Cancel
              </button>
              <button
                @click="handleDestroy"
                class="px-4 py-2 bg-error-600 text-white text-base font-medium rounded-md shadow-sm hover:bg-error-700 focus:outline-none focus:ring-2 focus:ring-error-300"
              >
                Yes, Destroy
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Destroy Progress -->
    <div v-if="isDestroying" class="mt-8 card p-6">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">Destruction Progress</h3>
      <div class="space-y-3">
        <div class="flex items-center">
          <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-error-600 mr-3"></div>
          <span class="text-sm text-gray-600">Removing resources...</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-2">
          <div class="bg-error-600 h-2 rounded-full animate-pulse" style="width: 60%"></div>
        </div>
      </div>
    </div>

    <!-- Current Deployments -->
    <div class="mt-8 card p-6">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">Current Deployments</h3>
      <div class="text-sm text-gray-500 text-center py-8">
        No active deployments found. Deploy resources first to see them here.
      </div>
    </div>
  </div>
</template>