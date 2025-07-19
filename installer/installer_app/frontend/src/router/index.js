import { createRouter, createWebHistory } from 'vue-router'

// Lazy load views for better performance
const HomeView = () => import('../views/HomeView.vue')
const DeployView = () => import('../views/DeployView.vue')
const BuildView = () => import('../views/BuildView.vue')
const DestroyView = () => import('../views/DestroyView.vue')
const DashboardView = () => import('../views/DashboardView.vue')

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: {
        title: 'OpenJourney Installer'
      }
    },
    {
      path: '/deploy',
      name: 'deploy',
      component: DeployView,
      meta: {
        title: 'Deploy - OpenJourney Installer'
      }
    },
    {
      path: '/build',
      name: 'build',
      component: BuildView,
      meta: {
        title: 'Build - OpenJourney Installer'
      }
    },
    {
      path: '/destroy',
      name: 'destroy',
      component: DestroyView,
      meta: {
        title: 'Destroy - OpenJourney Installer'
      }
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardView,
      meta: {
        title: 'Dashboard - OpenJourney Installer'
      }
    }
  ]
})

// Update document title based on route meta
router.beforeEach((to, from, next) => {
  document.title = to.meta.title || 'OpenJourney Installer'
  next()
})

export default router