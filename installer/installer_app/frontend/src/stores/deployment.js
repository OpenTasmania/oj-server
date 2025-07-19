import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useDeploymentStore = defineStore('deployment', () => {
  // State
  const deployments = ref([])
  const currentDeployment = ref(null)
  const isDeploying = ref(false)
  const deploymentProgress = ref(0)
  const deploymentLogs = ref([])
  const deploymentError = ref(null)

  // Getters
  const activeDeployments = computed(() => 
    deployments.value.filter(d => d.status === 'running' || d.status === 'deploying')
  )

  const completedDeployments = computed(() =>
    deployments.value.filter(d => d.status === 'completed')
  )

  const failedDeployments = computed(() =>
    deployments.value.filter(d => d.status === 'failed')
  )

  const hasActiveDeployments = computed(() => activeDeployments.value.length > 0)

  // Actions
  const deploy = async (config) => {
    isDeploying.value = true
    deploymentError.value = null
    deploymentProgress.value = 0
    deploymentLogs.value = []

    try {
      // TODO: Replace with actual API call
      console.log('Starting deployment with config:', config)
      
      // Simulate deployment process
      const deploymentId = Date.now().toString()
      const newDeployment = {
        id: deploymentId,
        name: `${config.env} Deployment`,
        environment: config.env,
        components: config.images,
        status: 'deploying',
        progress: 0,
        startedAt: new Date().toISOString(),
        config: { ...config }
      }

      deployments.value.push(newDeployment)
      currentDeployment.value = newDeployment

      // Simulate progress updates
      for (let i = 0; i <= 100; i += 10) {
        await new Promise(resolve => setTimeout(resolve, 200))
        deploymentProgress.value = i
        newDeployment.progress = i
        
        addLog(`Deployment progress: ${i}%`)
        
        if (i === 50) {
          addLog('Installing components...')
        } else if (i === 80) {
          addLog('Configuring services...')
        } else if (i === 100) {
          addLog('Deployment completed successfully!')
          newDeployment.status = 'completed'
          newDeployment.completedAt = new Date().toISOString()
        }
      }

      return newDeployment
    } catch (error) {
      console.error('Deployment failed:', error)
      deploymentError.value = error.message
      
      if (currentDeployment.value) {
        currentDeployment.value.status = 'failed'
        currentDeployment.value.error = error.message
      }
      
      addLog(`Deployment failed: ${error.message}`)
      throw error
    } finally {
      isDeploying.value = false
    }
  }

  const getDeploymentStatus = async (deploymentId) => {
    // TODO: Replace with actual API call
    const deployment = deployments.value.find(d => d.id === deploymentId)
    return deployment || null
  }

  const cancelDeployment = async (deploymentId) => {
    // TODO: Replace with actual API call
    const deployment = deployments.value.find(d => d.id === deploymentId)
    if (deployment && deployment.status === 'deploying') {
      deployment.status = 'cancelled'
      deployment.cancelledAt = new Date().toISOString()
      addLog('Deployment cancelled by user')
    }
    
    if (currentDeployment.value?.id === deploymentId) {
      isDeploying.value = false
    }
  }

  const addLog = (message) => {
    deploymentLogs.value.push({
      id: Date.now(),
      timestamp: new Date().toISOString(),
      message,
      level: 'info'
    })
  }

  const clearLogs = () => {
    deploymentLogs.value = []
  }

  const removeDeployment = (deploymentId) => {
    const index = deployments.value.findIndex(d => d.id === deploymentId)
    if (index > -1) {
      deployments.value.splice(index, 1)
    }
    
    if (currentDeployment.value?.id === deploymentId) {
      currentDeployment.value = null
    }
  }

  const setCurrentDeployment = (deployment) => {
    currentDeployment.value = deployment
  }

  const resetDeploymentState = () => {
    currentDeployment.value = null
    isDeploying.value = false
    deploymentProgress.value = 0
    deploymentLogs.value = []
    deploymentError.value = null
  }

  // Initialize with mock data for development
  const initializeMockData = () => {
    deployments.value = [
      {
        id: '1',
        name: 'Local Development',
        environment: 'local',
        components: ['openjourney-server', 'openjourney-web'],
        status: 'running',
        progress: 100,
        startedAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
        completedAt: new Date(Date.now() - 2 * 60 * 60 * 1000 + 5 * 60 * 1000).toISOString(), // 5 minutes later
        config: {
          env: 'local',
          images: ['openjourney-server', 'openjourney-web'],
          overwrite: false,
          production: false
        }
      }
    ]
  }

  return {
    // State
    deployments,
    currentDeployment,
    isDeploying,
    deploymentProgress,
    deploymentLogs,
    deploymentError,
    
    // Getters
    activeDeployments,
    completedDeployments,
    failedDeployments,
    hasActiveDeployments,
    
    // Actions
    deploy,
    getDeploymentStatus,
    cancelDeployment,
    addLog,
    clearLogs,
    removeDeployment,
    setCurrentDeployment,
    resetDeploymentState,
    initializeMockData
  }
})