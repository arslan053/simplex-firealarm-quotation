import { apiClient } from '@/shared/api/client';
import type {
  PriceListResponse,
  PriceUpdateItem,
  UploadResponse,
} from '../types';

export const tenantPricingApi = {
  getList: (params?: { search?: string; category?: string }) =>
    apiClient.get<PriceListResponse>('/price-list', { params }),

  updatePrices: (items: PriceUpdateItem[]) =>
    apiClient.put<{ updated: number }>('/price-list', { items }),

  downloadTemplate: () =>
    apiClient.get<Blob>('/price-list/template', { responseType: 'blob' }),

  uploadTemplate: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return apiClient.post<UploadResponse>('/price-list/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  getCategories: () =>
    apiClient.get<{ categories: string[] }>('/price-list/categories'),
};
