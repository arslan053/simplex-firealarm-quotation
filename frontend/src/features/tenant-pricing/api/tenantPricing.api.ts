import { apiClient } from '@/shared/api/client';
import type {
  PriceListResponse,
  PriceUpdateItem,
  UploadResponse,
} from '../types';

export const tenantPricingApi = {
  getList: (params?: { search?: string; category?: string }) =>
    apiClient.get<PriceListResponse>('/settings/pricing', { params }),

  updatePrices: (items: PriceUpdateItem[]) =>
    apiClient.put<{ updated: number }>('/settings/pricing', { items }),

  downloadTemplate: () =>
    apiClient.get<Blob>('/settings/pricing/template', { responseType: 'blob' }),

  uploadTemplate: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return apiClient.post<UploadResponse>('/settings/pricing/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  getCategories: () =>
    apiClient.get<{ categories: string[] }>('/settings/pricing/categories'),
};
