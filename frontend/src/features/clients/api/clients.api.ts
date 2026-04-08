import { apiClient } from '@/shared/api/client';
import type { Client, ClientListResponse, ClientSearchItem } from '../types';

export const clientsApi = {
  list: (params: { page?: number; limit?: number; search?: string } = {}) =>
    apiClient.get<ClientListResponse>('/clients', {
      params: {
        page: params.page ?? 1,
        limit: params.limit ?? 10,
        search: params.search || undefined,
      },
    }),

  get: (clientId: string) =>
    apiClient.get<Client>(`/clients/${clientId}`),

  create: (data: { name: string; company_name: string; email?: string; phone?: string; address?: string }) =>
    apiClient.post<Client>('/clients', data),

  update: (clientId: string, data: Partial<{ name: string; company_name: string; email: string; phone: string; address: string }>) =>
    apiClient.patch<Client>(`/clients/${clientId}`, data),

  search: (q: string) =>
    apiClient.get<ClientSearchItem[]>('/clients/search', { params: { q } }),

  listProjects: (clientId: string, params: { page?: number; limit?: number } = {}) =>
    apiClient.get(`/clients/${clientId}/projects`, {
      params: {
        page: params.page ?? 1,
        limit: params.limit ?? 10,
      },
    }),
};
