import { apiClient } from '@/shared/api/client';
import type { PricingResponse } from '../types/pricing';

export const pricingApi = {
  calculate: (projectId: string) =>
    apiClient.post<PricingResponse>(`/projects/${projectId}/pricing/calculate`),

  get: (projectId: string) =>
    apiClient.get<PricingResponse>(`/projects/${projectId}/pricing`),
};
