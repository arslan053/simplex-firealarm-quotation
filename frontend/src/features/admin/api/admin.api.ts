import { apiClient } from '@/shared/api/client';
import type { CreateTenantRequest, CreateTenantResponse, TenantListResponse } from '../types';

export const adminApi = {
  listTenants: (skip = 0, limit = 50) =>
    apiClient.get<TenantListResponse>('/admin/tenants', { params: { skip, limit } }),

  createTenant: (data: CreateTenantRequest) =>
    apiClient.post<CreateTenantResponse>('/admin/tenants', data),

  deleteTenant: (tenantId: string) =>
    apiClient.delete(`/admin/tenants/${tenantId}`),
};
