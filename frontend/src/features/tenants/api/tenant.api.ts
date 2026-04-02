import { apiClient } from '@/shared/api/client';
import type { TenantResolveResponse } from '../types';

export const tenantApi = {
  resolve: () => apiClient.get<TenantResolveResponse>('/tenants/resolve'),
};
