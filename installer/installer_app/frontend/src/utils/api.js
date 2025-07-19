import axios from 'axios'

// Create axios instance with default configuration
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000, // 30 seconds
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add timestamp to prevent caching
    config.params = {
      ...config.params,
      _t: Date.now()
    }
    
    // Log request in development
    if (import.meta.env.DEV) {
      console.log(`🚀 API Request: ${config.method?.toUpperCase()} ${config.url}`, {
        params: config.params,
        data: config.data
      })
    }
    
    return config
  },
  (error) => {
    console.error('Request interceptor error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    // Log response in development
    if (import.meta.env.DEV) {
      console.log(`✅ API Response: ${response.config.method?.toUpperCase()} ${response.config.url}`, {
        status: response.status,
        data: response.data
      })
    }
    
    return response
  },
  (error) => {
    // Log error in development
    if (import.meta.env.DEV) {
      console.error(`❌ API Error: ${error.config?.method?.toUpperCase()} ${error.config?.url}`, {
        status: error.response?.status,
        data: error.response?.data,
        message: error.message
      })
    }
    
    // Handle different error types
    if (error.response) {
      // Server responded with error status
      const { status, data } = error.response
      
      switch (status) {
        case 400:
          error.userMessage = data?.message || 'Invalid request. Please check your input.'
          break
        case 401:
          error.userMessage = 'Authentication required. Please log in.'
          break
        case 403:
          error.userMessage = 'Access denied. You do not have permission to perform this action.'
          break
        case 404:
          error.userMessage = 'The requested resource was not found.'
          break
        case 409:
          error.userMessage = data?.message || 'Conflict. The resource already exists or is in use.'
          break
        case 422:
          error.userMessage = data?.message || 'Validation failed. Please check your input.'
          break
        case 429:
          error.userMessage = 'Too many requests. Please wait a moment and try again.'
          break
        case 500:
          error.userMessage = 'Internal server error. Please try again later.'
          break
        case 502:
          error.userMessage = 'Service temporarily unavailable. Please try again later.'
          break
        case 503:
          error.userMessage = 'Service unavailable. Please try again later.'
          break
        default:
          error.userMessage = data?.message || `Server error (${status}). Please try again.`
      }
    } else if (error.request) {
      // Network error or no response
      if (error.code === 'ECONNABORTED') {
        error.userMessage = 'Request timeout. Please check your connection and try again.'
      } else {
        error.userMessage = 'Network error. Please check your connection and try again.'
      }
    } else {
      // Other error
      error.userMessage = 'An unexpected error occurred. Please try again.'
    }
    
    return Promise.reject(error)
  }
)

// API endpoints
export const endpoints = {
  // System endpoints
  system: {
    status: '/system/status',
    metrics: '/system/metrics',
    services: '/system/services',
    logs: '/system/logs'
  },
  
  // Deployment endpoints
  deployment: {
    list: '/deployments',
    create: '/deployments',
    get: (id) => `/deployments/${id}`,
    status: (id) => `/deployments/${id}/status`,
    cancel: (id) => `/deployments/${id}/cancel`,
    logs: (id) => `/deployments/${id}/logs`
  },
  
  // Build endpoints
  build: {
    list: '/builds',
    create: '/builds',
    get: (id) => `/builds/${id}`,
    status: (id) => `/builds/${id}/status`,
    cancel: (id) => `/builds/${id}/cancel`,
    logs: (id) => `/builds/${id}/logs`,
    artifacts: (id) => `/builds/${id}/artifacts`,
    download: (id, artifact) => `/builds/${id}/artifacts/${artifact}/download`
  },
  
  // Service management endpoints
  services: {
    list: '/services',
    get: (id) => `/services/${id}`,
    start: (id) => `/services/${id}/start`,
    stop: (id) => `/services/${id}/stop`,
    restart: (id) => `/services/${id}/restart`,
    logs: (id) => `/services/${id}/logs`
  }
}

// Utility functions
export const createFormData = (data) => {
  const formData = new FormData()
  
  Object.keys(data).forEach(key => {
    const value = data[key]
    
    if (Array.isArray(value)) {
      value.forEach(item => formData.append(key, item))
    } else if (value !== null && value !== undefined) {
      formData.append(key, value)
    }
  })
  
  return formData
}

export const downloadFile = async (url, filename) => {
  try {
    const response = await api.get(url, {
      responseType: 'blob'
    })
    
    const blob = new Blob([response.data])
    const downloadUrl = window.URL.createObjectURL(blob)
    
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    window.URL.revokeObjectURL(downloadUrl)
  } catch (error) {
    console.error('Download failed:', error)
    throw error
  }
}

export const uploadFile = async (url, file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  
  return api.post(url, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        onProgress(progress)
      }
    }
  })
}

// Export the configured axios instance
export default api