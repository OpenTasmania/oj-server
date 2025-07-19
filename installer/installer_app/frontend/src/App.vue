<script setup>
import { RouterView } from 'vue-router'
import AppHeader from './components/common/AppHeader.vue'
import AppNavigation from './components/common/AppNavigation.vue'
</script>

<template>
  <div id="app" class="min-h-screen bg-gray-50">
    <AppHeader />
    <div class="flex">
      <AppNavigation />
      <main class="flex-1 p-6">
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
      </main>
    </div>
  </div>
</template>

<style scoped>
/* Component-specific styles can go here */
</style>