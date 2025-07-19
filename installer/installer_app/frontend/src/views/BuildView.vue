<script setup>
import { ref, reactive } from 'vue'

const isBuilding = ref(false)
const buildForm = reactive({
  build_type: 'deb',
  architecture: 'amd64',
  rpi_model: '4'
})

const buildTypes = ref([
  { value: 'deb', label: 'Debian Package (.deb)' },
  { value: 'amd64', label: 'AMD64 Installer' },
  { value: 'rpi64', label: 'Raspberry Pi 64-bit Installer' }
])

const architectures = ref([
  { value: 'amd64', label: 'AMD64 (x86_64)' },
  { value: 'arm64', label: 'ARM64 (aarch64)' },
  { value: 'armhf', label: 'ARM Hard Float' }
])

const rpiModels = ref([
  { value: '3', label: 'Raspberry Pi 3' },
  { value: '4', label: 'Raspberry Pi 4' },
  { value: '5', label: 'Raspberry Pi 5' }
])

const handleBuild = async () => {
  isBuilding.value = true
  
  try {
    // TODO: Replace with actual API call
    console.log('Building with config:', buildForm)
    
    // Simulate build process
    await new Promise(resolve => setTimeout(resolve, 3000))
    
    alert('Build started successfully!')
  } catch (error) {
    console.error('Build failed:', error)
    alert('Build failed. Please try again.')
  } finally {
    isBuilding.value = false
  }
}

const getBuildDescription = () => {
  switch (buildForm.build_type) {
    case 'deb':
      return 'Creates a Debian package that can be installed using dpkg or apt.'
    case 'amd64':
      return 'Creates a custom Debian installer ISO for AMD64 architecture.'
    case 'rpi64':
      return 'Creates a custom installer for Raspberry Pi 64-bit systems.'
    default:
      return 'Select a build type to see description.'
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-2">Build Installer Package</h1>
      <p class="text-gray-600">
        Create custom installer packages for different platforms and architectures.
      </p>
    </div>

    <div class="card p-8">
      <form @submit.prevent="handleBuild" class="space-y-6">
        <!-- Build Type Selection -->
        <div>
          <label class="form-label">Build Type</label>
          <select v-model="buildForm.build_type" class="form-input">
            <option v-for="type in buildTypes" :key="type.value" :value="type.value">
              {{ type.label }}
            </option>
          </select>
          <p class="text-sm text-gray-500 mt-1">
            {{ getBuildDescription() }}
          </p>
        </div>

        <!-- Architecture Selection (for deb packages) -->
        <div v-if="buildForm.build_type === 'deb'">
          <label class="form-label">Architecture</label>
          <select v-model="buildForm.architecture" class="form-input">
            <option v-for="arch in architectures" :key="arch.value" :value="arch.value">
              {{ arch.label }}
            </option>
          </select>
          <p class="text-sm text-gray-500 mt-1">
            Select the target architecture for the Debian package.
          </p>
        </div>

        <!-- Raspberry Pi Model Selection (for rpi64 builds) -->
        <div v-if="buildForm.build_type === 'rpi64'">
          <label class="form-label">Raspberry Pi Model</label>
          <select v-model="buildForm.rpi_model" class="form-input">
            <option v-for="model in rpiModels" :key="model.value" :value="model.value">
              {{ model.label }}
            </option>
          </select>
          <p class="text-sm text-gray-500 mt-1">
            Select the target Raspberry Pi model for optimization.
          </p>
        </div>

        <!-- Build Summary -->
        <div class="bg-gray-50 p-4 rounded-lg">
          <h3 class="text-sm font-medium text-gray-900 mb-2">Build Configuration</h3>
          <div class="text-sm text-gray-600 space-y-1">
            <p><strong>Build Type:</strong> {{ buildTypes.find(t => t.value === buildForm.build_type)?.label }}</p>
            <p v-if="buildForm.build_type === 'deb'">
              <strong>Architecture:</strong> {{ architectures.find(a => a.value === buildForm.architecture)?.label }}
            </p>
            <p v-if="buildForm.build_type === 'rpi64'">
              <strong>Raspberry Pi Model:</strong> {{ rpiModels.find(m => m.value === buildForm.rpi_model)?.label }}
            </p>
          </div>
        </div>

        <!-- Build Requirements -->
        <div class="bg-warning-50 border border-warning-200 rounded-lg p-4">
          <div class="flex">
            <div class="flex-shrink-0">
              <svg class="h-5 w-5 text-warning-400" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
              </svg>
            </div>
            <div class="ml-3">
              <h3 class="text-sm font-medium text-warning-800">Build Requirements</h3>
              <div class="mt-2 text-sm text-warning-700">
                <ul class="list-disc list-inside space-y-1">
                  <li>Sufficient disk space (minimum 2GB free)</li>
                  <li>Docker installed and running</li>
                  <li>Internet connection for downloading dependencies</li>
                  <li v-if="buildForm.build_type !== 'deb'">Root/sudo privileges for ISO creation</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex justify-end space-x-4">
          <RouterLink to="/" class="btn btn-secondary">
            Cancel
          </RouterLink>
          <button
            type="submit"
            :disabled="isBuilding"
            class="btn btn-success disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="isBuilding" class="flex items-center">
              <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              Building...
            </span>
            <span v-else>Start Build</span>
          </button>
        </div>
      </form>
    </div>

    <!-- Build Progress -->
    <div v-if="isBuilding" class="mt-8 card p-6">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">Build Progress</h3>
      <div class="space-y-4">
        <div class="flex items-center">
          <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-success-600 mr-3"></div>
          <span class="text-sm text-gray-600">Preparing build environment...</span>
        </div>
        
        <div class="space-y-2">
          <div class="flex justify-between text-sm">
            <span class="text-gray-600">Overall Progress</span>
            <span class="text-gray-900">25%</span>
          </div>
          <div class="w-full bg-gray-200 rounded-full h-2">
            <div class="bg-success-600 h-2 rounded-full animate-pulse" style="width: 25%"></div>
          </div>
        </div>

        <div class="text-xs text-gray-500 bg-gray-100 p-3 rounded font-mono">
          <div>Downloading base images...</div>
          <div>Installing dependencies...</div>
          <div>Configuring build environment...</div>
        </div>
      </div>
    </div>

    <!-- Build History -->
    <div class="mt-8 card p-6">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">Recent Builds</h3>
      <div class="text-sm text-gray-500 text-center py-8">
        No recent builds found. Start your first build above.
      </div>
    </div>
  </div>
</template>