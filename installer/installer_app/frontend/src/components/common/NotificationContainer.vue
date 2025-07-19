<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useNotifications } from '@/composables/useNotifications'

const { 
  notifications, 
  removeNotification, 
  markAsRead, 
  handleAction 
} = useNotifications()

const getNotificationIcon = (type) => {
  switch (type) {
    case 'success':
      return '✅'
    case 'error':
      return '❌'
    case 'warning':
      return '⚠️'
    case 'info':
      return 'ℹ️'
    default:
      return '📢'
  }
}

const getNotificationClass = (type) => {
  const baseClass = 'notification-item border-l-4 p-4 rounded-lg shadow-lg transition-all duration-300 transform'
  
  switch (type) {
    case 'success':
      return `${baseClass} bg-green-50 border-green-400 text-green-800`
    case 'error':
      return `${baseClass} bg-red-50 border-red-400 text-red-800`
    case 'warning':
      return `${baseClass} bg-yellow-50 border-yellow-400 text-yellow-800`
    case 'info':
      return `${baseClass} bg-blue-50 border-blue-400 text-blue-800`
    default:
      return `${baseClass} bg-gray-50 border-gray-400 text-gray-800`
  }
}

const handleNotificationClick = (notification) => {
  markAsRead(notification.id)
}

const handleNotificationAction = (notification, action) => {
  handleAction(notification.id, action.action)
}

const handleClose = (notification) => {
  removeNotification(notification.id)
}

const formatTimestamp = (timestamp) => {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  
  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`
  return date.toLocaleDateString()
}

// Handle notification actions from other parts of the app
const handleNotificationActionEvent = (event) => {
  const { notification, actionType } = event.detail
  console.log('Notification action:', actionType, notification)
  
  // Handle different action types
  switch (actionType) {
    case 'view-deployment':
      // Navigate to deployment view
      break
    case 'view-build':
      // Navigate to build view
      break
    case 'view-component-details':
      // Show component details
      break
    case 'restart-component':
      // Restart component
      break
    default:
      console.log('Unhandled notification action:', actionType)
  }
}

onMounted(() => {
  window.addEventListener('notification-action', handleNotificationActionEvent)
})

onUnmounted(() => {
  window.removeEventListener('notification-action', handleNotificationActionEvent)
})
</script>

<template>
  <div class="notification-container fixed top-4 right-4 z-50 space-y-3 max-w-sm">
    <TransitionGroup name="notification" tag="div">
      <div
        v-for="notification in notifications"
        :key="notification.id"
        :class="getNotificationClass(notification.type)"
        @click="handleNotificationClick(notification)"
      >
        <!-- Notification Header -->
        <div class="flex items-start justify-between mb-2">
          <div class="flex items-center space-x-2">
            <span class="text-lg">{{ getNotificationIcon(notification.type) }}</span>
            <h4 class="font-semibold text-sm">{{ notification.title }}</h4>
          </div>
          <div class="flex items-center space-x-2">
            <span class="text-xs opacity-75">{{ formatTimestamp(notification.timestamp) }}</span>
            <button
              @click.stop="handleClose(notification)"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>
        </div>

        <!-- Notification Message -->
        <p class="text-sm mb-3 opacity-90">{{ notification.message }}</p>

        <!-- Notification Actions -->
        <div v-if="notification.actions && notification.actions.length > 0" class="flex space-x-2">
          <button
            v-for="action in notification.actions"
            :key="action.action"
            @click.stop="handleNotificationAction(notification, action)"
            class="text-xs px-3 py-1 rounded-full border border-current hover:bg-current hover:text-white transition-colors"
          >
            {{ action.label }}
          </button>
        </div>

        <!-- Progress bar for timed notifications -->
        <div
          v-if="!notification.persistent && notification.duration > 0"
          class="absolute bottom-0 left-0 h-1 bg-current opacity-30 rounded-bl-lg notification-progress"
          :style="{ animationDuration: `${notification.duration}ms` }"
        ></div>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.notification-enter-active {
  transition: all 0.3s ease-out;
}

.notification-leave-active {
  transition: all 0.3s ease-in;
}

.notification-enter-from {
  opacity: 0;
  transform: translateX(100%) scale(0.9);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(100%) scale(0.9);
}

.notification-move {
  transition: transform 0.3s ease;
}

.notification-item {
  cursor: pointer;
  position: relative;
  overflow: hidden;
}

.notification-item:hover {
  transform: translateX(-4px);
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
}

.notification-progress {
  animation: progress-shrink linear forwards;
}

@keyframes progress-shrink {
  from {
    width: 100%;
  }
  to {
    width: 0%;
  }
}

/* Custom scrollbar for when there are many notifications */
.notification-container {
  max-height: calc(100vh - 2rem);
  overflow-y: auto;
}

.notification-container::-webkit-scrollbar {
  width: 4px;
}

.notification-container::-webkit-scrollbar-track {
  background: transparent;
}

.notification-container::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 2px;
}

.notification-container::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}
</style>