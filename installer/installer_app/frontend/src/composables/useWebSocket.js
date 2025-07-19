import { ref, readonly, onMounted, onUnmounted, watch } from 'vue'

/**
 * WebSocket composable for real-time communication
 * Provides connection management, message handling, and automatic reconnection
 */
export function useWebSocket(url, options = {}) {
  const {
    autoConnect = true,
    reconnectInterval = 5000,
    maxReconnectAttempts = 10,
    heartbeatInterval = 30000,
    protocols = []
  } = options

  // Connection state
  const socket = ref(null)
  const isConnected = ref(false)
  const isConnecting = ref(false)
  const connectionError = ref(null)
  const reconnectAttempts = ref(0)

  // Message handling
  const messages = ref([])
  const lastMessage = ref(null)

  // Event listeners
  const eventListeners = ref(new Map())

  // Timers
  let reconnectTimer = null
  let heartbeatTimer = null

  /**
   * Connect to WebSocket server
   */
  const connect = () => {
    if (socket.value?.readyState === WebSocket.OPEN) {
      return Promise.resolve()
    }

    return new Promise((resolve, reject) => {
      try {
        isConnecting.value = true
        connectionError.value = null

        // Create WebSocket connection
        socket.value = new WebSocket(url, protocols)

        // Connection opened
        socket.value.onopen = (event) => {
          console.log('WebSocket connected:', url)
          isConnected.value = true
          isConnecting.value = false
          reconnectAttempts.value = 0
          connectionError.value = null

          // Start heartbeat
          startHeartbeat()

          // Emit connect event
          emitEvent('connect', event)
          resolve(event)
        }

        // Message received
        socket.value.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            
            // Handle heartbeat/ping messages
            if (data.type === 'ping') {
              send({ type: 'pong', timestamp: Date.now() })
              return
            }

            // Store message
            const message = {
              id: Date.now() + Math.random(),
              timestamp: new Date().toISOString(),
              data,
              raw: event.data
            }

            messages.value.push(message)
            lastMessage.value = message

            // Emit message event
            emitEvent('message', message)

            // Emit specific event type if available
            if (data.type) {
              emitEvent(data.type, data)
            }

          } catch (error) {
            console.error('Failed to parse WebSocket message:', error)
            emitEvent('error', { type: 'parse_error', error, raw: event.data })
          }
        }

        // Connection closed
        socket.value.onclose = (event) => {
          console.log('WebSocket disconnected:', event.code, event.reason)
          isConnected.value = false
          isConnecting.value = false

          // Stop heartbeat
          stopHeartbeat()

          // Emit disconnect event
          emitEvent('disconnect', event)

          // Attempt reconnection if not a clean close
          if (!event.wasClean && reconnectAttempts.value < maxReconnectAttempts) {
            scheduleReconnect()
          }
        }

        // Connection error
        socket.value.onerror = (event) => {
          console.error('WebSocket error:', event)
          connectionError.value = event
          isConnecting.value = false

          // Emit error event
          emitEvent('error', { type: 'connection_error', event })
          reject(event)
        }

      } catch (error) {
        console.error('Failed to create WebSocket connection:', error)
        connectionError.value = error
        isConnecting.value = false
        emitEvent('error', { type: 'creation_error', error })
        reject(error)
      }
    })
  }

  /**
   * Disconnect from WebSocket server
   */
  const disconnect = () => {
    if (socket.value) {
      // Clear timers
      clearReconnectTimer()
      stopHeartbeat()

      // Close connection
      socket.value.close(1000, 'Client disconnect')
      socket.value = null
    }

    isConnected.value = false
    isConnecting.value = false
    reconnectAttempts.value = 0
  }

  /**
   * Send message to WebSocket server
   */
  const send = (data) => {
    if (!socket.value || socket.value.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected, cannot send message:', data)
      return false
    }

    try {
      const message = typeof data === 'string' ? data : JSON.stringify(data)
      socket.value.send(message)
      
      // Emit send event
      emitEvent('send', { data, message })
      return true
    } catch (error) {
      console.error('Failed to send WebSocket message:', error)
      emitEvent('error', { type: 'send_error', error, data })
      return false
    }
  }

  /**
   * Schedule reconnection attempt
   */
  const scheduleReconnect = () => {
    if (reconnectAttempts.value >= maxReconnectAttempts) {
      console.error('Max reconnection attempts reached')
      emitEvent('reconnect_failed', { attempts: reconnectAttempts.value })
      return
    }

    clearReconnectTimer()
    
    const delay = reconnectInterval * Math.pow(1.5, reconnectAttempts.value) // Exponential backoff
    console.log(`Scheduling WebSocket reconnection in ${delay}ms (attempt ${reconnectAttempts.value + 1}/${maxReconnectAttempts})`)

    reconnectTimer = setTimeout(() => {
      reconnectAttempts.value++
      emitEvent('reconnect_attempt', { attempt: reconnectAttempts.value })
      connect().catch(() => {
        // Reconnection failed, will be handled by onclose
      })
    }, delay)
  }

  /**
   * Clear reconnection timer
   */
  const clearReconnectTimer = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  /**
   * Start heartbeat to keep connection alive
   */
  const startHeartbeat = () => {
    if (heartbeatInterval <= 0) return

    stopHeartbeat()
    heartbeatTimer = setInterval(() => {
      if (isConnected.value) {
        send({ type: 'ping', timestamp: Date.now() })
      }
    }, heartbeatInterval)
  }

  /**
   * Stop heartbeat
   */
  const stopHeartbeat = () => {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  /**
   * Add event listener
   */
  const on = (event, callback) => {
    if (!eventListeners.value.has(event)) {
      eventListeners.value.set(event, [])
    }
    eventListeners.value.get(event).push(callback)

    // Return unsubscribe function
    return () => off(event, callback)
  }

  /**
   * Remove event listener
   */
  const off = (event, callback) => {
    const listeners = eventListeners.value.get(event)
    if (listeners) {
      const index = listeners.indexOf(callback)
      if (index > -1) {
        listeners.splice(index, 1)
      }
    }
  }

  /**
   * Emit event to listeners
   */
  const emitEvent = (event, data) => {
    const listeners = eventListeners.value.get(event)
    if (listeners) {
      listeners.forEach(callback => {
        try {
          callback(data)
        } catch (error) {
          console.error(`Error in WebSocket event listener for '${event}':`, error)
        }
      })
    }
  }

  /**
   * Clear all messages
   */
  const clearMessages = () => {
    messages.value = []
    lastMessage.value = null
  }

  /**
   * Get connection status
   */
  const getStatus = () => {
    if (!socket.value) return 'disconnected'
    
    switch (socket.value.readyState) {
      case WebSocket.CONNECTING: return 'connecting'
      case WebSocket.OPEN: return 'connected'
      case WebSocket.CLOSING: return 'closing'
      case WebSocket.CLOSED: return 'disconnected'
      default: return 'unknown'
    }
  }

  // Auto-connect on mount if enabled
  onMounted(() => {
    if (autoConnect) {
      connect()
    }
  })

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect()
  })

  // Watch for URL changes
  watch(() => url, (newUrl, oldUrl) => {
    if (newUrl !== oldUrl && isConnected.value) {
      disconnect()
      if (autoConnect) {
        setTimeout(connect, 100) // Small delay to ensure cleanup
      }
    }
  })

  return {
    // Connection state
    socket: readonly(socket),
    isConnected: readonly(isConnected),
    isConnecting: readonly(isConnecting),
    connectionError: readonly(connectionError),
    reconnectAttempts: readonly(reconnectAttempts),

    // Messages
    messages: readonly(messages),
    lastMessage: readonly(lastMessage),

    // Methods
    connect,
    disconnect,
    send,
    on,
    off,
    clearMessages,
    getStatus
  }
}