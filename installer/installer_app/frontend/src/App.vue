<script setup>
import { RouterView } from 'vue-router'
import AppHeader from './components/common/AppHeader.vue'
import AppNavigation from './components/common/AppNavigation.vue'
import NotificationContainer from './components/common/NotificationContainer.vue'
import ErrorBoundary from './components/common/ErrorBoundary.vue'
</script>

<template>
  <div id="app" class="min-h-screen bg-gray-50">
    <AppHeader />
    <div class="flex">
      <AppNavigation />
      <main class="flex-1 p-6">
        <ErrorBoundary>
          <Suspense>
            <template #default>
              <RouterView />
            </template>
            <template #fallback>
              <div class="flex items-center justify-center h-64">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
              </div>
            </template>
          </Suspense>
        </ErrorBoundary>
      </main>
    </div>
    
    <!-- Global Notification Container -->
    <NotificationContainer />
  </div>
</template>

<style scoped>
/* Component-specific styles can go here */
</style>