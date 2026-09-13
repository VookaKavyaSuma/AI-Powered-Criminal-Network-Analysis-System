import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Attach JWT token to outgoing requests
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('cna_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Handle 401 Unauthorized globally
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Clear token and redirect to login if not already on login page
      localStorage.removeItem('cna_token');
      localStorage.removeItem('cna_user');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// ── API Service Endpoints ──────────────────────────────────────────────────

export const api = {
  // Auth
  login: async (username, password) => {
    const res = await apiClient.post('/auth/login', { username, password });
    return res.data;
  },
  getMe: async () => {
    const res = await apiClient.get('/auth/me');
    return res.data;
  },

  // Entities & Graphs
  searchEntities: async (q, limit = 20) => {
    const res = await apiClient.get('/entity/search', { params: { q, limit } });
    return res.data;
  },
  getEntityProfile: async (id) => {
    const res = await apiClient.get(`/entity/${encodeURIComponent(id)}`);
    return res.data;
  },
  getEntitySubgraph: async (id, hops = 2) => {
    const res = await apiClient.get(`/entity/${encodeURIComponent(id)}/graph`, { params: { hops } });
    return res.data;
  },

  // Analytics
  getInfluencers: async (sortBy = 'risk_score', limit = 10) => {
    const res = await apiClient.get('/analytics/influencers', { params: { sort_by: sortBy, limit } });
    return res.data;
  },
  getCommunities: async () => {
    const res = await apiClient.get('/analytics/communities');
    return res.data;
  },
  getLinkPredictions: async (limit = 20) => {
    const res = await apiClient.get('/analytics/link-predictions', { params: { limit } });
    return res.data;
  },
  getAlerts: async () => {
    const res = await apiClient.get('/analytics/alerts');
    return res.data;
  },
  rerunAnalytics: async () => {
    const res = await apiClient.post('/analytics/rerun');
    return res.data;
  },

  // Ingestion
  ingestFir: async ({ content, fir_number, station, officer, confidential_notes }) => {
    const res = await apiClient.post('/ingest/fir', {
      content,
      fir_number,
      station,
      officer,
      confidential_notes,
    });
    return res.data;
  },
  ingestCdr: async (formData) => {
    const res = await apiClient.post('/ingest/cdr', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  ingestTransactions: async (formData) => {
    const res = await apiClient.post('/ingest/transactions', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  // Natural Language Intelligence Query
  nlQuery: async (question) => {
    const res = await apiClient.post('/query/natural-language', { question });
    return res.data;
  },

  // Audit & Chain of Custody
  verifyAuditChain: async () => {
    const res = await apiClient.get('/audit/verify');
    return res.data;
  },
  getAuditLogs: async (limit = 50) => {
    const res = await apiClient.get('/audit/logs', { params: { limit } });
    return res.data;
  },
  simulateTampering: async (blockId, fakeAction = 'RECORD_ALTERED_BY_ATTACKER') => {
    const res = await apiClient.post('/audit/tamper-demo', {
      block_id: blockId,
      fake_action: fakeAction,
    });
    return res.data;
  },
};

export default api;
