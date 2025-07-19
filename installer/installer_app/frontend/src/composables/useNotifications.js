import { ref, computed } from 'vue'

/**
 * Notification system composable
 * Provides toast notifications, alerts, and real-time notification management
 */

// Global notification state
const notifications = ref([])
const maxNotifications = 5
let notificationId = 0

export function useNotifications() {
  
  /**
   * Add a new notification
   */
  const addNotification = (notification) => {
    const id = ++notificationId
    const newNotification = {
      id,
      title: notification.title || '',
      message: notification.message || '',
      type: notification.type || 'info', // info, success, warning, error
      duration: notification.duration || 5000,
      persistent: notification.persistent || false,
      actions: notification.actions || [],
      timestamp: new Date().toISOString(),
      ...notification
    }

    // Add to beginning of array
    notifications.value.unshift(newNotification)

    // Limit number of notifications
    if (notifications.value.length > maxNotifications) {
      notifications.value = notifications.value.slice(0, maxNotifications)
    }

    // Auto-remove non-persistent notifications
    if (!newNotification.persistent && newNotification.duration > 0) {
      setTimeout(() => {
        removeNotification(id)
      }, newNotification.duration)
    }

    return id
  }

  /**
   * Remove a notification by ID
   */
  const removeNotification = (id) => {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index > -1) {
      notifications.value.splice(index, 1)
    }
  }

  /**
   * Clear all notifications
   */
  const clearNotifications = () => {
    notifications.value = []
  }

  /**
   * Clear notifications by type
   */
  const clearNotificationsByType = (type) => {
    notifications.value = notifications.value.filter(n => n.type !== type)
  }

  /**
   * Convenience methods for different notification types
   */
  const success = (message, options = {}) => {
    return addNotification({
      type: 'success',
      title: options.title || 'Success',
      message,
      ...options
    })
  }

  const error = (message, options = {}) => {
    return addNotification({
      type: 'error',
      title: options.title || 'Error',
      message,
      duration: options.duration || 8000, // Longer duration for errors
      ...options
    })
  }

  const warning = (message, options = {}) => {
    return addNotification({
      type: 'warning',
      title: options.title || 'Warning',
      message,
      duration: options.duration || 6000,
      ...options
    })
  }

  const info = (message, options = {}) => {
    return addNotification({
      type: 'info',
      title: options.title || 'Information',
      message,
      ...options
    })
  }

  /**
   * System event notifications
   */
  const deploymentStarted = (deploymentName) => {
    return success(`Deployment "${deploymentName}" has started`, {
      title: 'Deployment Started',
      actions: [
        { label: 'View Progress', action: 'view-deployment' }
      ]
    })
  }

  const deploymentCompleted = (deploymentName) => {
    return success(`Deployment "${deploymentName}" completed successfully`, {
      title: 'Deployment Complete',
      actions: [
        { label: 'View Details', action: 'view-deployment-details' }
      ]
    })
  }

  const deploymentFailed = (deploymentName, errorMessage) => {
    return error(`Deployment "${deploymentName}" failed: ${errorMessage}`, {
      title: 'Deployment Failed',
      persistent: true,
      actions: [
        { label: 'View Logs', action: 'view-deployment-logs' },
        { label: 'Retry', action: 'retry-deployment' }
      ]
    })
  }

  const buildStarted = (buildType) => {
    return info(`Build "${buildType}" has started`, {
      title: 'Build Started',
      actions: [
        { label: 'View Progress', action: 'view-build' }
      ]
    })
  }

  const buildCompleted = (buildType, size) => {
    return success(`Build "${buildType}" completed successfully (${size})`, {
      title: 'Build Complete',
      actions: [
        { label: 'Download', action: 'download-build' },
        { label: 'View Details', action: 'view-build-details' }
      ]
    })
  }

  const buildFailed = (buildType, errorMessage) => {
    return error(`Build "${buildType}" failed: ${errorMessage}`, {
      title: 'Build Failed',
      persistent: true,
      actions: [
        { label: 'View Logs', action: 'view-build-logs' },
        { label: 'Retry', action: 'retry-build' }
      ]
    })
  }

  const systemAlert = (message, severity = 'warning') => {
    const type = severity === 'critical' ? 'error' : severity
    return addNotification({
      type,
      title: 'System Alert',
      message,
      persistent: severity === 'critical',
      duration: severity === 'critical' ? 0 : 8000
    })
  }

  const componentStatusChanged = (componentName, status, previousStatus) => {
    const statusMessages = {
      healthy: 'is now healthy',
      warning: 'is experiencing issues',
      error: 'has failed',
      stopped: 'has been stopped'
    }

    const message = `${componentName} ${statusMessages[status] || `status changed to ${status}`}`
    
    if (status === 'error') {
      return error(message, {
        title: 'Component Alert',
        actions: [
          { label: 'View Details', action: 'view-component-details' },
          { label: 'Restart', action: 'restart-component' }
        ]
      })
    } else if (status === 'warning') {
      return warning(message, {
        title: 'Component Warning',
        actions: [
          { label: 'View Details', action: 'view-component-details' }
        ]
      })
    } else if (status === 'healthy' && previousStatus !== 'healthy') {
      return success(message, {
        title: 'Component Recovered'
      })
    }
  }

  /**
   * Get notifications by type
   */
  const getNotificationsByType = (type) => {
    return computed(() => notifications.value.filter(n => n.type === type))
  }

  /**
   * Get unread notifications count
   */
  const unreadCount = computed(() => {
    return notifications.value.filter(n => !n.read).length
  })

  /**
   * Mark notification as read
   */
  const markAsRead = (id) => {
    const notification = notifications.value.find(n => n.id === id)
    if (notification) {
      notification.read = true
    }
  }

  /**
   * Mark all notifications as read
   */
  const markAllAsRead = () => {
    notifications.value.forEach(n => n.read = true)
  }

  /**
   * Handle notification action
   */
  const handleAction = (notificationId, actionType) => {
    const notification = notifications.value.find(n => n.id === notificationId)
    if (notification) {
      // Emit custom event for action handling
      const event = new CustomEvent('notification-action', {
        detail: { notification, actionType }
      })
      window.dispatchEvent(event)
      
      // Mark as read when action is taken
      markAsRead(notificationId)
    }
  }

  return {
    // State
    notifications: computed(() => notifications.value),
    unreadCount,

    // Core methods
    addNotification,
    removeNotification,
    clearNotifications,
    clearNotificationsByType,
    markAsRead,
    markAllAsRead,
    handleAction,

    // Convenience methods
    success,
    error,
    warning,
    info,

    // System event methods
    deploymentStarted,
    deploymentCompleted,
    deploymentFailed,
    buildStarted,
    buildCompleted,
    buildFailed,
    systemAlert,
    componentStatusChanged,

    // Utility methods
    getNotificationsByType
  }
}