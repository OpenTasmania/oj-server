<script setup>
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

const features = ref([
  {
    title: 'Deploy',
    description: 'Deploy OpenJourney Server to your environment with customizable configurations.',
    icon: '🚀',
    route: '/deploy',
    color: 'primary'
  },
  {
    title: 'Build',
    description: 'Build custom installer packages for different architectures and platforms.',
    icon: '🔧',
    route: '/build',
    color: 'success'
  },
  {
    title: 'Monitor',
    description: 'Monitor system status and view deployment progress in real-time.',
    icon: '📊',
    route: '/dashboard',
    color: 'warning'
  },
  {
    title: 'Destroy',
    description: 'Clean up and remove deployed resources when no longer needed.',
    icon: '🗑️',
    route: '/destroy',
    color: 'error'
  }
])
</script>

<template>
  <div class="max-w-7xl mx-auto">
    <!-- Hero Section -->
    <div class="text-center mb-12">
      <h1 class="text-4xl font-bold text-gray-900 mb-4">
        OpenJourney Server Installer
      </h1>
      <p class="text-xl text-gray-600 max-w-3xl mx-auto">
        A modern, user-friendly interface for deploying, managing, and monitoring your OpenJourney Server installation.
        Built with Vue.js 3.5 for a seamless experience.
      </p>
    </div>

    <!-- Feature Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
      <RouterLink
        v-for="feature in features"
        :key="feature.title"
        :to="feature.route"
        class="card p-6 hover:shadow-lg transition-shadow duration-200 group cursor-pointer"
      >
        <div class="text-center">
          <div class="text-4xl mb-4">{{ feature.icon }}</div>
          <h3 class="text-lg font-semibold text-gray-900 mb-2 group-hover:text-primary-600 transition-colors">
            {{ feature.title }}
          </h3>
          <p class="text-gray-600 text-sm">
            {{ feature.description }}
          </p>
        </div>
      </RouterLink>
    </div>

    <!-- Quick Actions -->
    <div class="card p-8">
      <h2 class="text-2xl font-bold text-gray-900 mb-6 text-center">Quick Actions</h2>
      <div class="flex flex-wrap justify-center gap-4">
        <RouterLink to="/deploy" class="btn btn-primary">
          Start Deployment
        </RouterLink>
        <RouterLink to="/dashboard" class="btn btn-secondary">
          View Dashboard
        </RouterLink>
        <RouterLink to="/build" class="btn btn-success">
          Build Package
        </RouterLink>
      </div>
    </div>

    <!-- System Status Preview -->
    <div class="mt-8 card p-6">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">System Status</h3>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="text-center p-4 bg-success-50 rounded-lg">
          <div class="text-success-600 font-semibold">System</div>
          <div class="text-2xl font-bold text-success-700">Ready</div>
        </div>
        <div class="text-center p-4 bg-primary-50 rounded-lg">
          <div class="text-primary-600 font-semibold">Services</div>
          <div class="text-2xl font-bold text-primary-700">0/0</div>
        </div>
        <div class="text-center p-4 bg-warning-50 rounded-lg">
          <div class="text-warning-600 font-semibold">Deployments</div>
          <div class="text-2xl font-bold text-warning-700">None</div>
        </div>
      </div>
    </div>
  </div>
</template>