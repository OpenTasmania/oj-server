import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useSystemStore = defineStore('system', () => {
  // State
  const systemStatus = ref({
    overall: 'healthy',
    uptime: '0h 0m',
    lastUpdated: null
  })

  const systemMetrics = ref({
    cpu: {
      usage: 0,
      cores: 4,
      temperature: null
    },
    memory: {
      usage: 0,
      total: 8192, // MB
      available: 8192
    },
    disk: {
      usage: 0,
      total: 500000, // MB
      available: 500000
    },
    network: {
      bytesIn: 0,
      bytesOut: 0,
      packetsIn: 0,
      packetsOut: 0
    }
  })

  const services = ref([])
  const systemLogs = ref([])
  const isLoading = ref(false)
  const lastRefresh = ref(null)

  // Getters
  const healthyServices = computed(() =>
    services.value.filter(s => s.status === 'running')
  )

  const unhealthyServices = computed(() =>
    services.value.filter(s => s.status !== 'running')
  )

  const systemHealth = computed(() => {
    const unhealthyCount = unhealthyServices.value.length
    const totalServices = services.value.length
    
    if (totalServices === 0) return 'unknown'
    if (unhealthyCount === 0) return 'healthy'
    if (unhealthyCount < totalServices / 2) return 'warning'
    return 'critical'
  })

  const memoryUsagePercent = computed(() => {
    const total = systemMetrics.value.memory.total
    const available = systemMetrics.value.memory.available
    return total > 0 ? Math.round(((total - available) / total) * 100) : 0
  })

  const diskUsagePercent = computed(() => {
    const total = systemMetrics.value.disk.total
    const available = systemMetrics.value.disk.available
    return total > 0 ? Math.round(((total - available) / total) * 100) : 0
  })

  const formatUptime = computed(() => {
    // Parse uptime string and format it nicely
    return systemStatus.value.uptime
  })

  // Actions
  const fetchSystemStatus = async () => {
    isLoading.value = true
    
    try {
      // TODO: Replace with actual API call
      console.log('Fetching system status...')
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 500))
      
      // Update with mock data
      systemStatus.value = {
        overall: ['healthy', 'warning', 'critical'][Math.floor(Math.random() * 3)],
        uptime: `${Math.floor(Math.random() * 24)}h ${Math.floor(Math.random() * 60)}m`,
        lastUpdated: new Date().toISOString()
      }
      
      lastRefresh.value = new Date().toISOString()
    } catch (error) {
      console.error('Failed to fetch system status:', error)
      systemStatus.value.overall = 'unknown'
    } finally {
      isLoading.value = false
    }
  }

  const fetchSystemMetrics = async () => {
    try {
      // TODO: Replace with actual API call
      console.log('Fetching system metrics...')
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 300))
      
      // Update with mock data
      systemMetrics.value = {
        cpu: {
          usage: Math.floor(Math.random() * 100),
          cores: 4,
          temperature: Math.floor(Math.random() * 30) + 40 // 40-70°C
        },
        memory: {
          usage: Math.floor(Math.random() * 100),
          total: 8192,
          available: Math.floor(Math.random() * 4096) + 2048
        },
        disk: {
          usage: Math.floor(Math.random() * 100),
          total: 500000,
          available: Math.floor(Math.random() * 200000) + 100000
        },
        network: {
          bytesIn: Math.floor(Math.random() * 1000000),
          bytesOut: Math.floor(Math.random() * 1000000),
          packetsIn: Math.floor(Math.random() * 10000),
          packetsOut: Math.floor(Math.random() * 10000)
        }
      }
    } catch (error) {
      console.error('Failed to fetch system metrics:', error)
    }
  }

  const fetchServices = async () => {
    try {
      // TODO: Replace with actual API call
      console.log('Fetching services status...')
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 400))
      
      // Update with mock data
      services.value = [
        {
          id: 'openjourney-server',
          name: 'OpenJourney Server',
          status: 'running',
          port: 8080,
          uptime: '2h 34m',
          memory: '256 MB',
          cpu: '12%'
        },
        {
          id: 'openjourney-web',
          name: 'OpenJourney Web',
          status: 'running',
          port: 3000,
          uptime: '2h 34m',
          memory: '128 MB',
          cpu: '5%'
        },
        {
          id: 'openjourney-api',
          name: 'OpenJourney API',
          status: Math.random() > 0.8 ? 'stopped' : 'running',
          port: 8081,
          uptime: '2h 30m',
          memory: '192 MB',
          cpu: '8%'
        },
        {
          id: 'postgresql',
          name: 'PostgreSQL Database',
          status: 'running',
          port: 5432,
          uptime: '2h 34m',
          memory: '512 MB',
          cpu: '15%'
        }
      ]
    } catch (error) {
      console.error('Failed to fetch services:', error)
    }
  }

  const fetchSystemLogs = async (limit = 100) => {
    try {
      // TODO: Replace with actual API call
      console.log('Fetching system logs...')
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 300))
      
      // Generate mock logs
      const logLevels = ['info', 'warning', 'error', 'debug']
      const logMessages = [
        'System startup completed',
        'Service health check passed',
        'Database connection established',
        'Memory usage within normal limits',
        'Disk space check completed',
        'Network interface configured',
        'SSL certificate validated',
        'Backup process initiated'
      ]
      
      systemLogs.value = Array.from({ length: Math.min(limit, 50) }, (_, i) => ({
        id: Date.now() + i,
        timestamp: new Date(Date.now() - i * 60000).toISOString(),
        level: logLevels[Math.floor(Math.random() * logLevels.length)],
        message: logMessages[Math.floor(Math.random() * logMessages.length)],
        source: 'system'
      }))
    } catch (error) {
      console.error('Failed to fetch system logs:', error)
    }
  }

  const restartService = async (serviceId) => {
    try {
      // TODO: Replace with actual API call
      console.log(`Restarting service: ${serviceId}`)
      
      const service = services.value.find(s => s.id === serviceId)
      if (service) {
        service.status = 'restarting'
        
        // Simulate restart process
        await new Promise(resolve => setTimeout(resolve, 2000))
        
        service.status = 'running'
        service.uptime = '0m'
      }
    } catch (error) {
      console.error(`Failed to restart service ${serviceId}:`, error)
      const service = services.value.find(s => s.id === serviceId)
      if (service) {
        service.status = 'error'
      }
    }
  }

  const stopService = async (serviceId) => {
    try {
      // TODO: Replace with actual API call
      console.log(`Stopping service: ${serviceId}`)
      
      const service = services.value.find(s => s.id === serviceId)
      if (service) {
        service.status = 'stopping'
        
        // Simulate stop process
        await new Promise(resolve => setTimeout(resolve, 1000))
        
        service.status = 'stopped'
      }
    } catch (error) {
      console.error(`Failed to stop service ${serviceId}:`, error)
    }
  }

  const startService = async (serviceId) => {
    try {
      // TODO: Replace with actual API call
      console.log(`Starting service: ${serviceId}`)
      
      const service = services.value.find(s => s.id === serviceId)
      if (service) {
        service.status = 'starting'
        
        // Simulate start process
        await new Promise(resolve => setTimeout(resolve, 1500))
        
        service.status = 'running'
        service.uptime = '0m'
      }
    } catch (error) {
      console.error(`Failed to start service ${serviceId}:`, error)
      const service = services.value.find(s => s.id === serviceId)
      if (service) {
        service.status = 'error'
      }
    }
  }

  const refreshAll = async () => {
    await Promise.all([
      fetchSystemStatus(),
      fetchSystemMetrics(),
      fetchServices(),
      fetchSystemLogs()
    ])
  }

  const clearLogs = () => {
    systemLogs.value = []
  }

  // Initialize with mock data for development
  const initializeMockData = () => {
    systemStatus.value = {
      overall: 'healthy',
      uptime: '2h 34m',
      lastUpdated: new Date().toISOString()
    }
    
    systemMetrics.value = {
      cpu: {
        usage: 45,
        cores: 4,
        temperature: 52
      },
      memory: {
        usage: 62,
        total: 8192,
        available: 3112
      },
      disk: {
        usage: 78,
        total: 500000,
        available: 110000
      },
      network: {
        bytesIn: 1247892,
        bytesOut: 892341,
        packetsIn: 8934,
        packetsOut: 7821
      }
    }
    
    // Initialize services and logs
    fetchServices()
    fetchSystemLogs()
  }

  return {
    // State
    systemStatus,
    systemMetrics,
    services,
    systemLogs,
    isLoading,
    lastRefresh,
    
    // Getters
    healthyServices,
    unhealthyServices,
    systemHealth,
    memoryUsagePercent,
    diskUsagePercent,
    formatUptime,
    
    // Actions
    fetchSystemStatus,
    fetchSystemMetrics,
    fetchServices,
    fetchSystemLogs,
    restartService,
    stopService,
    startService,
    refreshAll,
    clearLogs,
    initializeMockData
  }
})