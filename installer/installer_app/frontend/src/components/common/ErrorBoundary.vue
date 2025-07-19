<script setup>
import { ref, onErrorCaptured, provide } from 'vue'
import { useNotificationsStore } from '@/stores/notifications'

const props = defineProps({
  fallback: {
    type: Boolean,
    default: true
  },
  showDetails: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['error'])

const notifications = useNotificationsStore()
const hasError = ref(false)
const errorInfo = ref(null)
const errorId = ref(null)

// Capture errors from child components
onErrorCaptured((error, instance, info) => {
  hasError.value = true
  errorInfo.value = {
    error,
    instance,
    info,
    timestamp: new Date().toISOString(),
    userAgent: navigator.userAgent,
    url: window.location.href
  }

  // Log error to console for development
  console.error('ErrorBoundary caught an error:', error)
  console.error('Component info:', info)
  console.error('Instance:', instance)

  // Send error to notification system
  errorId.value = notifications.error(
    `Component error: ${error.message}`,
    {
      title: 'Application Error',
      persistent: true,
      data: errorInfo.value,
      actions: [
        {
          label: 'Reload Page',
          action: 'reload-page'
        },
        {
          label: 'Report Issue',
          action: 'report-issue'
        }
      ]
    }
  )

  // Emit error event for parent components
  emit('error', errorInfo.value)

  // Log error to external service (if configured)
  logErrorToService(errorInfo.value)

  // Prevent the error from propagating further
  return false
})

// Provide error recovery methods to child components
provide('errorBoundary', {
  recover: () => {
    hasError.value = false
    errorInfo.value = null
    if (errorId.value) {
      notifications.dismissNotification(errorId.value)
      errorId.value = null
    }
  },
  reportError: (customError) => {
    logErrorToService(customError || errorInfo.value)
  }
})

const logErrorToService = async (error) => {
  try {
    // In a real application, this would send to an error tracking service
    // like Sentry, LogRocket, or a custom endpoint
    const errorReport = {
      message: error.error?.message || 'Unknown error',
      stack: error.error?.stack,
      componentInfo: error.info,
      timestamp: error.timestamp,
      userAgent: error.userAgent,
      url: error.url,
      userId: null, // Would be populated if user is logged in
      sessionId: sessionStorage.getItem('sessionId') || 'anonymous'
    }

    // For now, just log to console
    console.log('Error report:', errorReport)
    
    // TODO: Implement actual error reporting service
    // await fetch('/api/v1/errors', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify(errorReport)
    // })
  } catch (reportingError) {
    console.error('Failed to report error:', reportingError)
  }
}

const handleReload = () => {
  window.location.reload()
}

const handleRetry = () => {
  hasError.value = false
  errorInfo.value = null
  if (errorId.value) {
    notifications.dismissNotification(errorId.value)
    errorId.value = null
  }
}
</script>

<template>
  <div class="error-boundary">
    <!-- Show error fallback UI if there's an error and fallback is enabled -->
    <div v-if="hasError && fallback" class="error-fallback">
      <div class="max-w-md mx-auto bg-white rounded-lg shadow-lg p-6 m-4">
        <div class="flex items-center mb-4">
          <div class="flex-shrink-0">
            <svg class="h-8 w-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <div class="ml-3">
            <h3 class="text-lg font-medium text-gray-900">
              Something went wrong
            </h3>
            <p class="text-sm text-gray-500">
              An unexpected error occurred in this component.
            </p>
          </div>
        </div>

        <!-- Error details (if enabled) -->
        <div v-if="showDetails && errorInfo" class="mb-4">
          <details class="bg-gray-50 rounded p-3">
            <summary class="cursor-pointer text-sm font-medium text-gray-700 mb-2">
              Error Details
            </summary>
            <div class="text-xs text-gray-600 space-y-2">
              <div>
                <strong>Message:</strong> {{ errorInfo.error?.message }}
              </div>
              <div>
                <strong>Component:</strong> {{ errorInfo.info }}
              </div>
              <div>
                <strong>Time:</strong> {{ new Date(errorInfo.timestamp).toLocaleString() }}
              </div>
            </div>
          </details>
        </div>

        <!-- Action buttons -->
        <div class="flex space-x-3">
          <button
            @click="handleRetry"
            class="flex-1 bg-primary-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            Try Again
          </button>
          <button
            @click="handleReload"
            class="flex-1 bg-gray-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
          >
            Reload Page
          </button>
        </div>
      </div>
    </div>

    <!-- Render children if no error or fallback is disabled -->
    <slot v-else />
  </div>
</template>

<style scoped>
.error-boundary {
  width: 100%;
  height: 100%;
}

.error-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}
</style>