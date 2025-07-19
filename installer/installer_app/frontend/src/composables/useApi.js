import { ref, computed } from 'vue'
import api, { endpoints } from '@/utils/api'
import { useNotificationsStore } from '@/stores/notifications'

export function useApi() {
  const notifications = useNotificationsStore()
  
  // Global loading state
  const isLoading = ref(false)
  const error = ref(null)
  
  // Request wrapper with error handling
  const request = async (apiCall, options = {}) => {
    const {
      showErrorNotification = true,
      showSuccessNotification = false,
      successMessage = 'Operation completed successfully',
      loadingState = true
    } = options
    
    if (loadingState) {
      isLoading.value = true
    }
    error.value = null
    
    try {
      const response = await apiCall()
      
      if (showSuccessNotification) {
        notifications.success(successMessage)
      }
      
      return response.data
    } catch (err) {
      error.value = err
      
      if (showErrorNotification) {
        notifications.error(err.userMessage || err.message || 'An error occurred')
      }
      
      throw err
    } finally {
      if (loadingState) {
        isLoading.value = false
      }
    }
  }
  
  // System API methods
  const system = {
    getStatus: (options = {}) => 
      request(() => api.get(endpoints.system.status), options),
    
    getMetrics: (options = {}) => 
      request(() => api.get(endpoints.system.metrics), options),
    
    getServices: (options = {}) => 
      request(() => api.get(endpoints.system.services), options),
    
    getLogs: (params = {}, options = {}) => 
      request(() => api.get(endpoints.system.logs, { params }), options)
  }
  
  // Deployment API methods
  const deployment = {
    list: (params = {}, options = {}) => 
      request(() => api.get(endpoints.deployment.list, { params }), options),
    
    create: (data, options = {}) => 
      request(() => api.post(endpoints.deployment.create, data), {
        showSuccessNotification: true,
        successMessage: 'Deployment started successfully',
        ...options
      }),
    
    get: (id, options = {}) => 
      request(() => api.get(endpoints.deployment.get(id)), options),
    
    getStatus: (id, options = {}) => 
      request(() => api.get(endpoints.deployment.status(id)), options),
    
    cancel: (id, options = {}) => 
      request(() => api.post(endpoints.deployment.cancel(id)), {
        showSuccessNotification: true,
        successMessage: 'Deployment cancelled',
        ...options
      }),
    
    getLogs: (id, params = {}, options = {}) => 
      request(() => api.get(endpoints.deployment.logs(id), { params }), options)
  }
  
  // Build API methods
  const build = {
    list: (params = {}, options = {}) => 
      request(() => api.get(endpoints.build.list, { params }), options),
    
    create: (data, options = {}) => 
      request(() => api.post(endpoints.build.create, data), {
        showSuccessNotification: true,
        successMessage: 'Build started successfully',
        ...options
      }),
    
    get: (id, options = {}) => 
      request(() => api.get(endpoints.build.get(id)), options),
    
    getStatus: (id, options = {}) => 
      request(() => api.get(endpoints.build.status(id)), options),
    
    cancel: (id, options = {}) => 
      request(() => api.post(endpoints.build.cancel(id)), {
        showSuccessNotification: true,
        successMessage: 'Build cancelled',
        ...options
      }),
    
    getLogs: (id, params = {}, options = {}) => 
      request(() => api.get(endpoints.build.logs(id), { params }), options),
    
    getArtifacts: (id, options = {}) => 
      request(() => api.get(endpoints.build.artifacts(id)), options),
    
    downloadArtifact: async (id, artifactName, options = {}) => {
      try {
        const response = await api.get(endpoints.build.download(id, artifactName), {
          responseType: 'blob'
        })
        
        // Create download link
        const blob = new Blob([response.data])
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = artifactName
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)
        
        if (options.showSuccessNotification !== false) {
          notifications.success(`Downloaded ${artifactName}`)
        }
      } catch (err) {
        if (options.showErrorNotification !== false) {
          notifications.error(`Failed to download ${artifactName}`)
        }
        throw err
      }
    }
  }
  
  // Service management API methods
  const services = {
    list: (options = {}) => 
      request(() => api.get(endpoints.services.list), options),
    
    get: (id, options = {}) => 
      request(() => api.get(endpoints.services.get(id)), options),
    
    start: (id, options = {}) => 
      request(() => api.post(endpoints.services.start(id)), {
        showSuccessNotification: true,
        successMessage: `Service ${id} started`,
        ...options
      }),
    
    stop: (id, options = {}) => 
      request(() => api.post(endpoints.services.stop(id)), {
        showSuccessNotification: true,
        successMessage: `Service ${id} stopped`,
        ...options
      }),
    
    restart: (id, options = {}) => 
      request(() => api.post(endpoints.services.restart(id)), {
        showSuccessNotification: true,
        successMessage: `Service ${id} restarted`,
        ...options
      }),
    
    getLogs: (id, params = {}, options = {}) => 
      request(() => api.get(endpoints.services.logs(id), { params }), options)
  }
  
  return {
    // State
    isLoading: computed(() => isLoading.value),
    error: computed(() => error.value),
    
    // Generic request method
    request,
    
    // API methods
    system,
    deployment,
    build,
    services,
    
    // Utility methods
    clearError: () => {
      error.value = null
    }
  }
}

// Specialized composables for specific use cases
export function useSystemApi() {
  const { system, isLoading, error, clearError } = useApi()
  
  return {
    ...system,
    isLoading,
    error,
    clearError
  }
}

export function useDeploymentApi() {
  const { deployment, isLoading, error, clearError } = useApi()
  
  return {
    ...deployment,
    isLoading,
    error,
    clearError
  }
}

export function useBuildApi() {
  const { build, isLoading, error, clearError } = useApi()
  
  return {
    ...build,
    isLoading,
    error,
    clearError
  }
}

export function useServicesApi() {
  const { services, isLoading, error, clearError } = useApi()
  
  return {
    ...services,
    isLoading,
    error,
    clearError
  }
}

// WebSocket composable for real-time updates
export function useWebSocket(url) {
  const socket = ref(null)
  const isConnected = ref(false)
  const messages = ref([])
  const error = ref(null)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = ref(5)
  
  const connect = () => {
    try {
      socket.value = new WebSocket(url)
      
      socket.value.onopen = () => {
        isConnected.value = true
        error.value = null
        reconnectAttempts.value = 0
        console.log('WebSocket connected:', url)
      }
      
      socket.value.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          messages.value.push({
            ...data,
            timestamp: new Date().toISOString(),
            id: Date.now()
          })
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }
      
      socket.value.onclose = (event) => {
        isConnected.value = false
        console.log('WebSocket disconnected:', event.code, event.reason)
        
        // Attempt to reconnect if not a normal closure
        if (event.code !== 1000 && reconnectAttempts.value < maxReconnectAttempts.value) {
          setTimeout(() => {
            reconnectAttempts.value++
            console.log(`Reconnecting... (${reconnectAttempts.value}/${maxReconnectAttempts.value})`)
            connect()
          }, Math.pow(2, reconnectAttempts.value) * 1000) // Exponential backoff
        }
      }
      
      socket.value.onerror = (err) => {
        error.value = err
        console.error('WebSocket error:', err)
      }
    } catch (err) {
      error.value = err
      console.error('Failed to create WebSocket:', err)
    }
  }
  
  const send = (data) => {
    if (socket.value && isConnected.value) {
      socket.value.send(JSON.stringify(data))
    } else {
      console.warn('WebSocket not connected, cannot send message')
    }
  }
  
  const disconnect = () => {
    if (socket.value) {
      socket.value.close(1000, 'Manual disconnect')
    }
  }
  
  const clearMessages = () => {
    messages.value = []
  }
  
  return {
    socket: computed(() => socket.value),
    isConnected: computed(() => isConnected.value),
    messages: computed(() => messages.value),
    error: computed(() => error.value),
    reconnectAttempts: computed(() => reconnectAttempts.value),
    
    connect,
    send,
    disconnect,
    clearMessages,
    reconnect: connect
  }
}