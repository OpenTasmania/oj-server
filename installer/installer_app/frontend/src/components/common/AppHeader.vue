<script setup>
import { ref } from 'vue'

const isMenuOpen = ref(false)

const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value
}
</script>

<template>
  <header class="bg-white shadow-sm border-b border-gray-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center h-16">
        <!-- Logo and Title -->
        <div class="flex items-center">
          <div class="flex-shrink-0">
            <h1 class="text-xl font-bold text-gray-900">
              OpenJourney Installer
            </h1>
          </div>
        </div>

        <!-- Desktop Navigation -->
        <nav class="hidden md:flex space-x-8">
          <RouterLink
            to="/"
            class="text-gray-500 hover:text-gray-700 px-3 py-2 rounded-md text-sm font-medium transition-colors"
            active-class="text-primary-600 bg-primary-50"
          >
            Home
          </RouterLink>
          <RouterLink
            to="/deploy"
            class="text-gray-500 hover:text-gray-700 px-3 py-2 rounded-md text-sm font-medium transition-colors"
            active-class="text-primary-600 bg-primary-50"
          >
            Deploy
          </RouterLink>
          <RouterLink
            to="/build"
            class="text-gray-500 hover:text-gray-700 px-3 py-2 rounded-md text-sm font-medium transition-colors"
            active-class="text-primary-600 bg-primary-50"
          >
            Build
          </RouterLink>
          <RouterLink
            to="/dashboard"
            class="text-gray-500 hover:text-gray-700 px-3 py-2 rounded-md text-sm font-medium transition-colors"
            active-class="text-primary-600 bg-primary-50"
          >
            Dashboard
          </RouterLink>
          <RouterLink
            to="/destroy"
            class="text-gray-500 hover:text-gray-700 px-3 py-2 rounded-md text-sm font-medium transition-colors"
            active-class="text-primary-600 bg-primary-50"
          >
            Destroy
          </RouterLink>
        </nav>

        <!-- System Status Indicator -->
        <div class="hidden md:flex items-center space-x-4">
          <div class="flex items-center space-x-2">
            <div class="w-2 h-2 bg-success-500 rounded-full"></div>
            <span class="text-sm text-gray-600">System Ready</span>
          </div>
        </div>

        <!-- Mobile menu button -->
        <div class="md:hidden">
          <button
            @click="toggleMenu"
            class="text-gray-500 hover:text-gray-700 focus:outline-none focus:text-gray-700 p-2"
          >
            <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                v-if="!isMenuOpen"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M4 6h16M4 12h16M4 18h16"
              />
              <path
                v-else
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Mobile Navigation Menu -->
    <div v-if="isMenuOpen" class="md:hidden">
      <div class="px-2 pt-2 pb-3 space-y-1 sm:px-3 bg-gray-50 border-t border-gray-200">
        <RouterLink
          to="/"
          @click="isMenuOpen = false"
          class="text-gray-500 hover:text-gray-700 block px-3 py-2 rounded-md text-base font-medium transition-colors"
          active-class="text-primary-600 bg-primary-50"
        >
          Home
        </RouterLink>
        <RouterLink
          to="/deploy"
          @click="isMenuOpen = false"
          class="text-gray-500 hover:text-gray-700 block px-3 py-2 rounded-md text-base font-medium transition-colors"
          active-class="text-primary-600 bg-primary-50"
        >
          Deploy
        </RouterLink>
        <RouterLink
          to="/build"
          @click="isMenuOpen = false"
          class="text-gray-500 hover:text-gray-700 block px-3 py-2 rounded-md text-base font-medium transition-colors"
          active-class="text-primary-600 bg-primary-50"
        >
          Build
        </RouterLink>
        <RouterLink
          to="/dashboard"
          @click="isMenuOpen = false"
          class="text-gray-500 hover:text-gray-700 block px-3 py-2 rounded-md text-base font-medium transition-colors"
          active-class="text-primary-600 bg-primary-50"
        >
          Dashboard
        </RouterLink>
        <RouterLink
          to="/destroy"
          @click="isMenuOpen = false"
          class="text-gray-500 hover:text-gray-700 block px-3 py-2 rounded-md text-base font-medium transition-colors"
          active-class="text-primary-600 bg-primary-50"
        >
          Destroy
        </RouterLink>
        <div class="px-3 py-2 border-t border-gray-200 mt-2 pt-2">
          <div class="flex items-center space-x-2">
            <div class="w-2 h-2 bg-success-500 rounded-full"></div>
            <span class="text-sm text-gray-600">System Ready</span>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>