import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useBuildStore = defineStore('build', () => {
  // State
  const builds = ref([])
  const currentBuild = ref(null)
  const isBuilding = ref(false)
  const buildProgress = ref(0)
  const buildLogs = ref([])
  const buildError = ref(null)

  // Getters
  const activeBuilds = computed(() => 
    builds.value.filter(b => b.status === 'building' || b.status === 'queued')
  )

  const completedBuilds = computed(() =>
    builds.value.filter(b => b.status === 'completed')
  )

  const failedBuilds = computed(() =>
    builds.value.filter(b => b.status === 'failed')
  )

  const recentBuilds = computed(() =>
    builds.value
      .sort((a, b) => new Date(b.startedAt) - new Date(a.startedAt))
      .slice(0, 10)
  )

  const hasActiveBuilds = computed(() => activeBuilds.value.length > 0)

  // Actions
  const build = async (config) => {
    isBuilding.value = true
    buildError.value = null
    buildProgress.value = 0
    buildLogs.value = []

    try {
      // TODO: Replace with actual API call
      console.log('Starting build with config:', config)
      
      // Simulate build process
      const buildId = Date.now().toString()
      const newBuild = {
        id: buildId,
        type: config.build_type,
        architecture: config.architecture || 'amd64',
        rpiModel: config.rpi_model || null,
        status: 'building',
        progress: 0,
        startedAt: new Date().toISOString(),
        config: { ...config },
        artifacts: []
      }

      builds.value.push(newBuild)
      currentBuild.value = newBuild

      // Simulate build stages with different progress steps
      const buildStages = [
        { progress: 10, message: 'Initializing build environment...' },
        { progress: 20, message: 'Downloading base images...' },
        { progress: 35, message: 'Installing dependencies...' },
        { progress: 50, message: 'Compiling source code...' },
        { progress: 65, message: 'Creating package structure...' },
        { progress: 80, message: 'Generating installer files...' },
        { progress: 95, message: 'Finalizing build artifacts...' },
        { progress: 100, message: 'Build completed successfully!' }
      ]

      for (const stage of buildStages) {
        await new Promise(resolve => setTimeout(resolve, 300))
        buildProgress.value = stage.progress
        newBuild.progress = stage.progress
        addLog(stage.message)
      }

      // Add build artifacts
      newBuild.artifacts = generateArtifacts(config)
      newBuild.status = 'completed'
      newBuild.completedAt = new Date().toISOString()

      return newBuild
    } catch (error) {
      console.error('Build failed:', error)
      buildError.value = error.message
      
      if (currentBuild.value) {
        currentBuild.value.status = 'failed'
        currentBuild.value.error = error.message
      }
      
      addLog(`Build failed: ${error.message}`)
      throw error
    } finally {
      isBuilding.value = false
    }
  }

  const generateArtifacts = (config) => {
    const artifacts = []
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
    
    switch (config.build_type) {
      case 'deb':
        artifacts.push({
          name: `openjourney-server_1.0.0_${config.architecture}.deb`,
          type: 'debian-package',
          size: '45.2 MB',
          path: `/builds/deb/openjourney-server_1.0.0_${config.architecture}.deb`
        })
        break
      case 'amd64':
        artifacts.push({
          name: `openjourney-installer-amd64-${timestamp}.iso`,
          type: 'iso-image',
          size: '1.2 GB',
          path: `/builds/iso/openjourney-installer-amd64-${timestamp}.iso`
        })
        break
      case 'rpi64':
        artifacts.push({
          name: `openjourney-installer-rpi${config.rpi_model}-${timestamp}.img`,
          type: 'disk-image',
          size: '890 MB',
          path: `/builds/rpi/openjourney-installer-rpi${config.rpi_model}-${timestamp}.img`
        })
        break
    }
    
    return artifacts
  }

  const getBuildStatus = async (buildId) => {
    // TODO: Replace with actual API call
    const build = builds.value.find(b => b.id === buildId)
    return build || null
  }

  const cancelBuild = async (buildId) => {
    // TODO: Replace with actual API call
    const build = builds.value.find(b => b.id === buildId)
    if (build && build.status === 'building') {
      build.status = 'cancelled'
      build.cancelledAt = new Date().toISOString()
      addLog('Build cancelled by user')
    }
    
    if (currentBuild.value?.id === buildId) {
      isBuilding.value = false
    }
  }

  const downloadArtifact = async (buildId, artifactName) => {
    // TODO: Replace with actual API call
    console.log(`Downloading artifact: ${artifactName} from build: ${buildId}`)
    
    // Simulate download
    addLog(`Starting download of ${artifactName}`)
    await new Promise(resolve => setTimeout(resolve, 1000))
    addLog(`Download of ${artifactName} completed`)
  }

  const deleteBuild = (buildId) => {
    const index = builds.value.findIndex(b => b.id === buildId)
    if (index > -1) {
      builds.value.splice(index, 1)
    }
    
    if (currentBuild.value?.id === buildId) {
      currentBuild.value = null
    }
  }

  const addLog = (message, level = 'info') => {
    buildLogs.value.push({
      id: Date.now(),
      timestamp: new Date().toISOString(),
      message,
      level
    })
  }

  const clearLogs = () => {
    buildLogs.value = []
  }

  const setCurrentBuild = (build) => {
    currentBuild.value = build
  }

  const resetBuildState = () => {
    currentBuild.value = null
    isBuilding.value = false
    buildProgress.value = 0
    buildLogs.value = []
    buildError.value = null
  }

  // Initialize with mock data for development
  const initializeMockData = () => {
    builds.value = [
      {
        id: '1',
        type: 'deb',
        architecture: 'amd64',
        rpiModel: null,
        status: 'completed',
        progress: 100,
        startedAt: new Date(Date.now() - 60 * 60 * 1000).toISOString(), // 1 hour ago
        completedAt: new Date(Date.now() - 55 * 60 * 1000).toISOString(), // 55 minutes ago
        config: {
          build_type: 'deb',
          architecture: 'amd64'
        },
        artifacts: [
          {
            name: 'openjourney-server_1.0.0_amd64.deb',
            type: 'debian-package',
            size: '45.2 MB',
            path: '/builds/deb/openjourney-server_1.0.0_amd64.deb'
          }
        ]
      },
      {
        id: '2',
        type: 'rpi64',
        architecture: 'arm64',
        rpiModel: '4',
        status: 'failed',
        progress: 65,
        startedAt: new Date(Date.now() - 30 * 60 * 1000).toISOString(), // 30 minutes ago
        error: 'Insufficient disk space',
        config: {
          build_type: 'rpi64',
          rpi_model: '4'
        },
        artifacts: []
      }
    ]
  }

  return {
    // State
    builds,
    currentBuild,
    isBuilding,
    buildProgress,
    buildLogs,
    buildError,
    
    // Getters
    activeBuilds,
    completedBuilds,
    failedBuilds,
    recentBuilds,
    hasActiveBuilds,
    
    // Actions
    build,
    getBuildStatus,
    cancelBuild,
    downloadArtifact,
    deleteBuild,
    addLog,
    clearLogs,
    setCurrentBuild,
    resetBuildState,
    initializeMockData
  }
})