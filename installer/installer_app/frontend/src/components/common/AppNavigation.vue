<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const breadcrumbs = computed(() => {
  const routeMap = {
    'home': { name: 'Home', icon: '🏠' },
    'deploy': { name: 'Deploy', icon: '🚀' },
    'build': { name: 'Build', icon: '🔧' },
    'dashboard': { name: 'Dashboard', icon: '📊' },
    'destroy': { name: 'Destroy', icon: '🗑️' }
  }
  
  return routeMap[route.name] || { name: 'Unknown', icon: '❓' }
})
</script>

<template>
  <!-- Breadcrumb Navigation -->
  <nav class="bg-white border-b border-gray-200 py-3 mb-6">
    <div class="flex items-center space-x-2 text-sm">
      <RouterLink 
        to="/" 
        class="text-gray-500 hover:text-gray-700 transition-colors"
      >
        Home
      </RouterLink>
      
      <span v-if="route.name !== 'home'" class="text-gray-400">/</span>
      
      <span 
        v-if="route.name !== 'home'" 
        class="flex items-center space-x-2 text-gray-900 font-medium"
      >
        <span>{{ breadcrumbs.icon }}</span>
        <span>{{ breadcrumbs.name }}</span>
      </span>
    </div>
  </nav>
</template>