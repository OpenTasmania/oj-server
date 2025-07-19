<script setup>
import { ref, computed, watch } from 'vue'
import { useDeploymentStore } from '@/stores/deployment'
import { useRouter } from 'vue-router'
import EnvironmentConfig from './EnvironmentConfig.vue'
import ComponentSelection from './ComponentSelection.vue'
import DeploymentConfig from './DeploymentConfig.vue'
import DeploymentReview from './DeploymentReview.vue'

const router = useRouter()
const deploymentStore = useDeploymentStore()

const currentStep = ref(1)
const totalSteps = 4

const deploymentConfig = ref({
  environment: '',
  components: [],
  resources: {
    cpu: '',
    memory: '',
    storage: ''
  },
  options: {
    overwrite: false,
    production: false,
    autoScale: false
  }
})

const stepTitles = [
  'Environment Selection',
  'Component Selection', 
  'Resource Configuration',
  'Review & Deploy'
]

const canProceed = computed(() => {
  switch (currentStep.value) {
    case 1: return deploymentConfig.value.environment !== ''
    case 2: return deploymentConfig.value.components.length > 0
    case 3: return deploymentConfig.value.resources.cpu && deploymentConfig.value.resources.memory
    case 4: return true
    default: return false
  }
})

const canGoBack = computed(() => currentStep.value > 1)
const canGoNext = computed(() => currentStep.value < totalSteps && canProceed.value)
const isLastStep = computed(() => currentStep.value === totalSteps)

const nextStep = () => {
  if (canGoNext.value) {
    currentStep.value++
  }
}

const previousStep = () => {
  if (canGoBack.value) {
    currentStep.value--
  }
}

const handleDeploy = async () => {
  try {
    await deploymentStore.deploy(deploymentConfig.value)
    router.push('/dashboard')
  } catch (error) {
    console.error('Deployment failed:', error)
    // Error handling will be improved in Phase 3
  }
}

// Watch for changes in deployment config to update store
watch(deploymentConfig, (newConfig) => {
  deploymentStore.updateConfig(newConfig)
}, { deep: true })
</script>

<template>
  <div class="deployment-wizard max-w-4xl mx-auto">
    <!-- Wizard Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-2">Deploy OpenJourney Server</h1>
      <p class="text-gray-600">
        Follow the steps below to configure and deploy OpenJourney Server to your chosen environment.
      </p>
    </div>

    <!-- Progress Steps -->
    <div class="wizard-steps mb-8">
      <div class="flex items-center justify-between">
        <div 
          v-for="step in totalSteps" 
          :key="step" 
          class="flex items-center"
          :class="{ 'flex-1': step < totalSteps }"
        >
          <div 
            class="step-indicator flex items-center justify-center w-10 h-10 rounded-full border-2 text-sm font-medium"
            :class="{
              'bg-primary-600 border-primary-600 text-white': currentStep >= step,
              'border-gray-300 text-gray-500': currentStep < step,
              'bg-green-600 border-green-600': currentStep > step
            }"
          >
            <span v-if="currentStep > step" class="text-white">✓</span>
            <span v-else>{{ step }}</span>
          </div>
          <div v-if="step < totalSteps" class="flex-1 mx-4">
            <div 
              class="h-1 rounded-full"
              :class="{
                'bg-primary-600': currentStep > step,
                'bg-gray-300': currentStep <= step
              }"
            ></div>
          </div>
        </div>
      </div>
      
      <!-- Step Labels -->
      <div class="flex justify-between mt-4">
        <div 
          v-for="(title, index) in stepTitles" 
          :key="index"
          class="text-sm text-center"
          :class="{
            'text-primary-600 font-medium': currentStep === index + 1,
            'text-gray-500': currentStep !== index + 1
          }"
          style="width: calc(100% / 4)"
        >
          {{ title }}
        </div>
      </div>
    </div>

    <!-- Wizard Content -->
    <div class="card p-8 min-h-96">
      <Transition name="slide" mode="out-in">
        <EnvironmentConfig 
          v-if="currentStep === 1" 
          v-model="deploymentConfig.environment"
          @next="nextStep"
        />
        <ComponentSelection 
          v-else-if="currentStep === 2" 
          v-model="deploymentConfig.components"
          @next="nextStep"
          @back="previousStep"
        />
        <DeploymentConfig 
          v-else-if="currentStep === 3" 
          v-model="deploymentConfig.resources"
          v-model:options="deploymentConfig.options"
          @next="nextStep"
          @back="previousStep"
        />
        <DeploymentReview 
          v-else-if="currentStep === 4" 
          :config="deploymentConfig"
          @deploy="handleDeploy"
          @back="previousStep"
        />
      </Transition>
    </div>

    <!-- Wizard Controls -->
    <div class="wizard-controls flex justify-between mt-8">
      <button 
        @click="previousStep"
        :disabled="!canGoBack"
        class="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Previous
      </button>
      
      <div class="flex space-x-4">
        <RouterLink to="/" class="btn btn-outline">
          Cancel
        </RouterLink>
        <button 
          v-if="!isLastStep"
          @click="nextStep"
          :disabled="!canProceed"
          class="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from {
  opacity: 0;
  transform: translateX(30px);
}

.slide-leave-to {
  opacity: 0;
  transform: translateX(-30px);
}

.wizard-steps {
  max-width: 600px;
  margin: 0 auto;
}

.step-indicator {
  transition: all 0.3s ease;
}
</style>