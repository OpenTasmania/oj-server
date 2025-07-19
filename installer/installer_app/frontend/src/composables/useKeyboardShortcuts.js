import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTheme } from './useTheme'
import { useNotificationsStore } from '@/stores/notifications'

// Global shortcuts registry
const globalShortcuts = ref(new Map())
const isEnabled = ref(true)
const pressedKeys = ref(new Set())

export function useKeyboardShortcuts() {
  const router = useRouter()
  const { toggleTheme } = useTheme()
  const notifications = useNotificationsStore()

  // Default global shortcuts
  const defaultShortcuts = {
    // Navigation shortcuts
    'ctrl+1': () => router.push('/'),
    'ctrl+2': () => router.push('/deploy'),
    'ctrl+3': () => router.push('/build'),
    'ctrl+4': () => router.push('/dashboard'),
    'ctrl+5': () => router.push('/destroy'),
    
    // Theme shortcuts
    'ctrl+shift+t': () => toggleTheme(),
    
    // Utility shortcuts
    'ctrl+k': (e) => {
      e.preventDefault()
      // Open command palette (if implemented)
      notifications.info('Command palette shortcut pressed', { title: 'Keyboard Shortcut' })
    },
    
    'ctrl+/': (e) => {
      e.preventDefault()
      showShortcutsHelp()
    },
    
    'escape': () => {
      // Close modals, clear selections, etc.
      document.dispatchEvent(new CustomEvent('escape-pressed'))
    },
    
    // Development shortcuts (only in development)
    'ctrl+shift+d': () => {
      if (import.meta.env.DEV) {
        console.log('Debug info:', {
          route: router.currentRoute.value,
          shortcuts: Array.from(globalShortcuts.value.keys())
        })
      }
    }
  }

  // Key combination parser
  const parseKeyCombo = (combo) => {
    const parts = combo.toLowerCase().split('+')
    return {
      ctrl: parts.includes('ctrl'),
      shift: parts.includes('shift'),
      alt: parts.includes('alt'),
      meta: parts.includes('meta') || parts.includes('cmd'),
      key: parts[parts.length - 1]
    }
  }

  // Check if key combination matches
  const matchesCombo = (event, combo) => {
    const parsed = parseKeyCombo(combo)
    return (
      event.ctrlKey === parsed.ctrl &&
      event.shiftKey === parsed.shift &&
      event.altKey === parsed.alt &&
      event.metaKey === parsed.meta &&
      event.key.toLowerCase() === parsed.key
    )
  }

  // Register a keyboard shortcut
  const registerShortcut = (combo, handler, options = {}) => {
    const {
      description = '',
      category = 'General',
      global = false,
      preventDefault = true
    } = options

    const shortcutData = {
      combo,
      handler,
      description,
      category,
      global,
      preventDefault,
      id: `${combo}-${Date.now()}`
    }

    globalShortcuts.value.set(combo, shortcutData)
    return shortcutData.id
  }

  // Unregister a keyboard shortcut
  const unregisterShortcut = (combo) => {
    return globalShortcuts.value.delete(combo)
  }

  // Handle keydown events
  const handleKeyDown = (event) => {
    if (!isEnabled.value) return

    // Track pressed keys for combinations
    pressedKeys.value.add(event.key.toLowerCase())

    // Check for registered shortcuts
    for (const [combo, shortcutData] of globalShortcuts.value) {
      if (matchesCombo(event, combo)) {
        if (shortcutData.preventDefault) {
          event.preventDefault()
        }
        
        try {
          shortcutData.handler(event)
        } catch (error) {
          console.error(`Error executing shortcut ${combo}:`, error)
        }
        break
      }
    }
  }

  // Handle keyup events
  const handleKeyUp = (event) => {
    pressedKeys.value.delete(event.key.toLowerCase())
  }

  // Enable/disable shortcuts
  const enableShortcuts = () => {
    isEnabled.value = true
  }

  const disableShortcuts = () => {
    isEnabled.value = false
  }

  // Show shortcuts help
  const showShortcutsHelp = () => {
    const shortcutsList = Array.from(globalShortcuts.value.values())
      .filter(s => s.description)
      .map(s => `${s.combo.toUpperCase()}: ${s.description}`)
      .join('\n')

    notifications.info(
      `Available keyboard shortcuts:\n\n${shortcutsList}`,
      {
        title: 'Keyboard Shortcuts',
        persistent: true,
        actions: [
          {
            label: 'Close',
            action: 'dismiss'
          }
        ]
      }
    )
  }

  // Get shortcuts by category
  const getShortcutsByCategory = () => {
    const categories = {}
    
    for (const shortcut of globalShortcuts.value.values()) {
      if (!shortcut.description) continue
      
      if (!categories[shortcut.category]) {
        categories[shortcut.category] = []
      }
      
      categories[shortcut.category].push({
        combo: shortcut.combo,
        description: shortcut.description
      })
    }
    
    return categories
  }

  // Format key combination for display
  const formatKeyCombo = (combo) => {
    return combo
      .split('+')
      .map(key => {
        switch (key.toLowerCase()) {
          case 'ctrl': return '⌃'
          case 'shift': return '⇧'
          case 'alt': return '⌥'
          case 'meta':
          case 'cmd': return '⌘'
          default: return key.toUpperCase()
        }
      })
      .join(' + ')
  }

  // Initialize shortcuts
  const initializeShortcuts = () => {
    // Register default shortcuts
    Object.entries(defaultShortcuts).forEach(([combo, handler]) => {
      const descriptions = {
        'ctrl+1': 'Go to Home',
        'ctrl+2': 'Go to Deploy',
        'ctrl+3': 'Go to Build',
        'ctrl+4': 'Go to Dashboard',
        'ctrl+5': 'Go to Destroy',
        'ctrl+shift+t': 'Toggle theme',
        'ctrl+k': 'Open command palette',
        'ctrl+/': 'Show keyboard shortcuts',
        'escape': 'Close modals/dialogs'
      }

      const categories = {
        'ctrl+1': 'Navigation',
        'ctrl+2': 'Navigation',
        'ctrl+3': 'Navigation',
        'ctrl+4': 'Navigation',
        'ctrl+5': 'Navigation',
        'ctrl+shift+t': 'Appearance',
        'ctrl+k': 'Utilities',
        'ctrl+/': 'Help',
        'escape': 'General'
      }

      registerShortcut(combo, handler, {
        description: descriptions[combo] || '',
        category: categories[combo] || 'General'
      })
    })

    // Add event listeners
    document.addEventListener('keydown', handleKeyDown)
    document.addEventListener('keyup', handleKeyUp)
  }

  // Cleanup
  const cleanup = () => {
    document.removeEventListener('keydown', handleKeyDown)
    document.removeEventListener('keyup', handleKeyUp)
  }

  // Lifecycle
  onMounted(() => {
    initializeShortcuts()
  })

  onUnmounted(() => {
    cleanup()
  })

  return {
    // State
    isEnabled: computed(() => isEnabled.value),
    pressedKeys: computed(() => Array.from(pressedKeys.value)),
    shortcuts: computed(() => Array.from(globalShortcuts.value.values())),
    
    // Methods
    registerShortcut,
    unregisterShortcut,
    enableShortcuts,
    disableShortcuts,
    showShortcutsHelp,
    getShortcutsByCategory,
    formatKeyCombo,
    
    // Utilities
    parseKeyCombo,
    matchesCombo
  }
}

// Composable for component-specific shortcuts
export function useComponentShortcuts(shortcuts = {}) {
  const componentShortcuts = ref(new Map())
  const isActive = ref(true)

  // Register component shortcuts
  const registerComponentShortcuts = () => {
    Object.entries(shortcuts).forEach(([combo, config]) => {
      const handler = typeof config === 'function' ? config : config.handler
      const options = typeof config === 'object' ? config : {}
      
      componentShortcuts.value.set(combo, { handler, options })
    })
  }

  // Handle component keydown
  const handleComponentKeyDown = (event) => {
    if (!isActive.value) return

    for (const [combo, { handler, options }] of componentShortcuts.value) {
      if (matchesCombo(event, combo)) {
        if (options.preventDefault !== false) {
          event.preventDefault()
        }
        
        try {
          handler(event)
        } catch (error) {
          console.error(`Error executing component shortcut ${combo}:`, error)
        }
        break
      }
    }
  }

  // Activate/deactivate component shortcuts
  const activate = () => {
    isActive.value = true
  }

  const deactivate = () => {
    isActive.value = false
  }

  // Helper to match key combinations (reuse from main composable)
  const matchesCombo = (event, combo) => {
    const parseKeyCombo = (combo) => {
      const parts = combo.toLowerCase().split('+')
      return {
        ctrl: parts.includes('ctrl'),
        shift: parts.includes('shift'),
        alt: parts.includes('alt'),
        meta: parts.includes('meta') || parts.includes('cmd'),
        key: parts[parts.length - 1]
      }
    }

    const parsed = parseKeyCombo(combo)
    return (
      event.ctrlKey === parsed.ctrl &&
      event.shiftKey === parsed.shift &&
      event.altKey === parsed.alt &&
      event.metaKey === parsed.meta &&
      event.key.toLowerCase() === parsed.key
    )
  }

  onMounted(() => {
    registerComponentShortcuts()
  })

  return {
    // State
    isActive: computed(() => isActive.value),
    shortcuts: computed(() => Array.from(componentShortcuts.value.keys())),
    
    // Methods
    handleComponentKeyDown,
    activate,
    deactivate,
    
    // Event handler for template use
    onKeydown: handleComponentKeyDown
  }
}

// Utility function to create shortcut help text
export function createShortcutHelp(shortcuts) {
  return Object.entries(shortcuts)
    .map(([combo, description]) => `${combo.toUpperCase()}: ${description}`)
    .join('\n')
}