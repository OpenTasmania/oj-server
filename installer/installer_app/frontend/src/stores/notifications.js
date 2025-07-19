import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useNotificationsStore = defineStore('notifications', () => {
  // State
  const notifications = ref([])
  const maxNotifications = ref(5)
  const defaultDuration = ref(5000) // 5 seconds

  // Getters
  const activeNotifications = computed(() =>
    notifications.value.filter(n => !n.dismissed)
  )

  const errorNotifications = computed(() =>
    activeNotifications.value.filter(n => n.type === 'error')
  )

  const warningNotifications = computed(() =>
    activeNotifications.value.filter(n => n.type === 'warning')
  )

  const successNotifications = computed(() =>
    activeNotifications.value.filter(n => n.type === 'success')
  )

  const infoNotifications = computed(() =>
    activeNotifications.value.filter(n => n.type === 'info')
  )

  const hasUnreadNotifications = computed(() =>
    activeNotifications.value.some(n => !n.read)
  )

  const unreadCount = computed(() =>
    activeNotifications.value.filter(n => !n.read).length
  )

  // Actions
  const addNotification = (notification) => {
    const id = Date.now().toString()
    const newNotification = {
      id,
      type: notification.type || 'info',
      title: notification.title || '',
      message: notification.message || '',
      duration: notification.duration ?? defaultDuration.value,
      persistent: notification.persistent || false,
      actions: notification.actions || [],
      data: notification.data || null,
      createdAt: new Date().toISOString(),
      read: false,
      dismissed: false
    }

    notifications.value.unshift(newNotification)

    // Limit the number of notifications
    if (notifications.value.length > maxNotifications.value * 2) {
      notifications.value = notifications.value.slice(0, maxNotifications.value * 2)
    }

    // Auto-dismiss non-persistent notifications
    if (!newNotification.persistent && newNotification.duration > 0) {
      setTimeout(() => {
        dismissNotification(id)
      }, newNotification.duration)
    }

    return id
  }

  const success = (message, options = {}) => {
    return addNotification({
      type: 'success',
      message,
      title: options.title || 'Success',
      ...options
    })
  }

  const error = (message, options = {}) => {
    return addNotification({
      type: 'error',
      message,
      title: options.title || 'Error',
      persistent: options.persistent ?? true, // Errors are persistent by default
      ...options
    })
  }

  const warning = (message, options = {}) => {
    return addNotification({
      type: 'warning',
      message,
      title: options.title || 'Warning',
      ...options
    })
  }

  const info = (message, options = {}) => {
    return addNotification({
      type: 'info',
      message,
      title: options.title || 'Information',
      ...options
    })
  }

  const dismissNotification = (id) => {
    const notification = notifications.value.find(n => n.id === id)
    if (notification) {
      notification.dismissed = true
      notification.dismissedAt = new Date().toISOString()
    }
  }

  const markAsRead = (id) => {
    const notification = notifications.value.find(n => n.id === id)
    if (notification) {
      notification.read = true
      notification.readAt = new Date().toISOString()
    }
  }

  const markAllAsRead = () => {
    activeNotifications.value.forEach(notification => {
      notification.read = true
      notification.readAt = new Date().toISOString()
    })
  }

  const removeNotification = (id) => {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index > -1) {
      notifications.value.splice(index, 1)
    }
  }

  const clearAll = () => {
    activeNotifications.value.forEach(notification => {
      notification.dismissed = true
      notification.dismissedAt = new Date().toISOString()
    })
  }

  const clearByType = (type) => {
    activeNotifications.value
      .filter(n => n.type === type)
      .forEach(notification => {
        notification.dismissed = true
        notification.dismissedAt = new Date().toISOString()
      })
  }

  const getNotification = (id) => {
    return notifications.value.find(n => n.id === id)
  }

  // Utility methods for common notification patterns
  const deploymentStarted = (deploymentName) => {
    return info(`Deployment "${deploymentName}" has started`, {
      title: 'Deployment Started',
      persistent: true,
      actions: [
        {
          label: 'View Progress',
          action: 'view-deployment'
        }
      ]
    })
  }

  const deploymentCompleted = (deploymentName) => {
    return success(`Deployment "${deploymentName}" completed successfully`, {
      title: 'Deployment Complete',
      actions: [
        {
          label: 'View Dashboard',
          action: 'view-dashboard'
        }
      ]
    })
  }

  const deploymentFailed = (deploymentName, errorMessage) => {
    return error(`Deployment "${deploymentName}" failed: ${errorMessage}`, {
      title: 'Deployment Failed',
      persistent: true,
      actions: [
        {
          label: 'View Logs',
          action: 'view-logs'
        },
        {
          label: 'Retry',
          action: 'retry-deployment'
        }
      ]
    })
  }

  const buildStarted = (buildType) => {
    return info(`Build "${buildType}" has started`, {
      title: 'Build Started',
      persistent: true,
      actions: [
        {
          label: 'View Progress',
          action: 'view-build'
        }
      ]
    })
  }

  const buildCompleted = (buildType, artifacts) => {
    return success(`Build "${buildType}" completed successfully`, {
      title: 'Build Complete',
      data: { artifacts },
      actions: [
        {
          label: 'Download',
          action: 'download-artifacts'
        }
      ]
    })
  }

  const buildFailed = (buildType, errorMessage) => {
    return error(`Build "${buildType}" failed: ${errorMessage}`, {
      title: 'Build Failed',
      persistent: true,
      actions: [
        {
          label: 'View Logs',
          action: 'view-build-logs'
        },
        {
          label: 'Retry',
          action: 'retry-build'
        }
      ]
    })
  }

  const systemAlert = (message, severity = 'warning') => {
    return addNotification({
      type: severity,
      message,
      title: 'System Alert',
      persistent: severity === 'error',
      actions: severity === 'error' ? [
        {
          label: 'View System',
          action: 'view-system'
        }
      ] : []
    })
  }

  const serviceStatusChanged = (serviceName, status) => {
    const type = status === 'running' ? 'success' : 
                 status === 'stopped' ? 'warning' : 'error'
    
    return addNotification({
      type,
      message: `Service "${serviceName}" is now ${status}`,
      title: 'Service Status Changed',
      persistent: type === 'error'
    })
  }

  // Initialize with mock notifications for development
  const initializeMockData = () => {
    // Add some sample notifications
    setTimeout(() => {
      info('Welcome to OpenJourney Installer', {
        title: 'Welcome',
        duration: 8000
      })
    }, 1000)

    setTimeout(() => {
      success('System initialization completed', {
        title: 'System Ready'
      })
    }, 2000)
  }

  return {
    // State
    notifications,
    maxNotifications,
    defaultDuration,
    
    // Getters
    activeNotifications,
    errorNotifications,
    warningNotifications,
    successNotifications,
    infoNotifications,
    hasUnreadNotifications,
    unreadCount,
    
    // Actions
    addNotification,
    success,
    error,
    warning,
    info,
    dismissNotification,
    markAsRead,
    markAllAsRead,
    removeNotification,
    clearAll,
    clearByType,
    getNotification,
    
    // Utility methods
    deploymentStarted,
    deploymentCompleted,
    deploymentFailed,
    buildStarted,
    buildCompleted,
    buildFailed,
    systemAlert,
    serviceStatusChanged,
    initializeMockData
  }
})