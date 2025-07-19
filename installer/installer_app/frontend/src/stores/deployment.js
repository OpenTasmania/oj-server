import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '@/composables/useApi'

export const useDeploymentStore = defineStore('deployment', () => {
  const { deployment: deploymentApi } = useApi()
  
  // State
  const deployments = ref([])
  const currentDeployment = ref(null)
  const isDeploying = ref(false)
  const deploymentProgress = ref(0)
  const deploymentLogs = ref([])
  const deploymentError = ref(null)
  const pollingInterval = ref(null)

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
      console.log('Starting deployment with config:', config)
      
      // Call the actual API
      const response = await deploymentApi.create(config)
      const deploymentId = response.deployment_id
      
      // Start polling for status updates
      startPolling(deploymentId)
      
      return { id: deploymentId }
    } catch (error) {
      console.error('Deployment failed:', error)
      deploymentError.value = error.message
      addLog(`Deployment failed: ${error.message}`)
      throw error
    } finally {
      isDeploying.value = false
    }
  }

  const startPolling = (deploymentId) => {
    // Clear any existing polling
    stopPolling()
    
    // Poll every 2 seconds for status updates
    pollingInterval.value = setInterval(async () => {
      try {
        const status = await deploymentApi.getStatus(deploymentId)
        updateDeploymentStatus(deploymentId, status)
        
        // Stop polling if deployment is complete
        if (['completed', 'failed', 'cancelled'].includes(status.status)) {
          stopPolling()
        }
      } catch (error) {
        console.error('Error polling deployment status:', error)
      }
    }, 2000)
  }

  const stopPolling = () => {
    if (pollingInterval.value) {
      clearInterval(pollingInterval.value)
      pollingInterval.value = null
    }
  }

  const updateDeploymentStatus = (deploymentId, status) => {
    // Update deployment in list
    const index = deployments.value.findIndex(d => d.id === deploymentId)
    if (index > -1) {
      deployments.value[index] = { ...deployments.value[index], ...status }
    } else {
      // Add new deployment if not found
      deployments.value.push(status)
    }
    
    // Update current deployment if it matches
    if (currentDeployment.value?.id === deploymentId) {
      currentDeployment.value = status
      deploymentProgress.value = status.progress || 0
      
      // Update logs if available
      if (status.logs && Array.isArray(status.logs)) {
        deploymentLogs.value = status.logs
      }
      
      // Update error state
      if (status.error) {
        deploymentError.value = status.error
      }
    }
  }

  const fetchDeployments = async () => {
    try {
      const response = await deploymentApi.list()
      deployments.value = Object.values(response.deployments || {})
    } catch (error) {
      console.error('Error fetching deployments:', error)
    }
  }

  const getDeploymentStatus = async (deploymentId) => {
    try {
      return await deploymentApi.getStatus(deploymentId)
    } catch (error) {
      console.error('Error getting deployment status:', error)
      return null
    }
  }

  const cancelDeployment = async (deploymentId) => {
    try {
      await deploymentApi.cancel(deploymentId)
      
      // Update local state
      const deployment = deployments.value.find(d => d.id === deploymentId)
      if (deployment) {
        deployment.status = 'cancelled'
        deployment.completed_at = new Date().toISOString()
      }
      
      if (currentDeployment.value?.id === deploymentId) {
        currentDeployment.value.status = 'cancelled'
        isDeploying.value = false
        stopPolling()
      }
      
      addLog('Deployment cancelled by user')
    } catch (error) {
      console.error('Error cancelling deployment:', error)
      throw error
    }
  }

  const destroy = async (config) => {
    try {
      console.log('Starting destroy operation with config:', config)
      const response = await deploymentApi.destroy ? 
        await deploymentApi.destroy(config) : 
        await fetch('/api/v1/destroy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(config)
        }).then(r => r.json())
      
      const deploymentId = response.deployment_id
      startPolling(deploymentId)
      
      return { id: deploymentId }
    } catch (error) {
      console.error('Destroy operation failed:', error)
      throw error
    }
  }

  const addLog = (message, level = 'info') => {
    deploymentLogs.value.push({
      id: Date.now(),
      timestamp: new Date().toISOString(),
      message,
      level
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
      stopPolling()
    }
  }

  const setCurrentDeployment = (deployment) => {
    currentDeployment.value = deployment
    if (deployment && ['deploying', 'pending'].includes(deployment.status)) {
      startPolling(deployment.id)
    }
  }

  const resetDeploymentState = () => {
    currentDeployment.value = null
    isDeploying.value = false
    deploymentProgress.value = 0
    deploymentLogs.value = []
    deploymentError.value = null
    stopPolling()
  }

  const updateConfig = (config) => {
    // Store the current config for reference
    // This method is called by DeploymentWizard.vue to update configuration
    console.log('Updating deployment config:', config)
    // The config is typically used immediately for deployment, so we don't need to persist it
    // But we could store it in a reactive ref if needed for other components
  }

  // Initialize by fetching real deployments
  const initialize = async () => {
    await fetchDeployments()
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
    destroy,
    fetchDeployments,
    getDeploymentStatus,
    cancelDeployment,
    addLog,
    clearLogs,
    removeDeployment,
    setCurrentDeployment,
    resetDeploymentState,
    updateConfig,
    startPolling,
    stopPolling,
    initialize
  }
})