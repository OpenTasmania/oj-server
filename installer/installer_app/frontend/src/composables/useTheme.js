import { ref, computed, watch, onMounted } from 'vue'

const THEME_KEY = 'openjourney-theme'
const THEMES = {
  light: 'light',
  dark: 'dark',
  system: 'system'
}

// Global theme state
const currentTheme = ref(THEMES.system)
const systemPrefersDark = ref(false)

export function useTheme() {
  // Computed theme (resolves 'system' to actual theme)
  const resolvedTheme = computed(() => {
    if (currentTheme.value === THEMES.system) {
      return systemPrefersDark.value ? THEMES.dark : THEMES.light
    }
    return currentTheme.value
  })

  const isDark = computed(() => resolvedTheme.value === THEMES.dark)
  const isLight = computed(() => resolvedTheme.value === THEMES.light)

  // Theme options for UI
  const themeOptions = [
    { value: THEMES.light, label: 'Light', icon: 'sun' },
    { value: THEMES.dark, label: 'Dark', icon: 'moon' },
    { value: THEMES.system, label: 'System', icon: 'computer-desktop' }
  ]

  // Set theme
  const setTheme = (theme) => {
    if (!Object.values(THEMES).includes(theme)) {
      console.warn(`Invalid theme: ${theme}`)
      return
    }
    
    currentTheme.value = theme
    localStorage.setItem(THEME_KEY, theme)
    applyTheme()
  }

  // Toggle between light and dark (skips system)
  const toggleTheme = () => {
    if (currentTheme.value === THEMES.system) {
      // If system, toggle to opposite of current system preference
      setTheme(systemPrefersDark.value ? THEMES.light : THEMES.dark)
    } else {
      // Toggle between light and dark
      setTheme(currentTheme.value === THEMES.light ? THEMES.dark : THEMES.light)
    }
  }

  // Apply theme to DOM
  const applyTheme = () => {
    const root = document.documentElement
    const theme = resolvedTheme.value
    
    // Remove existing theme classes
    root.classList.remove('light', 'dark')
    
    // Add current theme class
    root.classList.add(theme)
    
    // Update meta theme-color for mobile browsers
    updateMetaThemeColor(theme)
    
    // Dispatch custom event for other components to listen to
    window.dispatchEvent(new CustomEvent('theme-changed', { 
      detail: { theme, isDark: isDark.value } 
    }))
  }

  // Update meta theme color
  const updateMetaThemeColor = (theme) => {
    const metaThemeColor = document.querySelector('meta[name="theme-color"]')
    if (metaThemeColor) {
      const color = theme === THEMES.dark ? '#1f2937' : '#ffffff'
      metaThemeColor.setAttribute('content', color)
    }
  }

  // Detect system theme preference
  const detectSystemTheme = () => {
    if (typeof window !== 'undefined' && window.matchMedia) {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      systemPrefersDark.value = mediaQuery.matches
      
      // Listen for changes
      mediaQuery.addEventListener('change', (e) => {
        systemPrefersDark.value = e.matches
      })
    }
  }

  // Load saved theme from localStorage
  const loadSavedTheme = () => {
    if (typeof window !== 'undefined') {
      const savedTheme = localStorage.getItem(THEME_KEY)
      if (savedTheme && Object.values(THEMES).includes(savedTheme)) {
        currentTheme.value = savedTheme
      }
    }
  }

  // Initialize theme system
  const initializeTheme = () => {
    detectSystemTheme()
    loadSavedTheme()
    applyTheme()
  }

  // Get theme-specific CSS classes
  const getThemeClasses = (lightClasses = '', darkClasses = '') => {
    return computed(() => {
      return isDark.value ? darkClasses : lightClasses
    })
  }

  // Get theme-specific values
  const getThemeValue = (lightValue, darkValue) => {
    return computed(() => {
      return isDark.value ? darkValue : lightValue
    })
  }

  // CSS custom properties for theme colors
  const themeColors = computed(() => ({
    // Primary colors
    '--color-primary-50': isDark.value ? '#eff6ff' : '#eff6ff',
    '--color-primary-100': isDark.value ? '#dbeafe' : '#dbeafe',
    '--color-primary-500': isDark.value ? '#3b82f6' : '#3b82f6',
    '--color-primary-600': isDark.value ? '#2563eb' : '#2563eb',
    '--color-primary-700': isDark.value ? '#1d4ed8' : '#1d4ed8',
    
    // Background colors
    '--color-bg-primary': isDark.value ? '#111827' : '#ffffff',
    '--color-bg-secondary': isDark.value ? '#1f2937' : '#f9fafb',
    '--color-bg-tertiary': isDark.value ? '#374151' : '#f3f4f6',
    
    // Text colors
    '--color-text-primary': isDark.value ? '#f9fafb' : '#111827',
    '--color-text-secondary': isDark.value ? '#d1d5db' : '#6b7280',
    '--color-text-tertiary': isDark.value ? '#9ca3af' : '#9ca3af',
    
    // Border colors
    '--color-border-primary': isDark.value ? '#374151' : '#e5e7eb',
    '--color-border-secondary': isDark.value ? '#4b5563' : '#d1d5db',
    
    // Status colors
    '--color-success': isDark.value ? '#10b981' : '#059669',
    '--color-warning': isDark.value ? '#f59e0b' : '#d97706',
    '--color-error': isDark.value ? '#ef4444' : '#dc2626',
    '--color-info': isDark.value ? '#3b82f6' : '#2563eb'
  }))

  // Apply CSS custom properties
  const applyCSSCustomProperties = () => {
    const root = document.documentElement
    Object.entries(themeColors.value).forEach(([property, value]) => {
      root.style.setProperty(property, value)
    })
  }

  // Watch for theme changes
  watch(resolvedTheme, () => {
    applyTheme()
    applyCSSCustomProperties()
  })

  watch(systemPrefersDark, () => {
    if (currentTheme.value === THEMES.system) {
      applyTheme()
      applyCSSCustomProperties()
    }
  })

  // Initialize on mount
  onMounted(() => {
    initializeTheme()
    applyCSSCustomProperties()
  })

  return {
    // State
    currentTheme: computed(() => currentTheme.value),
    resolvedTheme,
    isDark,
    isLight,
    systemPrefersDark: computed(() => systemPrefersDark.value),
    
    // Theme options
    themeOptions,
    themes: THEMES,
    
    // Methods
    setTheme,
    toggleTheme,
    initializeTheme,
    
    // Utilities
    getThemeClasses,
    getThemeValue,
    themeColors,
    
    // CSS utilities
    applyCSSCustomProperties
  }
}

// Composable for theme-aware animations
export function useThemeTransitions() {
  const { isDark } = useTheme()
  
  const transitionClasses = computed(() => ({
    'transition-colors': true,
    'duration-200': true,
    'ease-in-out': true
  }))
  
  const fadeTransition = computed(() => ({
    name: 'theme-fade',
    mode: 'out-in'
  }))
  
  return {
    transitionClasses,
    fadeTransition,
    isDark
  }
}

// Composable for theme-aware icons
export function useThemeIcons() {
  const { isDark, currentTheme } = useTheme()
  
  const getThemeIcon = (theme) => {
    switch (theme) {
      case THEMES.light:
        return 'sun'
      case THEMES.dark:
        return 'moon'
      case THEMES.system:
        return 'computer-desktop'
      default:
        return 'sun'
    }
  }
  
  const currentThemeIcon = computed(() => getThemeIcon(currentTheme.value))
  
  return {
    getThemeIcon,
    currentThemeIcon,
    isDark
  }
}