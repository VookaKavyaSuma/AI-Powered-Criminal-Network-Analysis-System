const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, { headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options })
  if (!response.ok) throw new Error(`API request failed: ${response.status}`)
  return response.json()
}

export const api = {
  searchEntities: (query) => request(`/entity/search?q=${encodeURIComponent(query)}`),
  getInfluencers: () => request('/analytics/influencers'),
  getAlerts: () => request('/analytics/alerts'),
  getCommunities: () => request('/analytics/communities'),
  getAuditLogs: () => request('/audit/logs'),
}
