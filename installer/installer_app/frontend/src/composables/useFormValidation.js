import { ref, computed, watch, reactive } from 'vue'

export function useFormValidation(initialData = {}, validationRules = {}) {
  // Form data
  const formData = reactive({ ...initialData })
  
  // Validation state
  const errors = ref({})
  const touched = ref({})
  const isValidating = ref(false)
  const hasBeenSubmitted = ref(false)

  // Built-in validation rules
  const builtInRules = {
    required: (value, message = 'This field is required') => {
      if (value === null || value === undefined || value === '') {
        return message
      }
      if (Array.isArray(value) && value.length === 0) {
        return message
      }
      return null
    },

    email: (value, message = 'Please enter a valid email address') => {
      if (!value) return null
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      return emailRegex.test(value) ? null : message
    },

    minLength: (minLength, message) => (value) => {
      if (!value) return null
      const actualMessage = message || `Must be at least ${minLength} characters`
      return value.length >= minLength ? null : actualMessage
    },

    maxLength: (maxLength, message) => (value) => {
      if (!value) return null
      const actualMessage = message || `Must be no more than ${maxLength} characters`
      return value.length <= maxLength ? null : actualMessage
    },

    min: (minValue, message) => (value) => {
      if (value === null || value === undefined || value === '') return null
      const actualMessage = message || `Must be at least ${minValue}`
      return Number(value) >= minValue ? null : actualMessage
    },

    max: (maxValue, message) => (value) => {
      if (value === null || value === undefined || value === '') return null
      const actualMessage = message || `Must be no more than ${maxValue}`
      return Number(value) <= maxValue ? null : actualMessage
    },

    pattern: (regex, message = 'Invalid format') => (value) => {
      if (!value) return null
      return regex.test(value) ? null : message
    },

    url: (value, message = 'Please enter a valid URL') => {
      if (!value) return null
      try {
        new URL(value)
        return null
      } catch {
        return message
      }
    },

    numeric: (value, message = 'Must be a number') => {
      if (!value) return null
      return !isNaN(Number(value)) ? null : message
    },

    integer: (value, message = 'Must be a whole number') => {
      if (!value) return null
      return Number.isInteger(Number(value)) ? null : message
    },

    positive: (value, message = 'Must be a positive number') => {
      if (!value) return null
      return Number(value) > 0 ? null : message
    },

    // Custom validation for deployment configs
    validPort: (value, message = 'Must be a valid port number (1-65535)') => {
      if (!value) return null
      const port = Number(value)
      return port >= 1 && port <= 65535 ? null : message
    },

    validCpuLimit: (value, message = 'Must be a valid CPU limit (e.g., 0.5, 1, 2)') => {
      if (!value) return null
      const cpu = Number(value)
      return cpu > 0 && cpu <= 32 ? null : message
    },

    validMemoryLimit: (value, message = 'Must be a valid memory limit (e.g., 512Mi, 1Gi, 2Gi)') => {
      if (!value) return null
      const memoryRegex = /^\d+(\.\d+)?(Mi|Gi|Ti)$/
      return memoryRegex.test(value) ? null : message
    },

    validImageTag: (value, message = 'Must be a valid Docker image tag') => {
      if (!value) return null
      const tagRegex = /^[a-zA-Z0-9._-]+:[a-zA-Z0-9._-]+$/
      return tagRegex.test(value) ? null : message
    }
  }

  // Validate a single field
  const validateField = async (fieldName, value = formData[fieldName]) => {
    const rules = validationRules[fieldName]
    if (!rules) return null

    const fieldRules = Array.isArray(rules) ? rules : [rules]
    
    for (const rule of fieldRules) {
      let error = null
      
      if (typeof rule === 'function') {
        // Custom validation function
        error = await rule(value, formData)
      } else if (typeof rule === 'string') {
        // Built-in rule name
        if (builtInRules[rule]) {
          error = builtInRules[rule](value)
        }
      } else if (typeof rule === 'object' && rule.rule) {
        // Rule with parameters
        const { rule: ruleName, params = [], message } = rule
        if (builtInRules[ruleName]) {
          const ruleFunction = builtInRules[ruleName]
          if (params.length > 0) {
            error = ruleFunction(...params, message)(value)
          } else {
            error = ruleFunction(value, message)
          }
        }
      }
      
      if (error) {
        return error
      }
    }
    
    return null
  }

  // Validate all fields
  const validateForm = async () => {
    isValidating.value = true
    const newErrors = {}
    
    for (const fieldName of Object.keys(validationRules)) {
      const error = await validateField(fieldName)
      if (error) {
        newErrors[fieldName] = error
      }
    }
    
    errors.value = newErrors
    isValidating.value = false
    return Object.keys(newErrors).length === 0
  }

  // Validate field on change
  const validateFieldOnChange = async (fieldName) => {
    if (!touched.value[fieldName] && !hasBeenSubmitted.value) return
    
    const error = await validateField(fieldName)
    if (error) {
      errors.value[fieldName] = error
    } else {
      delete errors.value[fieldName]
    }
  }

  // Mark field as touched
  const touchField = (fieldName) => {
    touched.value[fieldName] = true
  }

  // Reset validation state
  const resetValidation = () => {
    errors.value = {}
    touched.value = {}
    hasBeenSubmitted.value = false
  }

  // Reset form data
  const resetForm = () => {
    Object.keys(formData).forEach(key => {
      formData[key] = initialData[key] || ''
    })
    resetValidation()
  }

  // Set form data
  const setFormData = (newData) => {
    Object.assign(formData, newData)
  }

  // Set field value
  const setFieldValue = (fieldName, value) => {
    formData[fieldName] = value
    validateFieldOnChange(fieldName)
  }

  // Handle form submission
  const handleSubmit = async (submitFn) => {
    hasBeenSubmitted.value = true
    
    // Mark all fields as touched
    Object.keys(validationRules).forEach(fieldName => {
      touched.value[fieldName] = true
    })
    
    const isValid = await validateForm()
    
    if (isValid && submitFn) {
      try {
        await submitFn(formData)
        return { success: true }
      } catch (error) {
        return { success: false, error }
      }
    }
    
    return { success: isValid }
  }

  // Computed properties
  const isValid = computed(() => Object.keys(errors.value).length === 0)
  
  const hasErrors = computed(() => Object.keys(errors.value).length > 0)
  
  const getFieldError = (fieldName) => {
    return computed(() => errors.value[fieldName] || null)
  }
  
  const isFieldTouched = (fieldName) => {
    return computed(() => touched.value[fieldName] || false)
  }
  
  const shouldShowError = (fieldName) => {
    return computed(() => {
      return (touched.value[fieldName] || hasBeenSubmitted.value) && errors.value[fieldName]
    })
  }

  // Watch for form data changes
  Object.keys(validationRules).forEach(fieldName => {
    watch(() => formData[fieldName], () => {
      validateFieldOnChange(fieldName)
    })
  })

  return {
    // Form data
    formData,
    
    // Validation state
    errors: computed(() => errors.value),
    touched: computed(() => touched.value),
    isValidating: computed(() => isValidating.value),
    isValid,
    hasErrors,
    hasBeenSubmitted: computed(() => hasBeenSubmitted.value),
    
    // Methods
    validateField,
    validateForm,
    touchField,
    resetValidation,
    resetForm,
    setFormData,
    setFieldValue,
    handleSubmit,
    
    // Field helpers
    getFieldError,
    isFieldTouched,
    shouldShowError,
    
    // Built-in rules for external use
    rules: builtInRules
  }
}

// Utility function to create validation rules
export function createValidationRules(rules) {
  return rules
}

// Common validation rule sets
export const commonRules = {
  deployment: {
    name: [
      'required',
      { rule: 'minLength', params: [3], message: 'Name must be at least 3 characters' },
      { rule: 'maxLength', params: [50], message: 'Name must be no more than 50 characters' },
      { rule: 'pattern', params: [/^[a-z0-9-]+$/], message: 'Name can only contain lowercase letters, numbers, and hyphens' }
    ],
    environment: ['required'],
    components: [(value) => value && value.length > 0 ? null : 'At least one component must be selected'],
    cpuLimit: ['validCpuLimit'],
    memoryLimit: ['validMemoryLimit'],
    replicas: [
      'required',
      'integer',
      'positive',
      { rule: 'min', params: [1], message: 'Must have at least 1 replica' },
      { rule: 'max', params: [10], message: 'Cannot have more than 10 replicas' }
    ]
  },
  
  build: {
    buildType: ['required'],
    imageTag: ['required', 'validImageTag'],
    dockerfile: ['required'],
    buildArgs: [(value) => {
      if (!value) return null
      try {
        JSON.parse(value)
        return null
      } catch {
        return 'Build args must be valid JSON'
      }
    }]
  },
  
  system: {
    port: ['required', 'validPort'],
    host: ['required'],
    logLevel: ['required'],
    maxConnections: [
      'required',
      'integer',
      'positive',
      { rule: 'min', params: [1] },
      { rule: 'max', params: [1000] }
    ]
  }
}