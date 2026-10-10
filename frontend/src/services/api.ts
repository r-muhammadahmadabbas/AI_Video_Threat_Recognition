import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const http = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const response = await axios.post(`${API_BASE}/auth/refresh`, { refresh_token: refreshToken })
          localStorage.setItem('access_token', response.data.access_token)
          localStorage.setItem('refresh_token', response.data.refresh_token)
          originalRequest.headers.Authorization = `Bearer ${response.data.access_token}`
          return http(originalRequest)
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

export const api = {
  login: async (email: string, password: string) => {
    const formData = new FormData()
    formData.append('username', email)
    formData.append('password', password)
    const response = await http.post('/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  getCurrentUser: async () => {
    const response = await http.get('/auth/me')
    return response.data
  },

  getCameras: async (params?: Record<string, any>) => {
    const response = await http.get('/cameras', { params })
    return response.data
  },

  createCamera: async (data: any) => {
    const response = await http.post('/cameras', data)
    return response.data
  },

  updateCamera: async (id: number, data: any) => {
    const response = await http.patch(`/cameras/${id}`, data)
    return response.data
  },

  deleteCamera: async (id: number) => {
    await http.delete(`/cameras/${id}`)
  },

  getIncidents: async (params?: Record<string, any>) => {
    const response = await http.get('/incidents', { params })
    return response.data
  },

  getIncident: async (id: number) => {
    const response = await http.get(`/incidents/${id}`)
    return response.data
  },

  verifyIncident: async (id: number, verified: boolean) => {
    const response = await http.post(`/incidents/${id}/verify`, { verified })
    return response.data
  },

  dismissIncident: async (id: number) => {
    const response = await http.post(`/incidents/${id}/dismiss`)
    return response.data
  },

  getZones: async (params?: Record<string, any>) => {
    const response = await http.get('/zones', { params })
    return response.data
  },

  createZone: async (data: any) => {
    const response = await http.post('/zones', data)
    return response.data
  },

  updateZone: async (id: number, data: any) => {
    const response = await http.patch(`/zones/${id}`, data)
    return response.data
  },

  deleteZone: async (id: number) => {
    await http.delete(`/zones/${id}`)
  },

  getRules: async (params?: Record<string, any>) => {
    const response = await http.get('/rules', { params })
    return response.data
  },

  createRule: async (data: any) => {
    const response = await http.post('/rules', data)
    return response.data
  },

  updateRule: async (id: number, data: any) => {
    const response = await http.patch(`/rules/${id}`, data)
    return response.data
  },

  deleteRule: async (id: number) => {
    await http.delete(`/rules/${id}`)
  },

  getUsers: async (params?: Record<string, any>) => {
    const response = await http.get('/users', { params })
    return response.data
  },

  createUser: async (data: any) => {
    const response = await http.post('/users', data)
    return response.data
  },

  updateUser: async (id: number, data: any) => {
    const response = await http.patch(`/users/${id}`, data)
    return response.data
  },

  deleteUser: async (id: number) => {
    await http.delete(`/users/${id}`)
  },

  getAuditLogs: async (params?: Record<string, any>) => {
    const response = await http.get('/audit', { params })
    return response.data
  },

  getEvidence: async (incidentId: number, params?: Record<string, any>) => {
    const response = await http.get(`/evidence/incident/${incidentId}`, { params })
    return response.data
  },

  getEvidenceFile: (evidenceId: number) => `${API_BASE}/evidence/${evidenceId}/file`,

  getEvidenceThumbnail: (evidenceId: number) => `${API_BASE}/evidence/${evidenceId}/thumbnail`,

  healthCheck: async () => {
    const response = await http.get('/health/ready')
    return response.data
  },
}