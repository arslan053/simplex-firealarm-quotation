import axios from 'axios';
import { config } from '@/app/config/env';

const apiClient = axios.create({
  baseURL: `${config.apiUrl}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((reqConfig) => {
  // Attach tenant hostname header — subdomain identifies the tenant
  reqConfig.headers['X-Tenant-Host'] = window.location.hostname;

  // Attach auth token if present
  const token = localStorage.getItem('access_token');
  if (token) {
    reqConfig.headers['Authorization'] = `Bearer ${token}`;
  }

  return reqConfig;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      if (!window.location.pathname.startsWith('/auth/')) {
        window.location.href = '/auth/login';
      }
    }
    return Promise.reject(error);
  },
);

export { apiClient };
